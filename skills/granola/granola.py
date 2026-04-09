#!/usr/bin/env python3
"""Granola API client for AgentOS.

Commands:
  list [limit] [page]   - List recent meetings with metadata
  get <doc_id>          - Get a meeting with full transcript + AI summary

Auth: reads ~/Library/Application Support/Granola/supabase.json
      Token auto-refreshed by the Granola app (~6hr lifetime)

Internal API (api.granola.ai):
  POST /v2/get-documents        {"limit": N, "offset": N}  → {"docs": [...]}
  POST /v1/get-documents-batch  {"documentIds": [...]}    → {"docs": [...]}
  POST /v1/get-document-transcript {"documentId": id}     → [utterance, ...]
  POST /v1/get-document-panels  {"documentId": id}        → [panel, ...]
  POST /v1/get-entity-set       {"entityType": str}       → {"data": [{id, ...}]}
  POST /v1/get-entity-batch     {"entity_type", "entity_ids"} → {"data": [full entities]}

Q&A/chat: chat_thread (grouping_key "meeting:{doc_id}") links to document; chat_message has thread_id.
Web: https://notes.granola.ai/t/{thread_id}

Local cache: ~/Library/Application Support/Granola/cache-v6.json — same entity shape, works offline.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from agentos import http, connection, provides, returns, timeout, web_read

DEFAULT_API_BASE = "https://api.granola.ai"
DEFAULT_AUTH_FILE = Path.home() / "Library" / "Application Support" / "Granola" / "supabase.json"
DEFAULT_CACHE_FILE = Path.home() / "Library" / "Application Support" / "Granola" / "cache-v6.json"


def _expand_path(p: str) -> Path:
    if p.startswith("~/"):
        return Path.home() / p[2:]
    return Path(p)


def _auth_file(con: dict | None) -> Path:
    if con and isinstance(con.get("vars"), dict):
        tf = con["vars"].get("token_file")
        if isinstance(tf, str) and tf.strip():
            return _expand_path(tf)
    return DEFAULT_AUTH_FILE


def _cache_file(con: dict | None) -> Path:
    if con and isinstance(con.get("vars"), dict):
        cf = con["vars"].get("cache_file")
        if isinstance(cf, str) and cf.strip():
            return _expand_path(cf)
    return DEFAULT_CACHE_FILE


def _api_base(con: dict | None) -> str:
    if con and con.get("base_url"):
        return str(con["base_url"]).rstrip("/")
    return DEFAULT_API_BASE


def _get_token(con: dict | None = None) -> str:
    auth_path = _auth_file(con)
    try:
        with open(auth_path) as f:
            data = json.load(f)
        tokens = json.loads(data["workos_tokens"])
        return tokens["access_token"]
    except FileNotFoundError:
        _die("Granola auth file not found. Install and open Granola first.")
    except (KeyError, json.JSONDecodeError) as e:
        _die(f"Could not parse Granola auth file: {e}")


async def _api_post(token: str, endpoint: str, body: dict, con: dict | None = None) -> object:
    url = f"{_api_base(con)}{endpoint}"
    resp = await http.post(url, json=body, **http.headers(accept="json", extra={
        "Authorization": f"Bearer {token}",
    }))
    if not resp.get("ok"):
        status = resp.get("status", 0)
        if status == 401:
            _die("Granola token expired. Open Granola to refresh it.")
        _die(f"Granola API error {status}: {resp.get('body', '')[:200]}")
    return resp.get("json") or json.loads(resp.get("body", "{}"))


def _die(msg: str) -> None:
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


def _html_to_markdown(html: str) -> str:
    """Convert Granola panel HTML to readable markdown.

    The original_content field is clean HTML (h3, ul/li, p) with no
    embedded styles or complex structure, so simple regex is sufficient.
    """
    if not html:
        return ""
    md = html
    md = re.sub(r"<h([1-6])[^>]*>(.*?)</h[1-6]>", lambda m: "#" * int(m.group(1)) + " " + m.group(2).strip() + "\n", md)
    md = re.sub(r"<li[^>]*>(.*?)</li>", lambda m: "- " + m.group(1).strip() + "\n", md, flags=re.DOTALL)
    md = re.sub(r"</?ul[^>]*>|</?ol[^>]*>", "", md)
    md = re.sub(r"<p[^>]*>(.*?)</p>", lambda m: m.group(1).strip() + "\n\n", md, flags=re.DOTALL)
    md = re.sub(r"<strong>(.*?)</strong>", r"**\1**", md)
    md = re.sub(r"<em>(.*?)</em>", r"*\1*", md)
    md = re.sub(r"<[^>]+>", "", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md


def _format_transcript(utterances: list, meeting_start: datetime) -> tuple[list, str]:
    """Convert Granola utterances to canonical transcript format.

    Returns (segments, plain_text) where:
    - segments: [{start_ms, end_ms, text, speaker, timestamp}, ...]
    - plain_text: "[HH:MM:SS] Speaker: text\n..." for FTS5 indexing
    """
    segments = []
    lines = []

    for u in utterances:
        if not u.get("is_final"):
            continue
        text = u.get("text", "").strip()
        if not text:
            continue

        ts = datetime.fromisoformat(u["start_timestamp"].replace("Z", "+00:00"))
        te = datetime.fromisoformat(u["end_timestamp"].replace("Z", "+00:00"))
        offset_ms = max(0, int((ts - meeting_start).total_seconds() * 1000))
        end_ms = max(0, int((te - meeting_start).total_seconds() * 1000))
        speaker = "You" if u.get("source") == "microphone" else "Other"

        segments.append({
            "startMs": offset_ms,
            "endMs": end_ms,
            "content": text,
            "speaker": speaker,
            "timestamp": u["start_timestamp"],
        })

        hh = offset_ms // 3_600_000
        mm = (offset_ms % 3_600_000) // 60_000
        ss = (offset_ms % 60_000) // 1_000
        lines.append(f"[{hh:02d}:{mm:02d}:{ss:02d}] {speaker}: {text}")

    return segments, "\n".join(lines)


def _normalize_meeting(doc: dict) -> dict:
    """Normalize a Granola document to AgentOS meeting output format."""
    cal = doc.get("google_calendar_event") or {}
    people = doc.get("people") or {}
    creator = people.get("creator") or {}
    creator_details = (creator.get("details") or {}).get("person") or {}

    attendees = []
    for a in (people.get("attendees") or []):
        if not a.get("email"):
            continue
        a_details = (a.get("details") or {}).get("person") or {}
        attendees.append({
            "email": a["email"],
            "name": a_details.get("name", {}).get("fullName") or a.get("name"),
            "avatar": a_details.get("avatar"),
            "jobTitle": (a_details.get("employment") or {}).get("title"),
            "organization": ((a.get("details") or {}).get("company") or {}).get("name"),
        })

    return {
        "id": doc["id"],
        "title": doc.get("title") or "",
        "createdAt": doc.get("created_at"),
        "updatedAt": doc.get("updated_at"),
        "start": (cal.get("start") or {}).get("dateTime") or doc.get("created_at"),
        "end": (cal.get("end") or {}).get("dateTime") or doc.get("updated_at"),
        "location": cal.get("hangoutLink") or cal.get("location"),
        "calendarLink": cal.get("htmlLink"),
        "granolaUrl": f"https://app.granola.ai/docs/{doc['id']}",
        "creationSource": doc.get("creation_source"),
        "validMeeting": doc.get("valid_meeting", True),
        "organizerEmail": creator.get("email"),
        "organizerName": creator_details.get("name", {}).get("fullName") or creator.get("name"),
        "attendees": attendees,
    }


async def _cmd_list(token: str, limit: int, page: int, con: dict | None = None) -> list:
    result = await _api_post(token, "/v2/get-documents", {"limit": limit, "offset": page * limit}, con)
    docs = result.get("docs", []) if isinstance(result, dict) else result
    return [_normalize_meeting(d) for d in docs]


async def _cmd_get(token: str, doc_id: str, con: dict | None = None) -> dict:
    # Fetch document metadata
    batch = await _api_post(token, "/v1/get-documents-batch", {"document_ids": [doc_id]}, con)
    docs = batch.get("docs", batch) if isinstance(batch, dict) else batch
    if not docs:
        _die(f"Document {doc_id} not found")
    doc = docs[0]
    meeting = _normalize_meeting(doc)

    # Fetch transcript
    utterances = await _api_post(token, "/v1/get-document-transcript", {"document_id": doc_id}, con)
    if utterances and isinstance(utterances, list):
        start_str = meeting.get("start") or doc.get("created_at")
        meeting_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        segments, transcript_text = _format_transcript(utterances, meeting_start)
        meeting["transcript_text"] = transcript_text
        meeting["segments"] = segments
        meeting["segment_count"] = len(segments)
        meeting["duration_ms"] = segments[-1]["end_ms"] if segments else 0
    else:
        meeting["transcript_text"] = ""
        meeting["segments"] = []
        meeting["segment_count"] = 0
        meeting["duration_ms"] = 0

    # Fetch AI summary panels
    panels = await _api_post(token, "/v1/get-document-panels", {"document_id": doc_id}, con)
    if panels and isinstance(panels, list):
        parts = [_html_to_markdown(p.get("original_content", "")) for p in panels]
        meeting["summary_text"] = "\n\n".join(p for p in parts if p)
    else:
        meeting["summary_text"] = ""

    return meeting


async def _cmd_list_conversations(token: str, document_id: str, con: dict | None = None) -> list:
    """List Q&A chat threads linked to a meeting document."""
    # get-entity-set returns IDs only; we need batch to get grouping_key
    set_resp = await _api_post(token, "/v1/get-entity-set", {"entity_type": "chat_thread"}, con)
    thread_ids = [e["id"] for e in (set_resp.get("data") or [])]
    if not thread_ids:
        return []

    batch_resp = await _api_post(token, "/v1/get-entity-batch", {
        "entity_type": "chat_thread",
        "entity_ids": thread_ids,
    }, con)
    target_key = f"meeting:{document_id}"
    threads = []
    for t in (batch_resp.get("data") or []):
        gk = (t.get("data") or {}).get("grouping_key", "")
        if gk != target_key:
            continue
        threads.append({
            "id": t["id"],
            "title": (t.get("data") or {}).get("title"),
            "createdAt": t.get("created_at"),
            "updatedAt": t.get("updated_at"),
            "documentId": document_id,
            "notesUrl": f"https://notes.granola.ai/t/{t['id']}",
        })
    return sorted(threads, key=lambda x: (x["updatedAt"] or ""), reverse=True)


async def _cmd_get_conversation(token: str, thread_id: str, con: dict | None = None) -> dict:
    """Get a Q&A conversation thread with all messages."""
    # Fetch thread
    batch_resp = await _api_post(token, "/v1/get-entity-batch", {
        "entity_type": "chat_thread",
        "entity_ids": [thread_id],
    }, con)
    threads = batch_resp.get("data") or []
    if not threads:
        _die(f"Thread {thread_id} not found")
    thread = threads[0]

    # Fetch all messages and filter by thread_id
    set_resp = await _api_post(token, "/v1/get-entity-set", {"entity_type": "chat_message"}, con)
    msg_ids = [e["id"] for e in (set_resp.get("data") or [])]
    if not msg_ids:
        messages = []
    else:
        msg_batch = await _api_post(token, "/v1/get-entity-batch", {
            "entity_type": "chat_message",
            "entity_ids": msg_ids,
        }, con)
        raw_msgs = [m for m in (msg_batch.get("data") or []) if (m.get("data") or {}).get("thread_id") == thread_id]
        raw_msgs.sort(key=lambda m: ((m.get("data") or {}).get("turn_index", 0), m.get("created_at", "")))
        messages = []
        for m in raw_msgs:
            d = m.get("data") or {}
            role = d.get("role", "unknown")
            text = d.get("raw_text") or ""
            for out in d.get("outputs") or []:
                if out.get("type") == "text" and out.get("text"):
                    text = out["text"]
                    break
            messages.append({
                "role": role,
                "content": text,
                "turnIndex": d.get("turn_index"),
                "createdAt": m.get("created_at"),
            })

    tdata = thread.get("data") or {}
    return {
        "id": thread["id"],
        "title": tdata.get("title"),
        "groupingKey": tdata.get("grouping_key"),
        "createdAt": thread.get("created_at"),
        "updatedAt": thread.get("updated_at"),
        "notesUrl": f"https://notes.granola.ai/t/{thread_id}",
        "messages": messages,
    }


# -----------------------------------------------------------------------------
# Cache path — read from local cache-v6.json (instant, offline, no token)
# -----------------------------------------------------------------------------


def _load_cache(cache_path: Path) -> dict:
    """Load the Granola app's local entity cache."""
    if not cache_path.exists():
        _die("Granola cache not found. Install and run Granola at least once.")
    with open(cache_path) as f:
        return json.load(f)


def _cmd_list_from_cache(limit: int = 20, page: int = 0, con: dict | None = None) -> list:
    """List meetings from local cache."""
    data = _load_cache(_cache_file(con))
    docs = (data.get("cache", {}).get("state", {}) or {}).get("documents", {})
    if not docs:
        return []
    items = [_normalize_meeting(d) for d in docs.values() if not d.get("deleted_at")]
    items.sort(key=lambda x: (x.get("updatedAt") or x.get("createdAt") or ""), reverse=True)
    start = page * limit
    return items[start : start + limit]


def _cmd_list_conversations_from_cache(document_id: str, con: dict | None = None) -> list:
    """List Q&A threads for a meeting from local cache."""
    data = _load_cache(_cache_file(con))
    threads = (data.get("cache", {}).get("state", {}).get("entities", {}) or {}).get("chat_thread", {})
    target_key = f"meeting:{document_id}"
    out = []
    for t in threads.values():
        if t.get("deleted_at"):
            continue
        gk = (t.get("data") or {}).get("grouping_key", "")
        if gk != target_key:
            continue
        out.append({
            "id": t["id"],
            "title": (t.get("data") or {}).get("title"),
            "createdAt": t.get("created_at"),
            "updatedAt": t.get("updated_at"),
            "documentId": document_id,
            "notesUrl": f"https://notes.granola.ai/t/{t['id']}",
        })
    return sorted(out, key=lambda x: (x["updatedAt"] or ""), reverse=True)


def _cmd_get_conversation_from_cache(thread_id: str, con: dict | None = None) -> dict:
    """Get a Q&A conversation from local cache."""
    data = _load_cache(_cache_file(con))
    threads = (data.get("cache", {}).get("state", {}).get("entities", {}) or {}).get("chat_thread", {})
    msgs = (data.get("cache", {}).get("state", {}).get("entities", {}) or {}).get("chat_message", {})
    thread = threads.get(thread_id)
    if not thread or thread.get("deleted_at"):
        _die(f"Thread {thread_id} not found in cache")
    raw_msgs = [m for m in msgs.values() if (m.get("data") or {}).get("thread_id") == thread_id and not m.get("deleted_at")]
    raw_msgs.sort(key=lambda m: ((m.get("data") or {}).get("turn_index", 0), m.get("created_at", "")))
    messages = []
    for m in raw_msgs:
        d = m.get("data") or {}
        role = d.get("role", "unknown")
        text = d.get("raw_text") or ""
        for out in d.get("outputs") or []:
            if out.get("type") == "text" and out.get("text"):
                text = out["text"]
                break
        messages.append({
            "role": role,
            "content": text,
            "turnIndex": d.get("turn_index"),
            "createdAt": m.get("created_at"),
        })
    tdata = thread.get("data") or {}
    return {
        "id": thread["id"],
        "title": tdata.get("title"),
        "groupingKey": tdata.get("grouping_key"),
        "createdAt": thread.get("created_at"),
        "updatedAt": thread.get("updated_at"),
        "notesUrl": f"https://notes.granola.ai/t/{thread_id}",
        "messages": messages,
        "source": "cache",
    }


def _connection_mode(con: object | None) -> str:
    """Effective data source from runtime-injected `connection` object."""
    if not isinstance(con, dict):
        return "api"
    name = con.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip().lower()
    return "api"


@returns("meeting[]")
@connection(["api", "cache"])
async def op_list_meetings(limit: int = 20, page: int = 0, connection: dict | None = None, **_kwargs) -> list:
    """Entry point for python: executor. `connection` is injected by AgentOS (api vs cache)."""
    mode = _connection_mode(connection)
    if mode == "cache":
        return _cmd_list_from_cache(limit, page, connection)
    if mode == "api":
        token = _get_token(connection)
        return await _cmd_list(token, limit, page, connection)
    _die(f"Unknown connection {mode!r}")


@returns("meeting")
@provides(web_read, urls=["app.granola.ai/docs/*"])
@connection("api")
@timeout(60)
async def op_get_meeting(id: str = None, url: str = None, connection: dict | None = None, **_kwargs) -> dict:
    """API only — local cache does not include full transcripts.

    Accepts either a direct `id` (UUID) or a Granola `url`
    (e.g. https://app.granola.ai/docs/<uuid>). If both are given, `url` wins.
    """
    doc_id = id
    if url:
        m = re.search(r"/docs/([0-9a-fA-F-]{36})", url)
        if m:
            doc_id = m.group(1)
    if not doc_id:
        _die("Either id or url is required for get_meeting")
    token = _get_token(connection)
    return await _cmd_get(token, doc_id, connection)


@returns("conversation[]")
@connection(["api", "cache"])
async def op_list_conversations(document_id: str, connection: dict | None = None, **_kwargs) -> list:
    """List Q&A/AI chat threads linked to a meeting transcript

        Args:
            document_id: Meeting document ID (UUID)
        """
    mode = _connection_mode(connection)
    if mode == "cache":
        return _cmd_list_conversations_from_cache(document_id, connection)
    if mode == "api":
        token = _get_token(connection)
        return await _cmd_list_conversations(token, document_id, connection)
    _die(f"Unknown connection {mode!r}")


@returns("conversation")
@connection(["api", "cache"])
async def op_get_conversation(thread_id: str, connection: dict | None = None, **_kwargs) -> dict:
    """Get a Q&A conversation with full message history

        Args:
            thread_id: Chat thread ID (UUID)
        """
    mode = _connection_mode(connection)
    if mode == "cache":
        return _cmd_get_conversation_from_cache(thread_id, connection)
    if mode == "api":
        token = _get_token(connection)
        out = await _cmd_get_conversation(token, thread_id, connection)
        out["source"] = "api"
        return out
    _die(f"Unknown connection {mode!r}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _die("Usage: granola.py <list|get|list_conversations|get_conversation> [args...]")

    cmd = sys.argv[1]
    try:
        if cmd == "list":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            page = int(sys.argv[3]) if len(sys.argv) > 3 else 0
            source = sys.argv[4] if len(sys.argv) > 4 else "api"
            if source == "cache":
                result = _cmd_list_from_cache(limit, page, None)
            else:
                token = _get_token(None)
                result = _cmd_list(token, limit, page, None)
        elif cmd == "get":
            if len(sys.argv) < 3:
                _die("Usage: granola.py get <doc_id>")
            token = _get_token(None)
            result = _cmd_get(token, sys.argv[2], None)
        elif cmd == "listConversations":
            if len(sys.argv) < 3:
                _die("Usage: granola.py list_conversations <document_id> [api|cache]")
            doc_id = sys.argv[2]
            source = sys.argv[3] if len(sys.argv) > 3 else "api"
            if source == "cache":
                result = _cmd_list_conversations_from_cache(doc_id, None)
            else:
                token = _get_token(None)
                result = _cmd_list_conversations(token, doc_id, None)
        elif cmd == "getConversation":
            if len(sys.argv) < 3:
                _die("Usage: granola.py get_conversation <thread_id> [api|cache]")
            thread_id = sys.argv[2]
            source = sys.argv[3] if len(sys.argv) > 3 else "api"
            if source == "cache":
                result = _cmd_get_conversation_from_cache(thread_id, None)
            else:
                token = _get_token(None)
                result = _cmd_get_conversation(token, thread_id, None)
        else:
            _die(f"Unknown command: {cmd}")

        print(json.dumps(result))
    except SystemExit:
        raise
    except Exception as e:
        _die(str(e))

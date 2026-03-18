#!/usr/bin/env python3
"""Granola API client for AgentOS.

Commands:
  list [limit] [page]   - List recent meetings with metadata
  get <doc_id>          - Get a meeting with full transcript + AI summary

Auth: reads ~/Library/Application Support/Granola/supabase.json
      Token auto-refreshed by the Granola app (~6hr lifetime)

Internal API (api.granola.ai):
  POST /v2/get-documents        {"limit": N, "offset": N}  → {"docs": [...]}
  POST /v1/get-documents-batch  {"document_ids": [...]}    → {"docs": [...]}
  POST /v1/get-document-transcript {"document_id": id}     → [utterance, ...]
  POST /v1/get-document-panels  {"document_id": id}        → [panel, ...]
  POST /v1/get-entity-set       {"entity_type": str}       → {"data": [{id, ...}]}
  POST /v1/get-entity-batch     {"entity_type", "entity_ids"} → {"data": [full entities]}

Q&A/chat: chat_thread (grouping_key "meeting:{doc_id}") links to document; chat_message has thread_id.
Web: https://notes.granola.ai/t/{thread_id}

Local cache: ~/Library/Application Support/Granola/cache-v6.json — same entity shape, works offline.
"""

import gzip
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://api.granola.ai"
AUTH_FILE = Path.home() / "Library" / "Application Support" / "Granola" / "supabase.json"
CACHE_PATH = Path.home() / "Library" / "Application Support" / "Granola" / "cache-v6.json"


def get_token() -> str:
    try:
        with open(AUTH_FILE) as f:
            data = json.load(f)
        tokens = json.loads(data["workos_tokens"])
        return tokens["access_token"]
    except FileNotFoundError:
        die("Granola auth file not found. Install and open Granola first.")
    except (KeyError, json.JSONDecodeError) as e:
        die(f"Could not parse Granola auth file: {e}")


def api_post(token: str, endpoint: str, body: dict) -> object:
    url = f"{BASE_URL}{endpoint}"
    req = Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip",
            "User-Agent": "AgentOS/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw)
    except HTTPError as e:
        if e.code == 401:
            die("Granola token expired. Open Granola to refresh it.")
        die(f"Granola API error {e.code}: {e.reason}")
    except URLError as e:
        die(f"Network error: {e.reason}")


def die(msg: str) -> None:
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


def html_to_markdown(html: str) -> str:
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


def format_transcript(utterances: list, meeting_start: datetime) -> tuple[list, str]:
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
            "start_ms": offset_ms,
            "end_ms": end_ms,
            "text": text,
            "speaker": speaker,
            "timestamp": u["start_timestamp"],
        })

        hh = offset_ms // 3_600_000
        mm = (offset_ms % 3_600_000) // 60_000
        ss = (offset_ms % 60_000) // 1_000
        lines.append(f"[{hh:02d}:{mm:02d}:{ss:02d}] {speaker}: {text}")

    return segments, "\n".join(lines)


def normalize_meeting(doc: dict) -> dict:
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
            "job_title": (a_details.get("employment") or {}).get("title"),
            "organization": ((a.get("details") or {}).get("company") or {}).get("name"),
        })

    return {
        "id": doc["id"],
        "title": doc.get("title") or "",
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        "start": (cal.get("start") or {}).get("dateTime") or doc.get("created_at"),
        "end": (cal.get("end") or {}).get("dateTime") or doc.get("updated_at"),
        "location": cal.get("hangoutLink") or cal.get("location"),
        "calendar_link": cal.get("htmlLink"),
        "granola_url": f"https://app.granola.ai/docs/{doc['id']}",
        "creation_source": doc.get("creation_source"),
        "valid_meeting": doc.get("valid_meeting", True),
        "organizer_email": creator.get("email"),
        "organizer_name": creator_details.get("name", {}).get("fullName") or creator.get("name"),
        "attendees": attendees,
    }


def cmd_list(token: str, limit: int, page: int) -> list:
    result = api_post(token, "/v2/get-documents", {"limit": limit, "offset": page * limit})
    docs = result.get("docs", []) if isinstance(result, dict) else result
    return [normalize_meeting(d) for d in docs]


def cmd_get(token: str, doc_id: str) -> dict:
    # Fetch document metadata
    batch = api_post(token, "/v1/get-documents-batch", {"document_ids": [doc_id]})
    docs = batch.get("docs", batch) if isinstance(batch, dict) else batch
    if not docs:
        die(f"Document {doc_id} not found")
    doc = docs[0]
    meeting = normalize_meeting(doc)

    # Fetch transcript
    utterances = api_post(token, "/v1/get-document-transcript", {"document_id": doc_id})
    if utterances and isinstance(utterances, list):
        start_str = meeting.get("start") or doc.get("created_at")
        meeting_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        segments, transcript_text = format_transcript(utterances, meeting_start)
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
    panels = api_post(token, "/v1/get-document-panels", {"document_id": doc_id})
    if panels and isinstance(panels, list):
        parts = [html_to_markdown(p.get("original_content", "")) for p in panels]
        meeting["summary_text"] = "\n\n".join(p for p in parts if p)
    else:
        meeting["summary_text"] = ""

    return meeting


def cmd_list_conversations(token: str, document_id: str) -> list:
    """List Q&A chat threads linked to a meeting document."""
    # get-entity-set returns IDs only; we need batch to get grouping_key
    set_resp = api_post(token, "/v1/get-entity-set", {"entity_type": "chat_thread"})
    thread_ids = [e["id"] for e in (set_resp.get("data") or [])]
    if not thread_ids:
        return []

    batch_resp = api_post(token, "/v1/get-entity-batch", {
        "entity_type": "chat_thread",
        "entity_ids": thread_ids,
    })
    target_key = f"meeting:{document_id}"
    threads = []
    for t in (batch_resp.get("data") or []):
        gk = (t.get("data") or {}).get("grouping_key", "")
        if gk != target_key:
            continue
        threads.append({
            "id": t["id"],
            "title": (t.get("data") or {}).get("title"),
            "created_at": t.get("created_at"),
            "updated_at": t.get("updated_at"),
            "document_id": document_id,
            "notes_url": f"https://notes.granola.ai/t/{t['id']}",
        })
    return sorted(threads, key=lambda x: (x["updated_at"] or ""), reverse=True)


def cmd_get_conversation(token: str, thread_id: str) -> dict:
    """Get a Q&A conversation thread with all messages."""
    # Fetch thread
    batch_resp = api_post(token, "/v1/get-entity-batch", {
        "entity_type": "chat_thread",
        "entity_ids": [thread_id],
    })
    threads = batch_resp.get("data") or []
    if not threads:
        die(f"Thread {thread_id} not found")
    thread = threads[0]

    # Fetch all messages and filter by thread_id
    set_resp = api_post(token, "/v1/get-entity-set", {"entity_type": "chat_message"})
    msg_ids = [e["id"] for e in (set_resp.get("data") or [])]
    if not msg_ids:
        messages = []
    else:
        msg_batch = api_post(token, "/v1/get-entity-batch", {
            "entity_type": "chat_message",
            "entity_ids": msg_ids,
        })
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
                "text": text,
                "turn_index": d.get("turn_index"),
                "created_at": m.get("created_at"),
            })

    tdata = thread.get("data") or {}
    return {
        "id": thread["id"],
        "title": tdata.get("title"),
        "grouping_key": tdata.get("grouping_key"),
        "created_at": thread.get("created_at"),
        "updated_at": thread.get("updated_at"),
        "notes_url": f"https://notes.granola.ai/t/{thread_id}",
        "messages": messages,
    }


# -----------------------------------------------------------------------------
# Cache path — read from local cache-v6.json (instant, offline, no token)
# -----------------------------------------------------------------------------


def load_cache() -> dict:
    """Load the Granola app's local entity cache."""
    if not CACHE_PATH.exists():
        die("Granola cache not found. Install and run Granola at least once.")
    with open(CACHE_PATH) as f:
        return json.load(f)


def cmd_list_from_cache(limit: int = 20, page: int = 0) -> list:
    """List meetings from local cache."""
    data = load_cache()
    docs = (data.get("cache", {}).get("state", {}) or {}).get("documents", {})
    if not docs:
        return []
    items = [normalize_meeting(d) for d in docs.values() if not d.get("deleted_at")]
    items.sort(key=lambda x: (x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    start = page * limit
    return items[start : start + limit]


def cmd_list_conversations_from_cache(document_id: str) -> list:
    """List Q&A threads for a meeting from local cache."""
    data = load_cache()
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
            "created_at": t.get("created_at"),
            "updated_at": t.get("updated_at"),
            "document_id": document_id,
            "notes_url": f"https://notes.granola.ai/t/{t['id']}",
        })
    return sorted(out, key=lambda x: (x["updated_at"] or ""), reverse=True)


def cmd_get_conversation_from_cache(thread_id: str) -> dict:
    """Get a Q&A conversation from local cache."""
    data = load_cache()
    threads = (data.get("cache", {}).get("state", {}).get("entities", {}) or {}).get("chat_thread", {})
    msgs = (data.get("cache", {}).get("state", {}).get("entities", {}) or {}).get("chat_message", {})
    thread = threads.get(thread_id)
    if not thread or thread.get("deleted_at"):
        die(f"Thread {thread_id} not found in cache")
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
            "text": text,
            "turn_index": d.get("turn_index"),
            "created_at": m.get("created_at"),
        })
    tdata = thread.get("data") or {}
    return {
        "id": thread["id"],
        "title": tdata.get("title"),
        "grouping_key": tdata.get("grouping_key"),
        "created_at": thread.get("created_at"),
        "updated_at": thread.get("updated_at"),
        "notes_url": f"https://notes.granola.ai/t/{thread_id}",
        "messages": messages,
        "source": "cache",
    }


def op_list_meetings(limit: int = 20, page: int = 0, source: str = "api") -> list:
    """Entry point for python: executor. List recent meetings. source: api|cache|auto."""
    if source == "cache":
        return cmd_list_from_cache(limit, page)
    if source == "api":
        token = get_token()
        return cmd_list(token, limit, page)
    # auto: try API, fall back to cache
    try:
        token = get_token()
        return cmd_list(token, limit, page)
    except (SystemExit, FileNotFoundError, OSError, KeyError, json.JSONDecodeError, URLError, HTTPError):
        return cmd_list_from_cache(limit, page)


def op_get_meeting(id: str) -> dict:
    """Entry point for python: executor. Get a meeting with full transcript. API only (cache has no transcript)."""
    token = get_token()
    return cmd_get(token, id)


def op_list_conversations(document_id: str, source: str = "api") -> list:
    """Entry point for python: executor. List Q&A conversations for a meeting. source: api|cache|auto."""
    if source == "cache":
        return cmd_list_conversations_from_cache(document_id)
    if source == "api":
        token = get_token()
        return cmd_list_conversations(token, document_id)
    # auto: try API, fall back to cache
    try:
        token = get_token()
        return cmd_list_conversations(token, document_id)
    except (SystemExit, FileNotFoundError, OSError, KeyError, json.JSONDecodeError, URLError, HTTPError):
        return cmd_list_conversations_from_cache(document_id)


def op_get_conversation(thread_id: str, source: str = "api") -> dict:
    """Entry point for python: executor. Get a Q&A conversation with messages. source: api|cache|auto."""
    if source == "cache":
        return cmd_get_conversation_from_cache(thread_id)
    if source == "api":
        token = get_token()
        return cmd_get_conversation(token, thread_id)
    # auto: try API, fall back to cache
    try:
        token = get_token()
        out = cmd_get_conversation(token, thread_id)
        out["source"] = "api"
        return out
    except (SystemExit, FileNotFoundError, OSError, KeyError, json.JSONDecodeError, URLError, HTTPError):
        return cmd_get_conversation_from_cache(thread_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        die("Usage: granola.py <list|get|list_conversations|get_conversation> [args...]")

    cmd = sys.argv[1]
    try:
        if cmd == "list":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            page = int(sys.argv[3]) if len(sys.argv) > 3 else 0
            source = sys.argv[4] if len(sys.argv) > 4 else "api"
            if source == "cache":
                result = cmd_list_from_cache(limit, page)
            else:
                token = get_token()
                result = cmd_list(token, limit, page)
        elif cmd == "get":
            if len(sys.argv) < 3:
                die("Usage: granola.py get <doc_id>")
            token = get_token()
            result = cmd_get(token, sys.argv[2])
        elif cmd == "list_conversations":
            if len(sys.argv) < 3:
                die("Usage: granola.py list_conversations <document_id> [api|cache]")
            doc_id = sys.argv[2]
            source = sys.argv[3] if len(sys.argv) > 3 else "api"
            if source == "cache":
                result = cmd_list_conversations_from_cache(doc_id)
            else:
                token = get_token()
                result = cmd_list_conversations(token, doc_id)
        elif cmd == "get_conversation":
            if len(sys.argv) < 3:
                die("Usage: granola.py get_conversation <thread_id> [api|cache]")
            thread_id = sys.argv[2]
            source = sys.argv[3] if len(sys.argv) > 3 else "api"
            if source == "cache":
                result = cmd_get_conversation_from_cache(thread_id)
            else:
                token = get_token()
                result = cmd_get_conversation(token, thread_id)
        else:
            die(f"Unknown command: {cmd}")

        print(json.dumps(result))
    except SystemExit:
        raise
    except Exception as e:
        die(str(e))

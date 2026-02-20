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

Official Enterprise API (public-api.granola.ai):
  GET  /v1/notes           cursor pagination, API key auth (Enterprise plan only)
  GET  /v1/notes/{id}      ?include=transcript returns transcript + summary_markdown
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        die("Usage: granola.py <list|get|search> [args...]")

    try:
        token = get_token()
    except SystemExit:
        raise
    except Exception as e:
        die(f"Auth error: {e}")

    cmd = sys.argv[1]
    try:
        if cmd == "list":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            page = int(sys.argv[3]) if len(sys.argv) > 3 else 0
            result = cmd_list(token, limit, page)
        elif cmd == "get":
            if len(sys.argv) < 3:
                die("Usage: granola.py get <doc_id>")
            result = cmd_get(token, sys.argv[2])
        else:
            die(f"Unknown command: {cmd}")

        print(json.dumps(result))
    except SystemExit:
        raise
    except Exception as e:
        die(str(e))

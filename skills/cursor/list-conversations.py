#!/usr/bin/env python3
"""List Cursor AI session conversations from local data.

Two data sources:
  1. JSONL transcripts (~/.cursor/projects/*/agent-transcripts/) — recent sessions
  2. SQLite databases (workspaceStorage + globalStorage) — full history going back months

Default mode reads JSONL only (fast, sub-second).
Backfill mode also reads SQLite for older conversations without JSONL transcripts.

Usage:
    python3 list-conversations.py --json                    # JSONL only (fast)
    python3 list-conversations.py --json --backfill         # JSONL + SQLite history
    python3 list-conversations.py --json --backfill --workspace /Users/joe/dev/agentos
    python3 list-conversations.py --id UUID --json          # Get one by ID (checks both sources)
    python3 list-conversations.py --stats                   # Show what's available
"""

import argparse
import glob
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

CURSOR_PROJECTS = os.path.expanduser("~/.cursor/projects")
WORKSPACE_STORAGE = os.path.expanduser("~/Library/Application Support/Cursor/User/workspaceStorage")
GLOBAL_STATE_DB = os.path.expanduser("~/Library/Application Support/Cursor/User/globalStorage/state.vscdb")


# ── JSONL transcript source ──────────────────────────────────────────────────


def find_transcripts():
    """Find all JSONL transcript files across all workspaces."""
    pattern = os.path.join(CURSOR_PROJECTS, "*", "agent-transcripts", "*", "*.jsonl")
    results = []
    for path in glob.glob(pattern):
        if "subagents" in path:
            continue
        mtime = os.path.getmtime(path)
        results.append((mtime, path))
    results.sort(key=lambda x: x[0], reverse=True)
    return results


def extract_user_query(text):
    """Extract the user's actual query from <user_query> tags."""
    match = re.search(r"<user_query>\s*(.*?)\s*</user_query>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def derive_name(first_query, max_len=80):
    """Derive a conversation name from the first user message."""
    if not first_query:
        return "Untitled conversation"
    text = " ".join(first_query.split())
    text = re.sub(r"@\S+", "", text).strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut + "…" if cut else text[:max_len] + "…"


def parse_jsonl_conversation(path):
    """Parse a JSONL transcript into a conversation dict."""
    uuid = Path(path).stem
    workspace = path.split("/projects/")[1].split("/agent-transcripts/")[0] if "/projects/" in path else "unknown"

    messages = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = d.get("role")
            if role not in ("user", "assistant"):
                continue

            content_blocks = d.get("message", {}).get("content", [])
            text_parts = []
            for block in content_blocks:
                if block.get("type") == "text":
                    text_parts.append(block["text"])
            full_text = "\n".join(text_parts)

            if role == "user":
                query = extract_user_query(full_text)
                if query:
                    messages.append(("user", query))
            elif role == "assistant":
                cleaned = re.sub(r"<[^>]+>", "", full_text).strip()
                if cleaned:
                    messages.append(("assistant", cleaned))

    if not messages:
        return None

    return _build_conversation(uuid, workspace, messages, path=path)


# ── SQLite backfill source ───────────────────────────────────────────────────


def discover_workspaces():
    """Scan Cursor workspaceStorage to map workspace paths to their state DBs.
    
    Returns: dict of { workspace_path: { db: path, composers: [...] } }
    """
    workspaces = {}
    if not os.path.isdir(WORKSPACE_STORAGE):
        return workspaces

    for entry in os.listdir(WORKSPACE_STORAGE):
        ws_dir = os.path.join(WORKSPACE_STORAGE, entry)
        ws_json = os.path.join(ws_dir, "workspace.json")
        state_db = os.path.join(ws_dir, "state.vscdb")

        if not os.path.isfile(ws_json) or not os.path.isfile(state_db):
            continue

        try:
            with open(ws_json) as f:
                folder = json.load(f).get("folder", "")
            if not folder:
                continue
            # file:///Users/joe/dev/agentos → /Users/joe/dev/agentos
            workspace_path = folder.replace("file://", "")
        except (json.JSONDecodeError, IOError):
            continue

        # Read composer metadata from workspace DB
        composers = _read_composer_metadata(state_db)
        if composers:
            workspaces[workspace_path] = {
                "db": state_db,
                "composers": composers,
            }

    return workspaces


def _read_composer_metadata(db_path):
    """Read composer list from a workspace state.vscdb.
    
    Returns list of dicts with composerId, name, createdAt, etc.
    This is cheap — reads one small JSON key.
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.execute(
            "SELECT value FROM ItemTable WHERE key = 'composer.composerData'"
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return []
        data = json.loads(row[0])
        return data.get("allComposers", [])
    except (sqlite3.Error, json.JSONDecodeError, IOError):
        return []


def reconstruct_conversation_from_blobs(composer_id, workspace_slug):
    """Read message blobs from global state.vscdb and reconstruct a conversation.
    
    Each conversation's messages are stored as individual KV entries:
      key: bubbleId:{composerId}:{messageId}
      value: JSON blob with type (1=user, 2=assistant), text, createdAt, etc.
    """
    if not os.path.isfile(GLOBAL_STATE_DB):
        return None

    try:
        conn = sqlite3.connect(f"file:{GLOBAL_STATE_DB}?mode=ro", uri=True)
        prefix = f"bubbleId:{composer_id}:"
        cursor = conn.execute(
            "SELECT value FROM cursorDiskKV WHERE key >= ? AND key < ?",
            (prefix, prefix[:-1] + chr(ord(':') + 1))
        )
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error:
        return None

    if not rows:
        return None

    # Parse blobs, extract messages with text
    raw_messages = []
    for (blob_json,) in rows:
        if not isinstance(blob_json, str):
            continue
        try:
            blob = json.loads(blob_json)
        except (json.JSONDecodeError, TypeError):
            continue

        typ = blob.get("type", 0)
        text = (blob.get("text", "") or "").strip()
        created = blob.get("createdAt", "")

        if text and typ in (1, 2):
            role = "user" if typ == 1 else "assistant"
            raw_messages.append((created, role, text))

    if not raw_messages:
        return None

    # Sort by timestamp
    raw_messages.sort(key=lambda x: x[0])
    messages = [(role, text) for _, role, text in raw_messages]

    return _build_conversation(composer_id, workspace_slug, messages)


def _workspace_path_to_slug(path):
    """Convert a workspace path to Cursor's slug format.
    
    /Users/joe/dev/agentos → Users-joe-dev-agentos
    """
    clean = path.lstrip("/")
    return clean.replace("/", "-")


# ── Shared ───────────────────────────────────────────────────────────────────


def _build_conversation(uuid, workspace, messages, path=None):
    """Build a conversation dict from a list of (role, text) tuples."""
    first_user = next((text for role, text in messages if role == "user"), None)
    last_user = None
    for role, text in reversed(messages):
        if role == "user":
            last_user = text
            break

    user_count = sum(1 for role, _ in messages if role == "user")

    transcript_parts = []
    for role, text in messages:
        transcript_parts.append(f"## {role}\n\n{text}\n")
    transcript = "\n".join(transcript_parts)

    if path:
        mtime = os.path.getmtime(path)
        last_message_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    else:
        last_message_at = datetime.now(tz=timezone.utc).isoformat()

    return {
        "id": uuid,
        "name": derive_name(first_user),
        "last_message": (" ".join((last_user or "").split()))[:200],
        "last_message_at": last_message_at,
        "message_count": user_count,
        "workspace": workspace,
        "transcript": transcript,
    }


# ── Main ─────────────────────────────────────────────────────────────────────


def get_jsonl_conversations():
    """Get all conversations from JSONL transcripts."""
    transcripts = find_transcripts()
    conversations = {}
    for _, path in transcripts:
        conv = parse_jsonl_conversation(path)
        if conv:
            conversations[conv["id"]] = conv
    return conversations


def get_backfill_conversations(workspace_filter=None, exclude_ids=None):
    """Get historical conversations from SQLite databases.
    
    Scans all Cursor workspaces, reads composer metadata, then reconstructs
    conversations from global blob store in batch. Optionally filter to one workspace.
    """
    workspaces = discover_workspaces()
    exclude_ids = exclude_ids or set()
    conversations = {}

    # Collect all (composerId, workspace_slug, composer_meta) tuples to process
    to_process = []
    for ws_path, ws_data in workspaces.items():
        if workspace_filter and not ws_path.startswith(workspace_filter):
            continue

        ws_slug = _workspace_path_to_slug(ws_path)

        for composer in ws_data["composers"]:
            cid = composer.get("composerId", "")
            if not cid or cid in exclude_ids:
                continue
            # Skip sub-agent tasks (duplicate IDs like "task-toolu_0")
            if cid.startswith("task-"):
                continue
            if composer.get("isArchived") or composer.get("isDraft"):
                continue
            to_process.append((cid, ws_slug, composer))

    if not to_process or not os.path.isfile(GLOBAL_STATE_DB):
        return conversations

    print(f"Backfilling {len(to_process)} conversations from SQLite...", file=sys.stderr)

    # Batch read: one query per conversation (LIKE prefix is indexed)
    try:
        conn = sqlite3.connect(f"file:{GLOBAL_STATE_DB}?mode=ro", uri=True)
    except sqlite3.Error as e:
        print(f"Failed to open global DB: {e}", file=sys.stderr)
        return conversations

    for i, (cid, ws_slug, composer) in enumerate(to_process):
        if (i + 1) % 50 == 0:
            print(f"  ...processed {i + 1}/{len(to_process)}", file=sys.stderr)

        try:
            # Range query uses the B-tree index (6ms vs 1.3s for LIKE)
            prefix = f"bubbleId:{cid}:"
            cursor = conn.execute(
                "SELECT value FROM cursorDiskKV WHERE key >= ? AND key < ?",
                (prefix, prefix[:-1] + chr(ord(':') + 1))
            )
            rows = cursor.fetchall()
        except sqlite3.Error:
            continue

        if not rows:
            continue

        # Parse blobs into messages
        raw_messages = []
        for (blob_json,) in rows:
            if not isinstance(blob_json, str):
                continue
            try:
                blob = json.loads(blob_json)
            except (json.JSONDecodeError, TypeError):
                continue
            typ = blob.get("type", 0)
            text = (blob.get("text", "") or "").strip()
            created = blob.get("createdAt", "")
            if text and typ in (1, 2):
                role = "user" if typ == 1 else "assistant"
                raw_messages.append((created, role, text))

        if not raw_messages:
            continue

        raw_messages.sort(key=lambda x: x[0])
        messages = [(role, text) for _, role, text in raw_messages]
        conv = _build_conversation(cid, ws_slug, messages)

        # Enrich with composer metadata
        created_ms = composer.get("createdAt", 0)
        if created_ms:
            conv["created_at"] = datetime.fromtimestamp(
                created_ms / 1000, tz=timezone.utc
            ).isoformat()

        updated_ms = composer.get("lastUpdatedAt", 0)
        if updated_ms:
            conv["last_message_at"] = datetime.fromtimestamp(
                updated_ms / 1000, tz=timezone.utc
            ).isoformat()

        if composer.get("name"):
            conv["name"] = composer["name"]

        conversations[cid] = conv

    conn.close()
    print(f"Backfilled {len(conversations)} conversations with text.", file=sys.stderr)
    return conversations


def get_by_id(conv_id):
    """Get a specific conversation by UUID, checking both sources."""
    # Try JSONL first
    pattern = os.path.join(
        CURSOR_PROJECTS, "*", "agent-transcripts", conv_id, f"{conv_id}.jsonl"
    )
    matches = glob.glob(pattern)
    if matches:
        return parse_jsonl_conversation(matches[0])

    # Fall back to SQLite
    workspaces = discover_workspaces()
    for ws_path, ws_data in workspaces.items():
        for composer in ws_data["composers"]:
            if composer.get("composerId") == conv_id:
                ws_slug = _workspace_path_to_slug(ws_path)
                return reconstruct_conversation_from_blobs(conv_id, ws_slug)

    return None


def show_stats():
    """Show what data is available across both sources."""
    # JSONL
    transcripts = find_transcripts()
    jsonl_ids = set()
    jsonl_by_workspace = {}
    for _, path in transcripts:
        uuid = Path(path).stem
        jsonl_ids.add(uuid)
        ws = path.split("/projects/")[1].split("/agent-transcripts/")[0] if "/projects/" in path else "unknown"
        jsonl_by_workspace[ws] = jsonl_by_workspace.get(ws, 0) + 1

    # SQLite
    workspaces = discover_workspaces()
    sqlite_total = 0
    sqlite_new = 0  # not in JSONL
    sqlite_by_workspace = {}
    for ws_path, ws_data in workspaces.items():
        slug = _workspace_path_to_slug(ws_path)
        count = len([c for c in ws_data["composers"]
                     if not c.get("isArchived") and not c.get("isDraft")])
        new = len([c for c in ws_data["composers"]
                   if not c.get("isArchived") and not c.get("isDraft")
                   and c.get("composerId") not in jsonl_ids])
        sqlite_total += count
        sqlite_new += new
        if count > 0:
            sqlite_by_workspace[slug] = {"total": count, "new": new, "path": ws_path}

    print(f"\n  JSONL transcripts:  {len(jsonl_ids)} sessions")
    print(f"  SQLite composers:  {sqlite_total} sessions ({sqlite_new} without JSONL)")
    print(f"  Workspaces:        {len(sqlite_by_workspace)} with data\n")

    # Sort by total descending
    for slug, info in sorted(sqlite_by_workspace.items(), key=lambda x: x[1]["total"], reverse=True):
        jsonl = jsonl_by_workspace.get(slug, 0)
        print(f"  {info['total']:4d} total  {info['new']:4d} sqlite-only  {jsonl:4d} jsonl  {info['path']}")

    print()


def main():
    parser = argparse.ArgumentParser(description="List Cursor session conversations")
    parser.add_argument("--id", default=None, help="Get a specific conversation by UUID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--backfill", action="store_true",
                        help="Include historical conversations from SQLite (slower)")
    parser.add_argument("--workspace", default=None,
                        help="Filter to workspace path (e.g. /Users/joe/dev/agentos)")
    parser.add_argument("--stats", action="store_true",
                        help="Show available data across both sources")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if args.id:
        conv = get_by_id(args.id)
        if not conv:
            if args.json:
                print(json.dumps(None))
            else:
                print(f"No transcript found for {args.id}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(conv, ensure_ascii=False))
        else:
            print(f"{conv['name']} ({conv['message_count']} exchanges)")
        return

    # Start with JSONL (always fast)
    conversations = get_jsonl_conversations()

    if args.backfill:
        # Add SQLite conversations, skip any already found in JSONL
        backfill = get_backfill_conversations(
            workspace_filter=args.workspace,
            exclude_ids=set(conversations.keys()),
        )
        conversations.update(backfill)

    # Sort by last_message_at descending
    result = sorted(conversations.values(), key=lambda c: c.get("last_message_at", ""), reverse=True)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        for conv in result:
            print(f"  {conv['id'][:8]}  {conv['name'][:60]}  ({conv['message_count']} exchanges)")


if __name__ == "__main__":
    main()

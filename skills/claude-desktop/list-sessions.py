#!/usr/bin/env python3
"""List Claude Code sessions from local JSONL transcripts.

Claude Code (the CLI, run from within Claude Desktop or standalone) stores
conversation transcripts as JSONL files at:
  ~/.claude/projects/{workspace-slug}/{session-uuid}.jsonl

Each line is a JSON object with type "user", "assistant", "system", etc.
User messages have a .message.content array; assistant messages have the same.

Usage:
    python3 list-sessions.py --json               # List all sessions
    python3 list-sessions.py --json --workspace /path/to/project
    python3 list-sessions.py --json --query "search term"
    python3 list-sessions.py --json --id UUID     # Get one session with full transcript
    python3 list-sessions.py --stats              # Show available data summary
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")


# ── Text extraction ──────────────────────────────────────────────────────────


def extract_text_from_content(content):
    """Extract plain text from a JSONL message content field.

    Content is either a string or a list of block objects like:
      [{"type": "text", "text": "..."}, {"type": "tool_use", ...}, ...]
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                # Skip tool_use, tool_result, thinking blocks
        return "\n".join(parts).strip()
    return ""


def derive_name(first_query, max_len=80):
    """Derive a conversation name from the first user message."""
    if not first_query:
        return "Untitled session"
    # Strip XML-style tags (like <local-command-caveat>...</local-command-caveat>)
    text = re.sub(r"<[^>]+>.*?</[^>]+>", "", first_query, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = " ".join(text.split())
    if not text:
        return "Untitled session"
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut + "…" if cut else text[:max_len] + "…"


def workspace_slug_to_path(slug):
    """Convert a project folder slug back to a filesystem path.

    Claude Code converts /Users/joe/dev/agentos → -Users-joe-dev-agentos
    """
    # Replace leading dash and internal dashes used as separators
    # Best effort: replace - with / unless it's clearly part of a name
    # The slug is: leading path sep becomes -, each / becomes -
    return "/" + slug.lstrip("-").replace("-", "/")


# ── JSONL parsing ────────────────────────────────────────────────────────────


def find_session_files(workspace_filter=None):
    """Find all JSONL session files.

    Returns list of (mtime, path) tuples sorted newest-first.
    """
    pattern = os.path.join(CLAUDE_PROJECTS_DIR, "*", "*.jsonl")
    results = []
    for path in glob.glob(pattern):
        # Skip agent sub-sessions (prefixed with 'agent-')
        if Path(path).stem.startswith("agent-"):
            continue
        if workspace_filter:
            # The workspace slug in the parent dir
            slug = Path(path).parent.name
            # Convert slug to path for comparison
            ws_path = workspace_slug_to_path(slug)
            if not ws_path.startswith(workspace_filter) and workspace_filter not in ws_path:
                continue
        mtime = os.path.getmtime(path)
        results.append((mtime, path))
    results.sort(key=lambda x: x[0], reverse=True)
    return results


def parse_session(path, include_transcript=False, query_filter=None):
    """Parse a JSONL session file into a session dict.

    Returns None if the file has no meaningful messages or doesn't match filter.
    """
    uuid = Path(path).stem
    workspace_slug = Path(path).parent.name

    # Convert slug back to a human-readable path
    # -Users-joe-dev-agentos → /Users/joe/dev/agentos (best effort)
    workspace_path = workspace_slug_to_path(workspace_slug)

    messages = []  # list of (role, text, timestamp)
    session_id = None
    cwd = None

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                t = obj.get("type", "")

                # Pick up session metadata from any message
                if session_id is None:
                    session_id = obj.get("sessionId")
                if cwd is None:
                    cwd = obj.get("cwd")

                if t not in ("user", "assistant"):
                    continue

                # Skip meta messages (system injections)
                if obj.get("isMeta"):
                    continue

                msg = obj.get("message", {})
                content = msg.get("content", "")
                text = extract_text_from_content(content)

                # Filter out very short or empty messages
                if not text or len(text.strip()) < 2:
                    continue

                timestamp = obj.get("timestamp", "")
                messages.append((t, text, timestamp))
    except (IOError, OSError):
        return None

    if not messages:
        return None

    # Build text for search matching
    full_text = " ".join(text for _, text, _ in messages).lower()
    if query_filter and query_filter.lower() not in full_text:
        return None

    # Derive name from first user message
    first_user_text = next((text for role, text, _ in messages if role == "user"), None)
    name = derive_name(first_user_text)

    # Last user message for preview
    last_user_text = None
    for role, text, _ in reversed(messages):
        if role == "user":
            last_user_text = text
            break

    # Timestamps
    mtime = os.path.getmtime(path)
    last_message_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    # First message timestamp from the file itself
    first_ts = messages[0][2] if messages else ""
    created_at = first_ts or last_message_at

    user_count = sum(1 for role, _, _ in messages if role == "user")
    assistant_count = sum(1 for role, _, _ in messages if role == "assistant")

    result = {
        "id": uuid,
        "name": name,
        "workspace": cwd or workspace_path,
        "created_at": created_at,
        "last_message_at": last_message_at,
        "last_message": (" ".join((last_user_text or "").split()))[:200],
        "message_count": user_count + assistant_count,
        "user_turns": user_count,
    }

    if include_transcript:
        transcript_parts = []
        for role, text, ts in messages:
            transcript_parts.append(f"## {role}\n\n{text}\n")
        result["transcript"] = "\n".join(transcript_parts)

    return result


# ── Main ─────────────────────────────────────────────────────────────────────


def cmd_list(workspace_filter=None, query_filter=None):
    """List all sessions (without transcripts for speed)."""
    files = find_session_files(workspace_filter=workspace_filter)
    results = []
    for _, path in files:
        session = parse_session(path, include_transcript=False, query_filter=query_filter)
        if session:
            results.append(session)
    return results


def cmd_get(session_id):
    """Get a single session with full transcript."""
    # Search all project dirs for the UUID
    pattern = os.path.join(CLAUDE_PROJECTS_DIR, "*", f"{session_id}.jsonl")
    matches = glob.glob(pattern)
    if not matches:
        return None
    return parse_session(matches[0], include_transcript=True)


def cmd_stats():
    """Print human-readable stats about available sessions."""
    files = find_session_files()
    total = len(files)
    if total == 0:
        print("No Claude Code sessions found.")
        print(f"Expected location: {CLAUDE_PROJECTS_DIR}")
        return

    # Workspace breakdown
    workspaces = {}
    for _, path in files:
        slug = Path(path).parent.name
        workspaces[slug] = workspaces.get(slug, 0) + 1

    print(f"Claude Code sessions: {total}")
    print(f"Workspaces: {len(workspaces)}")
    print()

    # Newest/oldest
    if files:
        newest_path = files[0][1]
        oldest_path = files[-1][1]
        newest_mtime = datetime.fromtimestamp(files[0][0]).strftime("%Y-%m-%d")
        oldest_mtime = datetime.fromtimestamp(files[-1][0]).strftime("%Y-%m-%d")
        print(f"Date range: {oldest_mtime} → {newest_mtime}")
        print()

    print("Sessions per workspace:")
    for slug, count in sorted(workspaces.items(), key=lambda x: -x[1]):
        ws_path = workspace_slug_to_path(slug)
        print(f"  {count:3d}  {ws_path}")


def main():
    parser = argparse.ArgumentParser(description="List Claude Code sessions")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--id", help="Get a specific session by UUID")
    parser.add_argument("--workspace", help="Filter to a workspace path")
    parser.add_argument("--query", help="Search sessions by content")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    args = parser.parse_args()

    if args.stats:
        cmd_stats()
        return

    if args.id:
        result = cmd_get(args.id)
        if result is None:
            if args.json:
                print(json.dumps([]))
            else:
                print(f"Session not found: {args.id}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps([result]))
        else:
            print(f"Session: {result['id']}")
            print(f"Name: {result['name']}")
            print(f"Workspace: {result['workspace']}")
            print(f"Created: {result['created_at']}")
            print(f"Messages: {result['message_count']}")
            print()
            print(result.get("transcript", ""))
        return

    results = cmd_list(
        workspace_filter=args.workspace,
        query_filter=args.query,
    )

    if args.json:
        print(json.dumps(results))
    else:
        for r in results:
            print(f"{r['id'][:8]}  {r['last_message_at'][:10]}  {r['name'][:60]}")


if __name__ == "__main__":
    main()

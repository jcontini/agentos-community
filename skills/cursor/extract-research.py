#!/usr/bin/env python3
"""
Extract sub-agent research from Cursor's internal SQLite database.

Cursor stores all conversation data in:
  ~/Library/Application Support/Cursor/User/globalStorage/state.vscdb

Sub-agent Task tool results are stored as agentKv:blob:{sha256} entries
in the cursorDiskKV table. Each blob is a JSON message containing:
  - role: "tool"
  - content[0].toolName: "Task"
  - content[0].result: final sub-agent output text
  - providerOptions.cursor.highLevelToolCallResult.output.success:
    - conversationSteps: full sub-agent conversation transcript
    - agentId: sub-agent UUID
    - durationMs: total runtime

This script finds research-quality Task results (ones with web searches
and substantial markdown output), extracts them, and saves to .research/
with YAML front matter for traceability.

Usage:
  python3 extract-research.py                    # list new research
  python3 extract-research.py --save             # save new to .research/
  python3 extract-research.py --all              # list all research (incl. already saved)
  python3 extract-research.py --blob <hash>      # extract a specific blob
"""

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
import textwrap
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────

GLOBAL_STATE_DB = os.path.expanduser(
    "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
)
WORKSPACE_STORAGE = os.path.expanduser(
    "~/Library/Application Support/Cursor/User/workspaceStorage"
)

# ─── Minimum thresholds to qualify as "research" ─────────────────────────────

MIN_SEARCHES = 3          # at least 3 web searches
MIN_OUTPUT_CHARS = 3000   # at least 3k chars of final output
MIN_STEPS = 5             # at least 5 conversation steps


# ─── Database helpers ────────────────────────────────────────────────────────

def open_db(path):
    """Open a SQLite DB read-only."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_task_blobs(conn, search_term=None):
    """Find all agentKv:blob entries that are Task tool results."""
    cur = conn.cursor()

    if search_term:
        cur.execute(
            """SELECT key, value FROM cursorDiskKV
               WHERE key LIKE 'agentKv:blob:%'
               AND CAST(value AS TEXT) LIKE '%"toolName":"Task"%'
               AND CAST(value AS TEXT) LIKE ?""",
            (f"%{search_term}%",),
        )
    else:
        cur.execute(
            """SELECT key, value FROM cursorDiskKV
               WHERE key LIKE 'agentKv:blob:%'
               AND CAST(value AS TEXT) LIKE '%"toolName":"Task"%'"""
        )

    return cur.fetchall()


# ─── Blob parsing ────────────────────────────────────────────────────────────

def parse_task_blob(blob_value):
    """Parse a Task tool result blob and extract research metadata."""
    try:
        # Handle both text and binary blob values
        if isinstance(blob_value, bytes):
            try:
                blob_value = blob_value.decode("utf-8")
            except UnicodeDecodeError:
                return None
        data = json.loads(blob_value)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None

    if data.get("role") != "tool":
        return None

    content = data.get("content", [])
    if not content or content[0].get("toolName") != "Task":
        return None

    item = content[0]
    result_text = item.get("result", "")

    # Extract sub-agent conversation data
    po = (
        data.get("providerOptions", {})
        .get("cursor", {})
        .get("highLevelToolCallResult", {})
        .get("output", {})
        .get("success", {})
    )

    steps = po.get("conversationSteps", [])
    agent_id = po.get("agentId")
    duration_ms = po.get("durationMs")

    # Extract searches and URLs from conversation steps
    searches = []
    urls_fetched = []
    final_text = ""

    for step in steps:
        if "toolCall" in step:
            tc = step["toolCall"]
            if "webSearchToolCall" in tc:
                args = tc["webSearchToolCall"].get("args", {})
                term = args.get("searchTerm", "")
                if term:
                    searches.append(term)
            elif "webFetchToolCall" in tc:
                args = tc["webFetchToolCall"].get("args", {})
                url = args.get("url", "")
                if url:
                    urls_fetched.append(url)

    # Get the final assistant message (the actual research output)
    for step in reversed(steps):
        if "assistantMessage" in step:
            final_text = step["assistantMessage"].get("text", "")
            break

    # Strip "This is the last output of the subagent:\n\n" prefix from result
    clean_result = result_text
    if clean_result.startswith("This is the last output of the subagent:"):
        clean_result = clean_result[len("This is the last output of the subagent:"):].lstrip()

    # Extract the tool call ID (used to map to workspace via task-{toolCallId} composers)
    tool_call_id = item.get("toolCallId", "")

    return {
        "result_text": clean_result,
        "final_text": final_text,
        "agent_id": agent_id,
        "tool_call_id": tool_call_id,
        "duration_ms": duration_ms,
        "steps": len(steps),
        "searches": searches,
        "urls_fetched": urls_fetched,
    }


def is_research(parsed):
    """Determine if a parsed Task blob qualifies as research."""
    if not parsed:
        return False
    text = parsed["final_text"] or parsed["result_text"]
    return (
        len(parsed["searches"]) >= MIN_SEARCHES
        and len(text) >= MIN_OUTPUT_CHARS
        and parsed["steps"] >= MIN_STEPS
    )


# ─── Workspace mapping ──────────────────────────────────────────────────────

def build_workspace_map():
    """Build a mapping of workspace storage hash → folder path."""
    ws_map = {}
    if not os.path.isdir(WORKSPACE_STORAGE):
        return ws_map

    for d in os.listdir(WORKSPACE_STORAGE):
        wj = os.path.join(WORKSPACE_STORAGE, d, "workspace.json")
        if os.path.exists(wj):
            try:
                with open(wj) as f:
                    data = json.load(f)
                folder = data.get("folder", data.get("workspace", ""))
                # Decode file:// URLs
                if folder.startswith("file:///"):
                    from urllib.parse import unquote
                    folder = unquote(folder[7:])
                ws_map[d] = folder
            except (json.JSONDecodeError, IOError):
                pass
    return ws_map


def build_conversation_index():
    """Build an index of conversation ID → {name, workspace, created_at}."""
    ws_map = build_workspace_map()
    convos = {}

    for ws_hash, folder in ws_map.items():
        db_path = os.path.join(WORKSPACE_STORAGE, ws_hash, "state.vscdb")
        if not os.path.exists(db_path):
            continue

        try:
            conn = open_db(db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT value FROM ItemTable WHERE key = 'composer.composerData'"
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                continue

            data = json.loads(row[0])
            for c in data.get("allComposers", []):
                cid = c.get("composerId", "")
                convos[cid] = {
                    "name": c.get("name", ""),
                    "workspace": folder,
                    "created_at": c.get("createdAt", 0),
                    "mode": c.get("unifiedMode", ""),
                    "branch": c.get("committedToBranch", ""),
                }
            conn.close()
        except (sqlite3.Error, json.JSONDecodeError):
            pass

    return convos


# ─── Title / slug generation ────────────────────────────────────────────────

def generate_title(parsed, blob_key=""):
    """Generate a human-readable title from the research content."""
    text = parsed["final_text"] or parsed["result_text"]

    # Try to extract the first H1 or H2 heading
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line.startswith("## ") and len(line) > 20:
            return line[3:].strip()

    # Fall back to first meaningful sentence
    for line in text.split("\n"):
        line = line.strip()
        if len(line) > 30 and not line.startswith("#") and not line.startswith("|"):
            return line[:80]

    return f"Research {blob_key[:16]}"


def slugify(text):
    """Convert text to a URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")[:60]


# ─── Front matter generation ────────────────────────────────────────────────

def yaml_list(items, indent=2):
    """Format a list for YAML."""
    prefix = " " * indent
    return "\n".join(f"{prefix}- {item}" for item in items)


def generate_front_matter(parsed, blob_key, title, conversation=None):
    """Generate YAML front matter for a research file."""
    # Determine date from conversation metadata or current date
    date = datetime.date.today().isoformat()
    conv_name = ""
    workspace = ""
    conv_id = ""

    if conversation:
        ts = conversation.get("created_at", 0)
        if ts:
            date = datetime.datetime.fromtimestamp(ts / 1000).date().isoformat()
        conv_name = conversation.get("name", "")
        workspace = conversation.get("workspace", "")

    lines = ["---"]
    lines.append(f"date: {date}")
    lines.append(f"topic: {title}")

    # Source block
    lines.append("source:")
    lines.append(f"  type: cursor-subagent")
    lines.append(f"  blob_key: {blob_key}")
    if parsed["agent_id"]:
        lines.append(f"  agent_id: {parsed['agent_id']}")
    if parsed["duration_ms"]:
        lines.append(f"  duration_ms: {parsed['duration_ms']}")
    lines.append(f"  conversation_steps: {parsed['steps']}")
    if workspace:
        lines.append(f"  workspace: {workspace}")
    if conv_name:
        lines.append(f"  conversation_name: {conv_name}")

    # Roadmap (placeholder — filled in manually)
    lines.append("roadmap: []")

    # Searches
    if parsed["searches"]:
        lines.append("searches:")
        for s in parsed["searches"]:
            # Escape YAML special chars
            s_escaped = s.replace('"', '\\"')
            lines.append(f'  - "{s_escaped}"')

    # URLs fetched
    if parsed["urls_fetched"]:
        lines.append("urls_fetched:")
        for u in parsed["urls_fetched"]:
            lines.append(f"  - {u}")

    lines.append("---")
    return "\n".join(lines)


# ─── Existing file check ────────────────────────────────────────────────────

def get_existing_blob_keys(research_dir):
    """Scan .research/ files and extract blob_key values from front matter."""
    keys = set()
    if not research_dir.is_dir():
        return keys

    for f in research_dir.glob("*.md"):
        try:
            content = f.read_text()
            # Parse YAML front matter
            if content.startswith("---"):
                end = content.index("---", 3)
                fm = content[3:end]
                for line in fm.split("\n"):
                    line = line.strip()
                    # Match both top-level and nested blob_key
                    if line.startswith("blob_key:"):
                        key = line.split(":", 1)[1].strip()
                        if key:
                            keys.add(key)
        except (ValueError, IOError):
            pass
    return keys


# ─── Workspace matching ──────────────────────────────────────────────────────

def _workspace_matches(ws_folder, target_path):
    """
    Check if a workspace folder matches a target path.
    Handles: case-insensitive comparison (macOS), .code-workspace files,
    and prefix matching for workspaces that are parent directories.
    """
    # Normalize both paths
    ws = ws_folder.lower().rstrip("/")
    target = target_path.lower().rstrip("/")

    # Handle .code-workspace files — extract the directory
    if ws.endswith(".code-workspace"):
        ws_dir = os.path.dirname(ws)
    else:
        ws_dir = ws

    # Direct match
    if ws_dir == target or ws == target:
        return True

    # Prefix match (workspace is parent of target, or vice versa)
    if target.startswith(ws_dir + "/") or ws_dir.startswith(target + "/"):
        return True

    # The workspace folder name contains the target directory name
    # e.g. /Users/joe/dev/AgentOS.code-workspace matches /Users/joe/dev/agentos
    ws_basename = os.path.basename(ws).replace(".code-workspace", "")
    target_basename = os.path.basename(target)
    if ws_basename == target_basename:
        # Same directory name, check parent
        if os.path.dirname(ws_dir) == os.path.dirname(target):
            return True

    return False


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract sub-agent research from Cursor's internal database."
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save new research to .research/ directory"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Show all research including already-saved"
    )
    parser.add_argument(
        "--blob", type=str,
        help="Extract a specific blob by hash (prefix match OK)"
    )
    parser.add_argument(
        "--search", type=str,
        help="Filter blobs containing this text"
    )
    parser.add_argument(
        "--min-searches", type=int, default=MIN_SEARCHES,
        help=f"Minimum web searches to qualify (default: {MIN_SEARCHES})"
    )
    parser.add_argument(
        "--min-chars", type=int, default=MIN_OUTPUT_CHARS,
        help=f"Minimum output chars to qualify (default: {MIN_OUTPUT_CHARS})"
    )
    parser.add_argument(
        "--workspace", type=str,
        help="Filter to research from conversations in this workspace folder"
    )
    parser.add_argument(
        "--filter", type=str,
        help="Only show research containing this text in output"
    )
    parser.add_argument(
        "--research-dir", type=str,
        help="Path to .research/ directory (default: cwd/.research/)"
    )

    args = parser.parse_args()

    # Determine research directory
    research_dir = Path(args.research_dir) if args.research_dir else Path.cwd() / ".research"

    if not os.path.exists(GLOBAL_STATE_DB):
        print(f"Error: Cursor state DB not found at {GLOBAL_STATE_DB}", file=sys.stderr)
        sys.exit(1)

    conn = open_db(GLOBAL_STATE_DB)

    # Build conversation index for metadata enrichment
    print("Building conversation index...", file=sys.stderr)
    convos = build_conversation_index()
    print(f"Found {len(convos)} conversations across workspaces.", file=sys.stderr)

    # Get existing blob keys to skip already-saved research
    existing_keys = get_existing_blob_keys(research_dir)

    if args.blob:
        # Extract a specific blob
        cur = conn.cursor()
        cur.execute(
            "SELECT key, value FROM cursorDiskKV WHERE key LIKE ?",
            (f"agentKv:blob:{args.blob}%",),
        )
        rows = cur.fetchall()
        if not rows:
            print(f"No blob found matching: {args.blob}", file=sys.stderr)
            sys.exit(1)
        for row in rows:
            blob_key = row["key"]
            parsed = parse_task_blob(row["value"])
            if parsed:
                text = parsed["final_text"] or parsed["result_text"]
                print(text)
            else:
                print(f"Blob {blob_key} is not a Task tool result", file=sys.stderr)
        conn.close()
        return

    # Find all Task tool result blobs
    print("Scanning for Task tool result blobs...", file=sys.stderr)
    blobs = get_task_blobs(conn, args.search)
    print(f"Found {len(blobs)} Task tool results.", file=sys.stderr)

    # Build workspace filter if specified
    workspace_convos = None
    if args.workspace:
        workspace_path = os.path.abspath(args.workspace)
        workspace_convos = set()
        for cid, cdata in convos.items():
            ws = cdata.get("workspace", "")
            if ws and _workspace_matches(ws, workspace_path):
                workspace_convos.add(cid)
        print(
            f"Workspace filter: {workspace_path} → {len(workspace_convos)} conversations",
            file=sys.stderr,
        )

    research_blobs = []
    for row in blobs:
        blob_key = row["key"]
        parsed = parse_task_blob(row["value"])

        if not parsed:
            continue

        # Apply custom thresholds
        text = parsed["final_text"] or parsed["result_text"]
        if (
            len(parsed["searches"]) < args.min_searches
            or len(text) < args.min_chars
            or parsed["steps"] < MIN_STEPS
        ):
            continue

        # Apply text filter
        if args.filter and args.filter.lower() not in text.lower():
            continue

        # Find matching conversation via tool_call_id → task-{toolCallId} composer
        conversation = None
        composer_key = f"task-{parsed['tool_call_id']}" if parsed["tool_call_id"] else ""
        if composer_key and composer_key in convos:
            conversation = convos[composer_key]
        elif parsed["agent_id"]:
            # Fallback: check by agent_id in tool call IDs
            for cid, cdata in convos.items():
                if cid.startswith("task-") and parsed["agent_id"] in cid:
                    conversation = cdata
                    break

        # Apply workspace filter
        if workspace_convos is not None:
            if conversation:
                # Use the composer_key to check workspace membership
                if composer_key and composer_key in workspace_convos:
                    pass  # matches workspace
                else:
                    # Check workspace path match
                    ws = conversation.get("workspace", "")
                    workspace_path = os.path.abspath(args.workspace)
                    if not _workspace_matches(ws, workspace_path):
                        continue
            else:
                # No conversation found — check blob content for workspace paths
                blob_text = ""
                try:
                    blob_text = row["value"].decode("utf-8") if isinstance(row["value"], bytes) else str(row["value"])
                except:
                    pass
                workspace_path = os.path.abspath(args.workspace)
                if workspace_path not in blob_text:
                    continue

        title = generate_title(parsed, blob_key)
        is_new = blob_key not in existing_keys

        research_blobs.append({
            "blob_key": blob_key,
            "parsed": parsed,
            "title": title,
            "conversation": conversation,
            "is_new": is_new,
        })

    # Sort by output length (most substantial first)
    research_blobs.sort(
        key=lambda r: len(r["parsed"]["final_text"] or r["parsed"]["result_text"]),
        reverse=True,
    )

    # Display results
    shown = 0
    saved = 0
    for r in research_blobs:
        if not args.all and not r["is_new"]:
            continue

        p = r["parsed"]
        text = p["final_text"] or p["result_text"]
        status = "NEW" if r["is_new"] else "SAVED"
        hash_short = r["blob_key"].split(":")[-1][:16]

        print(f"\n{'=' * 72}")
        print(f"[{status}] {r['title']}")
        print(f"  Blob:     {hash_short}...")
        print(f"  Output:   {len(text):,} chars")
        print(f"  Steps:    {p['steps']}")
        print(f"  Searches: {len(p['searches'])}")
        print(f"  URLs:     {len(p['urls_fetched'])}")
        if p["agent_id"]:
            print(f"  Agent:    {p['agent_id']}")
        if r["conversation"]:
            c = r["conversation"]
            print(f"  Conv:     {c['name']}")
            print(f"  Workspace: {c['workspace']}")
        shown += 1

        if args.save and r["is_new"]:
            # Generate filename
            date = datetime.date.today().isoformat()
            if r["conversation"] and r["conversation"]["created_at"]:
                ts = r["conversation"]["created_at"]
                date = datetime.datetime.fromtimestamp(ts / 1000).date().isoformat()

            slug = slugify(r["title"])
            filename = f"{date}-{slug}.md"
            filepath = research_dir / filename

            # Avoid overwriting
            counter = 1
            while filepath.exists():
                filename = f"{date}-{slug}-{counter}.md"
                filepath = research_dir / filename
                counter += 1

            # Generate content
            front_matter = generate_front_matter(
                p, r["blob_key"], r["title"], r["conversation"]
            )
            body = text

            research_dir.mkdir(exist_ok=True)
            filepath.write_text(f"{front_matter}\n\n{body}\n")
            print(f"  SAVED → {filepath}")
            saved += 1

    print(f"\n{'─' * 72}")
    print(f"Total research blobs: {len(research_blobs)}")
    print(f"Shown: {shown} | Already saved: {len(research_blobs) - sum(1 for r in research_blobs if r['is_new'])}")
    if args.save:
        print(f"Newly saved: {saved}")

    conn.close()


if __name__ == "__main__":
    main()

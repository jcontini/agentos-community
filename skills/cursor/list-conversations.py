#!/usr/bin/env python3
"""List Cursor AI session conversations from local JSONL transcripts.

Reads ALL JSONL transcript files from ~/.cursor/projects/*/agent-transcripts/
and returns structured JSON suitable for the AgentOS entity pipeline.
Each conversation includes a workspace property for graph-side filtering.

Usage:
    python3 list-conversations.py --json
    python3 list-conversations.py --id 3d3a1b3d-31c5-4e12-839c-f0c0f9f2d914 --json
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CURSOR_PROJECTS = os.path.expanduser("~/.cursor/projects")


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


def parse_conversation(path):
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

    mtime = os.path.getmtime(path)
    last_message_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    return {
        "id": uuid,
        "name": derive_name(first_user),
        "last_message": (" ".join((last_user or "").split()))[:200],
        "last_message_at": last_message_at,
        "message_count": user_count,
        "workspace": workspace,
        "transcript": transcript,
    }


def main():
    parser = argparse.ArgumentParser(description="List Cursor session conversations")
    parser.add_argument("--id", default=None, help="Get a specific conversation by UUID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.id:
        pattern = os.path.join(CURSOR_PROJECTS, "*", "agent-transcripts", args.id, f"{args.id}.jsonl")
        matches = glob.glob(pattern)
        if not matches:
            if args.json:
                print(json.dumps(None))
            else:
                print(f"No transcript found for {args.id}", file=sys.stderr)
            sys.exit(1)
        conv = parse_conversation(matches[0])
        if args.json:
            print(json.dumps(conv, ensure_ascii=False))
        else:
            print(f"{conv['name']} ({conv['message_count']} exchanges)")
        return

    transcripts = find_transcripts()
    conversations = []
    for _, path in transcripts:
        conv = parse_conversation(path)
        if conv:
            conversations.append(conv)

    if args.json:
        print(json.dumps(conversations, ensure_ascii=False))
    else:
        for conv in conversations:
            print(f"  {conv['id'][:8]}  {conv['name'][:60]}  ({conv['message_count']} exchanges)")


if __name__ == "__main__":
    main()

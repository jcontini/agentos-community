#!/usr/bin/env python3
"""
claude-api.py — httpx-based client for the claude.ai private API

Uses the sessionKey cookie saved by claude-login.py.
All API calls use httpx (NOT Playwright) — login is the only thing that
needs a browser. Once the sessionKey is extracted, httpx handles everything.

Required headers (bypass Cloudflare + match expected browser client):
  Cookie: sessionKey=sk-ant-sid02-...
  anthropic-client-version: claude-ai/web@1.1.5368
  Sec-Fetch-Site: same-origin
  Sec-Fetch-Mode: cors
  Sec-Fetch-Dest: empty

Usage:
  python3 claude-api.py --op organizations
  python3 claude-api.py --op conversations [--org ORG_UUID] [--limit 50] [--offset 0]
  python3 claude-api.py --op conversation --id CONV_UUID [--org ORG_UUID]
  python3 claude-api.py --op search --query TEXT [--org ORG_UUID]

Accounts / Orgs for anthropic@contini.co:
  c10a8db6-c2ed-4750-95ef-a0367a39362c  anthropic@contini.co's Organization  (chat, claude_pro)
  6b0831ae-5799-43af-90c2-4dba40206d35  A Third Party                        (api, prepaid)

Notes on the API:
  GET /api/organizations
    Returns list of all orgs the user has access to.

  GET /api/organizations/{org_uuid}/chat_conversations?limit=N&offset=N
    Lists conversations. Default limit 50. Sorted by updated_at desc.
    Returns: [{uuid, name, updated_at, created_at, ...}]

  GET /api/organizations/{org_uuid}/chat_conversations/{conv_uuid}
    ?tree=True&rendering_mode=messages&render_all_tools=true
    Returns full conversation with messages.
    Message roles: human | assistant
    Message content: [{type: "text", text: "..."}, {type: "tool_use", ...}]

  There is no server-side search endpoint — search is done client-side by
  fetching all conversations and filtering by name/content.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path

SESSION_PATH = Path.home() / ".config" / "agentos" / "claude-session.json"

BASE_URL = "https://claude.ai"

# Headers that match what a real Brave browser sends to bypass Cloudflare
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "anthropic-client-version": "claude-ai/web@1.1.5368",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-CH-UA": '"Brave";v="1.80", "Chromium";v="144", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Brave/1.80",
}


def load_session():
    """Load session from ~/.config/agentos/claude-session.json"""
    if not SESSION_PATH.exists():
        raise FileNotFoundError(
            f"No session found at {SESSION_PATH}. "
            "Run the claude skill login utility first."
        )
    return json.loads(SESSION_PATH.read_text())


def make_request(path, session_key, method="GET", body=None):
    """
    Make a request to the claude.ai API using urllib (stdlib, no httpx needed).
    Falls back to httpx if available for better error handling.

    Why urllib and not httpx?
    - urllib is stdlib — zero dependencies
    - httpx is better (connection pooling, HTTP/2, cleaner API) but requires install
    - For a skill that runs in a subprocess, stdlib is more reliable

    If httpx is available, it's used automatically for better performance.
    """
    url = f"{BASE_URL}{path}"
    headers = dict(HEADERS)
    headers["Cookie"] = f"sessionKey={session_key}"

    try:
        import httpx
        with httpx.Client(headers=headers, follow_redirects=True) as client:
            if method == "GET":
                resp = client.get(url)
            else:
                resp = client.request(method, url, json=body)
            resp.raise_for_status()
            return resp.json()
    except ImportError:
        pass

    # Fallback: urllib
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} for {url}: {body_text}") from e


# ── API operations ────────────────────────────────────────────────────────────

def get_organizations(session_key):
    """List all organizations the user has access to."""
    return make_request("/api/organizations", session_key)


def get_conversations(session_key, org_uuid, limit=50, offset=0):
    """
    List conversations in an org, most recently updated first.
    Returns list of conversation stubs (uuid, name, updated_at, etc.)
    """
    path = f"/api/organizations/{org_uuid}/chat_conversations"
    path += f"?limit={limit}&offset={offset}"
    return make_request(path, session_key)


def get_conversation(session_key, org_uuid, conv_uuid):
    """
    Get a full conversation with all messages.
    Returns conversation dict with messages list.
    Each message has: role (human|assistant), content (list of content blocks)
    """
    path = (
        f"/api/organizations/{org_uuid}/chat_conversations/{conv_uuid}"
        "?tree=True&rendering_mode=messages&render_all_tools=true"
    )
    return make_request(path, session_key)


def import_conversations(session_key, org_uuid, limit=50, offset=0):
    """
    Fetch conversations (paginated) with all their messages.
    Returns a flat list of message rows, each containing conversation metadata.
    This is the data source for the conversation.import skill operation —
    each row maps to a message entity in the Memex, making all content FTS-indexed.

    Output row shape:
      id               str   — "{conv_uuid}_{msg_uuid}" (stable, dedup-safe)
      conversation_id  str   — conv_uuid
      conversation_name str  — conversation title
      role             str   — "human" | "assistant"
      text             str   — message text content
      created_at       str   — ISO 8601 timestamp
    """
    convs = get_conversations(session_key, org_uuid, limit=limit, offset=offset)
    rows = []
    for conv_stub in convs:
        conv_uuid = conv_stub["uuid"]
        conv_name = conv_stub.get("name") or "(untitled)"
        try:
            conv = get_conversation(session_key, org_uuid, conv_uuid)
        except Exception:
            continue
        for msg in conv.get("chat_messages", []):
            content_blocks = msg.get("content", [])
            text_parts = [
                b.get("text", "") for b in content_blocks
                if b.get("type") == "text" and b.get("text")
            ]
            text = "\n".join(text_parts).strip()
            if not text:
                continue
            msg_uuid = msg.get("uuid", "")
            rows.append({
                "id": f"{conv_uuid}_{msg_uuid}",
                "conversation_id": conv_uuid,
                "conversation_name": conv_name,
                "role": msg.get("sender", "human"),
                "text": text,
                "created_at": msg.get("created_at", conv_stub.get("created_at")),
            })
    return rows


def search_conversations(session_key, org_uuid, query, limit=50):
    """
    Search conversations by name (title).
    The claude.ai API has no server-side search — this fetches all convs and
    filters locally. For content search, use get_conversation on each result.

    Fetches up to 5 pages (250 conversations) to cover recent history.
    """
    query_lower = query.lower()
    results = []
    offset = 0
    page_size = 50

    while offset < 250:  # cap at 5 pages
        page = get_conversations(session_key, org_uuid, limit=page_size, offset=offset)
        if not page:
            break
        for conv in page:
            name = (conv.get("name") or "").lower()
            if query_lower in name:
                results.append(conv)
        if len(page) < page_size:
            break
        offset += page_size

    return results[:limit]


# ── Formatting helpers ────────────────────────────────────────────────────────

def format_conversation_list(convs, org_uuid):
    """Format conversation list for agentOS transformer consumption."""
    out = []
    for c in convs:
        out.append({
            "uuid": c.get("uuid"),
            "name": c.get("name") or "(untitled)",
            "updated_at": c.get("updated_at"),
            "created_at": c.get("created_at"),
            "org_uuid": org_uuid,
        })
    return out


def format_conversation(conv, org_uuid):
    """Format a full conversation for agentOS transformer consumption."""
    messages = conv.get("chat_messages", [])
    formatted_messages = []
    for msg in messages:
        content_blocks = msg.get("content", [])
        text_parts = [
            b.get("text", "") for b in content_blocks
            if b.get("type") == "text" and b.get("text")
        ]
        formatted_messages.append({
            "role": msg.get("sender"),  # "human" or "assistant"
            "text": "\n".join(text_parts),
            "created_at": msg.get("created_at"),
            "uuid": msg.get("uuid"),
        })

    return {
        "uuid": conv.get("uuid"),
        "name": conv.get("name") or "(untitled)",
        "org_uuid": org_uuid,
        "created_at": conv.get("created_at"),
        "updated_at": conv.get("updated_at"),
        "messages": formatted_messages,
        "message_count": len(formatted_messages),
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="claude.ai API client")
    parser.add_argument("--op", required=True,
                        choices=["organizations", "conversations", "conversation", "search", "import"],
                        help="Operation to perform")
    parser.add_argument("--org", help="Org UUID (default: use saved session org)")
    parser.add_argument("--id", help="Conversation UUID (for conversation op)")
    parser.add_argument("--query", help="Search query (for search op)")
    parser.add_argument("--limit", type=int, default=50, help="Max results")
    parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    parser.add_argument("--account", help="Account name: 'personal' (default) or 'third-party'")
    args = parser.parse_args()

    session = load_session()
    session_key = session["session_key"]

    # Resolve org UUID: --org takes precedence, then --account name lookup, then session default
    ACCOUNT_ORGS = {
        "personal": "c10a8db6-c2ed-4750-95ef-a0367a39362c",
        "third-party": "6b0831ae-5799-43af-90c2-4dba40206d35",
    }
    if args.org:
        org_uuid = args.org
    elif args.account and args.account in ACCOUNT_ORGS:
        org_uuid = ACCOUNT_ORGS[args.account]
    else:
        org_uuid = session.get("org_uuid")

    if args.op == "organizations":
        orgs = get_organizations(session_key)
        print(json.dumps(orgs))

    elif args.op == "conversations":
        if not org_uuid:
            print(json.dumps({"error": "org UUID required"}))
            return 1
        convs = get_conversations(session_key, org_uuid, limit=args.limit, offset=args.offset)
        print(json.dumps(format_conversation_list(convs, org_uuid)))

    elif args.op == "conversation":
        if not args.id:
            print(json.dumps({"error": "--id required for conversation op"}))
            return 1
        if not org_uuid:
            print(json.dumps({"error": "org UUID required"}))
            return 1
        conv = get_conversation(session_key, org_uuid, args.id)
        print(json.dumps(format_conversation(conv, org_uuid)))

    elif args.op == "search":
        if not args.query:
            print(json.dumps({"error": "--query required for search op"}))
            return 1
        if not org_uuid:
            print(json.dumps({"error": "org UUID required"}))
            return 1
        results = search_conversations(session_key, org_uuid, args.query, limit=args.limit)
        print(json.dumps(format_conversation_list(results, org_uuid)))

    elif args.op == "import":
        if not org_uuid:
            print(json.dumps({"error": "org UUID required"}))
            return 1
        rows = import_conversations(session_key, org_uuid, limit=args.limit, offset=args.offset)
        print(json.dumps(rows))

    return 0


if __name__ == "__main__":
    sys.exit(main())

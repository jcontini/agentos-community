#!/usr/bin/env python3
"""
claude-api.py — httpx-based client for the claude.ai private API

Session key is injected by agentOS cookie matchmaking via --session-key.
All API calls use httpx (NOT Playwright) — login is the only thing that
needs a browser. Once the sessionKey is extracted, httpx handles everything.

Required headers (bypass Cloudflare + match expected browser client):
  Cookie: sessionKey=sk-ant-sid02-...
  anthropic-client-version: claude-ai/web@1.1.5368
  Sec-Fetch-Site: same-origin
  Sec-Fetch-Mode: cors
  Sec-Fetch-Dest: empty

Usage:
  python3 claude-api.py --session-key SK --op organizations
  python3 claude-api.py --session-key SK --op conversations [--org ORG_UUID] [--limit 50]
  python3 claude-api.py --session-key SK --op conversation --id CONV_UUID [--org ORG_UUID]
  python3 claude-api.py --session-key SK --op search --query TEXT [--org ORG_UUID]
  python3 claude-api.py --session-key SK --op import [--org ORG_UUID] [--limit 5] [--offset 0]

Org discovery:
  Run --op organizations to list all orgs the user has access to.
  The org with "chat" in its capabilities is the one with web chat history.
  If --org is omitted, auto-discovers the chat org via API.
"""

import argparse
import json
import sys
import httpx

BASE_URL = "https://claude.ai"

# Headers that match what a real browser sends to bypass Cloudflare
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


def make_request(path, session_key, method="GET", body=None):
    """Make a request to the claude.ai API using httpx.

    httpx is required — urllib gets Cloudflare 403'd on claude.ai.
    """
    url = f"{BASE_URL}{path}"
    headers = dict(HEADERS)
    headers["Cookie"] = f"sessionKey={session_key}"

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        if method == "GET":
            resp = client.get(url)
        else:
            resp = client.request(method, url, json=body)
        resp.raise_for_status()
        return resp.json()


# -- API operations ------------------------------------------------------------

def get_organizations(session_key):
    """List all organizations the user has access to."""
    return make_request("/api/organizations", session_key)


def resolve_org_uuid(session_key, org_uuid=None):
    """Resolve the org UUID to use.

    Priority: explicit --org > auto-discover chat org from API.
    """
    if org_uuid:
        return org_uuid

    # Auto-discover: find the org with "chat" capability
    orgs = get_organizations(session_key)
    for org in orgs:
        if "chat" in org.get("capabilities", []):
            return org["uuid"]

    # Fallback to first org
    if orgs:
        return orgs[0]["uuid"]

    raise RuntimeError("No organizations found for this account")


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


# -- Formatting helpers --------------------------------------------------------

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
    """Format a full conversation for agentOS transformer consumption.

    Messages are serialized into a readable 'content' field so the
    conversation transformer can map it — otherwise the messages array
    gets dropped during transformation.
    """
    messages = conv.get("chat_messages", [])
    formatted_messages = []
    content_lines = []
    for msg in messages:
        content_blocks = msg.get("content", [])
        text_parts = [
            b.get("text", "") for b in content_blocks
            if b.get("type") == "text" and b.get("text")
        ]
        text = "\n".join(text_parts)
        role = msg.get("sender", "human")
        formatted_messages.append({
            "role": role,
            "text": text,
            "created_at": msg.get("created_at"),
            "uuid": msg.get("uuid"),
        })
        if text.strip():
            label = "Human" if role == "human" else "Assistant"
            content_lines.append(f"**{label}:**\n{text}")

    return {
        "uuid": conv.get("uuid"),
        "name": conv.get("name") or "(untitled)",
        "org_uuid": org_uuid,
        "created_at": conv.get("created_at"),
        "updated_at": conv.get("updated_at"),
        "content": "\n\n---\n\n".join(content_lines),
        "messages": formatted_messages,
        "message_count": len(formatted_messages),
    }


# -- Operation entrypoints — called by the python: executor with kwargs --------

def op_list_conversations(session_key: str, account: str = None, limit: int = 50, offset: int = 0) -> list:
    org = resolve_org_uuid(session_key, account or None)
    convs = get_conversations(session_key, org, limit=int(limit or 50), offset=int(offset or 0))
    return format_conversation_list(convs, org)


def op_get_conversation(session_key: str, id: str, account: str = None) -> dict:
    org = resolve_org_uuid(session_key, account or None)
    conv = get_conversation(session_key, org, id)
    return format_conversation(conv, org)


def op_search_conversations(session_key: str, query: str, account: str = None, limit: int = 20) -> list:
    org = resolve_org_uuid(session_key, account or None)
    convs = search_conversations(session_key, org, query, limit=int(limit or 20))
    return format_conversation_list(convs, org)


def op_import_conversation(session_key: str, account: str = None, limit: int = 5, offset: int = 0) -> list:
    org = resolve_org_uuid(session_key, account or None)
    return import_conversations(session_key, org, limit=int(limit or 5), offset=int(offset or 0))


def op_list_orgs(session_key: str) -> list:
    return get_organizations(session_key)


# -- CLI entry point -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="claude.ai API client")
    parser.add_argument("--op", required=True,
                        choices=["organizations", "conversations", "conversation", "search", "import"],
                        help="Operation to perform")
    parser.add_argument("--org", help="Org UUID (default: auto-resolve from session or API)")
    parser.add_argument("--id", help="Conversation UUID (for conversation op)")
    parser.add_argument("--query", help="Search query (for search op)")
    parser.add_argument("--limit", type=int, default=50, help="Max results")
    parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    parser.add_argument("--session-key", required=True,
                        help="sessionKey cookie value (injected by agentOS cookie matchmaking)")
    args = parser.parse_args()

    session_key = args.session_key

    if args.op == "organizations":
        orgs = get_organizations(session_key)
        print(json.dumps(orgs))
        return 0

    # Resolve org UUID for all other operations
    org_uuid = resolve_org_uuid(session_key, args.org if args.org else None)

    if args.op == "conversations":
        convs = get_conversations(session_key, org_uuid, limit=args.limit, offset=args.offset)
        print(json.dumps(format_conversation_list(convs, org_uuid)))

    elif args.op == "conversation":
        if not args.id:
            print(json.dumps({"error": "--id required for conversation op"}))
            return 1
        conv = get_conversation(session_key, org_uuid, args.id)
        print(json.dumps(format_conversation(conv, org_uuid)))

    elif args.op == "search":
        if not args.query:
            print(json.dumps({"error": "--query required for search op"}))
            return 1
        results = search_conversations(session_key, org_uuid, args.query, limit=args.limit)
        print(json.dumps(format_conversation_list(results, org_uuid)))

    elif args.op == "import":
        rows = import_conversations(session_key, org_uuid, limit=args.limit, offset=args.offset)
        print(json.dumps(rows))

    return 0


if __name__ == "__main__":
    sys.exit(main())

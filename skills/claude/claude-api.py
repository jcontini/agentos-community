#!/usr/bin/env python3
"""
claude-api.py — claude.ai private API client

Session cookies are injected by agentOS cookie matchmaking.
All API calls use http.client() (NOT Playwright) — login is the only thing that
needs a browser. Once the sessionKey cookie is extracted, http handles everything.

Required headers (bypass Cloudflare + match expected browser client):
  Cookie: sessionKey=sk-ant-sid02-...
  anthropic-client-version: claude-ai/web@1.1.5368
  Sec-Fetch-Site: same-origin
  Sec-Fetch-Mode: cors
  Sec-Fetch-Dest: empty
"""

import json
import re
import sys

from agentos import http, get_cookies, parse_cookie

BASE_URL = "https://claude.ai"

CLAUDE_HEADERS = {
    "Content-Type": "application/json",
    "anthropic-client-version": "claude-ai/web@1.1.5368",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-CH-UA": '"Chromium";v="146", "Brave";v="146", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
}


def _client(cookie_header: str):
    """HTTP session configured for claude.ai (Cloudflare bypass, http2=False).

    Uses profile="json" (not "api") because CLAUDE_HEADERS already provides
    all Sec-* headers. Using "api" would cause duplicate Sec-CH-UA values
    from both sources — a clear WAF detection signal.
    """
    return http.client(cookies=cookie_header, profile="json", headers=CLAUDE_HEADERS, http2=False)


# -- API operations ------------------------------------------------------------


def _get_organizations(client):
    resp = client.get(f"{BASE_URL}/api/organizations")
    return resp["json"]


def _resolve_org_uuid(client, org_uuid=None, cookie_header=None):
    """Resolve the org UUID for chat operations.

    Priority: explicit org_uuid > lastActiveOrg cookie (probed) > /api/organizations.
    The lastActiveOrg cookie can be stale, so we probe with ?limit=1 before trusting it.
    """
    if org_uuid:
        return org_uuid
    # Try lastActiveOrg cookie — probe with a lightweight ?limit=1 before trusting.
    if cookie_header:
        last_active = parse_cookie(cookie_header, "lastActiveOrg")
        if last_active:
            probe = client.get(
                f"{BASE_URL}/api/organizations/{last_active}"
                f"/chat_conversations?limit=1"
            )
            if probe["status"] == 200:
                return last_active
    # Slow path: fetch all orgs, find chat-capable one.
    orgs = _get_organizations(client)
    for org in orgs:
        if "chat" in org.get("capabilities", []):
            return org["uuid"]
    if orgs:
        return orgs[0]["uuid"]
    raise RuntimeError("No organizations found for this account")


def _get_conversations(client, org_uuid, limit=50, offset=0):
    path = f"/api/organizations/{org_uuid}/chat_conversations?limit={limit}&offset={offset}"
    resp = client.get(f"{BASE_URL}{path}")
    return resp["json"]


def _get_conversation(client, org_uuid, conv_uuid):
    path = (
        f"/api/organizations/{org_uuid}/chat_conversations/{conv_uuid}"
        "?tree=True&rendering_mode=messages&render_all_tools=true"
    )
    resp = client.get(f"{BASE_URL}{path}")
    return resp["json"]


# -- Formatting helpers --------------------------------------------------------

def _format_conversation_list(convs, org_uuid):
    return [
        {
            "uuid": c.get("uuid"),
            "name": c.get("name") or "(untitled)",
            "updated_at": c.get("updated_at"),
            "created_at": c.get("created_at"),
            "org_uuid": org_uuid,
        }
        for c in convs
    ]


def _format_conversation(conv, org_uuid):
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


# -- Operation entrypoints — called by the python: executor with params: true --

def op_list_conversations(params: dict | None = None) -> list:
    params = params or {}
    cookie_header = get_cookies(params)
    limit = int(params.get("limit") or 50)
    offset = int(params.get("offset") or 0)
    org_uuid = params.get("org")
    with _client(cookie_header) as client:
        org = _resolve_org_uuid(client, org_uuid, cookie_header)
        convs = _get_conversations(client, org, limit=limit, offset=offset)
    return _format_conversation_list(convs, org)


def op_get_conversation(params: dict | None = None) -> dict:
    params = params or {}
    cookie_header = get_cookies(params)
    account = params.get("account")
    conv_id = params.get("id")
    url = params.get("url", "")
    if url:
        m = re.search(r"chat/([0-9a-fA-F-]{36})", url)
        if m:
            conv_id = m.group(1)
    if not conv_id:
        raise ValueError("id or url is required for get_conversation")
    with _client(cookie_header) as client:
        org = _resolve_org_uuid(client, account, cookie_header)
        conv = _get_conversation(client, org, conv_id)
    return _format_conversation(conv, org)


def op_search_conversations(params: dict | None = None) -> list:
    params = params or {}
    cookie_header = get_cookies(params)
    query = params.get("query", "")
    account = params.get("account")
    limit = int(params.get("limit") or 20)

    query_lower = query.lower()
    results = []
    offset = 0
    page_size = 50

    with _client(cookie_header) as client:
        org = _resolve_org_uuid(client, account, cookie_header)
        while offset < 250:
            page = _get_conversations(client, org, limit=page_size, offset=offset)
            if not page:
                break
            for conv in page:
                name = (conv.get("name") or "").lower()
                if query_lower in name:
                    results.append(conv)
            if len(page) < page_size:
                break
            offset += page_size

    return _format_conversation_list(results[:limit], org)


def op_import_conversation(params: dict | None = None) -> list:
    params = params or {}
    cookie_header = get_cookies(params)
    account = params.get("account")
    limit = int(params.get("limit") or 5)
    offset = int(params.get("offset") or 0)

    rows = []
    with _client(cookie_header) as client:
        org = _resolve_org_uuid(client, account, cookie_header)
        convs = _get_conversations(client, org, limit=limit, offset=offset)
        for conv_stub in convs:
            conv_uuid = conv_stub["uuid"]
            conv_name = conv_stub.get("name") or "(untitled)"
            try:
                conv = _get_conversation(client, org, conv_uuid)
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


def op_list_orgs(params: dict | None = None) -> list:
    params = params or {}
    cookie_header = get_cookies(params)
    with _client(cookie_header) as client:
        return _get_organizations(client)


# -- Session check — called by account.check with params: true -----------------

def check_session(params: dict | None = None) -> dict:
    """Verify Claude.ai session and identify the logged-in account.

    Validates operational access by resolving the chat org (which probes
    lastActiveOrg cookie if available), then fetches identity from /api/organizations.
    """
    params = params or {}
    cookie_header = get_cookies(params)
    if not cookie_header:
        return {"authenticated": False, "error": "no cookies"}

    try:
        with _client(cookie_header) as client:
            # Validate session: resolve org (probes lastActiveOrg, falls back to /api/organizations).
            _resolve_org_uuid(client, cookie_header=cookie_header)
            # Session is valid — resolve identity from orgs list.
            orgs = _get_organizations(client)
            return _identify_from_orgs(orgs)
    except Exception:
        return {"authenticated": False}


def _identify_from_orgs(orgs: list) -> dict:
    """Extract identity from the org list, preferring chat-capable orgs."""
    for org in orgs:
        if "chat" in org.get("capabilities", []):
            name = org.get("name", "")
            email = ""
            m = re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", name)
            if m:
                email = m.group(0)
            return {
                "authenticated": True,
                "domain": "claude.ai",
                "identifier": email or name,
                "display": email or name,
            }
    if orgs:
        name = orgs[0].get("name", "")
        return {
            "authenticated": True,
            "domain": "claude.ai",
            "identifier": name,
            "display": name,
        }
    return {"authenticated": False}


# -- CLI entry point -----------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="claude.ai API client")
    parser.add_argument("--op", required=True,
                        choices=["organizations", "conversations", "conversation", "search", "import"])
    parser.add_argument("--org", help="Org UUID")
    parser.add_argument("--id", help="Conversation UUID")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--cookies", required=True, help="Raw cookie header")
    args = parser.parse_args()

    mock_params = {
        "auth": {"cookies": args.cookies},
        "params": {
            "account": args.org,
            "id": args.id,
            "query": args.query,
            "limit": args.limit,
            "offset": args.offset,
        },
    }

    if args.op == "organizations":
        result = op_list_orgs(mock_params)
    elif args.op == "conversations":
        result = op_list_conversations(mock_params)
    elif args.op == "conversation":
        result = op_get_conversation(mock_params)
    elif args.op == "search":
        result = op_search_conversations(mock_params)
    elif args.op == "import":
        result = op_import_conversation(mock_params)
    else:
        result = {"error": f"unknown op: {args.op}"}

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

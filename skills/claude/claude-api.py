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

import base64
import json
import re
import sys

from agentos import http, get_cookies, parse_cookie

BASE_URL = "https://claude.ai"

# Claude.ai-specific headers — Cloudflare checks Sec-* and client hints.
# Uses Brave's UA identity (v="146") since that's the browser with the cookies.
# http2=False required — claude.ai Cloudflare config blocks HTTP/2 clients.
_CLAUDE_H = http.headers(waf="cf", accept="json", extra={
    "Content-Type": "application/json",
    "anthropic-client-version": "claude-ai/web@1.1.5368",
    "Sec-CH-UA": '"Chromium";v="146", "Brave";v="146", "Not-A.Brand";v="99"',
})
_CLAUDE_H["http2"] = False  # override waf="cf" default (True)


def _client(cookie_header: str):
    """HTTP session configured for claude.ai (Cloudflare bypass, http2=False)."""
    return http.client(cookies=cookie_header, **_CLAUDE_H)


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


# -- Operation entrypoints — called by the python: executor with auto-dispatch --

def op_list_conversations(*, org=None, limit=50, offset=0, **params) -> list:
    cookie_header = get_cookies(params)
    limit = int(limit)
    offset = int(offset)
    with _client(cookie_header) as client:
        resolved_org = _resolve_org_uuid(client, org, cookie_header)
        convs = _get_conversations(client, resolved_org, limit=limit, offset=offset)
    return _format_conversation_list(convs, resolved_org)


def op_get_conversation(*, id=None, url=None, org=None, **params) -> dict:
    cookie_header = get_cookies(params)
    conv_id = id
    if url:
        m = re.search(r"chat/([0-9a-fA-F-]{36})", url)
        if m:
            conv_id = m.group(1)
    if not conv_id:
        raise ValueError("id or url is required for get_conversation")
    with _client(cookie_header) as client:
        resolved_org = _resolve_org_uuid(client, org, cookie_header)
        conv = _get_conversation(client, resolved_org, conv_id)
    return _format_conversation(conv, resolved_org)


def op_search_conversations(*, query="", org=None, limit=20, **params) -> list:
    cookie_header = get_cookies(params)
    limit = int(limit)

    query_lower = query.lower()
    results = []
    offset = 0
    page_size = 50

    with _client(cookie_header) as client:
        resolved_org = _resolve_org_uuid(client, org, cookie_header)
        while offset < 250:
            page = _get_conversations(client, resolved_org, limit=page_size, offset=offset)
            if not page:
                break
            for conv in page:
                name = (conv.get("name") or "").lower()
                if query_lower in name:
                    results.append(conv)
            if len(page) < page_size:
                break
            offset += page_size

    return _format_conversation_list(results[:limit], resolved_org)


def op_import_conversation(*, org=None, limit=5, offset=0, **params) -> list:
    cookie_header = get_cookies(params)
    limit = int(limit)
    offset = int(offset)

    rows = []
    with _client(cookie_header) as client:
        resolved_org = _resolve_org_uuid(client, org, cookie_header)
        convs = _get_conversations(client, resolved_org, limit=limit, offset=offset)
        for conv_stub in convs:
            conv_uuid = conv_stub["uuid"]
            conv_name = conv_stub.get("name") or "(untitled)"
            try:
                conv = _get_conversation(client, resolved_org, conv_uuid)
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


def op_list_orgs(**params) -> list:
    cookie_header = get_cookies(params)
    with _client(cookie_header) as client:
        return _get_organizations(client)


# -- Session check — called by account.check with auto-dispatch ----------------

def check_session(**params) -> dict:
    """Verify Claude.ai session and identify the logged-in account.

    Validates operational access by resolving the chat org (which probes
    lastActiveOrg cookie if available), then fetches identity from /api/organizations.
    """
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
    }

    if args.op == "organizations":
        result = op_list_orgs(**mock_params)
    elif args.op == "conversations":
        result = op_list_conversations(org=args.org, limit=args.limit, offset=args.offset, **mock_params)
    elif args.op == "conversation":
        result = op_get_conversation(id=args.id, org=args.org, **mock_params)
    elif args.op == "search":
        result = op_search_conversations(query=args.query, org=args.org, limit=args.limit, **mock_params)
    elif args.op == "import":
        result = op_import_conversation(org=args.org, limit=args.limit, offset=args.offset, **mock_params)
    else:
        result = {"error": f"unknown op: {args.op}"}

    print(json.dumps(result, indent=2))
    return 0



# -- Magic link extraction — pure string parsing, no browser needed ------------

def _extract_magic_link_from_raw_email(raw_b64: str) -> str | None:
    """Extract the claude.ai magic link from a raw RFC 2822 email (base64url-encoded)."""
    raw_bytes = base64.urlsafe_b64decode(raw_b64 + "==")
    raw_str = raw_bytes.decode("utf-8", errors="replace")

    cleaned = re.sub(r'=\r?\n', '', raw_str)
    qp_pattern = r'href=3D"(https://claude\.ai/magic-link#[^"\s]+)'
    match = re.search(qp_pattern, cleaned, re.IGNORECASE)
    if match:
        url = match.group(1)
        return url.replace('=3D', '=').replace('=3d', '=')

    import quopri
    for part in raw_str.split('--'):
        if 'content-transfer-encoding: quoted-printable' in part.lower():
            try:
                body = quopri.decodestring(part.encode('utf-8', errors='replace')).decode('utf-8', errors='replace')
                m = re.search(r'href="(https://claude\.ai/magic-link#[^"]+)"', body, re.IGNORECASE)
                if m:
                    return m.group(1)
            except Exception:
                pass
    return None


def op_extract_magic_link(raw_email: str) -> dict:
    link = _extract_magic_link_from_raw_email(raw_email)
    if link:
        return {"magic_link": link}
    return {"error": "No magic link found in raw email content"}


if __name__ == "__main__":
    sys.exit(main())

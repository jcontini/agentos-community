#!/usr/bin/env python3
"""
claude-login.py — Browser helpers for claude.ai session extraction

This script provides thin CDP (Chrome DevTools Protocol) helpers for:
  1. Navigating to a magic link URL to complete login
  2. Extracting the sessionKey HttpOnly cookie from a logged-in browser
  3. Extracting a magic link URL from raw email content

No session file persistence — agentOS cookie matchmaking handles caching.
The extracted sessionKey is returned as JSON for the provider to cache in-memory.

Usage:
  python3 claude-login.py --magic-link URL [--port 9222]    # Navigate + extract
  python3 claude-login.py --extract-session [--port 9222]   # Just extract cookies
  python3 claude-login.py --extract-link-from-raw BASE64    # Parse magic link from email

Notes:
  - The sessionKey cookie is HttpOnly — it CANNOT be read via JS document.cookie.
    It must be extracted via CDP Network.getAllCookies (WebSocket).
  - After login, use claude-api.py (httpx) for all subsequent API calls.
  - Requires a browser running with CDP enabled on the specified port.
"""

import argparse
import base64
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


# -- CDP helpers ---------------------------------------------------------------

def cdp_get_targets(port=9222):
    """Return list of CDP targets from the running browser."""
    resp = httpx.get(f"http://localhost:{port}/json")
    resp.raise_for_status()
    return resp.json()


def cdp_find_tab(targets, url_fragment="claude.ai"):
    """Find the tab matching url_fragment, or fall back to first tab."""
    for t in targets:
        if url_fragment in t.get("url", ""):
            return t
    return targets[0] if targets else None


def _find_ws_module():
    """Find the Node.js ws module. Checks common locations."""
    candidates = [
        # @playwright/mcp bundles ws
        Path.home() / ".nvm" / "versions" / "node",
        Path("/usr/local/lib/node_modules"),
        Path("/opt/homebrew/lib/node_modules"),
    ]

    # Search nvm versions
    nvm_dir = candidates[0]
    if nvm_dir.exists():
        for version_dir in sorted(nvm_dir.iterdir(), reverse=True):
            ws_path = version_dir / "lib" / "node_modules" / "@playwright" / "mcp" / "node_modules" / "ws"
            if ws_path.exists():
                return str(ws_path)
            # Also check global ws install
            ws_path = version_dir / "lib" / "node_modules" / "ws"
            if ws_path.exists():
                return str(ws_path)

    # Check global locations
    for base in candidates[1:]:
        for ws_path in [base / "@playwright" / "mcp" / "node_modules" / "ws", base / "ws"]:
            if ws_path.exists():
                return str(ws_path)

    # Last resort: let Node resolve it
    return "ws"


_WS_NODE = _find_ws_module()


def _run_node(script, timeout=15):
    """Run a Node.js script and return stdout. Raises on failure."""
    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"Node.js failed: {result.stderr.strip()}")
    return result.stdout.strip()


def cdp_get_cookies(ws_url, domain_fragments=("claude", "anthropic")):
    """Extract cookies from the browser via CDP Network.getAllCookies.

    Uses Node.js ws module since Python stdlib has no WebSocket support.
    """
    script = f"""
const WebSocket = require('{_WS_NODE}');
const ws = new WebSocket('{ws_url}');
ws.on('open', () => ws.send(JSON.stringify({{id: 1, method: 'Network.getAllCookies'}})));
ws.on('message', (data) => {{
  const resp = JSON.parse(data);
  const cookies = (resp.result?.cookies || []).filter(c =>
    {json.dumps(list(domain_fragments))}.some(f => c.domain.includes(f))
  );
  console.log(JSON.stringify(cookies));
  ws.close();
}});
"""
    return json.loads(_run_node(script, timeout=10))


def cdp_navigate(ws_url, url):
    """Navigate the browser tab to a URL via CDP."""
    script = f"""
const WebSocket = require('{_WS_NODE}');
const ws = new WebSocket('{ws_url}');
ws.on('open', () => ws.send(JSON.stringify({{
  id: 1, method: 'Page.navigate', params: {{url: '{url}'}}
}})));
ws.on('message', () => {{ ws.close(); }});
"""
    _run_node(script, timeout=10)


def cdp_evaluate(ws_url, expression):
    """Run JS in the browser tab and return the result."""
    script = f"""
const WebSocket = require('{_WS_NODE}');
const ws = new WebSocket('{ws_url}');
ws.on('open', () => ws.send(JSON.stringify({{
  id: 1,
  method: 'Runtime.evaluate',
  params: {{expression: {json.dumps(expression)}, awaitPromise: true, returnByValue: true}}
}})));
ws.on('message', (data) => {{
  const resp = JSON.parse(data);
  console.log(JSON.stringify(resp.result?.result?.value ?? null));
  ws.close();
}});
"""
    return json.loads(_run_node(script, timeout=15))


def cdp_get_current_url(ws_url):
    """Get the current URL of the browser tab."""
    return cdp_evaluate(ws_url, "window.location.href")


# -- Magic link extraction from raw email -------------------------------------

def extract_magic_link_from_raw_email(raw_b64):
    """Extract the claude.ai magic link from a raw RFC 2822 email (base64url-encoded).

    The magic link appears as:
      href=3D"https://claude.ai/magic-link#TOKEN:BASE64EMAIL"
    (quoted-printable encoded, =3D is =, soft line breaks with =\\n)
    """
    # Normalize base64url to base64
    raw_bytes = base64.urlsafe_b64decode(raw_b64 + "==")
    raw_str = raw_bytes.decode("utf-8", errors="replace")

    # Remove QP soft line breaks, then search for the magic link
    cleaned = re.sub(r'=\r?\n', '', raw_str)
    qp_pattern = r'href=3D"(https://claude\.ai/magic-link#[^"\\s]+)'
    match = re.search(qp_pattern, cleaned, re.IGNORECASE)
    if match:
        url = match.group(1)
        url = url.replace('=3D', '=').replace('=3d', '=')
        return url

    # Fallback: try decoding QP body sections
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


# -- Browser login helpers -----------------------------------------------------

def check_logged_in(ws_url):
    """Check if already logged in by calling /api/organizations in the browser.

    Returns (is_logged_in, org_uuid, org_name).
    """
    result = cdp_evaluate(
        ws_url,
        "fetch('/api/organizations').then(r => r.json()).then(d => JSON.stringify(d))"
    )
    if not result:
        return False, None, None
    try:
        orgs = json.loads(result)
        if isinstance(orgs, list) and orgs:
            chat_org = next(
                (o for o in orgs if "chat" in o.get("capabilities", [])), orgs[0]
            )
            return True, chat_org["uuid"], chat_org["name"]
    except Exception:
        pass
    return False, None, None


# -- Operation entrypoint — called by the python: executor with kwargs ---------

def op_extract_magic_link(raw_email: str) -> dict:
    return extract_magic_link_from_raw_email(raw_email)


# -- Entry point ---------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Claude.ai browser login helpers")
    parser.add_argument("--magic-link", help="Navigate to magic link URL and extract session")
    parser.add_argument("--extract-session", action="store_true",
                        help="Extract cookies from current browser (already logged in)")
    parser.add_argument("--extract-link-from-raw", metavar="BASE64",
                        help="Extract magic link URL from base64url-encoded raw email")
    parser.add_argument("--port", type=int, default=9222, help="CDP port (default: 9222)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Mode: extract magic link from raw email (no browser needed)
    if args.extract_link_from_raw:
        link = extract_magic_link_from_raw_email(args.extract_link_from_raw)
        if link:
            print(json.dumps({"magic_link": link}))
            return 0
        else:
            print(json.dumps({"error": "No magic link found in raw email content"}))
            return 1

    # All other modes need a browser
    try:
        targets = cdp_get_targets(args.port)
    except Exception as e:
        print(json.dumps({"error": f"Cannot connect to CDP on port {args.port}: {e}"}))
        return 1

    tab = cdp_find_tab(targets, "claude.ai")
    if not tab:
        tab = targets[0] if targets else None
    if not tab:
        print(json.dumps({"error": "No browser tabs found on CDP"}))
        return 1

    ws_url = tab["webSocketDebuggerUrl"]

    if args.verbose:
        print(f"[login] Using tab: {tab['url']}", file=sys.stderr)

    if args.magic_link:
        # Navigate to magic link, wait for redirect, extract session
        if args.verbose:
            print(f"[login] Navigating to magic link...", file=sys.stderr)
        cdp_navigate(ws_url, args.magic_link)

        # Wait for redirect to /new (login complete)
        for i in range(10):
            time.sleep(1)
            current = cdp_get_current_url(ws_url)
            if current and "/new" in current:
                if args.verbose:
                    print("[login] Redirected to /new — login successful!", file=sys.stderr)
                break
            if args.verbose and i > 0 and i % 3 == 0:
                print(f"[login] Waiting for redirect... current: {current}", file=sys.stderr)

    # Check if logged in (works for both --magic-link and --extract-session)
    is_logged_in, org_uuid, org_name = check_logged_in(ws_url)
    if not is_logged_in:
        print(json.dumps({"error": "Not logged in — browser session has no valid auth"}))
        return 1

    # Extract cookies
    cookies = cdp_get_cookies(ws_url)
    session_key = next((c["value"] for c in cookies if c["name"] == "sessionKey"), None)

    if not session_key:
        print(json.dumps({"error": "sessionKey cookie not found"}))
        return 1

    if args.verbose:
        print(f"[login] Got sessionKey: {session_key[:30]}...", file=sys.stderr)

    # Output extracted session info (no file persistence — cookie matchmaking handles caching)
    result = {
        "session_key": session_key,
        "org_uuid": org_uuid,
        "org_name": org_name,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

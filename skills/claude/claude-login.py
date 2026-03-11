#!/usr/bin/env python3
"""
claude-login.py — Full automated login flow for claude.ai

Flow:
  1. Launch Playwright CDP browser (port 9222, must already be running)
  2. Check if already logged in by hitting /api/organizations
  3. If not → navigate to /login, fill email, submit
  4. Poll Gmail (joe@contini.co catch-all) for the magic link email
  5. Navigate to the magic link
  6. Wait for redirect to /new (confirms login)
  7. Extract sessionKey + lastActiveOrg via CDP Network.getAllCookies
  8. Save to ~/.config/agentos/claude-session.json
  9. Print JSON to stdout

Usage:
  python3 claude-login.py [--email EMAIL] [--gmail-account GMAIL] [--force]

Notes:
  - joe@contini.co is a catch-all for *@contini.co — Anthropic emails sent to
    anthropic@contini.co arrive in joe@contini.co inbox.
  - Gmail search: use `from:noreply after:TODAY` with account joe@contini.co
  - The sessionKey cookie is HttpOnly — it CANNOT be read via JS document.cookie.
    It must be extracted via CDP Network.getAllCookies (WebSocket to port 9222).
  - After login, use claude-api.py (httpx) for all subsequent API calls.
    DO NOT route API calls through Playwright evaluate — that's only for auth.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import email
import quopri
from datetime import datetime, timezone
from pathlib import Path


# ── CDP helpers (no external deps) ───────────────────────────────────────────

def cdp_get_targets(port=9222):
    """Return list of CDP targets from the running browser."""
    resp = urllib.request.urlopen(f"http://localhost:{port}/json")
    return json.loads(resp.read())


def cdp_find_tab(targets, url_fragment="claude.ai"):
    """Find the tab matching url_fragment, or fall back to first tab."""
    for t in targets:
        if url_fragment in t.get("url", ""):
            return t
    return targets[0] if targets else None


# We use Node.js for the WebSocket call since Python stdlib has no WS support
# and we don't want to require external packages.
_WS_NODE = "/Users/joe/.nvm/versions/node/v20.15.0/lib/node_modules/@playwright/mcp/node_modules/ws"

def cdp_get_cookies(ws_url, domain_fragments=("claude", "anthropic")):
    """
    Extract all cookies from the browser via CDP Network.getAllCookies.
    Returns list of cookie dicts. Filters to claude/anthropic domains by default.
    Uses Node.js ws module (comes with @playwright/mcp).
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
    import subprocess
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(f"CDP cookie extraction failed: {result.stderr}")
    return json.loads(result.stdout.strip())


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
    import subprocess
    subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)


def cdp_evaluate(ws_url, expression):
    """
    Run JS in the browser tab and return the result.
    Returns the raw value string.
    """
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
    import subprocess
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(f"CDP evaluate failed: {result.stderr}")
    return json.loads(result.stdout.strip())


# ── Gmail helpers (via agentOS Gmail skill REST API) ─────────────────────────

def gmail_search_recent_anthropic(account="joe@contini.co", max_age_minutes=10):
    """
    Search Gmail for recent Anthropic magic link emails.

    Key facts:
    - joe@contini.co is a catch-all for *@contini.co
    - Anthropic sends magic links from: noreply-*@mail.anthropic.com or support@mail.anthropic.com
    - Subject: "Secure link to log in to Claude.ai"
    - The magic link is in the HTML body as href="https://claude.ai/magic-link#..."
    - Email arrives within ~30 seconds typically
    - Raw email is base64url-encoded; body is quoted-printable HTML
    - Use get_raw to get the full RFC 2822 message and extract the href

    Returns the magic link URL string, or None if not found.
    """
    # This function is called from within the agentOS skill via command executor.
    # For standalone use, we call the agentOS HTTP API directly.
    # In practice, the skill readme documents this flow for the agent.
    raise NotImplementedError(
        "Use the agentOS gmail skill: "
        'email.search(query="from:anthropic after:TODAY", account="joe@contini.co") '
        "then email.get(id=...) with get_raw to extract the magic link href"
    )


def extract_magic_link_from_raw_email(raw_b64):
    """
    Extract the claude.ai magic link from a raw RFC 2822 email (base64url-encoded).

    The magic link appears as:
      href=3D"https://claude.ai/magic-link#TOKEN:BASE64EMAIL"
    (quoted-printable encoded, =3D is =, soft line breaks with =\n)

    Strategy:
    1. base64url-decode the raw email
    2. Find the quoted-printable HTML body part
    3. Decode quoted-printable
    4. Regex for https://claude.ai/magic-link#...
    """
    # Normalize base64url to base64
    raw_bytes = base64.urlsafe_b64decode(raw_b64 + "==")
    raw_str = raw_bytes.decode("utf-8", errors="replace")

    # Find the magic link in quoted-printable encoded form
    # Pattern: href=3D"https://claude.ai/magic-link#...  (may have soft line breaks =\n)
    # First: decode QP for the whole body section
    # Look for the href directly with QP soft-line-break handling
    # The href value ends at the closing " which is also QP-encoded as a regular char
    qp_pattern = r'href=3D"(https://claude\.ai/magic-link#[^"\\s]+)'
    # Handle soft line breaks: =\r\n or =\n before continuing
    # Remove soft line breaks first
    cleaned = re.sub(r'=\r?\n', '', raw_str)
    match = re.search(qp_pattern, cleaned, re.IGNORECASE)
    if match:
        # Decode any remaining QP entities in the URL (=3D -> =, etc.)
        url = match.group(1)
        url = url.replace('=3D', '=').replace('=3d', '=')
        return url

    # Fallback: try decoding QP body sections
    for part in raw_str.split('--'):
        if 'Content-Transfer-Encoding: quoted-printable' in part or \
           'content-transfer-encoding: quoted-printable' in part.lower():
            try:
                body = quopri.decodestring(part.encode('utf-8', errors='replace')).decode('utf-8', errors='replace')
                m = re.search(r'href="(https://claude\.ai/magic-link#[^"]+)"', body, re.IGNORECASE)
                if m:
                    return m.group(1)
            except Exception:
                pass

    return None


# ── Session persistence ───────────────────────────────────────────────────────

SESSION_PATH = Path.home() / ".config" / "agentos" / "claude-session.json"


def save_session(session_key, org_uuid, org_name, account_email):
    """Save session to ~/.config/agentos/claude-session.json"""
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "session_key": session_key,
        "org_uuid": org_uuid,
        "org_name": org_name,
        "account_email": account_email,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    SESSION_PATH.write_text(json.dumps(data, indent=2))
    return data


def load_session():
    """Load saved session. Returns None if not found or expired."""
    if not SESSION_PATH.exists():
        return None
    try:
        data = json.loads(SESSION_PATH.read_text())
        # Sessions last ~30 days; warn if older than 25 days
        saved = datetime.fromisoformat(data["saved_at"])
        age_days = (datetime.now(timezone.utc) - saved).days
        if age_days > 25:
            data["_warning"] = f"Session is {age_days} days old — may need refresh"
        return data
    except Exception:
        return None


# ── Main login flow ───────────────────────────────────────────────────────────

def check_logged_in(ws_url):
    """
    Returns (is_logged_in, org_uuid, org_name) by calling /api/organizations
    from within the browser context.
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
            # Find chat-capable org (personal account)
            chat_org = next(
                (o for o in orgs if "chat" in o.get("capabilities", [])), orgs[0]
            )
            return True, chat_org["uuid"], chat_org["name"]
    except Exception:
        pass
    return False, None, None


def do_login_flow(ws_url, email_addr, verbose=False):
    """
    Perform the full magic-link login flow.
    Returns sessionKey string on success, raises on failure.

    Steps:
    1. Navigate to /login
    2. Fill email input (selector: input[type=email])
    3. Click submit (selector: button[type=submit])
    4. Wait for "Secure link" email in Gmail (joe@contini.co catch-all)
    5. Extract magic link from raw email
    6. Navigate to magic link
    7. Wait for redirect to /new
    8. Extract sessionKey via CDP
    """
    if verbose:
        print(f"[login] Navigating to https://claude.ai/login", file=sys.stderr)

    # Step 1: Navigate to login
    cdp_navigate(ws_url, "https://claude.ai/login")
    time.sleep(2)

    # Step 2: Fill email
    cdp_evaluate(ws_url, f"""
      (function() {{
        const el = document.querySelector('input[type=email]');
        if (!el) throw new Error('email input not found');
        el.value = '';
        el.focus();
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype, 'value').set;
        nativeInputValueSetter.call(el, '{email_addr}');
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return 'filled';
      }})()
    """)
    time.sleep(0.5)

    # Step 3: Click submit
    cdp_evaluate(ws_url, """
      (function() {
        const btn = document.querySelector('button[type=submit]');
        if (!btn) throw new Error('submit button not found');
        btn.click();
        return 'clicked';
      })()
    """)

    if verbose:
        print("[login] Submitted email. Waiting for magic link email...", file=sys.stderr)

    # Step 4: Poll Gmail for magic link
    # NOTE: This step requires the agentOS Gmail skill to be available.
    # The skill's command executor calls this script; Gmail access happens
    # via the agentOS skill framework (not inline here).
    # For standalone use, raise to prompt agent to use Gmail skill.
    raise NotImplementedError(
        "Step 4 requires Gmail access via agentOS skill. "
        "The login utility in the claude skill readme orchestrates this."
    )


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Login to claude.ai and extract sessionKey")
    parser.add_argument("--email", default="anthropic@contini.co",
                        help="Email address to log in with (default: anthropic@contini.co)")
    parser.add_argument("--gmail-account", default="joe@contini.co",
                        help="Gmail account to check for magic link (catch-all)")
    parser.add_argument("--magic-link", help="Provide magic link directly (skip email polling)")
    parser.add_argument("--force", action="store_true", help="Force re-login even if session exists")
    parser.add_argument("--port", type=int, default=9222, help="CDP port (default: 9222)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Check saved session first
    if not args.force:
        session = load_session()
        if session:
            print(json.dumps(session))
            return 0

    # Connect to browser
    targets = cdp_get_targets(args.port)
    tab = cdp_find_tab(targets, "claude.ai")
    if not tab:
        # Navigate to claude.ai first
        tab = targets[0]
    ws_url = tab["webSocketDebuggerUrl"]

    if args.verbose:
        print(f"[login] Using tab: {tab['url']}", file=sys.stderr)

    # Check if already logged in
    is_logged_in, org_uuid, org_name = check_logged_in(ws_url)
    if is_logged_in and not args.force:
        if args.verbose:
            print(f"[login] Already logged in. Org: {org_name}", file=sys.stderr)
    else:
        # Need to login — if magic link provided, use it directly
        if args.magic_link:
            if args.verbose:
                print(f"[login] Navigating to magic link...", file=sys.stderr)
            cdp_navigate(ws_url, args.magic_link)
            time.sleep(3)
        else:
            # Full flow — requires Gmail integration (see skill readme)
            print(json.dumps({"error": "Not logged in. Run with --magic-link or use the claude skill login utility."}))
            return 1

        # Verify login
        is_logged_in, org_uuid, org_name = check_logged_in(ws_url)
        if not is_logged_in:
            print(json.dumps({"error": "Login failed — /api/organizations returned no results"}))
            return 1

    # Extract cookies
    cookies = cdp_get_cookies(ws_url)
    session_key = next((c["value"] for c in cookies if c["name"] == "sessionKey"), None)
    last_active_org = next((c["value"] for c in cookies if c["name"] == "lastActiveOrg"), org_uuid)

    if not session_key:
        print(json.dumps({"error": "sessionKey cookie not found after login"}))
        return 1

    if args.verbose:
        print(f"[login] Got sessionKey: {session_key[:30]}...", file=sys.stderr)

    # Save and output
    session = save_session(session_key, last_active_org, org_name, args.email)
    print(json.dumps(session))
    return 0


if __name__ == "__main__":
    sys.exit(main())

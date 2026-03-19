#!/usr/bin/env python3
"""Experiment: drive the mcp-auth.granola.ai PKCE OAuth flow from Python.

Steps:
  1. Dynamic client registration  → client_id (no secret needed)
  2. PKCE setup                   → code_verifier + code_challenge (S256)
  3. Local HTTP server            → catches the redirect callback
  4. Open browser                 → user already logged into Granola, auto-approves
  5. Token exchange               → access_token + refresh_token
  6. MCP probe                    → call initialize against stream.api.granola.ai

Requires: pip install "httpx[http2]"
Usage:    python mcp-oauth-test.py
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import httpx

AUTH_SERVER  = "https://mcp-auth.granola.ai"
MCP_ENDPOINT = "https://stream.api.granola.ai/v1/mcp-server"
REDIRECT_URI = "http://localhost:9876/callback"
SCOPES       = "openid profile email offline_access"
TOKEN_CACHE  = Path.home() / "Library" / "Application Support" / "Granola" / "mcp-oauth-token.json"


# ── PKCE helpers ──────────────────────────────────────────────────────────────

def pkce_pair() -> tuple[str, str]:
    verifier  = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


# ── Step 1: dynamic client registration ───────────────────────────────────────

def register_client(client: httpx.Client) -> str:
    print("\n── Step 1: dynamic client registration")
    resp = client.post(f"{AUTH_SERVER}/oauth2/register", json={
        "redirect_uris":  [REDIRECT_URI],
        "grant_types":    ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    })
    resp.raise_for_status()
    data = resp.json()
    client_id = data["client_id"]
    print(f"  client_id: {client_id}")
    return client_id


# ── Step 2-4: PKCE + local callback server ─────────────────────────────────────

_callback_code: str | None = None
_callback_state: str | None = None

def run_pkce_flow(client_id: str) -> str:
    """Opens browser to authorize URL, blocks until callback received."""
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)

    params = {
        "response_type":         "code",
        "client_id":             client_id,
        "redirect_uri":          REDIRECT_URI,
        "scope":                 SCOPES,
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
        "state":                 state,
    }
    url = f"{AUTH_SERVER}/oauth2/authorize?" + urllib.parse.urlencode(params)

    # Local HTTP server to catch the callback
    code_holder: list[str] = []
    ready = threading.Event()

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs     = urllib.parse.parse_qs(parsed.query)
            code   = (qs.get("code") or [""])[0]
            got_state = (qs.get("state") or [""])[0]

            if got_state != state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch")
                return

            code_holder.append(code)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authenticated. You can close this tab.</h1>")
            ready.set()

        def log_message(self, *_):
            pass

    server = http.server.HTTPServer(("localhost", 9876), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"\n── Step 2-3: opening browser for PKCE authorize")
    print(f"  URL: {url[:80]}...")
    webbrowser.open(url)

    print("  Waiting for callback on http://localhost:9876/callback ...")
    ready.wait(timeout=120)
    server.shutdown()

    if not code_holder:
        raise TimeoutError("No callback received within 120 s")

    print(f"  Auth code received: {code_holder[0][:20]}...")
    return code_holder[0], verifier


# ── Step 5: token exchange ─────────────────────────────────────────────────────

def exchange_code(client: httpx.Client, client_id: str, code: str, verifier: str) -> dict:
    print("\n── Step 5: token exchange")
    resp = client.post(f"{AUTH_SERVER}/oauth2/token", data={
        "grant_type":   "authorization_code",
        "code":         code,
        "redirect_uri": REDIRECT_URI,
        "client_id":    client_id,
        "code_verifier": verifier,
    })
    resp.raise_for_status()
    tokens = resp.json()
    print(f"  token_type:    {tokens.get('token_type')}")
    print(f"  expires_in:    {tokens.get('expires_in')}s")
    print(f"  scope:         {tokens.get('scope')}")
    print(f"  refresh_token: {'yes' if tokens.get('refresh_token') else 'no'}")
    print(f"  access_token:  {tokens.get('access_token', '')[:40]}...")
    return tokens


# ── Step 6: MCP probe ──────────────────────────────────────────────────────────

def probe_mcp(client: httpx.Client, access_token: str):
    print(f"\n── Step 6: MCP probe → {MCP_ENDPOINT}")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json, text/event-stream",
    }
    resp = client.post(MCP_ENDPOINT, headers=headers, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "agentos-probe", "version": "1.0"},
        }
    })
    print(f"  HTTP {resp.status_code}")
    if resp.status_code >= 400:
        if waa := resp.headers.get("WWW-Authenticate") or resp.headers.get("www-authenticate"):
            print(f"  WWW-Authenticate: {waa}")
        print(f"  Body: {resp.text[:400]}")
        return

    session_id = resp.headers.get("mcp-session-id")
    print(f"  session-id: {session_id}")

    raw = resp.text
    if raw.startswith("event:"):
        for line in raw.split("\n"):
            if line.startswith("data: "):
                raw = line[6:]
                break
    data = json.loads(raw)
    if "result" in data:
        si = data["result"].get("serverInfo", {})
        print(f"  server: {si.get('name')} {si.get('version')}")
        caps = data["result"].get("capabilities", {})
        print(f"  capabilities: {list(caps.keys())}")

    # tools/list
    resp2 = client.post(MCP_ENDPOINT, headers={**headers, "mcp-session-id": session_id or ""}, json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
    })
    if resp2.status_code == 200:
        raw2 = resp2.text
        if raw2.startswith("event:"):
            for line in raw2.split("\n"):
                if line.startswith("data: "):
                    raw2 = line[6:]
                    break
        data2 = json.loads(raw2)
        tools = data2.get("result", {}).get("tools", [])
        print(f"\n  Tools ({len(tools)}):")
        for t in tools:
            print(f"    - {t['name']}: {t.get('description','')[:70]}")


# ── main ──────────────────────────────────────────────────────────────────────

def load_cached_tokens() -> dict | None:
    try:
        with open(TOKEN_CACHE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_tokens(tokens: dict, client_id: str):
    out = {**tokens, "client_id": client_id}
    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_CACHE, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Tokens cached → {TOKEN_CACHE}")


def refresh_token(client: httpx.Client, cached: dict) -> dict:
    print("\n── Refreshing token")
    resp = client.post(f"{AUTH_SERVER}/oauth2/token", data={
        "grant_type":    "refresh_token",
        "refresh_token": cached["refresh_token"],
        "client_id":     cached["client_id"],
    })
    resp.raise_for_status()
    new = resp.json()
    print(f"  New access_token: {new.get('access_token','')[:40]}...")
    return {**cached, **new}


def main():
    with httpx.Client(http2=True, timeout=30) as client:

        cached = load_cached_tokens()

        if cached and cached.get("refresh_token"):
            print("Cached tokens found — refreshing.")
            try:
                tokens = refresh_token(client, cached)
                save_tokens(tokens, cached["client_id"])
            except httpx.HTTPStatusError as e:
                print(f"Refresh failed ({e.response.status_code}), re-running full flow.")
                cached = None

        if not cached:
            client_id = register_client(client)
            code, verifier = run_pkce_flow(client_id)
            tokens = exchange_code(client, client_id, code, verifier)
            save_tokens(tokens, client_id)

        probe_mcp(client, tokens["access_token"])


if __name__ == "__main__":
    main()

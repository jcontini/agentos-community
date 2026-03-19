#!/usr/bin/env python3
"""Drive an MCP OAuth PKCE flow end-to-end from the command line.

Useful for reverse-engineering MCP servers that require OAuth. Implements the
full flow: discovery → dynamic client registration → PKCE → token exchange → probe.

Requires: pip install "httpx[http2]"

Usage:
  python mcp-oauth-test.py <mcp-url>

The script discovers the OAuth server from the MCP endpoint's 401 response
or .well-known/oauth-authorization-server, then runs through the flow.
You can also specify the auth server directly:

  python mcp-oauth-test.py <mcp-url> --auth-server <auth-url>
"""

import base64
import hashlib
import http.server
import json
import secrets
import sys
import threading
import urllib.parse
import webbrowser

import httpx

REDIRECT_URI = "http://localhost:9876/callback"
SCOPES = "openid profile email offline_access"


def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def discover_auth_server(client: httpx.Client, mcp_url: str) -> str | None:
    """Try to discover the OAuth authorization server from the MCP endpoint."""
    parsed = urllib.parse.urlparse(mcp_url)
    base = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port and parsed.port not in (80, 443):
        base += f":{parsed.port}"

    # Try .well-known on the MCP host
    for path in ["/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"]:
        try:
            resp = client.get(f"{base}{path}")
            if resp.status_code == 200:
                data = resp.json()
                issuer = data.get("issuer") or data.get("authorization_endpoint", "").rsplit("/", 1)[0]
                if issuer:
                    print(f"  Discovered auth server: {issuer}")
                    return issuer
        except Exception:
            pass

    # Try a naked request and check WWW-Authenticate
    try:
        resp = client.post(mcp_url, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "probe", "version": "1.0"}}
        })
        if waa := resp.headers.get("WWW-Authenticate", ""):
            if "resource_metadata" in waa:
                rm_url = waa.split('resource_metadata="')[1].split('"')[0]
                rm = client.get(rm_url).json()
                servers = rm.get("authorization_servers", [])
                if servers:
                    print(f"  Auth server from resource_metadata: {servers[0]}")
                    return servers[0]
    except Exception:
        pass

    return None


def register_client(client: httpx.Client, auth_server: str) -> str:
    print("\n── Step 1: dynamic client registration")
    resp = client.post(f"{auth_server}/oauth2/register", json={
        "client_name": "mcp-oauth-test",
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    })
    resp.raise_for_status()
    data = resp.json()
    client_id = data["client_id"]
    print(f"  client_id: {client_id}")
    return client_id


def run_pkce_flow(auth_server: str, client_id: str) -> tuple[str, str]:
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    url = f"{auth_server}/oauth2/authorize?" + urllib.parse.urlencode(params)

    code_holder: list[str] = []
    ready = threading.Event()

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            code = (qs.get("code") or [""])[0]
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
    print(f"  URL: {url[:100]}...")
    webbrowser.open(url)

    print("  Waiting for callback on http://localhost:9876/callback ...")
    ready.wait(timeout=120)
    server.shutdown()

    if not code_holder:
        raise TimeoutError("No callback received within 120s")

    print(f"  Auth code received: {code_holder[0][:20]}...")
    return code_holder[0], verifier


def exchange_code(client: httpx.Client, auth_server: str, client_id: str, code: str, verifier: str) -> dict:
    print("\n── Step 4: token exchange")
    resp = client.post(f"{auth_server}/oauth2/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
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


def probe_mcp(client: httpx.Client, mcp_url: str, access_token: str):
    print(f"\n── Step 5: MCP probe with token")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    resp = client.post(mcp_url, headers=headers, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp-oauth-test", "version": "1.0"},
        }
    })
    print(f"  HTTP {resp.status_code}")
    if resp.status_code >= 400:
        if waa := resp.headers.get("WWW-Authenticate"):
            print(f"  WWW-Authenticate: {waa}")
        print(f"  Body: {resp.text[:400]}")
        return

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
    session_id = resp.headers.get("mcp-session-id")

    resp2 = client.post(mcp_url, headers={**headers, "mcp-session-id": session_id or ""}, json={
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
            print(f"    - {t['name']}: {t.get('description', '')[:70]}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {sys.argv[i]: sys.argv[i + 1] for i in range(1, len(sys.argv) - 1) if sys.argv[i].startswith("--")}

    if not args:
        print("Usage: python mcp-oauth-test.py <mcp-url> [--auth-server <url>]")
        sys.exit(1)

    mcp_url = args[0]
    auth_server = flags.get("--auth-server")

    with httpx.Client(http2=True, timeout=30) as client:
        if not auth_server:
            print(f"Discovering auth server for {mcp_url}...")
            auth_server = discover_auth_server(client, mcp_url)
            if not auth_server:
                print("Could not discover auth server. Use --auth-server <url>.")
                sys.exit(1)

        print(f"Auth server: {auth_server}")
        print(f"MCP endpoint: {mcp_url}")

        client_id = register_client(client, auth_server)
        code, verifier = run_pkce_flow(auth_server, client_id)
        tokens = exchange_code(client, auth_server, client_id, code, verifier)
        probe_mcp(client, mcp_url, tokens["access_token"])


if __name__ == "__main__":
    main()

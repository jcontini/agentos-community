#!/usr/bin/env python3
"""Probe Granola's MCP endpoint for reverse-engineering.

Follows docs/reverse-engineering/7-mcp.md. Uses httpx (not urllib) per 1-transport.md —
HTTP MCPs may sit behind CDNs; Python urllib's TLS fingerprint gets flagged.

Requires: pip install "httpx[http2]"

Usage:
  python mcp-probe.py                    # Layer 0-2: existence, transport, auth
  python mcp-probe.py tools             # Layer 3: tools/list
  python mcp-probe.py call <tool> '{}'  # Layer 4: tools/call (once known)

Auth: reads token from ~/Library/Application Support/Granola/supabase.json
      (same as granola.py). Set MCP_PROBE_NO_AUTH=1 for naked probe.
"""

import json
import os
import sys
from pathlib import Path

import httpx

MCP_URL = "https://mcp.granola.ai/mcp"
AUTH_FILE = Path.home() / "Library" / "Application Support" / "Granola" / "supabase.json"


def get_token() -> str | None:
    if os.environ.get("MCP_PROBE_NO_AUTH"):
        return None
    try:
        with open(AUTH_FILE) as f:
            data = json.load(f)
        tokens = json.loads(data["workos_tokens"])
        return tokens.get("access_token")
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None


def send_rpc(method: str, params: dict, token: str | None, session_id: str | None) -> tuple[dict, dict]:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if session_id:
        headers["mcp-session-id"] = session_id
    with httpx.Client(http2=True, timeout=30) as client:
        resp = client.post(MCP_URL, json=body, headers=headers)
        if resp.status_code >= 400:
            print(f"HTTP {resp.status_code}: {resp.reason_phrase}")
            if waa := resp.headers.get("WWW-Authenticate"):
                print(f"WWW-Authenticate: {waa}")
            if resp.text:
                print(f"Body: {resp.text[:500]}")
            resp.raise_for_status()
        raw = resp.text
        new_session = resp.headers.get("mcp-session-id")
        headers_out = {"mcp-session-id": new_session} if new_session else {}
    if raw.startswith("event:"):
        for line in raw.split("\n"):
            if line.startswith("data: "):
                return json.loads(line[6:]), headers_out
    return json.loads(raw), headers_out


def main():
    token = get_token()
    if token:
        print("✓ Token found (supabase.json)")
    else:
        print("⚠ No token (MCP_PROBE_NO_AUTH=1 or Granola not installed)")

    # Layer 1: initialize
    init_params = {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "granola-mcp-probe", "version": "1.0"},
    }
    rpc, headers = send_rpc("initialize", init_params, token, None)
    session_id = headers.get("mcp-session-id")
    print(f"Session: {session_id or 'none (stateless)'}")
    if "result" in rpc:
        si = rpc["result"].get("serverInfo", {})
        print(f"Server: {si.get('name', 'unknown')} {si.get('version', '')}")
    if "error" in rpc:
        print(f"Error: {rpc['error']}")
        sys.exit(1)

    # Layer 3: tools/list
    rpc2, _ = send_rpc("tools/list", {}, token, session_id)
    tools = rpc2.get("result", {}).get("tools", [])
    print(f"Tools: {len(tools)}")
    for t in tools:
        print(f"  - {t.get('name', '?')}: {t.get('description', '')[:60]}")

    if len(sys.argv) > 1 and sys.argv[1] == "call" and len(sys.argv) >= 4:
        tool_name = sys.argv[2]
        tool_args = json.loads(sys.argv[3])
        rpc3, _ = send_rpc("tools/call", {"name": tool_name, "arguments": tool_args}, token, session_id)
        print(json.dumps(rpc3, indent=2))


if __name__ == "__main__":
    main()

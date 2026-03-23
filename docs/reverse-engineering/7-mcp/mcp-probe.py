#!/usr/bin/env python3
"""Probe a Streamable HTTP MCP endpoint for reverse-engineering.

Follows the layers in this folder's index.md. Uses httpx with HTTP/2 —
MCP servers behind CDNs may flag urllib's TLS fingerprint.

Requires: pip install "httpx[http2]"

Usage:
  python mcp-probe.py <url>                          # Layer 0-2: existence, transport, auth
  python mcp-probe.py <url> --token <bearer_token>   # with auth
  python mcp-probe.py <url> tools                    # Layer 3: tools/list
  python mcp-probe.py <url> call <tool> '{}'         # Layer 4: tools/call
"""

import json
import sys

import httpx

def send_rpc(url: str, method: str, params: dict, token: str | None, session_id: str | None) -> tuple[dict, dict]:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if session_id:
        headers["mcp-session-id"] = session_id
    with httpx.Client(http2=True, timeout=30) as client:
        resp = client.post(url, json=body, headers=headers)
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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {sys.argv[i]: sys.argv[i + 1] for i in range(1, len(sys.argv) - 1) if sys.argv[i].startswith("--")}

    if not args:
        print("Usage: python mcp-probe.py <mcp-url> [tools] [call <tool> '<json>'] [--token <token>]")
        sys.exit(1)

    url = args[0]
    token = flags.get("--token")
    command = args[1] if len(args) > 1 else None

    print(f"Target: {url}")
    if token:
        print(f"Auth:   Bearer {token[:20]}...")
    else:
        print("Auth:   none")

    init_params = {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "mcp-probe", "version": "1.0"},
    }
    rpc, headers = send_rpc(url, "initialize", init_params, token, None)
    session_id = headers.get("mcp-session-id")
    print(f"Session: {session_id or 'none (stateless)'}")
    if "result" in rpc:
        si = rpc["result"].get("serverInfo", {})
        print(f"Server: {si.get('name', 'unknown')} {si.get('version', '')}")
        caps = rpc["result"].get("capabilities", {})
        if caps:
            print(f"Capabilities: {list(caps.keys())}")
    if "error" in rpc:
        print(f"Error: {rpc['error']}")
        sys.exit(1)

    if command in (None, "tools"):
        rpc2, _ = send_rpc(url, "tools/list", {}, token, session_id)
        tools = rpc2.get("result", {}).get("tools", [])
        print(f"\nTools ({len(tools)}):")
        for t in tools:
            print(f"  - {t.get('name', '?')}: {t.get('description', '')[:80]}")

    if command == "call" and len(args) >= 4:
        tool_name = args[2]
        tool_args = json.loads(args[3])
        rpc3, _ = send_rpc(url, "tools/call", {"name": tool_name, "arguments": tool_args}, token, session_id)
        print(json.dumps(rpc3, indent=2))


if __name__ == "__main__":
    main()

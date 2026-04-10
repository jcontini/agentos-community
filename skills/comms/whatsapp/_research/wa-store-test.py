#!/usr/bin/env python3
"""Test WhatsApp Web JS Store access via CDP.

Usage:
  1. Launch Brave with CDP:
     "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" --remote-debugging-port=9222
  2. Open https://web.whatsapp.com/ (or let this script open it)
  3. Run: python3 bin/wa-store-test.py
  4. Send/receive a WhatsApp message and watch the output

Tests hypotheses A2 (JS Store hooks) and A3 (CDP access with default profile).
Verified working on Brave (Chromium 146) with default profile, 2026-04-05.

Field mapping (WhatsApp Web uses __x_ prefix on message properties):
  __x_body        → message text
  __x_notifyName  → sender display name
  __x_t           → unix timestamp
  __x_type        → message type ("chat", "image", etc.)
  __x_id.fromMe   → true if sent by us
  __x_id.remote._serialized → chat JID
  __x_isNewMsg    → true if just arrived
  __x_ack         → delivery status (0=pending, 1=sent, 2=delivered, 3=read)
"""

import asyncio
import json
import sys

try:
    import aiohttp
    import websockets
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install aiohttp websockets")
    sys.exit(1)

CDP_PORT = 9222

HOOK_JS = """
(function() {
  if (window.__WA_TEST_HOOKS__) return 'ALREADY_HOOKED';
  window.__WA_TEST_HOOKS__ = true;

  const check = setInterval(() => {
    try {
      const { Msg, Chat } = window.require('WAWebCollections');
      clearInterval(check);

      Msg.on('add', (msg) => {
        console.log('__WA_MSG__' + JSON.stringify({
          body: msg.__x_body || '',
          sender: msg.__x_notifyName || '?',
          from: msg.__x_from?._serialized || '?',
          timestamp: msg.__x_t || 0,
          isOutgoing: msg.__x_id?.fromMe || false,
          chatId: msg.__x_id?.remote?._serialized || '?',
          type: msg.__x_type || '?',
          isNewMsg: msg.__x_isNewMsg || false,
          ack: msg.__x_ack
        }));
      });

      Chat.on('change', (chat) => {
        console.log('__WA_MSG__' + JSON.stringify({
          event: 'CHAT_UPDATE',
          id: chat.__x_id?._serialized || chat.id?._serialized || '?',
          name: chat.__x_name || chat.name || '?',
          unreadCount: chat.__x_unreadCount ?? chat.unreadCount ?? 0
        }));
      });

      console.log('__WA_MSG__' + JSON.stringify({event: 'READY', msg: 'Store hooks active'}));
    } catch(e) { /* not ready yet */ }
  }, 500);
})();
"""


async def main():
    # Step 1: Check CDP is listening (tests A3)
    print(f"Connecting to CDP on port {CDP_PORT}...")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"http://localhost:{CDP_PORT}/json", timeout=aiohttp.ClientTimeout(total=3)) as r:
                tabs = await r.json()
    except Exception as e:
        print(f"\n❌ A3 FAILED: Cannot reach CDP on port {CDP_PORT}")
        print(f"   Error: {e}")
        print(f"\n   Make sure Brave is launched with: --remote-debugging-port={CDP_PORT}")
        return

    print(f"✅ A3 PASS: CDP is listening. Found {len(tabs)} tab(s).")

    # Step 2: Find or open WhatsApp tab
    wa_tabs = [t for t in tabs if "web.whatsapp.com" in t.get("url", "")]
    if not wa_tabs:
        print("\n   No WhatsApp tab found. Opening one...")
        async with aiohttp.ClientSession() as s:
            async with s.put(f"http://localhost:{CDP_PORT}/json/new?https://web.whatsapp.com/") as r:
                tab = await r.json()
        print(f"   Opened WhatsApp tab. Waiting for it to load...")
        await asyncio.sleep(5)
        # Re-fetch tabs to get updated info
        async with aiohttp.ClientSession() as s:
            async with s.get(f"http://localhost:{CDP_PORT}/json") as r:
                tabs = await r.json()
        wa_tabs = [t for t in tabs if "web.whatsapp.com" in t.get("url", "")]

    if not wa_tabs:
        print("   ❌ Still no WhatsApp tab. Something went wrong.")
        return

    tab = wa_tabs[0]
    ws_url = tab["webSocketDebuggerUrl"]
    print(f"   WhatsApp tab: {tab['title']}")

    # Step 3: Connect and inject hooks (tests A2)
    pending = {}
    msg_id = 0

    async with websockets.connect(ws_url, max_size=2**24) as ws:
        async def send(method, params=None):
            nonlocal msg_id
            msg_id += 1
            cid = msg_id
            pending[cid] = asyncio.get_event_loop().create_future()
            await ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
            return cid

        console_events = asyncio.Queue()

        async def reader():
            async for raw in ws:
                data = json.loads(raw)
                if "id" in data and data["id"] in pending:
                    pending[data["id"]].set_result(data)
                elif data.get("method") == "Runtime.consoleAPICalled":
                    await console_events.put(data)

        reader_task = asyncio.create_task(reader())

        cid = await send("Runtime.enable")
        await asyncio.wait_for(pending[cid], timeout=5)

        cid = await send("Runtime.evaluate", {"expression": HOOK_JS})
        result = await asyncio.wait_for(pending[cid], timeout=5)
        hook_status = result.get("result", {}).get("result", {}).get("value", "?")
        print(f"\n   Hook status: {hook_status}")
        print("   Waiting for messages... (send or receive a WhatsApp message)\n")

        msg_count = 0
        while True:
            data = await console_events.get()
            for arg in data["params"].get("args", []):
                val = arg.get("value", "")
                if not isinstance(val, str) or not val.startswith("__WA_MSG__"):
                    continue

                event = json.loads(val[10:])
                etype = event.get("event", "")

                if etype == "READY":
                    print(f"   ✅ A2 PASS: {event['msg']}")
                    print("   Messages will appear below.\n")
                elif etype == "CHAT_UPDATE":
                    print(f"   📋 Chat: {event.get('name', '?')} (unread: {event.get('unreadCount', 0)})")
                else:
                    msg_count += 1
                    direction = "→ SENT" if event.get("isOutgoing") else "← RECV"
                    sender = event.get("sender", "?")
                    body = (event.get("body") or "")[:80] or "(no text)"
                    new_flag = " [NEW]" if event.get("isNewMsg") else ""
                    print(f"   #{msg_count} {direction} [{sender}]: {body}{new_flag}")
                    print(f"          chat={event.get('chatId', '?')}  type={event.get('type', '?')}  ack={event.get('ack', '?')}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDone.")

#!/usr/bin/env python3
"""WhatsApp Web CDP helper — quick navigation and data access.

Usage:
  python3 bin/wa.py chats                    # list unarchived chats
  python3 bin/wa.py archived [N]             # list top N archived (default 10)
  python3 bin/wa.py msgs <chat_name> [N]     # last N messages from chat (default 20)
  python3 bin/wa.py members <group_name>     # list group members
  python3 bin/wa.py send <chat_name> <text>  # send a message
  python3 bin/wa.py search <query>           # search chat names
  python3 bin/wa.py react <chat_name> <emoji> # react to last msg in chat
  python3 bin/wa.py starred                  # list starred messages
  python3 bin/wa.py statuses                 # list contacts' status stories
  python3 bin/wa.py communities              # list communities and subgroups
  python3 bin/wa.py channels [N]             # list followed channels (default 20)
  python3 bin/wa.py channel-msgs <name> [N]  # messages from a channel
  python3 bin/wa.py follow <channel_name>    # follow/subscribe to a channel
  python3 bin/wa.py unfollow <channel_name>  # unfollow/unsubscribe from a channel
  python3 bin/wa.py ai <message>             # send message to Meta AI
  python3 bin/wa.py ai-read [N]              # read last N Meta AI messages

Requires Brave running with --remote-debugging-port=9222 and WhatsApp Web open.
"""

import asyncio, json, sys, websockets, aiohttp
from datetime import datetime

CDP_PORT = 9222

async def get_wa_ws():
    """Find WhatsApp tab and return its CDP WebSocket URL."""
    async with aiohttp.ClientSession() as s:
        async with s.get(f"http://localhost:{CDP_PORT}/json", timeout=aiohttp.ClientTimeout(total=3)) as r:
            tabs = await r.json()
    wa = [t for t in tabs if "web.whatsapp.com" in t.get("url", "") and t.get("type") == "page"]
    if not wa:
        print("No WhatsApp tab found.")
        sys.exit(1)
    return wa[0]["webSocketDebuggerUrl"]


async def cdp_eval(expression, await_promise=False):
    """Connect to WhatsApp tab, evaluate JS, return parsed result."""
    ws_url = await get_wa_ws()
    async with websockets.connect(ws_url, max_size=2**24) as ws:
        pending = {}

        async def send(method, params=None):
            cid = len(pending) + 1
            pending[cid] = asyncio.get_event_loop().create_future()
            await ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
            return cid

        async def reader():
            async for raw in ws:
                data = json.loads(raw)
                if "id" in data and data["id"] in pending:
                    pending[data["id"]].set_result(data)

        rt = asyncio.create_task(reader())
        cid = await send("Runtime.enable")
        await asyncio.wait_for(pending[cid], timeout=5)

        cid = await send("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": await_promise
        })
        r = await asyncio.wait_for(pending[cid], timeout=30)
        rt.cancel()

        val = r.get("result", {}).get("result", {}).get("value", "")
        if val and isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
            return json.loads(val)
        return val


# ─── Chat commands ───────────────────────────────────────────────

async def cmd_chats():
    data = await cdp_eval("""
    (function() {
        const { Chat } = window.require('WAWebCollections');
        const chats = Chat.getModelsArray().filter(c => !c.__x_archive);
        return JSON.stringify(chats.map(c => ({
            name: c.__x_name || c.__x_formattedTitle || '?',
            group: (c.__x_id?._serialized || '').endsWith('@g.us'),
            unread: c.__x_unreadCount || 0
        })));
    })()
    """)
    print(f"{len(data)} unarchived chats:\n")
    for c in data:
        tag = " [GROUP]" if c["group"] else ""
        unread = f" ({c['unread']} unread)" if c.get("unread") else ""
        print(f"  {c['name']}{tag}{unread}")


async def cmd_archived(n=10):
    data = await cdp_eval(f"""
    (function() {{
        const {{ Chat }} = window.require('WAWebCollections');
        const chats = Chat.getModelsArray()
            .filter(c => c.__x_archive)
            .sort((a, b) => (b.__x_t || 0) - (a.__x_t || 0))
            .slice(0, {n});
        return JSON.stringify(chats.map(c => ({{
            name: c.__x_name || c.__x_formattedTitle || '?',
            group: (c.__x_id?._serialized || '').endsWith('@g.us'),
            t: c.__x_t || 0
        }})));
    }})()
    """)
    print(f"Top {len(data)} archived chats:\n")
    for c in data:
        tag = " [GROUP]" if c["group"] else ""
        ts = datetime.fromtimestamp(c["t"]).strftime("%b %d %H:%M") if c["t"] else "?"
        print(f"  {c['name']}{tag}  ({ts})")


async def cmd_msgs(chat_name, n=20):
    data = await cdp_eval(f"""
    (async function() {{
        const {{ Chat, Msg }} = window.require('WAWebCollections');
        const loader = window.require('WAWebChatLoadMessages');
        const chat = Chat.getModelsArray().find(c =>
            (c.__x_name || c.__x_formattedTitle || '').toLowerCase().includes('{chat_name.lower().replace("'", "\\'")}')
        );
        if (!chat) return JSON.stringify({{error: 'Chat not found'}});

        for (let i = 0; i < 3; i++) {{
            try {{ await loader.loadEarlierMsgs(chat); }} catch(e) {{ break; }}
        }}

        const chatId = chat.__x_id?._serialized;
        const msgs = Msg.getModelsArray()
            .filter(m => (m.__x_id?.remote?._serialized || '') === chatId)
            .sort((a, b) => (b.__x_t || 0) - (a.__x_t || 0))
            .slice(0, {n});

        return JSON.stringify({{
            chatName: chat.__x_name || chat.__x_formattedTitle,
            total: msgs.length,
            messages: msgs.map(m => {{
                let body = m.__x_body || '';
                if (!body && m.__x_richResponse?.fragments) {{
                    body = m.__x_richResponse.fragments.filter(f => f.type === 'Text').map(f => f.text).join('\\n');
                }}
                return {{
                body: body.substring(0, 300),
                caption: (m.__x_caption || '').substring(0, 200),
                from: m.__x_id?.fromMe ? 'you' : (m.__x_senderObj?.__x_name || m.__x_senderObj?.__x_pushname || m.__x_notifyName || '?'),
                type: m.__x_type || '?',
                t: m.__x_t || 0,
                hasReaction: m.__x_hasReaction || false,
                isForwarded: m.__x_isForwarded || false,
                forwardsCount: m.__x_forwardsCount || 0,
                star: m.__x_star || false,
                mimetype: m.__x_mimetype || null,
                isQuestion: m.__x_isQuestion || false,
                pollOptions: m.__x_pollOptions?.map(o => o.name) || null
            }};}}))
        }});
    }})()
    """, await_promise=True)
    if isinstance(data, dict) and data.get("error"):
        print(f"Error: {data['error']}")
        return
    print(f"{data['chatName']} — {data['total']} messages:\n")
    for m in reversed(data["messages"]):
        ts = datetime.fromtimestamp(m["t"]).strftime("%b %d %H:%M") if m["t"] else "?"
        body = m.get("body", "") or m.get("caption", "") or f"({m['type']})"
        extras = []
        if m.get("hasReaction"): extras.append("reaction")
        if m.get("star"): extras.append("starred")
        if m.get("isForwarded"): extras.append(f"fwd:{m['forwardsCount']}")
        if m.get("mimetype"): extras.append(m["mimetype"])
        if m.get("isQuestion"): extras.append("POLL")
        extra_str = f" [{', '.join(extras)}]" if extras else ""
        print(f"  [{ts}] {m['from']}: {body[:150]}{extra_str}")
        if m.get("pollOptions"):
            for opt in m["pollOptions"]:
                print(f"    - {opt}")


async def cmd_members(group_name):
    data = await cdp_eval(f"""
    (async function() {{
        const {{ Chat, Contact }} = window.require('WAWebCollections');
        const openCmd = window.require('WAWebCmd');
        const chat = Chat.getModelsArray().find(c =>
            (c.__x_name || c.__x_formattedTitle || '').toLowerCase().includes('{group_name.lower().replace("'", "\\'")}')
            && (c.__x_id?._serialized || '').endsWith('@g.us')
        );
        if (!chat) return JSON.stringify({{error: 'Group not found'}});

        if (openCmd?.openChatAt) await openCmd.openChatAt(chat);
        await new Promise(r => setTimeout(r, 2000));

        const meta = chat.__x_groupMetadata;
        const parts = meta?.participants?.getModelsArray?.() || [];

        return JSON.stringify({{
            name: chat.__x_name || chat.__x_formattedTitle,
            count: parts.length || meta?.__x_size || 0,
            members: parts.map(p => {{
                const lid = p.__x_id?._serialized;
                const contact = Contact.get(lid);
                return {{
                    name: contact?.__x_name || contact?.__x_pushname || contact?.__x_formattedName || lid,
                    phone: contact?.__x_phoneNumber?._serialized || null,
                    admin: p.__x_isAdmin || false
                }};
            }})
        }});
    }})()
    """, await_promise=True)
    if isinstance(data, dict) and data.get("error"):
        print(f"Error: {data['error']}")
        return
    print(f"{data['name']} — {data['count']} members:\n")
    for m in data["members"]:
        admin = " (admin)" if m["admin"] else ""
        phone = f" [{m['phone']}]" if m.get("phone") else ""
        print(f"  {m['name']}{admin}{phone}")


async def cmd_send(chat_name, text):
    data = await cdp_eval(f"""
    (async function() {{
        const {{ Chat }} = window.require('WAWebCollections');
        const {{ addAndSendMsgToChat }} = window.require('WAWebSendMsgChatAction');
        const chat = Chat.getModelsArray().find(c =>
            (c.__x_name || c.__x_formattedTitle || '').toLowerCase().includes('{chat_name.lower().replace("'", "\\'")}')
        );
        if (!chat) return JSON.stringify({{error: 'Chat not found'}});
        await addAndSendMsgToChat(chat, {{ body: `{text.replace('`', '\\`')}`, type: 'chat' }});
        return JSON.stringify({{sent: true, to: chat.__x_name || chat.__x_formattedTitle}});
    }})()
    """, await_promise=True)
    if isinstance(data, dict) and data.get("error"):
        print(f"Error: {data['error']}")
    else:
        print(f"Sent to {data['to']}")


async def cmd_search(query):
    data = await cdp_eval(f"""
    (function() {{
        const {{ Chat }} = window.require('WAWebCollections');
        const q = '{query.lower().replace("'", "\\'")}';
        const matches = Chat.getModelsArray()
            .filter(c => (c.__x_name || c.__x_formattedTitle || '').toLowerCase().includes(q))
            .sort((a, b) => (b.__x_t || 0) - (a.__x_t || 0))
            .slice(0, 20);
        return JSON.stringify(matches.map(c => ({{
            name: c.__x_name || c.__x_formattedTitle || '?',
            group: (c.__x_id?._serialized || '').endsWith('@g.us'),
            archived: c.__x_archive || false,
            t: c.__x_t || 0
        }})));
    }})()
    """)
    print(f'Found {len(data)} chats matching "{query}":\n')
    for c in data:
        tag = " [GROUP]" if c["group"] else ""
        arc = " (archived)" if c["archived"] else ""
        ts = datetime.fromtimestamp(c["t"]).strftime("%b %d") if c["t"] else "?"
        print(f"  {c['name']}{tag}{arc}  ({ts})")


# ─── Reaction commands ───────────────────────────────────────────

async def cmd_react(chat_name, emoji):
    data = await cdp_eval(f"""
    (async function() {{
        const {{ Chat, Msg }} = window.require('WAWebCollections');
        const {{ sendReactionToMsg }} = window.require('WAWebSendReactionMsgAction');
        const chat = Chat.getModelsArray().find(c =>
            (c.__x_name || c.__x_formattedTitle || '').toLowerCase().includes('{chat_name.lower().replace("'", "\\'")}')
        );
        if (!chat) return JSON.stringify({{error: 'Chat not found'}});

        const chatId = chat.__x_id?._serialized;
        const lastMsg = Msg.getModelsArray()
            .filter(m => (m.__x_id?.remote?._serialized || '') === chatId)
            .sort((a, b) => (b.__x_t || 0) - (a.__x_t || 0))[0];
        if (!lastMsg) return JSON.stringify({{error: 'No messages found'}});

        await sendReactionToMsg(lastMsg, '{emoji}');
        return JSON.stringify({{
            reacted: true,
            emoji: '{emoji}',
            msgBody: (lastMsg.__x_body || '').substring(0, 80),
            chat: chat.__x_name || chat.__x_formattedTitle
        }});
    }})()
    """, await_promise=True)
    if isinstance(data, dict) and data.get("error"):
        print(f"Error: {data['error']}")
    else:
        print(f"Reacted {data['emoji']} to: {data['msgBody'][:60]}")


# ─── Starred messages ────────────────────────────────────────────

async def cmd_starred():
    data = await cdp_eval("""
    (function() {
        const { StarredMsg, Contact } = window.require('WAWebCollections');
        const msgs = StarredMsg.getModelsArray()
            .sort((a, b) => (b.__x_t || 0) - (a.__x_t || 0));
        return JSON.stringify(msgs.map(m => ({
            body: (m.__x_body || '').substring(0, 200),
            caption: (m.__x_caption || '').substring(0, 200),
            type: m.__x_type || '?',
            t: m.__x_t || 0,
            from: m.__x_id?.fromMe ? 'you' : (m.__x_senderObj?.__x_name || m.__x_notifyName || '?'),
            chat: m.__x_id?.remote?._serialized || '?',
            mimetype: m.__x_mimetype || null,
            hasReaction: m.__x_hasReaction || false
        })));
    })()
    """)
    print(f"{len(data)} starred messages:\n")
    for m in data:
        ts = datetime.fromtimestamp(m["t"]).strftime("%b %d %H:%M") if m["t"] else "?"
        body = m.get("body", "") or m.get("caption", "") or f"({m['type']})"
        media = f" [{m['mimetype']}]" if m.get("mimetype") else ""
        print(f"  [{ts}] {m['from']}: {body[:120]}{media}")


# ─── Status / Stories ─────────────────────────────────────────────

async def cmd_statuses():
    data = await cdp_eval("""
    (async function() {
        const C = window.require('WAWebCollections');
        const statuses = C.Status.getModelsArray();
        const results = [];
        for (const s of statuses) {
            const contact = C.Contact.get(s.__x_id?._serialized);
            try { await s.loadMore(); } catch(e) {}
            const allMsgs = s.getAllMsgs?.() || [];
            results.push({
                contact: contact?.__x_name || contact?.__x_pushname || '?',
                totalCount: s.__x_totalCount || 0,
                unreadCount: s.__x_unreadCount || 0,
                messages: allMsgs.map(m => ({
                    type: m.__x_type || '?',
                    body: (m.__x_body || '').substring(0, 100),
                    caption: (m.__x_caption || '').substring(0, 100),
                    t: m.__x_t || 0,
                    mimetype: m.__x_mimetype || null,
                    duration: m.__x_duration || null,
                    size: m.__x_size || null
                }))
            });
        }
        return JSON.stringify(results);
    })()
    """, await_promise=True)
    print(f"{len(data)} contacts with status stories:\n")
    for s in data:
        unread = f" ({s['unreadCount']} unread)" if s["unreadCount"] else ""
        print(f"  {s['contact']} — {s['totalCount']} stories{unread}")
        for m in s["messages"]:
            ts = datetime.fromtimestamp(m["t"]).strftime("%b %d %H:%M") if m["t"] else "?"
            media = f" [{m['mimetype']}]" if m["mimetype"] else ""
            dur = f" {m['duration']}s" if m.get("duration") else ""
            body = m.get("body", "")[:60] or m.get("caption", "")[:60] or "(media)"
            print(f"    [{ts}] {m['type']}{media}{dur}")


# ─── Communities ──────────────────────────────────────────────────

async def cmd_communities():
    data = await cdp_eval("""
    (function() {
        const { Chat } = window.require('WAWebCollections');
        const C = window.require('WAWebCollections');
        const communities = Chat.getModelsArray().filter(c => {
            const meta = c.__x_groupMetadata;
            return meta && meta.__x_isParentGroup === true;
        });
        return JSON.stringify(communities.map(c => {
            const meta = c.__x_groupMetadata;
            const joinedIds = meta.__x_joinedSubgroups || [];
            const unjoinedIds = meta.__x_unjoinedSubgroups || [];

            const joinedChats = joinedIds.map(id => {
                const sid = typeof id === 'string' ? id : (id?._serialized || String(id));
                const chat = Chat.getModelsArray().find(ch => ch.__x_id?._serialized === sid);
                return { name: chat?.__x_name || chat?.__x_formattedTitle || '?', id: sid };
            });

            const unjoinedMetas = C.WAWebUnjoinedSubgroupMetadataCollection?.getModelsArray?.() || [];
            const unjoinedChats = unjoinedIds.map(id => {
                const sid = typeof id === 'string' ? id : (id?._serialized || String(id));
                const meta = unjoinedMetas.find(u => u.__x_id?._serialized === sid);
                return {
                    name: meta?.__x_subject || '?',
                    id: sid,
                    size: meta?.__x_size || 0
                };
            });

            return {
                name: c.__x_name || c.__x_formattedTitle || '?',
                desc: (meta.__x_desc || '').substring(0, 100),
                size: meta.__x_size || 0,
                joinedSubgroups: joinedChats,
                unjoinedSubgroups: unjoinedChats
            };
        }));
    })()
    """)
    print(f"{len(data)} communities:\n")
    for c in data:
        print(f"  {c['name']} (size: {c['size']})")
        if c["desc"]:
            print(f"    {c['desc'][:80]}")
        if c["joinedSubgroups"]:
            print(f"    Joined ({len(c['joinedSubgroups'])}):")
            for sg in c["joinedSubgroups"]:
                print(f"      + {sg['name']}")
        if c["unjoinedSubgroups"]:
            print(f"    Available ({len(c['unjoinedSubgroups'])}):")
            for sg in c["unjoinedSubgroups"]:
                sz = f" ({sg['size']} members)" if sg.get("size") else ""
                print(f"      - {sg['name']}{sz}")
        print()


# ─── Channels / Newsletters ──────────────────────────────────────

async def cmd_channels(n=20):
    data = await cdp_eval(f"""
    (function() {{
        const C = window.require('WAWebCollections');
        const metas = C.WAWebNewsletterMetadataCollection.getModelsArray()
            .filter(n => n.__x_isSubscribedOrOwned)
            .sort((a, b) => (b.__x_size || 0) - (a.__x_size || 0))
            .slice(0, {n});
        return JSON.stringify(metas.map(n => ({{
            name: n.__x_name || '?',
            desc: (n.__x_description || '').substring(0, 100),
            size: n.__x_size || 0,
            verified: n.__x_verified || false,
            membershipType: n.__x_membershipType || '?'
        }})));
    }})()
    """)
    if not data:
        # Show top channels if no subscriptions
        data = await cdp_eval(f"""
        (function() {{
            const C = window.require('WAWebCollections');
            const metas = C.WAWebNewsletterMetadataCollection.getModelsArray()
                .sort((a, b) => (b.__x_size || 0) - (a.__x_size || 0))
                .slice(0, {n});
            return JSON.stringify(metas.map(n => ({{
                name: n.__x_name || '?',
                desc: (n.__x_description || '').substring(0, 100),
                size: n.__x_size || 0,
                verified: n.__x_verified || false,
                subscribed: n.__x_isSubscribedOrOwned || false
            }})));
        }})()
        """)
        print(f"Top {len(data)} channels (none subscribed):\n")
    else:
        print(f"{len(data)} followed channels:\n")
    for c in data:
        v = " [verified]" if c.get("verified") else ""
        sub = " (subscribed)" if c.get("subscribed") else ""
        print(f"  {c['name']}{v}{sub} — {c['size']:,} followers")
        if c["desc"]:
            print(f"    {c['desc'][:80]}")


async def cmd_channel_msgs(channel_name, n=20):
    data = await cdp_eval(f"""
    (async function() {{
        const C = window.require('WAWebCollections');
        const loader = window.require('WAWebChatLoadMessages');

        const nlMeta = C.WAWebNewsletterMetadataCollection.getModelsArray()
            .find(n => (n.__x_name || '').toLowerCase().includes('{channel_name.lower().replace("'", "\\'")}'));
        if (!nlMeta) return JSON.stringify({{error: 'Channel not found'}});

        const nlId = nlMeta.__x_id?._serialized;
        const chat = C.WAWebNewsletterCollection.getModelsArray()
            .find(c => c.__x_id?._serialized === nlId);

        if (chat) {{
            try {{ await loader.loadEarlierMsgs(chat); }} catch(e) {{}}
            try {{ await loader.loadEarlierMsgs(chat); }} catch(e) {{}}
        }}

        const msgs = C.Msg.getModelsArray()
            .filter(m => (m.__x_id?.remote?._serialized || '') === nlId)
            .sort((a, b) => (b.__x_t || 0) - (a.__x_t || 0))
            .slice(0, {n});

        return JSON.stringify({{
            channel: nlMeta.__x_name,
            followers: nlMeta.__x_size || 0,
            verified: nlMeta.__x_verified || false,
            total: msgs.length,
            messages: msgs.map(m => ({{
                type: m.__x_type || '?',
                body: (m.__x_body || '').substring(0, 300),
                caption: (m.__x_caption || '').substring(0, 200),
                t: m.__x_t || 0,
                mimetype: m.__x_mimetype || null,
                hasReaction: m.__x_hasReaction || false,
                forwardsCount: m.__x_forwardsCount || 0,
                isQuestion: m.__x_isQuestion || false,
                pollOptions: m.__x_pollOptions?.map(o => o.name) || null,
                duration: m.__x_duration || null
            }}))
        }});
    }})()
    """, await_promise=True)
    if isinstance(data, dict) and data.get("error"):
        print(f"Error: {data['error']}")
        return
    v = " [verified]" if data.get("verified") else ""
    print(f"{data['channel']}{v} ({data['followers']:,} followers) — {data['total']} messages:\n")
    for m in reversed(data["messages"]):
        ts = datetime.fromtimestamp(m["t"]).strftime("%b %d %H:%M") if m["t"] else "?"
        body = m.get("body", "")
        # Skip base64 thumbnail data in display
        if body and body.startswith("/9j/"):
            body = "(image thumbnail)"
        body = body[:150] or m.get("caption", "")[:150] or f"({m['type']})"
        extras = []
        if m.get("mimetype"): extras.append(m["mimetype"])
        if m.get("hasReaction"): extras.append("reactions")
        if m.get("forwardsCount"): extras.append(f"fwd:{m['forwardsCount']:,}")
        if m.get("isQuestion"): extras.append("POLL")
        if m.get("duration"): extras.append(f"{m['duration']}s")
        extra_str = f" [{', '.join(extras)}]" if extras else ""
        print(f"  [{ts}] {m['type']}{extra_str}")
        print(f"    {body}")
        if m.get("pollOptions"):
            for opt in m["pollOptions"]:
                print(f"      - {opt}")


async def cmd_follow(channel_name):
    data = await cdp_eval(f"""
    (async function() {{
        const {{ subscribeToNewsletterAction }} = window.require('WAWebNewsletterSubscribeAction');
        const C = window.require('WAWebCollections');

        const nlMeta = C.WAWebNewsletterMetadataCollection.getModelsArray()
            .find(n => (n.__x_name || '').toLowerCase().includes('{channel_name.lower().replace("'", "\\'")}'));
        if (!nlMeta) return JSON.stringify({{error: 'Channel not found'}});

        const before = nlMeta.__x_isSubscribedOrOwned;
        try {{
            await subscribeToNewsletterAction(nlMeta, {{
                entryPoint: 'discover',
                eventSurface: 'channel_profile',
                eventUnit: 'follow_button'
            }});
            await new Promise(r => setTimeout(r, 1000));
            return JSON.stringify({{
                success: true,
                channel: nlMeta.__x_name,
                wasSubscribed: before,
                isSubscribed: nlMeta.__x_isSubscribedOrOwned
            }});
        }} catch(e) {{
            return JSON.stringify({{error: e.message}});
        }}
    }})()
    """, await_promise=True)
    if isinstance(data, dict) and data.get("error"):
        print(f"Error: {data['error']}")
    else:
        print(f"Followed {data['channel']} (was: {data['wasSubscribed']} -> now: {data['isSubscribed']})")


async def cmd_unfollow(channel_name):
    data = await cdp_eval(f"""
    (async function() {{
        const {{ unsubscribeFromNewsletterAction }} = window.require('WAWebNewsletterUnsubscribeAction');
        const C = window.require('WAWebCollections');

        const nlMeta = C.WAWebNewsletterMetadataCollection.getModelsArray()
            .find(n => (n.__x_name || '').toLowerCase().includes('{channel_name.lower().replace("'", "\\'")}'));
        if (!nlMeta) return JSON.stringify({{error: 'Channel not found'}});

        const before = nlMeta.__x_isSubscribedOrOwned;
        try {{
            await unsubscribeFromNewsletterAction(nlMeta, {{
                entryPoint: 'channel_profile',
                eventSurface: 'channel_profile',
                eventUnit: 'unfollow_button'
            }});
            await new Promise(r => setTimeout(r, 1000));
            return JSON.stringify({{
                success: true,
                channel: nlMeta.__x_name,
                wasSubscribed: before,
                isSubscribed: nlMeta.__x_isSubscribedOrOwned
            }});
        }} catch(e) {{
            return JSON.stringify({{error: e.message}});
        }}
    }})()
    """, await_promise=True)
    if isinstance(data, dict) and data.get("error"):
        print(f"Error: {data['error']}")
    else:
        print(f"Unfollowed {data['channel']} (was: {data['wasSubscribed']} -> now: {data['isSubscribed']})")


# ─── Meta AI ──────────────────────────────────────────────────────

async def cmd_ai(message):
    # Meta AI requires DOM-based send — addAndSendMsgToChat silently drops bot messages.
    # Must: open AI chat → type into compose box → press Enter.
    escaped = message.replace("\\", "\\\\").replace("`", "\\`").replace("'", "\\'")
    data = await cdp_eval(f"""
    (async function() {{
        const C = window.require('WAWebCollections');
        const openCmd = window.require('WAWebCmd');
        const aiChat = C.Chat.getModelsArray().find(c => c.__x_id?._serialized === '13135550002@c.us');
        if (!aiChat) return JSON.stringify({{error: 'Meta AI chat not found'}});

        // Open the AI chat
        if (openCmd?.openChatAt) await openCmd.openChatAt(aiChat);
        await new Promise(r => setTimeout(r, 1000));

        // Type into compose box via DOM
        const composeBox = document.querySelector('[contenteditable="true"][data-tab="10"]');
        if (!composeBox) return JSON.stringify({{error: 'Compose box not found — is the AI chat open?'}});

        composeBox.focus();
        document.execCommand('insertText', false, '{escaped}');
        await new Promise(r => setTimeout(r, 300));

        // Press Enter to send
        composeBox.dispatchEvent(new KeyboardEvent('keydown', {{
            key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
        }}));

        await new Promise(r => setTimeout(r, 1000));
        return JSON.stringify({{sent: true, to: 'Meta AI'}});
    }})()
    """, await_promise=True)
    if isinstance(data, dict) and data.get("error"):
        print(f"Error: {data['error']}")
    else:
        print(f"Sent to Meta AI: {message}")


async def cmd_ai_read(n=10):
    data = await cdp_eval(f"""
    (function() {{
        const C = window.require('WAWebCollections');
        const msgs = C.Msg.getModelsArray()
            .filter(m => (m.__x_id?.remote?._serialized || '') === '13135550002@c.us')
            .sort((a, b) => (b.__x_t || 0) - (a.__x_t || 0))
            .slice(0, {n});
        return JSON.stringify(msgs.map(m => {{
            // Meta AI uses rich_response type — text is in __x_richResponse.fragments
            let body = m.__x_body || '';
            if (!body && m.__x_richResponse?.fragments) {{
                body = m.__x_richResponse.fragments
                    .filter(f => f.type === 'Text')
                    .map(f => f.text)
                    .join('\\n');
            }}
            return {{
                body: body.substring(0, 500),
                fromMe: m.__x_id?.fromMe || false,
                t: m.__x_t || 0,
                type: m.__x_type || '?',
                streaming: m.__x_activeBotMsgStreamingInProgress || false
            }};
        }}));
    }})()
    """)
    print(f"Meta AI — last {len(data)} messages:\n")
    for m in reversed(data):
        ts = datetime.fromtimestamp(m["t"]).strftime("%b %d %H:%M") if m["t"] else "?"
        who = "YOU" if m["fromMe"] else "AI"
        streaming = " [streaming...]" if m.get("streaming") else ""
        print(f"  [{ts}] {who}{streaming}: {m['body'][:200]}")


# ─── Main ─────────────────────────────────────────────────────────

async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "chats":
        await cmd_chats()
    elif cmd == "archived":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        await cmd_archived(n)
    elif cmd == "msgs":
        if len(sys.argv) < 3:
            print("Usage: wa.py msgs <chat_name> [N]")
            return
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        await cmd_msgs(sys.argv[2], n)
    elif cmd == "members":
        if len(sys.argv) < 3:
            print("Usage: wa.py members <group_name>")
            return
        await cmd_members(sys.argv[2])
    elif cmd == "send":
        if len(sys.argv) < 4:
            print("Usage: wa.py send <chat_name> <text>")
            return
        await cmd_send(sys.argv[2], " ".join(sys.argv[3:]))
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: wa.py search <query>")
            return
        await cmd_search(sys.argv[2])
    elif cmd == "react":
        if len(sys.argv) < 4:
            print("Usage: wa.py react <chat_name> <emoji>")
            return
        await cmd_react(sys.argv[2], sys.argv[3])
    elif cmd == "starred":
        await cmd_starred()
    elif cmd == "statuses":
        await cmd_statuses()
    elif cmd == "communities":
        await cmd_communities()
    elif cmd == "channels":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        await cmd_channels(n)
    elif cmd == "channel-msgs":
        if len(sys.argv) < 3:
            print("Usage: wa.py channel-msgs <channel_name> [N]")
            return
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        await cmd_channel_msgs(sys.argv[2], n)
    elif cmd == "follow":
        if len(sys.argv) < 3:
            print("Usage: wa.py follow <channel_name>")
            return
        await cmd_follow(sys.argv[2])
    elif cmd == "unfollow":
        if len(sys.argv) < 3:
            print("Usage: wa.py unfollow <channel_name>")
            return
        await cmd_unfollow(sys.argv[2])
    elif cmd == "ai":
        if len(sys.argv) < 3:
            print("Usage: wa.py ai <message>")
            return
        await cmd_ai(" ".join(sys.argv[2:]))
    elif cmd == "ai-read":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        await cmd_ai_read(n)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)

if __name__ == "__main__":
    asyncio.run(main())

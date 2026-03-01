---
id: imessage
name: iMessage
description: Send and read iMessages and SMS from macOS Messages app
icon: icon.svg
color: "#34C759"

website: https://support.apple.com/messages

auth: none
platforms: [macos]
connects_to: imessage

seed:
  # Apple / iMessage
  - id: imessage
    types: [software]
    name: iMessage
    data:
      software_type: service
      url: https://support.apple.com/explore/messages
      launched: "2011"
      platforms: [ios, ipados, macos, watchos, visionos]
      wikidata_id: Q290267
    relationships:
      - role: offered_by
        to: apple

  - id: apple
    types: [organization]
    name: Apple Inc.
    data:
      type: company
      url: https://apple.com
      founded: "1976"
      ticker: AAPL
      exchange: NASDAQ
      wikidata_id: Q312

  # Peter Steinberger (@steipete) — creator of imsg, OpenClaw, gogcli, PSPDFKit
  - id: steipete
    types: [person]
    name: Peter Steinberger
    data:
      nickname: steipete
      location: Vienna, Austria
      url: https://steipete.me
      notes: Prolific open source developer. Creator of PSPDFKit, OpenClaw, imsg, gogcli, and dozens of CLI tools. Built the imsg tool that powers AgentOS iMessage sending.
    relationships:
      - role: claims
        to: steipete-github

  - id: steipete-github
    types: [account]
    name: steipete
    data:
      platform: github
      handle: steipete
      url: https://github.com/steipete
      follower_count: 4500

  - id: imsg-software
    types: [software]
    name: imsg
    data:
      software_type: cli
      url: https://github.com/steipete/imsg
      platforms: [macos]
      pricing: open_source
      launched: "2025"
      notes: Native Swift CLI for sending and reading iMessages. Uses public macOS APIs and AppleScript — no private APIs. Powers AgentOS iMessage send capability.
    relationships:
      - role: created_by
        to: steipete

  - id: openclaw
    types: [software]
    name: OpenClaw
    data:
      software_type: platform
      url: https://openclaw.ai
      platforms: [macos, linux, web]
      pricing: open_source
      notes: Personal AI assistant platform. Runs on your own devices, integrates with WhatsApp, Telegram, Slack, Discord, Teams, Signal, iMessage. 200K+ GitHub stars.
    relationships:
      - role: created_by
        to: steipete

  - id: gogcli
    types: [software]
    name: gogcli
    data:
      software_type: cli
      url: https://github.com/steipete/gogcli
      platforms: [macos, linux, windows]
      pricing: open_source
      launched: "2025"
      notes: Google Workspace CLI — Gmail, Calendar, Drive, Contacts, Tasks, Sheets, Docs from the terminal. JSON-first output. Potential future AgentOS Gmail/Google adapter.
    relationships:
      - role: created_by
        to: steipete

credits:
  - skill: imsg
    relationship: appreciates
    reason: Native Swift CLI by Peter Steinberger (@steipete) that powers message.send. https://github.com/steipete/imsg

database: "~/Library/Messages/chat.db"

requires:
  - name: imsg
    install:
      macos: brew tap steipete/tap && brew install imsg
    url: https://github.com/steipete/imsg
    description: Swift CLI for sending iMessages (used for message.send)

instructions: |
  iMessage stores messages in a local SQLite database.
  - Date format: nanoseconds since macOS epoch (2001-01-01)
  - Convert with: date / 1000000000 + 978307200 → Unix timestamp
  - Phone numbers in E.164 format: +1XXXXXXXXXX
  - Handles can be phone or email
  - Sending uses the imsg CLI (brew tap steipete/tap && brew install imsg)
  - Recipients can be phone numbers (+14155551234) or email addresses
  - Service options: imessage, sms, or auto (tries iMessage first, falls back to SMS)

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

transformers:
  conversation:
    terminology: Chat
    mapping:
      id: .id
      name: .name
      is_group: '.type == "group"'
      updated_at: .updated_at
      _participant_handles: .participant_handles
      
      # Typed reference: extract person from first participant (DMs)
      # Handles are already E.164 format (+12025551234) or email
      participant:
        person:
          phone: 'if (._participant_handles | type == "string") then (._participant_handles | split(",") | .[0] | if (startswith("+")) then . elif test("^[0-9]+$") then "+" + . else null end) else null end'
          email: 'if (._participant_handles | type == "string") then (._participant_handles | split(",") | .[0] | if (contains("@") and (startswith("+") | not)) then . else null end) else null end'
          name: .name

  message:
    terminology: Message
    mapping:
      id: .id
      conversation_id: .conversation_id
      content: .content
      sender: .sender_handle
      is_outgoing: .is_outgoing
      timestamp: .timestamp
      _sender_handle: .sender_handle
      
      # Typed reference: extract sender as person (incoming messages only)
      # Handles are already E.164 format (+12025551234) or email
      from:
        person:
          phone: 'if (.is_outgoing != true and ._sender_handle != null) then (if (._sender_handle | startswith("+")) then ._sender_handle elif (._sender_handle | test("^[0-9]+$")) then "+" + ._sender_handle else null end) else null end'
          email: 'if (.is_outgoing != true and ._sender_handle != null and (._sender_handle | contains("@")) and (._sender_handle | startswith("+") | not)) then ._sender_handle else null end'
          name: .sender

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  conversation.list:
    description: List all iMessage/SMS conversations
    returns: conversation[]
    params:
      limit: { type: integer }
    sql:
      query: |
        SELECT 
          c.ROWID as id,
          COALESCE(c.display_name, c.chat_identifier) as name,
          c.service_name as platform,
          CASE 
            WHEN (SELECT COUNT(*) FROM chat_handle_join chj WHERE chj.chat_id = c.ROWID) > 1 
            THEN 'group' 
            ELSE 'direct' 
          END as type,
          datetime(
            (SELECT MAX(m.date) FROM message m 
             JOIN chat_message_join cmj ON m.ROWID = cmj.message_id 
             WHERE cmj.chat_id = c.ROWID) / 1000000000 + 978307200, 
            'unixepoch'
          ) as updated_at,
          (SELECT GROUP_CONCAT(h.id, ',')
           FROM handle h
           JOIN chat_handle_join chj ON h.ROWID = chj.handle_id
           WHERE chj.chat_id = c.ROWID) as participant_handles
        FROM chat c
        WHERE EXISTS (
          SELECT 1 FROM message m
          JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
          WHERE cmj.chat_id = c.ROWID
        )
        ORDER BY updated_at DESC
        LIMIT :limit
      params:
        limit: '.params.limit // 1000'
      response:
        root: "/"

  conversation.get:
    description: Get a specific conversation with metadata
    returns: conversation
    params:
      id: { type: string, required: true }
    sql:
      query: |
        SELECT 
          c.ROWID as id,
          COALESCE(c.display_name, c.chat_identifier) as name,
          c.service_name as platform,
          CASE 
            WHEN (SELECT COUNT(*) FROM chat_handle_join chj WHERE chj.chat_id = c.ROWID) > 1 
            THEN 'group' 
            ELSE 'direct' 
          END as type,
          datetime(
            (SELECT MAX(m.date) FROM message m 
             JOIN chat_message_join cmj ON m.ROWID = cmj.message_id 
             WHERE cmj.chat_id = c.ROWID) / 1000000000 + 978307200, 
            'unixepoch'
          ) as updated_at,
          (SELECT GROUP_CONCAT(h.id, ',')
           FROM handle h
           JOIN chat_handle_join chj ON h.ROWID = chj.handle_id
           WHERE chj.chat_id = c.ROWID) as participant_handles
        FROM chat c
        WHERE c.ROWID = :id
      params:
        id: .params.id
      response:
        root: "/0"

  message.list:
    description: List messages in a conversation
    returns: message[]
    params:
      conversation_id: { type: string, required: true }
      limit: { type: integer }
    sql:
      query: |
        SELECT 
          m.ROWID as id,
          :conversation_id as conversation_id,
          m.text as content,
          m.is_from_me as is_outgoing,
          CASE m.is_from_me 
            WHEN 1 THEN NULL 
            ELSE h.id 
          END as sender_handle,
          datetime(m.date / 1000000000 + 978307200, 'unixepoch') as timestamp
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        WHERE cmj.chat_id = :conversation_id
          AND m.text IS NOT NULL AND m.text != ''
        ORDER BY m.date DESC
        LIMIT :limit
      params:
        conversation_id: .params.conversation_id
        limit: '.params.limit // 1000'
      response:
        root: "/"

  message.get:
    description: Get a specific message by ID
    returns: message
    params:
      id: { type: string, required: true }
    sql:
      query: |
        SELECT 
          m.ROWID as id,
          c.ROWID as conversation_id,
          m.text as content,
          m.is_from_me as is_outgoing,
          CASE m.is_from_me 
            WHEN 1 THEN NULL 
            ELSE h.id 
          END as sender_handle,
          datetime(m.date / 1000000000 + 978307200, 'unixepoch') as timestamp
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE m.ROWID = :id
      params:
        id: .params.id
      response:
        root: "/0"

  message.search:
    description: Search messages by text content
    returns: message[]
    params:
      query: { type: string, required: true }
      limit: { type: integer }
    sql:
      query: |
        SELECT 
          m.ROWID as id,
          c.ROWID as conversation_id,
          COALESCE(c.display_name, c.chat_identifier) as conversation_name,
          m.text as content,
          m.is_from_me as is_outgoing,
          CASE m.is_from_me 
            WHEN 1 THEN 'Me' 
            ELSE COALESCE(h.id, 'Unknown') 
          END as sender_handle,
          datetime(m.date / 1000000000 + 978307200, 'unixepoch') as timestamp
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE m.text LIKE '%' || :query || '%'
        ORDER BY m.date DESC
        LIMIT :limit
      params:
        query: .params.query
        limit: '.params.limit // 1000'
      response:
        root: "/"

  message.send:
    description: Send an iMessage or SMS to a phone number or email
    returns: void
    params:
      to: { type: string, required: true, description: "Recipient phone number (E.164 like +14155551234) or email address" }
      text: { type: string, required: true, description: "Message body" }
      service: { type: string, default: "imessage", description: "Service: imessage, sms, or auto" }
      file: { type: string, description: "Path to file attachment" }
    command:
      binary: imsg
      args:
        - "send"
        - "--to"
        - "{{params.to}}"
        - "--text"
        - "{{params.text}}"
        - "--service"
        - "{{params.service}}"
        - "--json"
      timeout: 15
---

# iMessage

Send and read iMessages and SMS from the macOS Messages app.

## Requirements

- **macOS only** — Reads from local Messages database, sends via Messages.app
- **Full Disk Access** — System Settings → Privacy & Security → Full Disk Access (for reading)
- **Automation permission** — System Settings → Privacy & Security → Automation → allow Terminal to control Messages.app (for sending)
- **imsg CLI** — `brew tap steipete/tap && brew install imsg` (for sending)

## Sending Messages

Send uses [imsg](https://github.com/steipete/imsg) by [Peter Steinberger](https://github.com/steipete) — a native Swift CLI that talks to Messages.app via public macOS APIs and AppleScript. No private APIs, stable across macOS versions.

Recipients can be:
- Phone numbers in E.164 format: `+14155551234`
- Email addresses registered with Apple ID: `user@example.com`

```bash
# Send via API
curl -X POST http://localhost:3456/use/imessage/message.send \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{"to": "+14155551234", "text": "Hello from AgentOS!"}'
```

## Handles

iMessage handles are already in E.164 format for phone numbers (`+12025551234`) or email addresses.
This enables direct matching with WhatsApp contacts for social graph deduplication.

## Features

- **Send** messages via iMessage or SMS
- **List** all conversations
- **Get** messages from a conversation  
- **Search** across all messages

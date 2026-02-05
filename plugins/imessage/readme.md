---
id: imessage
name: iMessage
description: Read iMessages and SMS from macOS Messages app
icon: icon.svg
color: "#34C759"

website: https://support.apple.com/messages
platform: macos

database: "~/Library/Messages/chat.db"

instructions: |
  iMessage stores messages in a local SQLite database.
  - Date format: nanoseconds since macOS epoch (2001-01-01)
  - Convert with: date / 1000000000 + 978307200 → Unix timestamp
  - Phone numbers in E.164 format: +1XXXXXXXXXX
  - Handles can be phone or email

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
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
      limit: { type: integer, default: 50 }
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
        LIMIT {{params.limit | default: 50}}
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
        WHERE c.ROWID = {{params.id}}
      response:
        root: "/0"

  message.list:
    description: List messages in a conversation
    returns: message[]
    params:
      conversation_id: { type: string, required: true }
      limit: { type: integer, default: 100 }
    sql:
      query: |
        SELECT 
          m.ROWID as id,
          {{params.conversation_id}} as conversation_id,
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
        WHERE cmj.chat_id = {{params.conversation_id}}
          AND m.text IS NOT NULL AND m.text != ''
        ORDER BY m.date DESC
        LIMIT {{params.limit | default: 100}}
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
        WHERE m.ROWID = {{params.id}}
      response:
        root: "/0"

  message.search:
    description: Search messages by text content
    returns: message[]
    params:
      query: { type: string, required: true }
      limit: { type: integer, default: 50 }
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
        WHERE m.text LIKE '%{{params.query}}%'
        ORDER BY m.date DESC
        LIMIT {{params.limit | default: 50}}
      response:
        root: "/"
---

# iMessage

Read iMessages and SMS from the macOS Messages app. Read-only access to message history.

## Requirements

- **macOS only** - Reads from local Messages database
- **Full Disk Access required** - Grant in System Settings → Privacy & Security → Full Disk Access

## Handles

iMessage handles are already in E.164 format for phone numbers (`+12025551234`) or email addresses.
This enables direct matching with WhatsApp contacts for social graph deduplication.

## Features

- List all conversations
- Get messages from a conversation  
- Search across all messages
- Read-only access (no sending)

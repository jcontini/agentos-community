---
id: imessage
name: iMessage
description: Read iMessages and SMS from macOS Messages app
icon: icon.png
tags: [messages, chat]

website: https://support.apple.com/messages
platform: macos

# No auth block = no credentials needed (local database)

database: "~/Library/Messages/chat.db"

instructions: |
  iMessage stores messages in a local SQLite database.
  - Date format: nanoseconds since macOS epoch (2001-01-01)
  - Convert with: date / 1000000000 + 978307200 → Unix timestamp
  - Services: iMessage, SMS, or RCS
  - Phone numbers in E.164 format: +1XXXXXXXXXX
  - Group chats identified by participant count > 1

# Action implementations (merged from mapping.yaml)
actions:
  list_conversations:
    operation: read
    label: "List conversations"
    description: List all conversations
    params:
      limit: { type: number, default: 50 }
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
          (SELECT SUBSTR(m.text, 1, 100)
           FROM message m
           JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
           WHERE cmj.chat_id = c.ROWID AND m.text IS NOT NULL
           ORDER BY m.date DESC LIMIT 1) as last_message_preview
        FROM chat c
        WHERE EXISTS (
          SELECT 1 FROM message m
          JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
          WHERE cmj.chat_id = c.ROWID
        )
        ORDER BY updated_at DESC
        LIMIT {{params.limit | default: 50}}
      response:
        mapping:
          id: "[].id"
          type: "[].type"
          name: "[].name"
          platform: "[].platform"
          updated_at: "[].updated_at"
          connector: "'imessage'"

  get_conversation:
    operation: read
    label: "Get conversation"
    description: Get a specific conversation with participants
    params:
      conversation_id: { type: string, required: true }
    sql:
      query: |
        SELECT 
          c.ROWID as id,
          COALESCE(c.display_name, c.chat_identifier) as name,
          c.service_name as platform,
          c.is_archived,
          (SELECT GROUP_CONCAT(h.id, ', ')
           FROM handle h
           JOIN chat_handle_join chj ON h.ROWID = chj.handle_id
           WHERE chj.chat_id = c.ROWID) as participant_handles,
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
          (SELECT COUNT(*) FROM message m
           JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
           WHERE cmj.chat_id = c.ROWID) as message_count
        FROM chat c
        WHERE c.ROWID = {{params.conversation_id}}
      response:
        mapping:
          id: ".id"
          type: ".type"
          name: ".name"
          platform: ".platform"
          is_archived: ".is_archived"
          updated_at: ".updated_at"
          connector: "'imessage'"

  list:
    operation: read
    label: "List messages"
    description: List messages in a conversation
    params:
      conversation_id: { type: string, required: true }
      limit: { type: number, default: 100 }
    sql:
      query: |
        SELECT 
          m.ROWID as id,
          {{params.conversation_id}} as conversation_id,
          m.text as content,
          'text' as content_type,
          m.is_from_me as is_outgoing,
          CASE m.is_from_me 
            WHEN 1 THEN NULL 
            ELSE h.id 
          END as sender_handle,
          datetime(m.date / 1000000000 + 978307200, 'unixepoch') as timestamp,
          datetime(m.date_delivered / 1000000000 + 978307200, 'unixepoch') as delivered_at,
          datetime(m.date_read / 1000000000 + 978307200, 'unixepoch') as read_at,
          m.is_read,
          m.cache_has_attachments as has_attachments,
          m.reply_to_guid,
          m.thread_originator_guid
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        WHERE cmj.chat_id = {{params.conversation_id}}
          AND m.text IS NOT NULL AND m.text != ''
        ORDER BY m.date DESC
        LIMIT {{params.limit | default: 100}}
      response:
        mapping:
          id: "[].id"
          conversation_id: "[].conversation_id"
          content: "[].content"
          content_type: "[].content_type"
          sender:
            handle: "[].sender_handle"
            is_self: "[].is_outgoing"
          is_outgoing: "[].is_outgoing"
          timestamp: "[].timestamp"
          delivered_at: "[].delivered_at"
          read_at: "[].read_at"
          is_read: "[].is_read"
          reply_to:
            message_id: "[].reply_to_guid"
          thread_id: "[].thread_originator_guid"
          connector: "'imessage'"

  get:
    operation: read
    label: "Get message"
    description: Get a specific message by ID
    params:
      message_id: { type: string, required: true }
    sql:
      query: |
        SELECT 
          m.ROWID as id,
          c.ROWID as conversation_id,
          m.text as content,
          'text' as content_type,
          m.is_from_me as is_outgoing,
          CASE m.is_from_me 
            WHEN 1 THEN NULL 
            ELSE h.id 
          END as sender_handle,
          datetime(m.date / 1000000000 + 978307200, 'unixepoch') as timestamp,
          datetime(m.date_delivered / 1000000000 + 978307200, 'unixepoch') as delivered_at,
          datetime(m.date_read / 1000000000 + 978307200, 'unixepoch') as read_at,
          m.is_read,
          m.cache_has_attachments as has_attachments,
          m.reply_to_guid,
          m.thread_originator_guid
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE m.ROWID = {{params.message_id}}
      response:
        mapping:
          id: ".id"
          conversation_id: ".conversation_id"
          content: ".content"
          content_type: ".content_type"
          sender:
            handle: ".sender_handle"
            is_self: ".is_outgoing"
          is_outgoing: ".is_outgoing"
          timestamp: ".timestamp"
          delivered_at: ".delivered_at"
          read_at: ".read_at"
          is_read: ".is_read"
          reply_to:
            message_id: ".reply_to_guid"
          thread_id: ".thread_originator_guid"
          connector: "'imessage'"

  search:
    operation: read
    label: "Search messages"
    description: Search messages by text content
    params:
      query: { type: string, required: true }
      limit: { type: number, default: 50 }
    sql:
      query: |
        SELECT 
          m.ROWID as id,
          c.ROWID as conversation_id,
          COALESCE(c.display_name, c.chat_identifier) as conversation_name,
          m.text as content,
          'text' as content_type,
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
        mapping:
          id: "[].id"
          conversation_id: "[].conversation_id"
          content: "[].content"
          content_type: "[].content_type"
          sender:
            handle: "[].sender_handle"
            is_self: "[].is_outgoing"
          is_outgoing: "[].is_outgoing"
          timestamp: "[].timestamp"
          connector: "'imessage'"

  get_unread:
    operation: read
    label: "Get unread messages"
    description: Get all unread messages
    params:
      limit: { type: number, default: 50 }
    sql:
      query: |
        SELECT 
          m.ROWID as id,
          c.ROWID as conversation_id,
          COALESCE(c.display_name, c.chat_identifier) as conversation_name,
          m.text as content,
          'text' as content_type,
          h.id as sender_handle,
          datetime(m.date / 1000000000 + 978307200, 'unixepoch') as timestamp
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE m.is_read = 0
          AND m.is_from_me = 0
          AND m.text IS NOT NULL AND m.text != ''
        ORDER BY m.date DESC
        LIMIT {{params.limit | default: 50}}
      response:
        mapping:
          id: "[].id"
          conversation_id: "[].conversation_id"
          content: "[].content"
          content_type: "[].content_type"
          sender:
            handle: "[].sender_handle"
            is_self: "false"
          is_outgoing: "false"
          is_read: "false"
          timestamp: "[].timestamp"
          connector: "'imessage'"

  get_attachments:
    operation: read
    label: "Get attachments"
    description: Get attachments for a message
    params:
      message_id: { type: string, required: true }
    sql:
      query: |
        SELECT 
          a.ROWID as id,
          CASE 
            WHEN a.mime_type LIKE 'image/%' THEN 'image'
            WHEN a.mime_type LIKE 'video/%' THEN 'video'
            WHEN a.mime_type LIKE 'audio/%' THEN 'audio'
            WHEN a.uti = 'com.apple.coreaudio-format' THEN 'voice_note'
            WHEN a.is_sticker = 1 THEN 'sticker'
            ELSE 'file'
          END as type,
          a.filename as local_path,
          a.transfer_name as filename,
          a.mime_type,
          a.uti,
          a.total_bytes as size_bytes,
          a.is_sticker
        FROM attachment a
        JOIN message_attachment_join maj ON a.ROWID = maj.attachment_id
        WHERE maj.message_id = {{params.message_id}}
      response:
        mapping:
          id: "[].id"
          type: "[].type"
          filename: "[].filename"
          local_path: "[].local_path"
          mime_type: "[].mime_type"
          size_bytes: "[].size_bytes"
---

# iMessage

Read iMessages and SMS from the macOS Messages app. Read-only access to message history.

## Requirements

- **macOS only** - Reads from local Messages database
- **Full Disk Access required** - macOS does NOT auto-prompt for this permission

### Granting Full Disk Access

1. Open **System Settings → Privacy & Security → Full Disk Access**
2. Click **+** and add the app
3. Restart the app

## Database Structure

### Key Tables

| Table | Description |
|-------|-------------|
| `message` | Individual messages with text, timestamps, flags |
| `chat` | Conversations (1:1 or group) |
| `handle` | Phone numbers and email addresses |
| `attachment` | Media files attached to messages |
| `chat_message_join` | Links messages to chats |
| `chat_handle_join` | Links participants to chats |
| `message_attachment_join` | Links attachments to messages |

### Date Conversion

iMessage uses nanoseconds since macOS epoch (2001-01-01):

```sql
datetime(date / 1000000000 + 978307200, 'unixepoch') as timestamp
```

### Conversation Types

- **Direct (1:1)**: Single participant in `chat_handle_join`
- **Group**: Multiple participants in `chat_handle_join`
- **Service**: `iMessage`, `SMS`, or `RCS` in `service_name`

## Features

- List all conversations with last message preview
- Get messages from a specific conversation
- Search across all messages
- Get participants in a conversation
- Read-only access (no sending)

## Notes

- Phone numbers stored as `+1XXXXXXXXXX` (E.164 format)
- Media-only messages have NULL text content
- `is_from_me = 1` indicates outgoing messages
- Group chats have `display_name` set (usually)

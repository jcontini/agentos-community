---
id: whatsapp
name: WhatsApp
description: Read WhatsApp messages from local macOS database
icon: icon.svg
color: "#2CD46B"
tags: [messages, chat, conversations]

website: https://www.whatsapp.com/
platform: macos

# No auth block = no credentials needed (local database)

database: "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite"

instructions: |
  WhatsApp stores messages in a local SQLite database.
  - Date format: seconds since macOS epoch (2001-01-01)
  - Convert with: date + 978307200 → Unix timestamp
  - JID format: PHONENUMBER@s.whatsapp.net (DM) or ID@g.us (group)
  - Session types: 0 = DM, 1 = group, 3 = broadcast/status

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  conversation:
    terminology: Chat
    mapping:
      id: .id
      name: .name
      is_group: ".type == 'group'"
      unread_count: .unread_count
      updated_at: .updated_at
      _contact_jid: .contact_jid

  message:
    terminology: Message
    mapping:
      id: .id
      conversation_id: .conversation_id
      content: .content
      sender: .sender_name
      is_outgoing: .is_outgoing
      timestamp: .timestamp
      _reply_to_id: .reply_to_id

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  conversation.list:
    description: List all WhatsApp conversations
    returns: conversation[]
    params:
      limit: { type: integer, default: 50 }
    sql:
      query: |
        SELECT 
          cs.Z_PK as id,
          cs.ZPARTNERNAME as name,
          CASE cs.ZSESSIONTYPE 
            WHEN 1 THEN 'group' 
            ELSE 'direct' 
          END as type,
          cs.ZUNREADCOUNT as unread_count,
          datetime(cs.ZLASTMESSAGEDATE + 978307200, 'unixepoch') as updated_at,
          cs.ZCONTACTJID as contact_jid
        FROM ZWACHATSESSION cs
        WHERE cs.ZREMOVED = 0
          AND cs.ZSESSIONTYPE IN (0, 1)
        ORDER BY cs.ZLASTMESSAGEDATE DESC
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
          cs.Z_PK as id,
          cs.ZPARTNERNAME as name,
          CASE cs.ZSESSIONTYPE 
            WHEN 1 THEN 'group' 
            ELSE 'direct' 
          END as type,
          cs.ZUNREADCOUNT as unread_count,
          cs.ZARCHIVED as is_archived,
          datetime(cs.ZLASTMESSAGEDATE + 978307200, 'unixepoch') as updated_at,
          cs.ZCONTACTJID as contact_jid,
          (SELECT COUNT(*) FROM ZWAMESSAGE m WHERE m.ZCHATSESSION = cs.Z_PK) as message_count
        FROM ZWACHATSESSION cs
        WHERE cs.Z_PK = {{params.id}}
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
          m.Z_PK as id,
          {{params.conversation_id}} as conversation_id,
          m.ZTEXT as content,
          m.ZISFROMME as is_outgoing,
          CASE m.ZISFROMME 
            WHEN 1 THEN NULL 
            ELSE m.ZFROMJID 
          END as sender_handle,
          m.ZPUSHNAME as sender_name,
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch') as timestamp,
          m.ZSTARRED as is_starred,
          m.ZPARENTMESSAGE as reply_to_id
        FROM ZWAMESSAGE m
        WHERE m.ZCHATSESSION = {{params.conversation_id}}
          AND m.ZTEXT IS NOT NULL AND m.ZTEXT != ''
        ORDER BY m.ZMESSAGEDATE DESC
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
          m.Z_PK as id,
          m.ZCHATSESSION as conversation_id,
          m.ZTEXT as content,
          m.ZISFROMME as is_outgoing,
          CASE m.ZISFROMME 
            WHEN 1 THEN NULL 
            ELSE m.ZFROMJID 
          END as sender_handle,
          m.ZPUSHNAME as sender_name,
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch') as timestamp,
          m.ZSTARRED as is_starred,
          m.ZPARENTMESSAGE as reply_to_id
        FROM ZWAMESSAGE m
        WHERE m.Z_PK = {{params.id}}
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
          m.Z_PK as id,
          m.ZCHATSESSION as conversation_id,
          cs.ZPARTNERNAME as conversation_name,
          m.ZTEXT as content,
          m.ZISFROMME as is_outgoing,
          CASE m.ZISFROMME 
            WHEN 1 THEN 'Me' 
            ELSE COALESCE(m.ZPUSHNAME, m.ZFROMJID) 
          END as sender_name,
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch') as timestamp
        FROM ZWAMESSAGE m
        LEFT JOIN ZWACHATSESSION cs ON m.ZCHATSESSION = cs.Z_PK
        WHERE m.ZTEXT LIKE '%{{params.query}}%'
        ORDER BY m.ZMESSAGEDATE DESC
        LIMIT {{params.limit | default: 50}}
      response:
        root: "/"

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

utilities:
  get_unread:
    description: Get all unread messages
    params:
      limit: { type: integer, default: 50 }
    returns:
      id: string
      conversation_id: string
      content: string
      sender_name: string
      timestamp: string
    sql:
      query: |
        SELECT 
          m.Z_PK as id,
          m.ZCHATSESSION as conversation_id,
          cs.ZPARTNERNAME as conversation_name,
          m.ZTEXT as content,
          COALESCE(m.ZPUSHNAME, m.ZFROMJID) as sender_name,
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch') as timestamp
        FROM ZWAMESSAGE m
        JOIN ZWACHATSESSION cs ON m.ZCHATSESSION = cs.Z_PK
        WHERE cs.ZUNREADCOUNT > 0
          AND m.ZISFROMME = 0
          AND m.ZTEXT IS NOT NULL AND m.ZTEXT != ''
        ORDER BY m.ZMESSAGEDATE DESC
        LIMIT {{params.limit | default: 50}}
      response:
        root: "/"

  get_participants:
    description: Get participants in a group conversation
    params:
      conversation_id: { type: string, required: true }
    returns:
      id: string
      handle: string
      name: string
      is_admin: boolean
    sql:
      query: |
        SELECT 
          gm.Z_PK as id,
          gm.ZMEMBERJID as handle,
          COALESCE(gm.ZCONTACTNAME, gm.ZFIRSTNAME, gm.ZMEMBERJID) as name,
          gm.ZISADMIN as is_admin,
          gm.ZISACTIVE as is_active
        FROM ZWAGROUPMEMBER gm
        WHERE gm.ZCHATSESSION = {{params.conversation_id}}
      response:
        root: "/"
---

# WhatsApp

Read WhatsApp messages from the local macOS database. Read-only access to message history.

## Requirements

- **macOS only** - Reads from local WhatsApp database
- **WhatsApp desktop app** - Must be installed and logged in

## Database Structure

### Key Tables

| Table | Description |
|-------|-------------|
| `ZWACHATSESSION` | Conversations (chats and groups) |
| `ZWAMESSAGE` | Individual messages |
| `ZWAGROUPMEMBER` | Group participants |
| `ZWAGROUPINFO` | Group metadata |
| `ZWAMEDIAITEM` | Media attachments |

### Session Types

| Value | Type |
|-------|------|
| 0 | Direct message (1:1) |
| 1 | Group chat |
| 3 | Broadcast/Status |

### Date Conversion

WhatsApp uses seconds since macOS epoch (2001-01-01):

```sql
datetime(ZMESSAGEDATE + 978307200, 'unixepoch') as timestamp
```

### JID Format

- DM: `12125551234@s.whatsapp.net`
- Group: `1234567890-1602721391@g.us`

## Features

- List all conversations
- Get messages from a specific conversation
- Search across all messages
- Get group participants
- Read-only access (no sending)

## Notes

- `ZISFROMME = 1` indicates outgoing messages
- `ZFROMJID` contains sender JID for incoming group messages
- `ZPUSHNAME` contains sender's display name
- Media messages may have NULL text content

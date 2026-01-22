---
id: whatsapp
name: WhatsApp
description: Read WhatsApp messages from local macOS database
icon: icon.svg
color: "#25D366"
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

# Action implementations (merged from mapping.yaml)
actions:
  list_conversations:
    operation: read
    label: "List conversations"
    description: List all WhatsApp conversations
    params:
      limit: { type: number, default: 50 }
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
          AND cs.ZSESSIONTYPE IN (0, 1)  -- DM or group, exclude broadcasts
        ORDER BY cs.ZLASTMESSAGEDATE DESC
        LIMIT {{params.limit | default: 50}}
      response:
        mapping:
          id: "[].id"
          type: "[].type"
          name: "[].name"
          unread_count: "[].unread_count"
          updated_at: "[].updated_at"
          contact_jid: "[].contact_jid"
          platform: "'whatsapp'"
          connector: "'whatsapp'"

  get_conversation:
    operation: read
    label: "Get conversation"
    description: Get a specific conversation with metadata
    params:
      conversation_id: { type: string, required: true }
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
        WHERE cs.Z_PK = {{params.conversation_id}}
      response:
        mapping:
          id: ".id"
          type: ".type"
          name: ".name"
          unread_count: ".unread_count"
          is_archived: ".is_archived"
          updated_at: ".updated_at"
          platform: "'whatsapp'"
          connector: "'whatsapp'"

  get_participants:
    operation: read
    label: "Get participants"
    description: Get participants in a group conversation
    params:
      conversation_id: { type: string, required: true }
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
        mapping:
          id: "[].id"
          type: "'user'"
          handle: "[].handle"
          name: "[].name"

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
          m.Z_PK as id,
          {{params.conversation_id}} as conversation_id,
          m.ZTEXT as content,
          'text' as content_type,
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
        mapping:
          id: "[].id"
          conversation_id: "[].conversation_id"
          content: "[].content"
          content_type: "[].content_type"
          sender:
            handle: "[].sender_handle"
            name: "[].sender_name"
            is_self: "[].is_outgoing"
          is_outgoing: "[].is_outgoing"
          timestamp: "[].timestamp"
          reply_to:
            message_id: "[].reply_to_id"
          connector: "'whatsapp'"

  get:
    operation: read
    label: "Get message"
    description: Get a specific message by ID
    params:
      message_id: { type: string, required: true }
    sql:
      query: |
        SELECT 
          m.Z_PK as id,
          m.ZCHATSESSION as conversation_id,
          m.ZTEXT as content,
          'text' as content_type,
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
        WHERE m.Z_PK = {{params.message_id}}
      response:
        mapping:
          id: ".id"
          conversation_id: ".conversation_id"
          content: ".content"
          content_type: ".content_type"
          sender:
            handle: ".sender_handle"
            name: ".sender_name"
            is_self: ".is_outgoing"
          is_outgoing: ".is_outgoing"
          timestamp: ".timestamp"
          reply_to:
            message_id: ".reply_to_id"
          connector: "'whatsapp'"

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
          m.Z_PK as id,
          m.ZCHATSESSION as conversation_id,
          cs.ZPARTNERNAME as conversation_name,
          m.ZTEXT as content,
          'text' as content_type,
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
        mapping:
          id: "[].id"
          conversation_id: "[].conversation_id"
          content: "[].content"
          content_type: "[].content_type"
          sender:
            name: "[].sender_name"
            is_self: "[].is_outgoing"
          is_outgoing: "[].is_outgoing"
          timestamp: "[].timestamp"
          connector: "'whatsapp'"

  get_unread:
    operation: read
    label: "Get unread messages"
    description: Get all unread messages
    params:
      limit: { type: number, default: 50 }
    sql:
      query: |
        SELECT 
          m.Z_PK as id,
          m.ZCHATSESSION as conversation_id,
          cs.ZPARTNERNAME as conversation_name,
          m.ZTEXT as content,
          'text' as content_type,
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
        mapping:
          id: "[].id"
          conversation_id: "[].conversation_id"
          content: "[].content"
          content_type: "[].content_type"
          sender:
            name: "[].sender_name"
            is_self: "false"
          is_outgoing: "false"
          is_read: "false"
          timestamp: "[].timestamp"
          connector: "'whatsapp'"

  get_profile_photo:
    # Chained executor: SQL lookup contact → ls for photo file → SQL to build response
    - operation: read
      sql:
        database: "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ContactsV2.sqlite"
        query: |
          SELECT 
            COALESCE(c.ZFULLNAME, '') as name, 
            COALESCE(REPLACE(c.ZLID, '@lid', ''), '') as lid
          FROM (SELECT 1) d
          LEFT JOIN ZWAADDRESSBOOKCONTACT c 
            ON c.ZPHONENUMBER LIKE '%' || substr('{{params.phone}}', -10) || '%'
          LIMIT 1
      as: contact
    
    - operation: read
      command:
        binary: /bin/bash
        args:
          - "-c"
          - "lid='{{contact[0].lid}}'; dir=\"$HOME/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/Media/Profile\"; ls \"$dir/$lid-\"*.jpg 2>/dev/null | head -1 || ls \"$dir/$lid-\"*.thumb 2>/dev/null | head -1"
      as: photo
    
    - operation: read
      sql:
        database: ":memory:"
        query: |
          SELECT 
            CASE WHEN '{{contact[0].lid}}' NOT IN ('', 'null', 'undefined') THEN '{{contact[0].name}}' ELSE NULL END as name,
            CASE WHEN '{{contact[0].lid}}' NOT IN ('', 'null', 'undefined') THEN '{{contact[0].lid}}' ELSE NULL END as lid,
            CASE 
              WHEN '{{contact[0].lid}}' IN ('', 'null', 'undefined') THEN NULL
              WHEN trim('{{photo}}') != '' THEN trim('{{photo}}')
              ELSE NULL
            END as path,
            CASE 
              WHEN '{{contact[0].lid}}' IN ('', 'null', 'undefined') THEN NULL
              WHEN trim('{{photo}}') LIKE '%.jpg' THEN 'hires'
              WHEN trim('{{photo}}') LIKE '%.thumb' THEN 'thumb'
              ELSE NULL
            END as size,
            CASE 
              WHEN '{{contact[0].lid}}' IN ('', 'null', 'undefined') THEN 'contact_not_on_whatsapp'
              WHEN trim('{{photo}}') = '' THEN 'no_photo_set'
              ELSE NULL
            END as reason
      response:
        mapping:
          name: ".name"
          lid: ".lid"
          path: ".path"
          size: ".size"
          reason: ".reason"
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

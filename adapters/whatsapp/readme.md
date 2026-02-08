---
id: whatsapp
name: WhatsApp
description: Read WhatsApp messages from local macOS database
icon: icon.svg
color: "#2CD46B"

website: https://www.whatsapp.com/

auth: none

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
  person:
    terminology: Contact
    mapping:
      id: .jid
      name: '.real_name // .contact_name // .display_name // .phone // .jid'
      phone: '.phone // (.jid | split("@") | .[0] | if startswith("+") then . else "+" + . end)'
      nickname: .username
      notes: .about
      
      # Display fields for views
      avatar.path: .profile_photo
      
      # Typed reference: creates image entity for avatar
      avatar:
        image:
          path: .profile_photo

  conversation:
    terminology: Chat
    mapping:
      id: .id
      name: .name
      is_group: '.type == "group"'
      unread_count: .unread_count
      updated_at: .updated_at
      _contact_jid: .contact_jid
      
      # Typed reference: extract person from conversation partner (DMs only)
      # JID format: "12125551234@s.whatsapp.net" → phone: "+12125551234"
      participant:
        person:
          phone: 'if (._contact_jid | type == "string" and endswith("@s.whatsapp.net")) then (._contact_jid | split("@") | .[0] | "+" + .) else null end'
          name: .name

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
      _sender_handle: .sender_handle
      
      # Typed reference: extract sender as person (incoming messages only)
      # JID format: "12125551234@s.whatsapp.net" → phone: "+12125551234"
      from:
        person:
          phone: 'if (.is_outgoing != true and ._sender_handle != null and (._sender_handle | type == "string") and (._sender_handle | endswith("@s.whatsapp.net"))) then (._sender_handle | split("@") | .[0] | "+" + .) else null end'
          name: .sender

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  person.list:
    description: Get all WhatsApp contacts with profile info
    returns: person[]
    params:
      limit: { type: integer, default: 500 }
    sql:
      attach:
        contacts: '"~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ContactsV2.sqlite"'
      query: |
        SELECT DISTINCT
          -- Identity
          cs.ZCONTACTJID as jid,
          c.ZPHONENUMBER as phone,
          
          -- Names (priority: push > contact > partner)
          pn.ZPUSHNAME as real_name,
          c.ZFULLNAME as contact_name,
          cs.ZPARTNERNAME as display_name,
          
          -- Rich data
          c.ZABOUTTEXT as about,
          c.ZUSERNAME as username,
          pp.ZPATH as profile_photo
          
        FROM ZWACHATSESSION cs
        LEFT JOIN contacts.ZWAADDRESSBOOKCONTACT c ON (
          cs.ZCONTACTJID = c.ZWHATSAPPID OR 
          cs.ZCONTACTJID = c.ZLID
        )
        LEFT JOIN ZWAPROFILEPUSHNAME pn ON cs.ZCONTACTJID = pn.ZJID
        LEFT JOIN ZWAPROFILEPICTUREITEM pp ON cs.ZCONTACTJID = pp.ZJID
        WHERE cs.ZSESSIONTYPE = 0 
          AND cs.ZREMOVED = 0
          AND cs.ZCONTACTJID IS NOT NULL
        ORDER BY cs.ZLASTMESSAGEDATE DESC
        LIMIT :limit
      params:
        limit: '.params.limit // 500'
      response:
        root: "/"

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
        LIMIT :limit
      params:
        limit: '.params.limit // 50'
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
        WHERE cs.Z_PK = :id
      params:
        id: .params.id
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
          :conversation_id as conversation_id,
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
        WHERE m.ZCHATSESSION = :conversation_id
          AND m.ZTEXT IS NOT NULL AND m.ZTEXT != ''
        ORDER BY m.ZMESSAGEDATE DESC
        LIMIT :limit
      params:
        conversation_id: .params.conversation_id
        limit: '.params.limit // 100'
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
        WHERE m.Z_PK = :id
      params:
        id: .params.id
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
        WHERE m.ZTEXT LIKE '%' || :query || '%'
        ORDER BY m.ZMESSAGEDATE DESC
        LIMIT :limit
      params:
        query: .params.query
        limit: '.params.limit // 50'
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
        LIMIT :limit
      params:
        limit: '.params.limit // 50'
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
        WHERE gm.ZCHATSESSION = :conversation_id
      params:
        conversation_id: .params.conversation_id
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

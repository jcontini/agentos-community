---
id: whatsapp
name: WhatsApp
description: Read WhatsApp messages from local macOS database
category: communication
icon: https://cdn.simpleicons.org/whatsapp
color: "#25D366"
platform: macos
protocol: shell

requires:
  - sqlite3  # Pre-installed on macOS

actions:
  list_conversations:
    description: List recent WhatsApp conversations
    params:
      limit:
        type: number
        default: 20
        description: Number of conversations to return
    run: |
      sqlite3 -header -separator ' | ' ~/Library/Group\ Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite << 'SQL'
      SELECT 
          cs.ZPARTNERNAME as contact,
          CASE cs.ZSESSIONTYPE WHEN 1 THEN 'group' ELSE 'dm' END as type,
          cs.ZUNREADCOUNT as unread,
          datetime(cs.ZLASTMESSAGEDATE + 978307200, 'unixepoch', 'localtime') as last_message_date,
          SUBSTR(cs.ZLASTMESSAGETEXT, 1, 50) as preview
      FROM ZWACHATSESSION cs
      WHERE cs.ZREMOVED = 0
      ORDER BY cs.ZLASTMESSAGEDATE DESC
      LIMIT ${PARAM_LIMIT:-20};
      SQL

  list_messages:
    description: Get messages from a conversation or all recent messages
    params:
      contact:
        type: string
        description: Contact name or phone number to filter by
      days:
        type: number
        description: Only messages from last N days
      limit:
        type: number
        default: 30
        description: Max messages to return
    run: |
      WHERE_CLAUSE="WHERE m.ZTEXT IS NOT NULL AND m.ZTEXT != ''"
      if [ -n "$PARAM_CONTACT" ]; then
        WHERE_CLAUSE="$WHERE_CLAUSE AND (cs.ZPARTNERNAME LIKE '%$PARAM_CONTACT%' OR cs.ZCONTACTJID LIKE '%$PARAM_CONTACT%')"
      fi
      if [ -n "$PARAM_DAYS" ]; then
        WHERE_CLAUSE="$WHERE_CLAUSE AND m.ZMESSAGEDATE + 978307200 >= CAST(strftime('%s', 'now', '-$PARAM_DAYS days') AS INTEGER)"
      fi
      
      sqlite3 -header -separator ' | ' ~/Library/Group\ Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite << SQL
      SELECT 
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch', 'localtime') as date,
          CASE WHEN cs.ZSESSIONTYPE = 1 THEN cs.ZPARTNERNAME ELSE '' END as group_name,
          CASE 
            WHEN m.ZISFROMME = 1 THEN 'Me'
            WHEN cs.ZSESSIONTYPE != 1 THEN cs.ZPARTNERNAME
            ELSE COALESCE(ppn.ZPUSHNAME, cs.ZPARTNERNAME)
          END as sender,
          m.ZTEXT as message
      FROM ZWAMESSAGE m
      LEFT JOIN ZWACHATSESSION cs ON m.ZCHATSESSION = cs.Z_PK
      LEFT JOIN ZWAGROUPMEMBER gm ON m.ZGROUPMEMBER = gm.Z_PK
      LEFT JOIN ZWAPROFILEPUSHNAME ppn ON gm.ZMEMBERJID = ppn.ZJID
      $WHERE_CLAUSE
      ORDER BY m.ZMESSAGEDATE DESC
      LIMIT ${PARAM_LIMIT:-30};
      SQL

  get_unread:
    description: Get all unread messages
    run: |
      sqlite3 -header -separator ' | ' ~/Library/Group\ Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite << 'SQL'
      SELECT 
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch', 'localtime') as date,
          CASE WHEN cs.ZSESSIONTYPE = 1 THEN cs.ZPARTNERNAME ELSE '' END as group_name,
          CASE 
            WHEN cs.ZSESSIONTYPE != 1 THEN cs.ZPARTNERNAME
            ELSE COALESCE(ppn.ZPUSHNAME, cs.ZPARTNERNAME)
          END as sender,
          m.ZTEXT as message
      FROM ZWAMESSAGE m
      JOIN ZWACHATSESSION cs ON m.ZCHATSESSION = cs.Z_PK
      LEFT JOIN ZWAGROUPMEMBER gm ON m.ZGROUPMEMBER = gm.Z_PK
      LEFT JOIN ZWAPROFILEPUSHNAME ppn ON gm.ZMEMBERJID = ppn.ZJID
      WHERE cs.ZUNREADCOUNT > 0
        AND m.ZISFROMME = 0
        AND m.ZTEXT IS NOT NULL AND m.ZTEXT != ''
      ORDER BY m.ZMESSAGEDATE DESC;
      SQL

  search:
    description: Search messages by text content
    params:
      query:
        type: string
        required: true
        description: Text to search for in messages
      limit:
        type: number
        default: 20
        description: Max results to return
    run: |
      sqlite3 -header -separator ' | ' ~/Library/Group\ Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite << SQL
      SELECT 
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch', 'localtime') as date,
          CASE WHEN cs.ZSESSIONTYPE = 1 THEN cs.ZPARTNERNAME ELSE '' END as group_name,
          CASE 
            WHEN m.ZISFROMME = 1 THEN 'Me'
            WHEN cs.ZSESSIONTYPE != 1 THEN cs.ZPARTNERNAME
            ELSE COALESCE(ppn.ZPUSHNAME, cs.ZPARTNERNAME)
          END as sender,
          m.ZTEXT as message
      FROM ZWAMESSAGE m
      LEFT JOIN ZWACHATSESSION cs ON m.ZCHATSESSION = cs.Z_PK
      LEFT JOIN ZWAGROUPMEMBER gm ON m.ZGROUPMEMBER = gm.Z_PK
      LEFT JOIN ZWAPROFILEPUSHNAME ppn ON gm.ZMEMBERJID = ppn.ZJID
      WHERE m.ZTEXT LIKE '%$PARAM_QUERY%'
      ORDER BY m.ZMESSAGEDATE DESC
      LIMIT ${PARAM_LIMIT:-20};
      SQL

  get_today:
    description: Get all messages from today
    run: |
      sqlite3 -header -separator ' | ' ~/Library/Group\ Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite << 'SQL'
      SELECT 
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch', 'localtime') as date,
          CASE WHEN cs.ZSESSIONTYPE = 1 THEN cs.ZPARTNERNAME ELSE '' END as group_name,
          CASE 
            WHEN m.ZISFROMME = 1 THEN 'Me'
            WHEN cs.ZSESSIONTYPE != 1 THEN cs.ZPARTNERNAME
            ELSE COALESCE(ppn.ZPUSHNAME, cs.ZPARTNERNAME)
          END as sender,
          m.ZTEXT as message
      FROM ZWAMESSAGE m
      LEFT JOIN ZWACHATSESSION cs ON m.ZCHATSESSION = cs.Z_PK
      LEFT JOIN ZWAGROUPMEMBER gm ON m.ZGROUPMEMBER = gm.Z_PK
      LEFT JOIN ZWAPROFILEPUSHNAME ppn ON gm.ZMEMBERJID = ppn.ZJID
      WHERE m.ZMESSAGEDATE + 978307200 >= CAST(strftime('%s', 'now', 'start of day', 'localtime') AS INTEGER)
        AND m.ZTEXT IS NOT NULL AND m.ZTEXT != ''
      ORDER BY m.ZMESSAGEDATE DESC;
      SQL
---

# WhatsApp

Read WhatsApp messages from the local macOS database. This is read-only access to your message history.

## Requirements

- **macOS only** - Reads from local WhatsApp database
- **WhatsApp desktop app** - Must be installed and logged in

## Tools

### list_conversations
List recent WhatsApp conversations with preview.

**Parameters:**
- `limit` (optional): Number of conversations, default 20

**Example:**
```
use-plugin(plugin: "whatsapp", tool: "list_conversations")
use-plugin(plugin: "whatsapp", tool: "list_conversations", params: {limit: 10})
```

### list_messages
Get messages, optionally filtered by contact or time range.

**Parameters:**
- `contact` (optional): Filter by contact name or phone number
- `days` (optional): Only messages from last N days
- `limit` (optional): Max messages, default 30

**Examples:**
```
use-plugin(plugin: "whatsapp", tool: "list_messages")
use-plugin(plugin: "whatsapp", tool: "list_messages", params: {contact: "Mom"})
use-plugin(plugin: "whatsapp", tool: "list_messages", params: {days: 7, limit: 50})
```

### get_unread
Get all unread messages across all conversations.

**Example:**
```
use-plugin(plugin: "whatsapp", tool: "get_unread")
```

### search
Search message content.

**Parameters:**
- `query` (required): Text to search for
- `limit` (optional): Max results, default 20

**Example:**
```
use-plugin(plugin: "whatsapp", tool: "search", params: {query: "dinner"})
```

### get_today
Get all messages from today.

**Example:**
```
use-plugin(plugin: "whatsapp", tool: "get_today")
```

## Notes

- This is **read-only** - you cannot send messages through this plugin
- Group chats show sender names in the `sender` field
- Phone numbers in the database use format like `13125551234` (no + prefix)
- Messages are returned newest first
- Media messages (images, videos) won't have text content

## Database Details

- **Location:** `~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite`
- **Date format:** Seconds since macOS epoch (2001-01-01) - converted automatically
- **JID format:** `PHONENUMBER@s.whatsapp.net`

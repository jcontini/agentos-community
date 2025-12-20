---
id: imessage
name: iMessage
description: Read iMessages and SMS from macOS Messages app
icon: https://upload.wikimedia.org/wikipedia/commons/thumb/5/51/IMessage_logo.svg/1200px-IMessage_logo.svg.png
color: "#34C759"
platform: macos

tags: [text messages, iMessages, SMS]

requires:
  - sqlite3  # Pre-installed on macOS

permissions:
  - full_disk_access

actions:
  get_conversations:
    readonly: true
    description: List recent iMessage/SMS conversations
    params:
      limit:
        type: number
        default: 20
        description: Number of conversations to return
    run: |
      DB="$HOME/Library/Messages/chat.db"
      if [ ! -r "$DB" ]; then
        echo "Error: Cannot read iMessage database. agentOS needs Full Disk Access." >&2
        echo "Fix: System Settings → Privacy & Security → Full Disk Access → Enable agentOS" >&2
        exit 1
      fi
      sqlite3 -header -separator ' | ' "$DB" << SQL
      SELECT 
          c.ROWID as id,
          COALESCE(c.display_name, c.chat_identifier) as contact,
          c.service_name as service,
          (SELECT datetime(MAX(m.date)/1000000000 + 978307200, 'unixepoch', 'localtime')
           FROM message m
           JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
           WHERE cmj.chat_id = c.ROWID) as last_message,
          (SELECT SUBSTR(m.text, 1, 50)
           FROM message m
           JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
           WHERE cmj.chat_id = c.ROWID AND m.text IS NOT NULL
           ORDER BY m.date DESC LIMIT 1) as preview
      FROM chat c
      WHERE EXISTS (
          SELECT 1 FROM message m
          JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
          WHERE cmj.chat_id = c.ROWID
      )
      ORDER BY last_message DESC
      LIMIT ${PARAM_LIMIT:-20};
      SQL

  get_messages:
    readonly: true
    description: Get messages from a conversation or all recent messages
    params:
      contact:
        type: string
        description: Phone number or email to filter by (partial match)
      days:
        type: number
        description: Only messages from last N days
      limit:
        type: number
        default: 30
        description: Max messages to return
    run: |
      DB="$HOME/Library/Messages/chat.db"
      if [ ! -r "$DB" ]; then
        echo "Error: Cannot read iMessage database. agentOS needs Full Disk Access." >&2
        echo "Fix: System Settings → Privacy & Security → Full Disk Access → Enable agentOS" >&2
        exit 1
      fi
      WHERE_CLAUSE="WHERE m.text IS NOT NULL AND m.text != ''"
      if [ -n "$PARAM_CONTACT" ]; then
        WHERE_CLAUSE="$WHERE_CLAUSE AND h.id LIKE '%$PARAM_CONTACT%'"
      fi
      if [ -n "$PARAM_DAYS" ]; then
        WHERE_CLAUSE="$WHERE_CLAUSE AND m.date/1000000000 + 978307200 >= CAST(strftime('%s', 'now', '-$PARAM_DAYS days') AS INTEGER)"
      fi
      
      sqlite3 -header -separator ' | ' "$DB" << SQL
      SELECT 
          datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as date,
          CASE WHEN c.display_name IS NOT NULL THEN c.display_name ELSE '' END as group_name,
          CASE m.is_from_me WHEN 1 THEN 'Me' ELSE COALESCE(h.id, 'Unknown') END as sender,
          m.text as message
      FROM message m
      LEFT JOIN handle h ON m.handle_id = h.ROWID
      LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
      LEFT JOIN chat c ON cmj.chat_id = c.ROWID
      $WHERE_CLAUSE
      ORDER BY m.date DESC
      LIMIT ${PARAM_LIMIT:-30};
      SQL

  get_unread:
    readonly: true
    description: Get all unread messages
    run: |
      DB="$HOME/Library/Messages/chat.db"
      if [ ! -r "$DB" ]; then
        echo "Error: Cannot read iMessage database. agentOS needs Full Disk Access." >&2
        echo "Fix: System Settings → Privacy & Security → Full Disk Access → Enable agentOS" >&2
        exit 1
      fi
      sqlite3 -header -separator ' | ' "$DB" << 'SQL'
      SELECT 
          datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as date,
          CASE WHEN c.display_name IS NOT NULL THEN c.display_name ELSE '' END as group_name,
          COALESCE(h.id, 'Unknown') as sender,
          m.text as message
      FROM message m
      LEFT JOIN handle h ON m.handle_id = h.ROWID
      LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
      LEFT JOIN chat c ON cmj.chat_id = c.ROWID
      WHERE m.is_read = 0
        AND m.is_from_me = 0
        AND m.text IS NOT NULL AND m.text != ''
      ORDER BY m.date DESC;
      SQL

  search:
    readonly: true
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
      DB="$HOME/Library/Messages/chat.db"
      if [ ! -r "$DB" ]; then
        echo "Error: Cannot read iMessage database. agentOS needs Full Disk Access." >&2
        echo "Fix: System Settings → Privacy & Security → Full Disk Access → Enable agentOS" >&2
        exit 1
      fi
      sqlite3 -header -separator ' | ' "$DB" << SQL
      SELECT 
          datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as date,
          CASE WHEN c.display_name IS NOT NULL THEN c.display_name ELSE '' END as group_name,
          CASE m.is_from_me WHEN 1 THEN 'Me' ELSE COALESCE(h.id, 'Unknown') END as sender,
          m.text as message
      FROM message m
      LEFT JOIN handle h ON m.handle_id = h.ROWID
      LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
      LEFT JOIN chat c ON cmj.chat_id = c.ROWID
      WHERE m.text LIKE '%$PARAM_QUERY%'
      ORDER BY m.date DESC
      LIMIT ${PARAM_LIMIT:-20};
      SQL

  get_today:
    readonly: true
    description: Get all messages from today
    run: |
      DB="$HOME/Library/Messages/chat.db"
      if [ ! -r "$DB" ]; then
        echo "Error: Cannot read iMessage database. agentOS needs Full Disk Access." >&2
        echo "Fix: System Settings → Privacy & Security → Full Disk Access → Enable agentOS" >&2
        exit 1
      fi
      sqlite3 -header -separator ' | ' "$DB" << 'SQL'
      SELECT 
          datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as date,
          CASE WHEN c.display_name IS NOT NULL THEN c.display_name ELSE '' END as group_name,
          CASE m.is_from_me WHEN 1 THEN 'Me' ELSE COALESCE(h.id, 'Unknown') END as sender,
          m.text as message
      FROM message m
      LEFT JOIN handle h ON m.handle_id = h.ROWID
      LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
      LEFT JOIN chat c ON cmj.chat_id = c.ROWID
      WHERE m.date/1000000000 + 978307200 >= CAST(strftime('%s', 'now', 'start of day', 'localtime') AS INTEGER)
        AND m.text IS NOT NULL AND m.text != ''
      ORDER BY m.date DESC;
      SQL
---

# iMessage

Read iMessages and SMS from the macOS Messages app. This is read-only access to your message history.

## Requirements

- **macOS only** - Reads from local Messages database
- **Full Disk Access required** - Unlike Contacts/Calendar, macOS does NOT auto-prompt for this permission

### Granting Full Disk Access

1. Open **System Settings → Privacy & Security → Full Disk Access**
2. Click the **+** button
3. Navigate to `/Applications` and select **agentOS**
4. Restart agentOS

Note: The iMessage database is in a protected system location. Without Full Disk Access, queries will fail with a permissions error.

## Tools

### get_conversations
List recent conversations with last message preview.

**Parameters:**
- `limit` (optional): Number of conversations, default 20

### get_messages
Get messages, optionally filtered by contact or time range.

**Parameters:**
- `contact` (optional): Filter by phone number or email (partial match works)
- `days` (optional): Only messages from last N days
- `limit` (optional): Max messages, default 30

### get_unread
Get all unread messages across all conversations.

### search
Search message content.

**Parameters:**
- `query` (required): Text to search for
- `limit` (optional): Max results, default 20

### get_today
Get all messages from today.

## Notes

- This is **read-only** - you cannot send messages through this plugin
- Phone numbers are stored in E.164 format: `+1XXXXXXXXXX`
- Use the `apple-contacts` plugin to resolve phone numbers to names
- Group chats show the group name in the `group_name` field
- Messages are returned newest first
- Media-only messages (images, videos) won't appear (no text content)

## Database Details

- **Location:** `~/Library/Messages/chat.db`
- **Date format:** Nanoseconds since macOS epoch (2001-01-01) - converted automatically
- **Services:** iMessage, SMS, or RCS shown in `service` field

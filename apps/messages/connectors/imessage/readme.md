---
id: imessage
name: iMessage
description: Read iMessages and SMS from macOS Messages app
icon: icon.png
color: "#34C759"

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

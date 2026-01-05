---
id: whatsapp
name: WhatsApp
description: Read WhatsApp messages from local macOS database
icon: icon.svg
color: "#25D366"

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

# WhatsApp Backup Research

> Research notes from analyzing [WhatsApp-Chat-Exporter](https://github.com/KnugiHK/WhatsApp-Chat-Exporter) (v0.13.0, MIT license, 960+ stars). This documents how WhatsApp stores data across platforms, how backups work, and what's relevant for building an AgentOS backup/import adapter.

---

## Current State: Our WhatsApp Adapter

Our existing adapter reads the **macOS desktop app's live SQLite database** at:

```
~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite
```

This gives real-time access to conversations, messages, contacts, and groups — but only while WhatsApp Desktop is installed and logged in. A backup adapter would complement this by allowing import of historical data from phone backups.

---

## Platform Overview

WhatsApp stores its data in SQLite databases on all platforms. The schemas differ significantly between iOS and Android, but the core entities are the same: contacts, conversations (sessions/chats), messages, media, and calls.

| Platform | Database | Contact DB | Encryption |
|----------|----------|------------|------------|
| Android | `msgstore.db` | `wa.db` | crypt12, crypt14, crypt15 |
| iOS (backup) | `ChatStorage.sqlite` (hash: `7c7fba66...`) | `ContactsV2.sqlite` (hash: `b8548dc3...`) | iTunes backup encryption |
| macOS Desktop | `ChatStorage.sqlite` (Group Containers) | `ContactsV2.sqlite` (separate) | None (disk access) |

---

## Android Database Schema

Android has evolved through two schema generations. The exporter handles both.

### Legacy Schema (older Android versions)

**Messages table: `messages`**

| Column | Type | Description |
|--------|------|-------------|
| `_id` | INTEGER | Primary key |
| `key_remote_jid` | TEXT | Chat JID (e.g., `12125551234@s.whatsapp.net`) |
| `key_from_me` | INTEGER | 1 = sent by user |
| `timestamp` | INTEGER | Unix timestamp in milliseconds |
| `data` | TEXT | Message text content |
| `status` | INTEGER | 6 = metadata/system message |
| `edit_version` | INTEGER | 7 = deleted message |
| `thumb_image` | BLOB | Thumbnail data |
| `remote_resource` | TEXT | Sender JID in group chats |
| `media_wa_type` | INTEGER | Media type (see below) |
| `media_caption` | TEXT | Caption for media messages |
| `key_id` | TEXT | Unique message key |
| `received_timestamp` | INTEGER | When received |
| `read_device_timestamp` | INTEGER | When read |

Related tables:
- `messages_quotes` — quoted/replied messages
- `message_media` — media file metadata
- `missed_call_logs` — call records
- `message_system` — system message actions
- `receipt_user` — read/delivery receipts
- `wa_contacts` — contact info (`jid`, `display_name`, `wa_name`, `status`)

### New Schema (recent Android versions)

**Messages table: `message`** (singular, not `messages`)

| Column | Type | Description |
|--------|------|-------------|
| `_id` | INTEGER | Primary key |
| `chat_row_id` | INTEGER | FK to `chat._id` |
| `from_me` | INTEGER | 1 = sent by user |
| `timestamp` | INTEGER | Unix timestamp in milliseconds |
| `text_data` | TEXT | Message text (was `data`) |
| `status` | INTEGER | Message status |
| `message_type` | INTEGER | Media type (was `media_wa_type`) |
| `sender_jid_row_id` | INTEGER | FK to `jid._id` |
| `key_id` | TEXT | Unique message key |
| `received_timestamp` | INTEGER | When received |

Related tables:
- `message_quoted` — quoted/replied messages
- `message_media` — media file paths and metadata
- `message_location` — latitude/longitude
- `message_thumbnail` — thumbnail blobs
- `message_future` — edit versions
- `message_add_on` + `message_add_on_reaction` — reactions
- `message_vcard` — shared contacts
- `jid` — JID lookup table (`_id`, `raw_string`, `type`)
- `jid_map` — LID-to-JID mapping (newer databases)
- `chat` — chat metadata (`_id`, `jid_row_id`, `subject`)
- `call_log` — call history

### JID Resolution (Android)

Recent Android versions introduced a `jid_map` table for LID (Local ID) resolution:

```sql
-- Resolve LID to actual JID
SELECT COALESCE(lid_global.raw_string, jid.raw_string) as key_remote_jid
FROM message
  LEFT JOIN chat ON chat._id = message.chat_row_id
  INNER JOIN jid ON jid._id = chat.jid_row_id
  LEFT JOIN jid_map ON chat.jid_row_id = jid_map.lid_row_id
  LEFT JOIN jid lid_global ON jid_map.jid_row_id = lid_global._id
```

### Android Media Types (`media_wa_type` / `message_type`)

| Value | Type |
|-------|------|
| 0 | Text |
| 1 | Image |
| 2 | Audio/Voice |
| 3 | Video |
| 4 | Contact (vCard) |
| 5 | Location |
| 7 | System |
| 9 | Document |
| 13 | GIF |
| 14 | Deleted message |
| 15 | Deleted message (new schema) |
| 20 | Sticker |

### Android Reactions

Only available in the new schema:

```sql
SELECT
  message_add_on.parent_message_row_id,
  message_add_on_reaction.reaction,
  message_add_on.from_me,
  jid.raw_string as sender_jid
FROM message_add_on
  INNER JOIN message_add_on_reaction 
    ON message_add_on._id = message_add_on_reaction.message_add_on_row_id
  LEFT JOIN jid ON message_add_on.sender_jid_row_id = jid._id
```

---

## iOS Database Schema

iOS uses a different schema with Core Data-style naming (`ZWA*` prefixed tables, `Z_PK` primary keys).

### Key Tables

| Table | Description |
|-------|-------------|
| `ZWACHATSESSION` | Conversations |
| `ZWAMESSAGE` | Messages |
| `ZWAMEDIAITEM` | Media attachments |
| `ZWAGROUPMEMBER` | Group participants |
| `ZWAGROUPINFO` | Group metadata |
| `ZWAPROFILEPUSHNAME` | Contact push names |
| `ZWAPROFILEPICTUREITEM` | Profile pictures |
| `ZWAADDRESSBOOKCONTACT` | Address book contacts |
| `ZWAVCARDMENTION` | Shared vCards |
| `ZWACDCALLEVENT` + `ZWAAGGREGATECALLEVENT` | Call history |

### iOS Messages

| Column | Type | Description |
|--------|------|-------------|
| `Z_PK` | INTEGER | Primary key |
| `ZCHATSESSION` | INTEGER | FK to chat session |
| `ZISFROMME` | INTEGER | 1 = sent by user |
| `ZMESSAGEDATE` | REAL | **Seconds since macOS epoch (2001-01-01)** |
| `ZTEXT` | TEXT | Message content |
| `ZMESSAGETYPE` | INTEGER | Message type |
| `ZGROUPMEMBER` | INTEGER | FK to group member (for group chats) |
| `ZFROMJID` | TEXT | Sender JID (incoming) |
| `ZPUSHNAME` | TEXT | Sender display name |
| `ZSTANZAID` | TEXT | Unique message stanza ID |
| `ZMETADATA` | BLOB | Contains reply references |
| `ZSTARRED` | INTEGER | Star/favorite flag |
| `ZPARENTMESSAGE` | INTEGER | Reply-to message PK |
| `ZSENTDATE` | REAL | Sent timestamp |

### iOS Date Conversion

**Critical**: iOS uses Apple/macOS epoch (2001-01-01 00:00:00 UTC), not Unix epoch.

```
Apple timestamp + 978307200 = Unix timestamp
```

```sql
datetime(ZMESSAGEDATE + 978307200, 'unixepoch') as timestamp
```

### iOS Message Types

| Value | Type |
|-------|------|
| 6 | System/metadata message |
| 14 | Deleted message |
| 15 | Sticker |

### iOS Reply Detection

Replies are encoded in the `ZMETADATA` blob. If it starts with `\x2a\x14`, bytes 2-19 contain the stanza ID of the quoted message (truncated to 17 chars).

```python
if content["ZMETADATA"].startswith(b"\x2a\x14"):
    quoted_stanza = content["ZMETADATA"][2:19].decode()
```

### iOS Session Types

| Value | Type |
|-------|------|
| 0 | Direct message (1:1) |
| 1 | Group chat |
| 3 | Broadcast / Status |

### iOS Backup File Identifiers

When extracting from an iTunes/Finder backup, files are referenced by SHA-1 hashes:

| Hash | File |
|------|------|
| `7c7fba66680ef796b916b067077cc246adacf01d` | ChatStorage.sqlite (messages) |
| `b8548dc30aa1030df0ce18ef08b882cf7ab5212f` | ContactsV2.sqlite (contacts) |
| `1b432994e958845fffe8e2f190f26d1511534088` | CallHistory.sqlite (calls) |

Domain: `AppDomainGroup-group.net.whatsapp.WhatsApp.shared`

For WhatsApp Business:
| Hash | File |
|------|------|
| `724bd3b98b18518b455a87c1f3ac3a0d189c4466` | ChatStorage.sqlite |
| `d7246a707f51ddf8b17ee2dddabd9e0a4da5c552` | ContactsV2.sqlite |
| `b463f7c4365eefc5a8723930d97928d4e907c603` | CallHistory.sqlite |

Domain: `AppDomainGroup-group.net.whatsapp.WhatsAppSMB.shared`

---

## Android Backup Encryption

### Format Evolution

| Format | Era | Key Source |
|--------|-----|-----------|
| crypt12 | Older | 158-byte key file from `/data/data/com.whatsapp/files/key` |
| crypt14 | Mid | Same key file, different offsets |
| crypt15 | Current | 32-byte hex key (E2E backup) OR key file |

### Decryption Process

1. **Key extraction**: 
   - crypt12/14: Read 158-byte key file, extract AES key from bytes 126-158
   - crypt15 with hex key: Derive via `HMAC-SHA256(HMAC-SHA256(zeros, key), "backup encryption\x01")`
   - crypt15 with key file: Parse Java serialized object, then derive as above

2. **Signature verification** (crypt12/14 only): Validate key file signature matches backup header

3. **Decryption**: AES-256-GCM
   - IV location varies by format (crypt14 has multiple known offsets, may need brute-force)
   - Ciphertext ends with 32-byte footer (16-byte GCM tag + 16 padding)

4. **Decompression**: zlib decompress the decrypted data

5. **Result**: Raw SQLite database (`msgstore.db`)

### crypt14 Offset Complexity

The IV and database-start positions vary across WhatsApp versions. Known offsets:

```
IV=67, DB=191  (most common)
IV=67, DB=190
IV=66, DB=99
IV=67, DB=193
IV=67, DB=194
IV=67, DB=158
IV=67, DB=196
```

If known offsets fail, the exporter brute-forces up to 200x200 = 40,000 combinations.

### iOS Backup Encryption

iOS backups can be encrypted by iTunes/Finder. This is a separate layer from WhatsApp's own encryption.

- Uses `iphone_backup_decrypt` library to decrypt
- Requires the iTunes backup password
- The `Manifest.db` in the backup maps file hashes to relative paths
- Files are stored in subdirectories named by their first 2 hash characters
- Metadata (creation/modification times) stored as binary plists

**Important**: If WhatsApp's own E2E backup encryption is enabled, the database files will be missing from the iTunes backup entirely. Users must disable WhatsApp's E2E backup before making an iTunes backup.

---

## Media Storage

### Android Media Paths

Media is stored under the `WhatsApp/` directory with structure:

```
WhatsApp/
  Media/
    WhatsApp Images/
    WhatsApp Video/
    WhatsApp Audio/
    WhatsApp Voice Notes/
    WhatsApp Documents/
    WhatsApp Stickers/
```

Referenced in `message_media.file_path` (relative to media folder).

### iOS Media Paths

Media is stored under the WhatsApp domain:

```
AppDomainGroup-group.net.whatsapp.WhatsApp.shared/
  Message/
    <media files referenced by ZMEDIALOCALPATH>
  Media/
    Profile/
      Photo.jpg           (user's own avatar)
      <phone>*.jpg        (contact avatars)
      <phone>*.thumb      (contact avatar thumbnails)
```

Referenced in `ZWAMEDIAITEM.ZMEDIALOCALPATH`.

---

## JID Format

JIDs (Jabber IDs) identify users and groups:

| Pattern | Type |
|---------|------|
| `12125551234@s.whatsapp.net` | Individual user (DM) |
| `1234567890-1602721391@g.us` | Group chat |
| `status@broadcast` | Status broadcasts |

### JID Types (Android `jid.type`)

| Value | Type |
|-------|------|
| 0 | Private message |
| 1 | Group |
| 5 | System broadcast |
| 7 | Status (filtered out of media queries) |
| 11 | Status |

---

## Output Formats

The exporter produces:

1. **HTML** — per-chat HTML files with WhatsApp-style rendering, avatars, media embedding
2. **JSON** — single file or per-chat, with optional Telegram-compatible format
3. **Text** — plain text format similar to WhatsApp's official export

The JSON format per chat looks like:

```json
{
  "12125551234@s.whatsapp.net": {
    "name": "Contact Name",
    "type": "ios",
    "my_avatar": "path/to/Photo.jpg",
    "their_avatar": "path/to/avatar.jpg",
    "status": "Hey there!",
    "messages": {
      "123": {
        "from_me": false,
        "timestamp": 1707000000,
        "time": "14:30",
        "key_id": "ABC123",
        "data": "Hello!",
        "media": false,
        "meta": false,
        "sender": null,
        "reply": null,
        "caption": null,
        "sticker": false,
        "reactions": {"You": "👍"}
      }
    }
  }
}
```

---

## Relevance for AgentOS

### What a Backup Adapter Could Do

1. **Import from Android backup**: Accept `msgstore.db.crypt14` or `.crypt15` + key, decrypt, parse into entities
2. **Import from iOS backup**: Accept iTunes backup directory path, extract and parse
3. **Import from JSON**: Accept pre-exported JSON from WhatsApp-Chat-Exporter
4. **Import from plain export**: Parse WhatsApp's official `.txt` export files

### The Simplest Path: JSON Import

The easiest approach would be to have users run `wtsexporter` themselves to produce JSON, then build an adapter that reads that JSON. This avoids dealing with encryption, platform detection, and database schema evolution.

```bash
pip install whatsapp-chat-exporter
wtsexporter -a -k key -b msgstore.db.crypt15 -j whatsapp.json --no-html --per-chat
```

Then our adapter reads the per-chat JSON files.

### The More Ambitious Path: Direct Database Parsing

We could do what the exporter does — accept the raw database and parse it ourselves. This means:

- Handling two Android schema versions (legacy `messages` table vs new `message` table)
- Handling iOS schema (`ZWA*` tables)
- Dealing with encryption (would need Python subprocess or Rust crypto)
- JID resolution with `jid_map` for newer Android databases

Our existing adapter already handles the iOS/macOS schema (it's the same `ChatStorage.sqlite`). For a backup import, we'd mainly need Android support.

### Key Differences from Live Desktop Adapter

| Aspect | Desktop (current) | Backup (future) |
|--------|-------------------|-----------------|
| Source | Live SQLite file | Encrypted backup or extracted DB |
| Platform | macOS only | Cross-platform (Android + iOS backups) |
| Freshness | Real-time | Point-in-time snapshot |
| Auth | File system access | Key file or password |
| Media | Available on disk | Bundled in backup, needs extraction |

### Dependencies

If we go the direct route:
- `pycryptodome` — AES-GCM decryption (Android backups)
- `javaobj-py3` — Java serialized key file parsing (crypt15)
- `iphone_backup_decrypt` — iOS encrypted backup handling

If we go the JSON import route:
- Just `whatsapp-chat-exporter` as a user prerequisite

---

## References

- [WhatsApp-Chat-Exporter](https://github.com/KnugiHK/WhatsApp-Chat-Exporter) — MIT, Python, v0.13.0
- [WhatsApp-Key-DB-Extractor](https://github.com/YuvrajRaghuvanshiS/WhatsApp-Key-DB-Extractor) — Android key extraction (root or ADB)
- [iphone_backup_decrypt](https://github.com/KnugiHK/iphone_backup_decrypt) — iOS backup decryption
- WhatsApp E2E backup docs: https://faq.whatsapp.com/820124435853543

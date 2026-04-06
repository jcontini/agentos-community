---
id: mimestream
name: Mimestream
description: "Read and search email from Mimestream, a native macOS email client for Gmail"
color: "#3B82F6"
website: "https://mimestream.com"
privacy_url: "https://mimestream.com/privacy"

connections:
  db:
    sqlite: ~/Library/Containers/com.mimestream.Mimestream/Data/Library/Application Support/Mimestream/Mimestream.sqlite

accounts:
  list_via: list_accounts
  id_field: email

provides:
- auth: oauth
  service: google
  via: credential_get
  account_param: account

product:
  name: Mimestream
  website: https://mimestream.com
  developer: Mimestream LLC
---

# Mimestream

Read and search email from [Mimestream](https://mimestream.com/), a native macOS email client for Gmail.

This integration also satisfies `oauth.service: google` for connections that declare it — the runtime routes token requests through `provides: google` / `credential_get`.

## Requirements

- **macOS only** -- reads from Mimestream's local Core Data SQLite database
- **Mimestream installed** -- the app must be installed and have synced at least once
- **Full Disk Access** -- System Settings > Privacy & Security > Full Disk Access (for the process reading the database)

## Database

Mimestream stores emails in a Core Data SQLite database at:

```
~/Library/Containers/com.mimestream.Mimestream/Data/Library/Application Support/Mimestream/Mimestream.sqlite
```

Core Data timestamps use Apple's reference date (2001-01-01). The skill converts these automatically by adding 978307200 seconds.

## Capabilities

```
OPERATION             ENTITY TYPE    DESCRIPTION
--------------------  -------------  ----------------------------------------
email.list            email          List emails with mailbox/account filters
email.get             email          Full email with body, headers, recipients
email.search          email          Full-text search across all fields
conversation.list     conversation   List email threads
conversation.get      conversation   Get thread metadata
# file.list           file           List email attachments (blocked: file type not registered)
# file.get            file           Get a specific attachment (blocked: file type not registered)
list_accounts         (utility)      Show configured accounts
list_mailboxes        (utility)      Show mailbox roles and unread counts
```

## Entity Mapping

```
person --claim--> account
account --send--> email
email --attach--> file
```

- `email` extends message (work > document > post > message > email)
- `file` extends document (work > document > file)
- `conversation` holds email threads
- `account` (platform: email) represents sender/recipient addresses
- Sender accounts are auto-created via typed references when emails sync
- Files are linked to their source emails via the `attach` relationship

## Notes

- This skill is **read-only** -- it cannot send emails or modify state
- Mimestream syncs with Gmail, so data reflects what has been synced locally
- Search covers subject, snippet, body text, sender, and recipients

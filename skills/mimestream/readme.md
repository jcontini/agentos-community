---
id: mimestream
name: Mimestream
description: Read and search email from Mimestream, a native macOS email client for Gmail
icon: icon.svg
color: "#3B82F6"

website: https://mimestream.com
privacy_url: https://mimestream.com/privacy

auth: none

# Mimestream stores Google OAuth tokens in the macOS Keychain under
# "Mimestream: {email}" / "OAuth" as NSKeyedArchiver binary plists.
# These tokens have full Google scopes (Gmail, Contacts, Calendar).
# Mimestream can act as a Google auth provider skill for other consumers.
provides:
  - service: google
    scopes:
      - https://mail.google.com/
      - https://www.googleapis.com/auth/contacts
      - https://www.googleapis.com/auth/contacts.other.readonly
      - https://www.googleapis.com/auth/calendar.events
      - https://www.googleapis.com/auth/directory.readonly
      - https://www.googleapis.com/auth/gmail.settings.basic
      - https://www.googleapis.com/auth/userinfo.profile
    via: credential_get
    account_param: account
    accounts_via: list_accounts
    account_field: email
database: "~/Library/Containers/com.mimestream.Mimestream/Data/Library/Application Support/Mimestream/Mimestream.sqlite"

# ==============================================================================
# TRANSFORMERS
# ==============================================================================

adapters:
  email:
    id: .id
    name: .subject
    text: .snippet
    author: .from_email
    datePublished: .date_received
    subject: .subject
    snippet: .snippet
    from_address: .from_email
    timestamp: .date_received
    is_starred: '.is_flagged == 1'
    is_draft: '.is_draft == 1'
    message_id: .message_id
    in_reply_to: .in_reply_to
    conversation_id: '.thread_id | tostring'
    content: .body_text
    data.account_email: .account_email
    data.is_unread: '.is_unread == 1'
    data.has_attachments: '.has_attachments == 1'
    data.is_sent: '.is_sent == 1'
    data.is_trash: '.is_trash == 1'
    data.is_spam: '.is_spam == 1'
    data.to_raw: .to_raw
    data.cc_raw: .cc_raw
    data.bcc_raw: .bcc_raw
    data.body_html: .body_html
    data.size_estimate: .size_estimate
    from:
      account:
        handle: .from_email
        platform: '"email"'
        display_name: .from_name

  conversation:
    id: '.id | tostring'
    name: .subject
    text: .snippet
    datePublished: .date_updated
    last_message: .snippet
    last_message_at: .date_updated
    data.account_email: .account_email
    data.message_count: .message_count
    data.has_unread: '.has_unread == 1'
    data.has_attachments: '.has_attachments == 1'

  # BLOCKED: file entity type not yet registered in engine type system (task eb14f8fa)
  # Uncomment when _type creation via MCP lands data in the right column
  # file:
  #   terminology: Attachment
  #   mapping:
  #     id: '.id | tostring'
  #     name: .filename
  #     filename: .filename
  #     mime_type: .mime_type
  #     size: .size
  #     is_inline: '.is_inline == 1'
  #     data.downloaded: '.downloaded == 1'
  #     email_id:
  #       ref: email
  #       value: '.email_id | tostring'
  #       rel: attach

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:
  list_emails:
    description: List emails, optionally filtered by mailbox, account, or flags
    returns: email[]
    params:
      account: { type: string, description: "Account display name — use exact values from list_accounts (e.g. 'user@example.com' or 'Adavia')" }
      mailbox: { type: string, description: "Filter by mailbox: inbox, sent, drafts, trash, spam, flagged" }
      is_unread: { type: boolean, description: "Filter to unread only" }
      limit: { type: integer }
    sql:
      query: |
        SELECT
          m.Z_PK as id,
          m.ZSUBJECT as subject,
          m.ZSNIPPET as snippet,
          datetime(m.ZDATERECEIVED + 978307200, 'unixepoch') as date_received,
          datetime(m.ZDATESENT + 978307200, 'unixepoch') as date_sent,
          m.ZISUNREAD as is_unread,
          m.ZISFLAGGED as is_flagged,
          m.ZISDRAFT as is_draft,
          m.ZISSENT as is_sent,
          m.ZISTRASHED as is_trash,
          m.ZISSPAM as is_spam,
          m.ZHASATTACHMENT as has_attachments,
          t.Z_PK as thread_id,
          a.ZNAME as account_email,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(substr(m.ZFROMHEADER, 1, instr(m.ZFROMHEADER, '<') - 1), ' "')
            ELSE NULL
          END as from_name,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(replace(substr(m.ZFROMHEADER, instr(m.ZFROMHEADER, '<') + 1), '>', ''))
            ELSE trim(m.ZFROMHEADER)
          END as from_email
        FROM ZMESSAGE m
        LEFT JOIN ZACCOUNT a ON m.ZACCOUNT = a.Z_PK
        LEFT JOIN ZMESSAGETHREAD t ON m.ZTHREAD = t.Z_PK
        WHERE m.ZISTRASHED = 0
          AND m.ZISSPAM = 0
          AND (:account IS NULL OR a.ZNAME = :account)
          AND (:is_unread IS NULL OR m.ZISUNREAD = :is_unread)
          AND (:mailbox IS NULL OR (
            (:mailbox = 'inbox' AND m.ZISININBOX = 1) OR
            (:mailbox = 'sent' AND m.ZISSENT = 1) OR
            (:mailbox = 'drafts' AND m.ZISDRAFT = 1) OR
            (:mailbox = 'trash' AND m.ZISTRASHED = 1) OR
            (:mailbox = 'spam' AND m.ZISSPAM = 1) OR
            (:mailbox = 'flagged' AND m.ZISFLAGGED = 1)
          ))
        ORDER BY m.ZDATERECEIVED DESC
        LIMIT :limit
      params:
        account: .params.account
        is_unread: 'if .params.is_unread == true then 1 elif .params.is_unread == false then 0 else null end'
        mailbox: .params.mailbox
        limit: '.params.limit // 1000'

  get_email:
    description: Get a specific email with full body content and headers
    returns: email
    params:
      id: { type: string, required: true }
    sql:
      query: |
        SELECT
          m.Z_PK as id,
          m.ZSUBJECT as subject,
          m.ZSNIPPET as snippet,
          datetime(m.ZDATERECEIVED + 978307200, 'unixepoch') as date_received,
          datetime(m.ZDATESENT + 978307200, 'unixepoch') as date_sent,
          m.ZISUNREAD as is_unread,
          m.ZISFLAGGED as is_flagged,
          m.ZISDRAFT as is_draft,
          m.ZISSENT as is_sent,
          m.ZISTRASHED as is_trash,
          m.ZISSPAM as is_spam,
          m.ZHASATTACHMENT as has_attachments,
          m.ZSIZEESTIMATE as size_estimate,
          t.Z_PK as thread_id,
          a.ZNAME as account_email,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(substr(m.ZFROMHEADER, 1, instr(m.ZFROMHEADER, '<') - 1), ' "')
            ELSE NULL
          END as from_name,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(replace(substr(m.ZFROMHEADER, instr(m.ZFROMHEADER, '<') + 1), '>', ''))
            ELSE trim(m.ZFROMHEADER)
          END as from_email,
          c.ZTO as to_raw,
          c.ZCC as cc_raw,
          c.ZBCC as bcc_raw,
          c.ZBODYTEXT as body_text,
          c.ZBODYHTML as body_html,
          c.ZMESSAGEID as message_id,
          c.ZINREPLYTO as in_reply_to
        FROM ZMESSAGE m
        LEFT JOIN ZACCOUNT a ON m.ZACCOUNT = a.Z_PK
        LEFT JOIN ZMESSAGETHREAD t ON m.ZTHREAD = t.Z_PK
        LEFT JOIN ZMESSAGECONTENT c ON m.ZCONTENT = c.Z_PK
        WHERE m.Z_PK = :id
      params:
        id: .params.id
      response:
        root: "/0"

  search_emails:
    description: Search emails by subject, snippet, body text, or sender
    returns: email[]
    params:
      query: { type: string, required: true }
      account: { type: string, description: "Account display name from list_accounts (e.g. 'user@example.com' or 'Adavia')" }
      limit: { type: integer }
    sql:
      query: |
        SELECT
          m.Z_PK as id,
          m.ZSUBJECT as subject,
          m.ZSNIPPET as snippet,
          datetime(m.ZDATERECEIVED + 978307200, 'unixepoch') as date_received,
          m.ZISUNREAD as is_unread,
          m.ZISFLAGGED as is_flagged,
          m.ZHASATTACHMENT as has_attachments,
          t.Z_PK as thread_id,
          a.ZNAME as account_email,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(substr(m.ZFROMHEADER, 1, instr(m.ZFROMHEADER, '<') - 1), ' "')
            ELSE NULL
          END as from_name,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(replace(substr(m.ZFROMHEADER, instr(m.ZFROMHEADER, '<') + 1), '>', ''))
            ELSE trim(m.ZFROMHEADER)
          END as from_email
        FROM ZMESSAGE m
        LEFT JOIN ZACCOUNT a ON m.ZACCOUNT = a.Z_PK
        LEFT JOIN ZMESSAGETHREAD t ON m.ZTHREAD = t.Z_PK
        LEFT JOIN ZMESSAGECONTENT c ON m.ZCONTENT = c.Z_PK
        WHERE m.ZISTRASHED = 0
          AND m.ZISSPAM = 0
          AND (:account IS NULL OR a.ZNAME = :account)
          AND (
            m.ZSUBJECT LIKE '%' || :query || '%'
            OR m.ZSNIPPET LIKE '%' || :query || '%'
            OR c.ZBODYTEXT LIKE '%' || :query || '%'
            OR m.ZFROMHEADER LIKE '%' || :query || '%'
            OR c.ZTO LIKE '%' || :query || '%'
          )
        ORDER BY m.ZDATERECEIVED DESC
        LIMIT :limit
      params:
        query: .params.query
        account: .params.account
        limit: '.params.limit // 1000'

  list_conversations:
    description: List email threads with latest message info
    returns: conversation[]
    params:
      account: { type: string, description: "Account display name from list_accounts (e.g. 'user@example.com' or 'Adavia')" }
      limit: { type: integer }
    sql:
      query: |
        SELECT
          t.Z_PK as id,
          a.ZNAME as account_email,
          (SELECT ZSUBJECT FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED DESC LIMIT 1) as subject,
          (SELECT ZSNIPPET FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED DESC LIMIT 1) as snippet,
          (SELECT datetime(ZDATERECEIVED + 978307200, 'unixepoch') FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED DESC LIMIT 1) as date_updated,
          (SELECT COUNT(*) FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK) as message_count,
          (SELECT MAX(ZISUNREAD) FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK) as has_unread,
          t.ZHASATTACHMENT as has_attachments
        FROM ZMESSAGETHREAD t
        LEFT JOIN ZACCOUNT a ON t.ZACCOUNT = a.Z_PK
        WHERE (:account IS NULL OR a.ZNAME = :account)
        ORDER BY date_updated DESC
        LIMIT :limit
      params:
        account: .params.account
        limit: '.params.limit // 1000'

  get_conversation:
    description: Get all messages in an email thread
    returns: conversation
    params:
      id: { type: string, required: true }
    sql:
      query: |
        SELECT
          t.Z_PK as id,
          a.ZNAME as account_email,
          (SELECT ZSUBJECT FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED ASC LIMIT 1) as subject,
          (SELECT ZSNIPPET FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED DESC LIMIT 1) as snippet,
          (SELECT datetime(ZDATERECEIVED + 978307200, 'unixepoch') FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED DESC LIMIT 1) as date_updated,
          (SELECT COUNT(*) FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK) as message_count,
          (SELECT MAX(ZISUNREAD) FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK) as has_unread,
          t.ZHASATTACHMENT as has_attachments
        FROM ZMESSAGETHREAD t
        LEFT JOIN ZACCOUNT a ON t.ZACCOUNT = a.Z_PK
        WHERE t.Z_PK = :id
      params:
        id: .params.id
      response:
        root: "/0"

  # BLOCKED: file entity type not yet registered (task eb14f8fa)
  # file.list:
  #   description: List email attachments, optionally filtered by email or account
  #   returns: file[]
  #   params:
  #     email_id: { type: string, description: "Filter to attachments from a specific email" }
  #     account: { type: string, description: "Account display name from list_accounts (e.g. 'user@example.com' or 'Adavia')" }
  #     limit: { type: integer }
  #   sql:
  #     query: |
  #       SELECT
  #         a.Z_PK as id, a.ZFILENAME as filename, a.ZMIMETYPE as mime_type,
  #         a.ZSIZE as size, a.ZINLINE as is_inline, a.ZDOWNLOADED as downloaded,
  #         m.Z_PK as email_id
  #       FROM ZATTACHMENT a
  #       JOIN ZMESSAGECONTENT c ON a.ZCONTENT = c.Z_PK
  #       JOIN ZMESSAGE m ON m.ZCONTENT = c.Z_PK
  #       LEFT JOIN ZACCOUNT acct ON m.ZACCOUNT = acct.Z_PK
  #       WHERE m.ZISTRASHED = 0 AND m.ZISSPAM = 0
  #         AND (:email_id IS NULL OR m.Z_PK = :email_id)
  #         AND (:account IS NULL OR acct.ZNAME = :account)
  #       ORDER BY m.ZDATERECEIVED DESC, a.Z_PK
  #       LIMIT :limit
  #     params:
  #       email_id: .params.email_id
  #       account: .params.account
  #       limit: '.params.limit // 1000'
  #
  # file.get:
  #   description: Get a specific attachment
  #   returns: file
  #   params:
  #     id: { type: string, required: true }
  #   sql:
  #     query: |
  #       SELECT
  #         a.Z_PK as id, a.ZFILENAME as filename, a.ZMIMETYPE as mime_type,
  #         a.ZSIZE as size, a.ZINLINE as is_inline, a.ZDOWNLOADED as downloaded,
  #         m.Z_PK as email_id
  #       FROM ZATTACHMENT a
  #       JOIN ZMESSAGECONTENT c ON a.ZCONTENT = c.Z_PK
  #       JOIN ZMESSAGE m ON m.ZCONTENT = c.Z_PK
  #       WHERE a.Z_PK = :id
  #     params:
  #       id: .params.id
  #     response:
  #       root: "/0"

  list_accounts:
    description: List configured email accounts with their primary email address
    returns:
      id: integer
      name: string
      email: string
      color: string
    sql:
      query: |
        SELECT
          a.Z_PK as id,
          a.ZNAME as name,
          i.ZADDRESS as email,
          a.ZCOLOR as color
        FROM ZACCOUNT a
        LEFT JOIN ZIDENTITY i ON i.ZACCOUNT = a.Z_PK AND i.ZPRIMARY = 1
        ORDER BY a.ZDISPLAYORDER

  credential_get:
    description: |
      Get a live Google OAuth access token sourced from Mimestream's keychain.
      Returns access_token, refresh_token, client_id, and token_url.
      Used by consumer skills (gmail, google-calendar, etc.) as a Google provider operation.
    params:
      account: { type: string, required: true, description: "Email address (e.g. 'user@example.com' or 'user@example.com')" }
    returns:
      access_token: string
      refresh_token: string
      client_id: string
      token_url: string
    steps:
      steps:
        # Step 1: Read the NSKeyedArchiver binary plist from the macOS Keychain.
        # The `security` CLI returns the value as a hex string (-x flag).
        # We use a command here because the keyring crate returns raw bytes
        # (which fail UTF-8 decode), while `security -x` gives us the hex we need.
        - id: raw
          command:
            binary: bash
            args:
              - "-c"
              - 'security find-generic-password -s "Mimestream: $1" -a "OAuth" -w 2>/dev/null | tr -d "\n"'
              - "--"
              - ".params.account"

        # Step 2: Decode the hex → binary plist → extract token fields by $objects index.
        # These indices are stable across Mimestream versions (verified on both accounts).
        - id: fields
          plist:
            input: ".raw"
            extract:
              refresh_token: 32   # Google refresh token (1//01...)
              client_id: 13       # OAuth client ID (1064022...apps.googleusercontent.com)
              token_url: 10       # Token endpoint (https://www.googleapis.com/oauth2/v4/token)

        # Step 3: Exchange the refresh token for a live access token.
        - id: token_response
          rest:
            url: ".fields.token_url"
            method: POST
            encoding: form
            body:
              grant_type: refresh_token
              refresh_token: ".fields.refresh_token"
              client_id: ".fields.client_id"

      response:
        transform: |
          {
            access_token: .token_response.access_token,
            expires_in: .token_response.expires_in,
            refresh_token: .fields.refresh_token,
            client_id: .fields.client_id,
            token_url: .fields.token_url
          }

  list_mailboxes:
    description: List mailboxes/labels for an account
    params:
      account: { type: string, description: "Account display name from list_accounts (e.g. 'user@example.com' or 'Adavia')" }
    returns:
      id: integer
      name: string
      role: string
      unread_count: integer
      total_count: integer
      account_email: string
    sql:
      query: |
        SELECT
          m.Z_PK as id,
          m.ZNAME as name,
          m.ZROLE as role,
          m.ZUNREADMESSAGECOUNT as unread_count,
          m.ZTOTALMESSAGECOUNT as total_count,
          m.ZTAGBACKGROUNDCOLOR as color,
          a.Z_PK as account_id,
          a.ZNAME as account_email
        FROM ZMAILBOX m
        LEFT JOIN ZACCOUNT a ON m.ZACCOUNT = a.Z_PK
        WHERE m.ZROLE IS NOT NULL
          AND (:account IS NULL OR a.ZNAME = :account)
        ORDER BY
          a.ZDISPLAYORDER,
          CASE m.ZROLE
            WHEN 'INBOX' THEN 1
            WHEN 'INBOX_PRIMARY' THEN 2
            WHEN 'DRAFT' THEN 3
            WHEN 'SENT' THEN 4
            WHEN 'IMPORTANT' THEN 5
            WHEN 'TRASH' THEN 6
            WHEN 'SPAM' THEN 7
            ELSE 10
          END
      params:
        account: .params.account


---

# Mimestream

Read and search email from [Mimestream](https://mimestream.com/), a native macOS email client for Gmail.

This skill also acts as a Google auth provider for consumer skills that declare `auth: { oauth: { service: google } }`.

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

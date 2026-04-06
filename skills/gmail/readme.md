---
id: gmail
name: Gmail
description: "Full-featured Gmail — read, search, send, reply, forward, label, archive, draft, attachments, filters, and batch operations. Auth can use the shared `google` OAuth capability when a provider integration is available."
color: "#EA4335"
website: "https://mail.google.com"
privacy_url: "https://policies.google.com/privacy"

connections:
  gmail:
    base_url: https://gmail.googleapis.com/gmail/v1/users/me
    domain: gmail.googleapis.com
    auth:
      type: oauth
      service: google
      scopes:
      - https://mail.google.com/
  sync:
    base_url: https://mail.google.com
    domain: mail.google.com
    auth:
      type: cookies
      domain: .google.com
      names:
      - SID
      - HSID
      - SSID
      - OSID
      - __Secure-1PSID
      - __Secure-3PSID

product:
  name: Gmail
  website: https://mail.google.com
  developer: Google LLC
---

# Gmail

Full-featured email via the [Gmail REST API](https://developers.google.com/gmail/api) — read, search, send, reply, forward, label, archive, draft, attachments, filters, and batch operations.

## Agent Guidance

**Use `email.list` for everything.** `list_emails` returns full emails — subject, snippet, headers, body — in one call. No need to call `get_email` separately per message. Use `search_emails` for query-driven searches; it also returns full content.

**Always default to inbox.** When the user asks to check email or see unread messages, ALWAYS scope to the inbox first using `query: "in:inbox is:unread"`. Do NOT use bare `is:unread` — that searches all mail including Promotions, Updates, and Spam and will return hundreds of irrelevant messages. After showing inbox results, briefly note counts for other categories if there are any (e.g. "Also 50+ unread in Promotions — want me to show those?").

**Folder query syntax** — use the `query` param, not `label_ids`:
- Inbox: `in:inbox`
- Spam: `in:spam`
- Promotions: `category:promotions`
- Updates: `category:updates`
- Social: `category:social`

Do not pass `label_ids` as an array param — it causes a 400 error from the API.

## Auth — Google OAuth via `provides: google`

When some integration already holds Google OAuth tokens (often via macOS Keychain) and declares `provides: google` with a `credential_get` path, this skill can reuse those tokens — no separate Gmail API project for the user.

How it works:
1. A provider stores OAuth material in a system-specific way (Keychain entry shape depends on the app).
2. The provider's `provides` / `credential_get` surface is matched by the runtime.
3. This skill declares `connections.gmail.oauth.service: google`.
4. The resolver injects the configured auth headers on REST calls.
5. If multiple providers satisfy `google`, the agent should ask the user which one to use.

**Without a matching provider:** complete the standard OAuth flow at `GET /sys/oauth/authorize/gmail`.

## Capabilities

```
OPERATION             DESCRIPTION
────────────────────  ───────────────────────────────────────────────────
conversation.list     Browse threads with snippets (best for browsing)
conversation.get      Full thread with all messages, headers, body
email.get             Full email with body, headers, attachment metadata
email.list            List emails with full content (subject, snippet, body)
email.search          Search emails with full content (Gmail query syntax)
email.send            Compose and send a new email (text or HTML)
email.reply           Reply to an email (keeps it in the thread)
email.forward         Forward an email to another recipient
email.modify          Mark read/unread, star, archive, label, spam
email.trash           Move to trash
email.untrash         Restore from trash
email.batch_modify    Bulk label/read/archive (up to 1000 messages)
email.batch_delete    Permanently delete in bulk (IRREVERSIBLE)
list_drafts           List drafts
get_draft             Get a draft with full content
create_draft          Create a new draft
update_draft          Update an existing draft
send_draft            Send a draft
delete_draft          Permanently delete a draft
get_profile           Account info (email, message count, history ID)
list_labels           All labels with IDs
create_label          Create a new label
update_label          Update label name or visibility
delete_label          Delete a label
list_filters          List server-side filters/rules
create_filter         Create a filter (auto-label, skip inbox, forward)
delete_filter         Delete a filter
get_attachment        Download an attachment by ID
get_raw               Full RFC 2822 raw message source
get_history           Incremental changes since a history ID (for sync)
get_vacation          Vacation/auto-reply settings
set_vacation          Set or disable vacation auto-reply
list_send_as          List send-as aliases
```

## Gmail Query Syntax

```
is:unread                     Unread messages
is:starred                    Starred messages
is:important                  Important messages
from:boss@company.com         From a specific sender
to:me                         Sent directly to me
subject:invoice               Subject contains "invoice"
after:2026/01/01              Messages after a date
before:2026/02/01             Messages before a date
has:attachment                Messages with attachments
filename:pdf                  Attachments with specific type
label:INBOX is:unread         Unread inbox messages
in:sent                       Sent mail
in:trash                      Trashed messages
in:spam                       Spam messages
category:social               Social category
category:promotions           Promotions category
larger:5M                     Messages larger than 5MB
```

## Accounts

Each Gmail address is a separate account. Pass `account: "user@example.com"` to
target a specific address. See the **Configured Accounts** section above for available accounts.

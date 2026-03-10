---
id: gmail
name: Gmail
description: Read and search Gmail via the Gmail REST API. Auth sourced from Mimestream (no OAuth setup needed if Mimestream is installed).
color: "#EA4335"

website: https://mail.google.com
privacy_url: https://policies.google.com/privacy

# No client_id or client_secret needed — auth is sourced from Mimestream's keychain.
# The system finds Mimestream's `provides: [{ service: google }]` declaration and
# calls its `credential.get` utility to get a live access token automatically.
auth:
  oauth:
    service: google
    scopes:
      - https://mail.google.com/

api:
  base_url: https://gmail.googleapis.com/gmail/v1/users/me

seed:
  - id: gmail
    types: [software]
    name: Gmail
    data:
      software_type: web_app
      url: https://mail.google.com
      launched: "2004"
      pricing: free
    relationships:
      - role: offered_by
        to: google

instructions: |
  Gmail skill — reads and sends email via the Gmail REST API. Auth is automatic when Mimestream is installed.

  Available accounts are listed in the Configured Accounts section of this readme.
  Pass the email address as the `account` param (e.g. account: "user@example.com").

  Key concepts:
  - Messages have IDs (hex strings like "19cd96cdb6276b79") and thread IDs
  - email.list returns stubs (id + threadId only); use email.get for full content
  - email.search uses Gmail query syntax: "from:sender@example.com", "subject:invoice", "after:2026/01/01"
  - Labels: INBOX, SENT, DRAFT, TRASH, SPAM, STARRED, UNREAD (system labels are uppercase)
  - email.list with query: "is:unread label:inbox" for unread inbox messages

# ==============================================================================
# TRANSFORMERS
# ==============================================================================

transformers:
  email:
    terminology: Email
    mapping:
      id: .id
      subject: 'if .payload then .payload.headers | map(select(.name == "Subject")) | .[0].value // "(no subject)" else "(no subject)" end'
      snippet: '.snippet // ""'
      from_address: 'if .payload then .payload.headers | map(select(.name == "From")) | .[0].value // "" else "" end'
      timestamp: 'if .internalDate then .internalDate | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S") else null end'
      is_starred: 'if .labelIds then .labelIds | contains(["STARRED"]) else false end'
      is_unread: 'if .labelIds then .labelIds | contains(["UNREAD"]) else false end'
      is_draft: 'if .labelIds then .labelIds | contains(["DRAFT"]) else false end'
      message_id: 'if .payload then .payload.headers | map(select(.name == "Message-ID")) | .[0].value // "" else "" end'
      conversation_id: '.threadId // ""'
      content: 'if .payload then (.payload.parts // [.payload] | map(select(.mimeType == "text/plain")) | if length > 0 then .[0].body.data // "" | @base64d else "" end) else "" end'
      data.label_ids: '.labelIds // []'
      data.size_estimate: .sizeEstimate
      data.history_id: .historyId

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:
  email.list:
    description: List emails, optionally filtered by label, search query, or account
    returns: email[]
    params:
      account: { type: string, description: "Gmail address — see Configured Accounts in readme" }
      label_ids: { type: array, description: "Filter by label IDs (e.g. ['INBOX', 'UNREAD'])" }
      query: { type: string, description: "Gmail search query (e.g. 'from:boss@company.com is:unread')" }
      limit: { type: integer, description: "Max results (default: 20)" }
      page_token: { type: string, description: "Token for next page of results" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages"
      method: GET
      query:
        maxResults: ".params.limit // 20"
        q: ".params.query"
        pageToken: ".params.page_token"
        labelIds: ".params.label_ids"
      response:
        transform: ".messages // []"

  email.get:
    description: Get a specific email with full body content and headers
    returns: email
    params:
      id: { type: string, required: true, description: "Message ID from email.list" }
      account: { type: string, description: "Gmail address" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/{{params.id}}"
      method: GET
      query:
        format: full

  email.search:
    description: Search emails using Gmail query syntax
    returns: email[]
    params:
      query: { type: string, required: true, description: "Gmail search syntax: 'from:x@y.com', 'subject:invoice', 'after:2026/01/01', 'is:unread'" }
      account: { type: string, description: "Gmail address" }
      limit: { type: integer, description: "Max results (default: 20)" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages"
      method: GET
      query:
        q: ".params.query"
        maxResults: ".params.limit // 20"
      response:
        transform: ".messages // []"

  email.send:
    description: Send an email
    returns: email
    params:
      account: { type: string, description: "Gmail address to send from" }
      to: { type: string, required: true, description: "Recipient email address" }
      subject: { type: string, required: true, description: "Email subject" }
      body: { type: string, required: true, description: "Email body (plain text)" }
      cc: { type: string, description: "CC recipients (comma-separated)" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
      method: POST
      body: |
        {
          "raw": "{{[\"To: \", params.to, \"\\r\\nSubject: \", params.subject, \"\\r\\nContent-Type: text/plain\\r\\n\\r\\n\", params.body] | join(\"\") | @base64}}"
        }

# ==============================================================================
# UTILITIES
# ==============================================================================

utilities:
  get_profile:
    description: Get Gmail account profile (email address, message count, history ID)
    params:
      account: { type: string, description: "Gmail address" }
    returns:
      emailAddress: string
      messagesTotal: integer
      threadsTotal: integer
      historyId: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/profile"
      method: GET

  list_labels:
    description: List all Gmail labels (system labels and user-created labels)
    params:
      account: { type: string, description: "Gmail address" }
    returns:
      id: string
      name: string
      type: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/labels"
      method: GET
      response:
        transform: ".labels // []"


---

# Gmail

Read, search, and send email via the [Gmail REST API](https://developers.google.com/gmail/api).

## Auth — No Setup Required (with Mimestream)

If [Mimestream](https://mimestream.com/) is installed, this skill automatically borrows its Google OAuth tokens from the macOS Keychain. No OAuth app registration, no API keys to enter.

How it works:
1. Mimestream stores Google OAuth tokens in the Keychain under `"Mimestream: {email}"` / `"OAuth"`
2. The `mimestream` skill reads those tokens via its `credential.get` utility
3. This skill declares `auth: { oauth: { service: google } }`
4. The resolver matches the provider → calls `credential.get` → injects `Authorization: Bearer {token}`

**Without Mimestream:** complete the standard OAuth flow at `GET /sys/oauth/authorize/gmail`.

## Capabilities

```
OPERATION          DESCRIPTION
─────────────────  ───────────────────────────────────────────────
email.list         List emails with label/query filters
email.get          Full email with body, headers, attachments list
email.search       Search with Gmail query syntax
email.send         Send an email
get_profile        Account info (email, total messages)
list_labels        All labels (INBOX, SENT, custom labels)
```

## Gmail Query Syntax

```
is:unread                     Unread messages
from:boss@company.com         From a specific sender
subject:invoice               Subject contains "invoice"
after:2026/01/01              Messages after a date
before:2026/02/01             Messages before a date
has:attachment                Messages with attachments
label:INBOX is:unread         Unread inbox messages
```

## Accounts

Each Gmail address is a separate account. Pass `account: "user@example.com"` to
target a specific address. See the **Configured Accounts** section above for available accounts.

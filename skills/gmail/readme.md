---
id: gmail
name: Gmail
description: Full-featured Gmail skill — read, search, send, reply, forward, label, archive, draft, attachments, filters, and batch operations. Auth sourced from Mimestream (no OAuth setup needed).
color: "#EA4335"

website: https://mail.google.com
privacy_url: https://policies.google.com/privacy
connects_to: gmail

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
  Gmail skill — full-featured email via the Gmail REST API. Auth is automatic when Mimestream is installed.

  Available accounts are listed in the Configured Accounts section of this readme.
  Pass the email address as the `account` param (e.g. account: "user@example.com").

  CHOOSING THE RIGHT OPERATION:
  - To browse emails: use conversation.list (returns thread snippets) then conversation.get for full content
  - To read a specific email: use email.get with the message ID
  - email.list and email.search return ID stubs ONLY (no subject, no sender, no body) — they are useful
    for getting message IDs to pass to email.get, but do not contain readable content on their own.
  - Prefer conversation.list over email.list for browsing — threads have snippets and subjects.

  REPLYING TO EMAILS — email.reply requires 3 values from the original message:
  - thread_id: the original email's conversation_id (threadId)
  - in_reply_to: the original email's message_id header (Message-ID, not the Gmail ID)
  - subject: must start with "Re: " followed by the original subject
  Use conversation.get or email.get first to get these values.

  MANAGING EMAILS — email.modify is a single operation for all label changes:
  - Mark read:   email.modify with remove_labels: ["UNREAD"]
  - Mark unread:  email.modify with add_labels: ["UNREAD"]
  - Star:        email.modify with add_labels: ["STARRED"]
  - Unstar:      email.modify with remove_labels: ["STARRED"]
  - Archive:     email.modify with remove_labels: ["INBOX"]
  - Move to spam: email.modify with add_labels: ["SPAM"] and remove_labels: ["INBOX"]
  - Apply label:  email.modify with add_labels: ["Label_123"]

  ATTACHMENTS:
  - email.get includes attachment metadata (filename, mimeType, size, attachmentId) in data.attachments
  - Use attachment.get with the messageId and attachmentId to download the actual file content
  - Attachment data is returned as URL-safe base64

  Key concepts:
  - Messages have IDs (hex strings like "19cd96cdb6276b79") and thread IDs
  - email.search uses Gmail query syntax: "from:sender@example.com", "subject:invoice", "after:2026/01/01"
  - Labels: INBOX, SENT, DRAFT, TRASH, SPAM, STARRED, UNREAD, IMPORTANT, CATEGORY_SOCIAL, CATEGORY_PROMOTIONS, CATEGORY_UPDATES, CATEGORY_FORUMS (system labels are uppercase)
  - conversation.get returns the full thread with all messages, headers, and body content
  - Every email has a conversation_id (threadId) linking it to its thread
  - Sender and recipient accounts are auto-created as entities (from/to/cc/bcc typed references)

# ==============================================================================
# TRANSFORMERS
# ==============================================================================

transformers:
  email:
    terminology: Email
    mapping:
      # Helper pattern for headers: map+select can return [], so check length before .[0].value
      id: .id
      subject: 'if .payload then (.payload.headers | map(select(.name == "Subject")) | if length > 0 then .[0].value else "(no subject)" end) else "(no subject)" end'
      snippet: '.snippet // ""'
      timestamp: 'if .internalDate then .internalDate | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S") else null end'
      is_starred: 'if .labelIds then .labelIds | contains(["STARRED"]) else false end'
      is_unread: 'if .labelIds then .labelIds | contains(["UNREAD"]) else false end'
      is_draft: 'if .labelIds then .labelIds | contains(["DRAFT"]) else false end'
      message_id: 'if .payload then (.payload.headers | map(select(.name == "Message-ID")) | if length > 0 then .[0].value else "" end) else "" end'
      in_reply_to: 'if .payload then (.payload.headers | map(select(.name == "In-Reply-To")) | if length > 0 then .[0].value else null end) else null end'
      conversation_id: '.threadId // ""'
      # Gmail uses URL-safe base64 (- instead of +, _ instead of /). Convert before decoding.
      content: 'if .payload then (.payload.parts // [.payload] | map(select(.mimeType == "text/plain")) | if length > 0 then .[0].body.data // "" | gsub("-"; "+") | gsub("_"; "/") | @base64d else "" end) else "" end'
      data.label_ids: '.labelIds // []'
      data.size_estimate: .sizeEstimate
      data.history_id: .historyId
      data.references: 'if .payload then (.payload.headers | map(select(.name == "References")) | if length > 0 then .[0].value else null end) else null end'
      data.reply_to: 'if .payload then (.payload.headers | map(select(.name == "Reply-To")) | if length > 0 then .[0].value else null end) else null end'
      data.delivered_to: 'if .payload then (.payload.headers | map(select(.name == "Delivered-To")) | if length > 0 then .[0].value else null end) else null end'
      # Attachment metadata: extract filename, mimeType, size, attachmentId from all parts
      data.attachments: 'if .payload then (def collect_parts: if .parts then .parts[] | collect_parts else . end; [collect_parts | select(.filename != null and .filename != "" and .body.attachmentId != null) | {filename: .filename, mime_type: .mimeType, size: .body.size, attachment_id: .body.attachmentId}]) else [] end'

      # Typed reference: resolve sender as an account entity.
      # Gmail returns From as "Display Name <email@example.com>" or just "email@example.com".
      # Parses name/email with jaq, auto-creates/deduplicates account entity, links via send relationship.
      from:
        account:
          handle: 'if .payload then (.payload.headers | map(select(.name == "From")) | if length > 0 then .[0].value else null end | if . != null and test("<") then split("<") | .[1] | rtrimstr(">") elif . != null then . else null end) else null end'
          platform: '"email"'
          display_name: 'if .payload then (.payload.headers | map(select(.name == "From")) | if length > 0 then .[0].value else null end | if . != null and test("<") then split("<") | .[0] | rtrimstr(" ") | ltrimstr("\"") | rtrimstr("\"") else null end) else null end'

      # Multi-value typed references: To, Cc, Bcc recipients.
      # _source splits the header into {email, name} objects per address.
      # Split on ">, " to avoid breaking names with commas (e.g. "Bernstein, David H.").
      # Each address becomes an account entity linked to this email.
      # account[] signals the engine to create one entity per array element.
      to:
        account[]:
          _source: 'if .payload then (.payload.headers | map(select(.name == "To")) | if length > 0 then .[0].value else null end | if . != null then split(">, ") | map(ltrimstr(" ") | if test("<") then {email: (split("<") | .[1] | rtrimstr(">")), name: (split("<") | .[0] | rtrimstr(" ") | ltrimstr("\"") | rtrimstr("\""))} elif test("@") then {email: (rtrimstr(">")), name: null} else null end) | map(select(. != null)) else [] end) else [] end'
          handle: .email
          platform: '"email"'
          display_name: .name
      cc:
        account[]:
          _source: 'if .payload then (.payload.headers | map(select(.name == "Cc")) | if length > 0 then .[0].value else null end | if . != null then split(">, ") | map(ltrimstr(" ") | if test("<") then {email: (split("<") | .[1] | rtrimstr(">")), name: (split("<") | .[0] | rtrimstr(" ") | ltrimstr("\"") | rtrimstr("\""))} elif test("@") then {email: (rtrimstr(">")), name: null} else null end) | map(select(. != null)) else [] end) else [] end'
          handle: .email
          platform: '"email"'
          display_name: .name
      bcc:
        account[]:
          _source: 'if .payload then (.payload.headers | map(select(.name == "Bcc")) | if length > 0 then .[0].value else null end | if . != null then split(">, ") | map(ltrimstr(" ") | if test("<") then {email: (split("<") | .[1] | rtrimstr(">")), name: (split("<") | .[0] | rtrimstr(" ") | ltrimstr("\"") | rtrimstr("\""))} elif test("@") then {email: (rtrimstr(">")), name: null} else null end) | map(select(. != null)) else [] end) else [] end'
          handle: .email
          platform: '"email"'
          display_name: .name

  conversation:
    terminology: Thread
    mapping:
      id: .id
      # For full thread (conversation.get): use subject from first message.
      # For list stubs (conversation.list): snippet only, truncated to 120 chars.
      name: 'if .messages then (.messages | .[0].payload.headers | map(select(.name == "Subject")) | if length > 0 then .[0].value else "(no subject)" end) else (.snippet // "" | if length > 120 then .[:120] + "…" else . end) end'
      last_message: '.snippet // ""'
      last_message_at: 'if .messages then (.messages | last | .internalDate | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S")) else null end'
      data.message_count: 'if .messages then (.messages | length) else null end'
      data.history_id: .historyId

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:

  # --- Reading ---

  email.list:
    description: "List email IDs (stubs only — no subject/body). Use conversation.list to browse with snippets, or email.get for full content."
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
    description: Get a specific email with full body content, headers, and attachment metadata
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
    description: "Search for email IDs using Gmail query syntax (stubs only — use email.get for full content)"
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

  conversation.list:
    description: List email threads with snippets, optionally filtered by label or search query (best for browsing)
    returns: conversation[]
    params:
      account: { type: string, description: "Gmail address — see Configured Accounts in readme" }
      query: { type: string, description: "Gmail search query (e.g. 'from:boss@company.com is:unread')" }
      label_ids: { type: array, description: "Filter by label IDs (e.g. ['INBOX'])" }
      limit: { type: integer, description: "Max results (default: 20)" }
      page_token: { type: string, description: "Token for next page of results" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/threads"
      method: GET
      query:
        maxResults: ".params.limit // 20"
        q: ".params.query"
        pageToken: ".params.page_token"
        labelIds: ".params.label_ids"
      response:
        transform: ".threads // []"

  conversation.get:
    description: Get a full email thread with all messages, headers, body content, and attachment metadata
    returns: conversation
    params:
      id: { type: string, required: true, description: "Thread ID from conversation.list or email's conversation_id" }
      account: { type: string, description: "Gmail address" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/threads/{{params.id}}"
      method: GET
      query:
        format: full

  # --- Sending ---

  email.send:
    description: Send a new email (plain text or HTML)
    returns: email
    params:
      account: { type: string, description: "Gmail address to send from" }
      to: { type: string, required: true, description: "Recipient email address(es), comma-separated" }
      subject: { type: string, required: true, description: "Email subject" }
      body: { type: string, required: true, description: "Email body (plain text)" }
      html_body: { type: string, description: "HTML body (takes priority over body if provided)" }
      cc: { type: string, description: "CC recipients (comma-separated)" }
      bcc: { type: string, description: "BCC recipients (comma-separated)" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
      method: POST
      body: |
        {
          "raw": "{{["To: ", params.to, "\r\n", (if params.cc then ["Cc: ", params.cc, "\r\n"] | join("") else "" end), (if params.bcc then ["Bcc: ", params.bcc, "\r\n"] | join("") else "" end), "Subject: ", params.subject, "\r\nMIME-Version: 1.0\r\nContent-Type: ", (if params.html_body then "text/html" else "text/plain" end), "; charset=utf-8\r\n\r\n", (if params.html_body then params.html_body else params.body end)] | join("") | @base64}}"
        }

  email.reply:
    description: "Reply to an email (stays in the same thread). Get the original email first with email.get to obtain thread_id, in_reply_to, and subject."
    returns: email
    params:
      account: { type: string, description: "Gmail address to send from" }
      to: { type: string, required: true, description: "Recipient email address(es)" }
      thread_id: { type: string, required: true, description: "Thread ID (the original email's conversation_id / threadId)" }
      in_reply_to: { type: string, required: true, description: "Message-ID header of the email being replied to (e.g. '<abc@mail.gmail.com>')" }
      subject: { type: string, required: true, description: "Must start with 'Re: ' followed by original subject" }
      body: { type: string, required: true, description: "Reply body (plain text)" }
      html_body: { type: string, description: "HTML reply body (takes priority over body)" }
      cc: { type: string, description: "CC recipients (comma-separated)" }
      bcc: { type: string, description: "BCC recipients (comma-separated)" }
      references: { type: string, description: "References header chain (from original email's data.references + message_id)" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
      method: POST
      body: |
        {
          "raw": "{{["To: ", params.to, "\r\n", (if params.cc then ["Cc: ", params.cc, "\r\n"] | join("") else "" end), (if params.bcc then ["Bcc: ", params.bcc, "\r\n"] | join("") else "" end), "Subject: ", params.subject, "\r\nIn-Reply-To: ", params.in_reply_to, "\r\nReferences: ", (if params.references then params.references else params.in_reply_to end), "\r\nMIME-Version: 1.0\r\nContent-Type: ", (if params.html_body then "text/html" else "text/plain" end), "; charset=utf-8\r\n\r\n", (if params.html_body then params.html_body else params.body end)] | join("") | @base64}}",
          "threadId": "{{params.thread_id}}"
        }

  email.forward:
    description: "Forward an email. Get the original email first with email.get to obtain the body content, then compose a new message with the forwarded content."
    returns: email
    params:
      account: { type: string, description: "Gmail address to send from" }
      to: { type: string, required: true, description: "Recipient email address(es) to forward to" }
      subject: { type: string, required: true, description: "Subject (typically 'Fwd: ' followed by original subject)" }
      body: { type: string, required: true, description: "Message body including the forwarded content" }
      html_body: { type: string, description: "HTML body (takes priority over body)" }
      cc: { type: string, description: "CC recipients (comma-separated)" }
      bcc: { type: string, description: "BCC recipients (comma-separated)" }
      thread_id: { type: string, description: "Original thread ID (to keep forward in same thread)" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
      method: POST
      body: |
        {
          "raw": "{{["To: ", params.to, "\r\n", (if params.cc then ["Cc: ", params.cc, "\r\n"] | join("") else "" end), (if params.bcc then ["Bcc: ", params.bcc, "\r\n"] | join("") else "" end), "Subject: ", params.subject, "\r\nMIME-Version: 1.0\r\nContent-Type: ", (if params.html_body then "text/html" else "text/plain" end), "; charset=utf-8\r\n\r\n", (if params.html_body then params.html_body else params.body end)] | join("") | @base64}}"
          {{- if params.thread_id then [", \"threadId\": \"", params.thread_id, "\""] | join("") else "" end}}
        }

  # --- Modifying ---

  email.modify:
    description: "Modify email labels — mark read/unread, star/unstar, archive, move to spam, apply/remove labels"
    returns: email
    params:
      id: { type: string, required: true, description: "Message ID" }
      account: { type: string, description: "Gmail address" }
      add_labels: { type: array, description: "Label IDs to add (e.g. ['STARRED', 'UNREAD', 'Label_123'])" }
      remove_labels: { type: array, description: "Label IDs to remove (e.g. ['INBOX', 'UNREAD'])" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/{{params.id}}/modify"
      method: POST
      body: |
        {
          "addLabelIds": {{params.add_labels // []}},
          "removeLabelIds": {{params.remove_labels // []}}
        }

  email.trash:
    description: Move an email to trash
    returns: email
    params:
      id: { type: string, required: true, description: "Message ID" }
      account: { type: string, description: "Gmail address" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/{{params.id}}/trash"
      method: POST

  email.untrash:
    description: Remove an email from trash
    returns: email
    params:
      id: { type: string, required: true, description: "Message ID" }
      account: { type: string, description: "Gmail address" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/{{params.id}}/untrash"
      method: POST

  email.batch_modify:
    description: "Modify labels on multiple emails at once (max 1000 IDs)"
    returns: void
    params:
      account: { type: string, description: "Gmail address" }
      ids: { type: array, required: true, description: "Array of message IDs (max 1000)" }
      add_labels: { type: array, description: "Label IDs to add" }
      remove_labels: { type: array, description: "Label IDs to remove" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/batchModify"
      method: POST
      body: |
        {
          "ids": {{params.ids}},
          "addLabelIds": {{params.add_labels // []}},
          "removeLabelIds": {{params.remove_labels // []}}
        }

  email.batch_delete:
    description: "Permanently delete multiple emails (CANNOT BE UNDONE — max 1000 IDs)"
    returns: void
    params:
      account: { type: string, description: "Gmail address" }
      ids: { type: array, required: true, description: "Array of message IDs to permanently delete (max 1000)" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/batchDelete"
      method: POST
      body: |
        {
          "ids": {{params.ids}}
        }

  # Drafts, labels, and filters are in utilities (not entity-typed operations)

# ==============================================================================
# UTILITIES
# ==============================================================================

utilities:

  # --- Drafts ---

  list_drafts:
    description: List drafts
    params:
      account: { type: string, description: "Gmail address" }
      query: { type: string, description: "Gmail search query to filter drafts" }
      limit: { type: integer, description: "Max results (default: 20)" }
      page_token: { type: string, description: "Token for next page of results" }
    returns:
      id: string
      message: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
      method: GET
      query:
        maxResults: ".params.limit // 20"
        q: ".params.query"
        pageToken: ".params.page_token"
      response:
        transform: ".drafts // []"

  get_draft:
    description: Get a draft with full message content
    params:
      id: { type: string, required: true, description: "Draft ID from list_drafts" }
      account: { type: string, description: "Gmail address" }
    returns:
      id: string
      message: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/drafts/{{params.id}}"
      method: GET
      query:
        format: full

  create_draft:
    description: Create a new draft email
    params:
      account: { type: string, description: "Gmail address" }
      to: { type: string, required: true, description: "Recipient email address(es)" }
      subject: { type: string, required: true, description: "Email subject" }
      body: { type: string, required: true, description: "Email body (plain text)" }
      html_body: { type: string, description: "HTML body (takes priority over body)" }
      cc: { type: string, description: "CC recipients (comma-separated)" }
      bcc: { type: string, description: "BCC recipients (comma-separated)" }
      thread_id: { type: string, description: "Thread ID to associate the draft with" }
    returns:
      id: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
      method: POST
      body: |
        {
          "message": {
            "raw": "{{["To: ", params.to, "\r\n", (if params.cc then ["Cc: ", params.cc, "\r\n"] | join("") else "" end), (if params.bcc then ["Bcc: ", params.bcc, "\r\n"] | join("") else "" end), "Subject: ", params.subject, "\r\nMIME-Version: 1.0\r\nContent-Type: ", (if params.html_body then "text/html" else "text/plain" end), "; charset=utf-8\r\n\r\n", (if params.html_body then params.html_body else params.body end)] | join("") | @base64}}"
            {{- if params.thread_id then [", \"threadId\": \"", params.thread_id, "\""] | join("") else "" end}}
          }
        }

  update_draft:
    description: Update an existing draft
    params:
      id: { type: string, required: true, description: "Draft ID to update" }
      account: { type: string, description: "Gmail address" }
      to: { type: string, required: true, description: "Recipient email address(es)" }
      subject: { type: string, required: true, description: "Email subject" }
      body: { type: string, required: true, description: "Email body (plain text)" }
      html_body: { type: string, description: "HTML body (takes priority over body)" }
      cc: { type: string, description: "CC recipients (comma-separated)" }
      bcc: { type: string, description: "BCC recipients (comma-separated)" }
    returns:
      id: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/drafts/{{params.id}}"
      method: PUT
      body: |
        {
          "message": {
            "raw": "{{["To: ", params.to, "\r\n", (if params.cc then ["Cc: ", params.cc, "\r\n"] | join("") else "" end), (if params.bcc then ["Bcc: ", params.bcc, "\r\n"] | join("") else "" end), "Subject: ", params.subject, "\r\nMIME-Version: 1.0\r\nContent-Type: ", (if params.html_body then "text/html" else "text/plain" end), "; charset=utf-8\r\n\r\n", (if params.html_body then params.html_body else params.body end)] | join("") | @base64}}"
          }
        }

  send_draft:
    description: Send an existing draft
    params:
      id: { type: string, required: true, description: "Draft ID to send" }
      account: { type: string, description: "Gmail address" }
    returns:
      id: string
      threadId: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/drafts/send"
      method: POST
      body: |
        {
          "id": "{{params.id}}"
        }

  delete_draft:
    description: "Permanently delete a draft (CANNOT BE UNDONE)"
    params:
      id: { type: string, required: true, description: "Draft ID to delete" }
      account: { type: string, description: "Gmail address" }
    returns:
      status: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/drafts/{{params.id}}"
      method: DELETE

  # --- Account ---

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

  get_attachment:
    description: "Download an email attachment (returns base64url-encoded data). Use email.get to find attachment IDs in data.attachments."
    params:
      message_id: { type: string, required: true, description: "Message ID the attachment belongs to" }
      attachment_id: { type: string, required: true, description: "Attachment ID from email.get's data.attachments[].attachment_id" }
      account: { type: string, description: "Gmail address" }
    returns:
      data: string
      size: integer
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/{{params.message_id}}/attachments/{{params.attachment_id}}"
      method: GET

  get_raw:
    description: "Get the full RFC 2822 raw source of an email (base64url-encoded)"
    params:
      id: { type: string, required: true, description: "Message ID" }
      account: { type: string, description: "Gmail address" }
    returns:
      raw: string
      id: string
      threadId: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/messages/{{params.id}}"
      method: GET
      query:
        format: raw

  get_history:
    description: "Get incremental changes since a history ID (for efficient sync). Get the starting historyId from get_profile or any previous email/thread response."
    params:
      start_history_id: { type: string, required: true, description: "History ID to start from" }
      account: { type: string, description: "Gmail address" }
      label_id: { type: string, description: "Filter changes to a specific label" }
      history_types: { type: array, description: "Filter to specific change types: messageAdded, messageDeleted, labelAdded, labelRemoved" }
      limit: { type: integer, description: "Max results (default: 100)" }
      page_token: { type: string, description: "Token for next page" }
    returns:
      history: array
      historyId: string
      nextPageToken: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/history"
      method: GET
      query:
        startHistoryId: ".params.start_history_id"
        labelId: ".params.label_id"
        historyTypes: ".params.history_types"
        maxResults: ".params.limit // 100"
        pageToken: ".params.page_token"

  get_vacation:
    description: Get vacation/auto-reply settings
    params:
      account: { type: string, description: "Gmail address" }
    returns:
      enableAutoReply: boolean
      responseSubject: string
      responseBodyPlainText: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/settings/vacation"
      method: GET

  set_vacation:
    description: Set or disable vacation/auto-reply
    returns:
      enableAutoReply: boolean
      responseSubject: string
    params:
      account: { type: string, description: "Gmail address" }
      enabled: { type: boolean, required: true, description: "Enable or disable auto-reply" }
      subject: { type: string, description: "Auto-reply subject (required if enabled)" }
      body: { type: string, description: "Auto-reply body in plain text" }
      html_body: { type: string, description: "Auto-reply body in HTML" }
      contacts_only: { type: boolean, description: "Only reply to contacts (default: false)" }
      domain_only: { type: boolean, description: "Only reply to same domain (default: false)" }
      start_time: { type: integer, description: "Start time in milliseconds since epoch" }
      end_time: { type: integer, description: "End time in milliseconds since epoch" }
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/settings/vacation"
      method: PUT
      body: |
        {
          "enableAutoReply": {{params.enabled}},
          "responseSubject": "{{params.subject // ""}}",
          "responseBodyPlainText": "{{params.body // ""}}",
          "responseBodyHtml": "{{params.html_body // ""}}",
          "restrictToContacts": {{params.contacts_only // false}},
          "restrictToDomain": {{params.domain_only // false}}
          {{- if params.start_time then [", \"startTime\": ", (params.start_time | tostring)] | join("") else "" end}}
          {{- if params.end_time then [", \"endTime\": ", (params.end_time | tostring)] | join("") else "" end}}
        }

  create_label:
    description: Create a new Gmail label
    params:
      account: { type: string, description: "Gmail address" }
      name: { type: string, required: true, description: "Label name (use / for nesting, e.g. 'Projects/AgentOS')" }
      show_in_label_list: { type: string, description: "Visibility in label list: labelShow (default), labelShowIfUnread, labelHide" }
      show_in_message_list: { type: string, description: "Visibility in message list: show (default), hide" }
    returns:
      id: string
      name: string
      type: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/labels"
      method: POST
      body: |
        {
          "name": "{{params.name}}",
          "labelListVisibility": "{{params.show_in_label_list // "labelShow"}}",
          "messageListVisibility": "{{params.show_in_message_list // "show"}}"
        }

  update_label:
    description: Update a Gmail label (name, visibility)
    params:
      id: { type: string, required: true, description: "Label ID" }
      account: { type: string, description: "Gmail address" }
      name: { type: string, description: "New label name" }
      show_in_label_list: { type: string, description: "labelShow, labelShowIfUnread, or labelHide" }
      show_in_message_list: { type: string, description: "show or hide" }
    returns:
      id: string
      name: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/labels/{{params.id}}"
      method: PATCH
      body: |
        {
          {{- if params.name then ["\"name\": \"", params.name, "\""] | join("") else "" end}}
          {{- if params.show_in_label_list then [", \"labelListVisibility\": \"", params.show_in_label_list, "\""] | join("") else "" end}}
          {{- if params.show_in_message_list then [", \"messageListVisibility\": \"", params.show_in_message_list, "\""] | join("") else "" end}}
        }

  delete_label:
    description: "Delete a Gmail label (does not delete the emails, just removes the label)"
    params:
      id: { type: string, required: true, description: "Label ID (not the name — use list_labels to find IDs)" }
      account: { type: string, description: "Gmail address" }
    returns:
      status: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/labels/{{params.id}}"
      method: DELETE

  list_filters:
    description: List all server-side email filters/rules
    params:
      account: { type: string, description: "Gmail address" }
    returns:
      id: string
      criteria: string
      action: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/settings/filters"
      method: GET
      response:
        transform: ".filter // []"

  create_filter:
    description: Create a server-side email filter/rule
    params:
      account: { type: string, description: "Gmail address" }
      from: { type: string, description: "Match sender address" }
      to: { type: string, description: "Match recipient address" }
      subject: { type: string, description: "Match subject" }
      query: { type: string, description: "Match Gmail query" }
      has_attachment: { type: boolean, description: "Match messages with attachments" }
      add_labels: { type: array, description: "Label IDs to add to matching messages" }
      remove_labels: { type: array, description: "Label IDs to remove (e.g. ['INBOX'] to skip inbox)" }
      forward_to: { type: string, description: "Email address to forward matching messages to" }
    returns:
      id: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/settings/filters"
      method: POST
      body: |
        {
          "criteria": {
            {{- if params.from then ["\"from\": \"", params.from, "\""] | join("") else "" end}}
            {{- if params.to then [", \"to\": \"", params.to, "\""] | join("") else "" end}}
            {{- if params.subject then [", \"subject\": \"", params.subject, "\""] | join("") else "" end}}
            {{- if params.query then [", \"query\": \"", params.query, "\""] | join("") else "" end}}
            {{- if params.has_attachment then ", \"hasAttachment\": true" else "" end}}
          },
          "action": {
            "addLabelIds": {{params.add_labels // []}},
            "removeLabelIds": {{params.remove_labels // []}}
            {{- if params.forward_to then [", \"forward\": \"", params.forward_to, "\""] | join("") else "" end}}
          }
        }

  delete_filter:
    description: Delete a server-side email filter/rule
    params:
      id: { type: string, required: true, description: "Filter ID from list_filters" }
      account: { type: string, description: "Gmail address" }
    returns:
      status: string
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/settings/filters/{{params.id}}"
      method: DELETE

  list_send_as:
    description: "List send-as aliases (email addresses you can send from)"
    params:
      account: { type: string, description: "Gmail address" }
    returns:
      sendAsEmail: string
      displayName: string
      isDefault: boolean
      isPrimary: boolean
    rest:
      url: "https://gmail.googleapis.com/gmail/v1/users/me/settings/sendAs"
      method: GET
      response:
        transform: ".sendAs // []"


---

# Gmail

Full-featured email via the [Gmail REST API](https://developers.google.com/gmail/api) — read, search, send, reply, forward, label, archive, draft, attachments, filters, and batch operations.

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
OPERATION             DESCRIPTION
────────────────────  ───────────────────────────────────────────────────
conversation.list     Browse threads with snippets (best for browsing)
conversation.get      Full thread with all messages, headers, body
email.get             Full email with body, headers, attachment metadata
email.list            Email ID stubs (use conversation.list to browse)
email.search          Search email IDs with Gmail query syntax
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

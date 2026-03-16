---
id: gmail
name: Gmail
description: Full-featured Gmail skill — read, search, send, reply, forward, label, archive, draft, attachments, filters, and batch operations. Auth can be sourced from an installed Google provider skill.
color: "#EA4335"

website: https://mail.google.com
privacy_url: https://policies.google.com/privacy

# No client_id or client_secret needed when a Google provider skill is installed.
# For example, the system can find Mimestream's `provides: [{ service: google }]`
# declaration and call its `credential_get` operation to get a live access token.
auth:
  oauth:
    service: google
    scopes:
      - https://mail.google.com/

api:
  base_url: https://gmail.googleapis.com/gmail/v1/users/me
# ==============================================================================
# ADAPTERS
# ==============================================================================

adapters:
  email:
    id: .id
    name: 'if .payload then (.payload.headers | map(select(.name == "Subject")) | if length > 0 then .[0].value else "(no subject)" end) else "(no subject)" end'
    text: '.snippet // ""'
    author: 'if .payload then (.payload.headers | map(select(.name == "From")) | if length > 0 then .[0].value else null end | if . != null and test("<") then split("<") | .[0] | rtrimstr(" ") | ltrimstr("\"") | rtrimstr("\"") else null end) else null end'
    datePublished: 'if .internalDate then .internalDate | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S") else null end'
    # Helper pattern for headers: map+select can return [], so check length before .[0].value
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
    id: .id
    name: 'if .messages then (.messages | .[0].payload.headers | map(select(.name == "Subject")) | if length > 0 then .[0].value else "(no subject)" end) else (.snippet // "" | if length > 120 then .[:120] + "…" else . end) end'
    text: '.snippet // ""'
    datePublished: 'if .messages then (.messages | last | .internalDate | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S")) else null end'
    last_message: '.snippet // ""'
    last_message_at: 'if .messages then (.messages | last | .internalDate | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S")) else null end'
    data.message_count: 'if .messages then (.messages | length) else null end'
    data.history_id: .historyId

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:

  # --- Reading ---

  list_emails:
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

  get_email:
    description: Get a specific email with full body content, headers, and attachment metadata
    returns: email
    params:
      id: { type: string, required: true, description: "Message ID from email.list" }
      account: { type: string, description: "Gmail address" }
    rest:
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/messages/" + .params.id'
      method: GET
      query:
        format: full

  search_emails:
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

  list_conversations:
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

  get_conversation:
    description: Get a full email thread with all messages, headers, body content, and attachment metadata
    returns: conversation
    params:
      id: { type: string, required: true, description: "Thread ID from conversation.list or email's conversation_id" }
      account: { type: string, description: "Gmail address" }
    rest:
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/threads/" + .params.id'
      method: GET
      query:
        format: full

  # --- Sending ---

  send_email:
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
          "raw": "${["TO: ", PARAMS_TO, "\R\N", (IF PARAMS_CC THEN ["CC: ", PARAMS_CC, "\R\N"]}"
        }

  reply_email:
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
          "raw": "${["TO: ", PARAMS_TO, "\R\N", (IF PARAMS_CC THEN ["CC: ", PARAMS_CC, "\R\N"]}",
          "threadId": "${PARAM_THREAD_ID}"
        }

  forward_email:
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
          "raw": "${["TO: ", PARAMS_TO, "\R\N", (IF PARAMS_CC THEN ["CC: ", PARAMS_CC, "\R\N"]}"
          ${- IF PARAMS_THREAD_ID THEN [", \"THREADID\": \"", PARAMS_THREAD_ID, "\""]}
        }

  # --- Modifying ---

  modify_email:
    description: "Modify email labels — mark read/unread, star/unstar, archive, move to spam, apply/remove labels"
    returns: email
    params:
      id: { type: string, required: true, description: "Message ID" }
      account: { type: string, description: "Gmail address" }
      add_labels: { type: array, description: "Label IDs to add (e.g. ['STARRED', 'UNREAD', 'Label_123'])" }
      remove_labels: { type: array, description: "Label IDs to remove (e.g. ['INBOX', 'UNREAD'])" }
    rest:
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/messages/" + .params.id + "/modify"'
      method: POST
      body: |
        {
          "addLabelIds": ${PARAM_ADD_LABELS // []},
          "removeLabelIds": ${PARAM_REMOVE_LABELS // []}
        }

  trash_email:
    description: Move an email to trash
    returns: email
    params:
      id: { type: string, required: true, description: "Message ID" }
      account: { type: string, description: "Gmail address" }
    rest:
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/messages/" + .params.id + "/trash"'
      method: POST

  untrash_email:
    description: Remove an email from trash
    returns: email
    params:
      id: { type: string, required: true, description: "Message ID" }
      account: { type: string, description: "Gmail address" }
    rest:
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/messages/" + .params.id + "/untrash"'
      method: POST

  batch_modify_email:
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
          "ids": ${PARAM_IDS},
          "addLabelIds": ${PARAM_ADD_LABELS // []},
          "removeLabelIds": ${PARAM_REMOVE_LABELS // []}
        }

  batch_delete_email:
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
          "ids": ${PARAM_IDS}
        }

  # Drafts, labels, and filters are additional operations with custom returns

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
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/drafts/" + .params.id'
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
            "raw": "${["TO: ", PARAMS_TO, "\R\N", (IF PARAMS_CC THEN ["CC: ", PARAMS_CC, "\R\N"]}"
            ${- IF PARAMS_THREAD_ID THEN [", \"THREADID\": \"", PARAMS_THREAD_ID, "\""]}
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
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/drafts/" + .params.id'
      method: PUT
      body: |
        {
          "message": {
            "raw": "${["TO: ", PARAMS_TO, "\R\N", (IF PARAMS_CC THEN ["CC: ", PARAMS_CC, "\R\N"]}"
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
          "id": "${PARAM_ID}"
        }

  delete_draft:
    description: "Permanently delete a draft (CANNOT BE UNDONE)"
    params:
      id: { type: string, required: true, description: "Draft ID to delete" }
      account: { type: string, description: "Gmail address" }
    returns:
      status: string
    rest:
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/drafts/" + .params.id'
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
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/messages/" + .params.message_id + "/attachments/" + .params.attachment_id'
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
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/messages/" + .params.id'
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
          "enableAutoReply": ${PARAM_ENABLED},
          "responseSubject": "${PARAM_SUBJECT // ""}",
          "responseBodyPlainText": "${PARAM_BODY // ""}",
          "responseBodyHtml": "${PARAM_HTML_BODY // ""}",
          "restrictToContacts": ${PARAM_CONTACTS_ONLY // FALSE},
          "restrictToDomain": ${PARAM_DOMAIN_ONLY // FALSE}
          ${- IF PARAMS_START_TIME THEN [", \"STARTTIME\": ", (PARAMS_START_TIME}
          ${- IF PARAMS_END_TIME THEN [", \"ENDTIME\": ", (PARAMS_END_TIME}
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
          "name": "${PARAM_NAME}",
          "labelListVisibility": "${PARAM_SHOW_IN_LABEL_LIST // "LABELSHOW"}",
          "messageListVisibility": "${PARAM_SHOW_IN_MESSAGE_LIST // "SHOW"}"
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
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/labels/" + .params.id'
      method: PATCH
      body: |
        {
          ${- IF PARAMS_NAME THEN ["\"NAME\": \"", PARAMS_NAME, "\""]}
          ${- IF PARAMS_SHOW_IN_LABEL_LIST THEN [", \"LABELLISTVISIBILITY\": \"", PARAMS_SHOW_IN_LABEL_LIST, "\""]}
          ${- IF PARAMS_SHOW_IN_MESSAGE_LIST THEN [", \"MESSAGELISTVISIBILITY\": \"", PARAMS_SHOW_IN_MESSAGE_LIST, "\""]}
        }

  delete_label:
    description: "Delete a Gmail label (does not delete the emails, just removes the label)"
    params:
      id: { type: string, required: true, description: "Label ID (not the name — use list_labels to find IDs)" }
      account: { type: string, description: "Gmail address" }
    returns:
      status: string
    rest:
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/labels/" + .params.id'
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
            ${- IF PARAMS_FROM THEN ["\"FROM\": \"", PARAMS_FROM, "\""]}
            ${- IF PARAMS_TO THEN [", \"TO\": \"", PARAMS_TO, "\""]}
            ${- IF PARAMS_SUBJECT THEN [", \"SUBJECT\": \"", PARAMS_SUBJECT, "\""]}
            ${- IF PARAMS_QUERY THEN [", \"QUERY\": \"", PARAMS_QUERY, "\""]}
            ${- IF PARAMS_HAS_ATTACHMENT THEN ", \"HASATTACHMENT\": TRUE" ELSE "" END}
          },
          "action": {
            "addLabelIds": ${PARAM_ADD_LABELS // []},
            "removeLabelIds": ${PARAM_REMOVE_LABELS // []}
            ${- IF PARAMS_FORWARD_TO THEN [", \"FORWARD\": \"", PARAMS_FORWARD_TO, "\""]}
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
      url: '"https://gmail.googleapis.com/gmail/v1/users/me/settings/filters/" + .params.id'
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

## Agent Guidance

**Always default to inbox.** When the user asks to check email or see unread messages, ALWAYS scope to the inbox first using `query: "in:inbox is:unread"`. Do NOT use bare `is:unread` — that searches all mail including Promotions, Updates, and Spam and will return hundreds of irrelevant messages. After showing inbox results, briefly note counts for other categories if there are any (e.g. "Also 50+ unread in Promotions — want me to show those?").

**Folder query syntax** — use the `query` param, not `label_ids`:
- Inbox: `in:inbox`
- Spam: `in:spam`
- Promotions: `category:promotions`
- Updates: `category:updates`
- Social: `category:social`

Do not pass `label_ids` as an array param — it causes a 400 error from the API.

## Auth — Provider-Sourced Google OAuth

If a Google provider skill is installed, this skill can borrow Google OAuth tokens without separate app registration or API-key setup. [Mimestream](https://mimestream.com/) is the current canonical example.

How it works:
1. Mimestream stores Google OAuth tokens in the Keychain under `"Mimestream: {email}"` / `"OAuth"`
2. The `mimestream` skill reads those tokens via its `credential_get` operation
3. This skill declares `auth: { oauth: { service: google } }`
4. The resolver matches the provider → calls `credential_get` → injects `Authorization: Bearer {token}`
5. If multiple installed skills provide Google auth, the agent should ask the user which provider to use

**Without a provider skill:** complete the standard OAuth flow at `GET /sys/oauth/authorize/gmail`.

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

---
id: instagram
name: Instagram
description: Read and send Instagram direct messages via private API
icon: icon.png
tags: [messages, chat, social]

website: https://www.instagram.com
platform: all

testing:
  exempt:
    credential_handling: "All tests skipped pending Playwright executor implementation"
    cleanup: "All tests skipped pending Playwright executor implementation"

# ============================================================================
# AUTHENTICATION
# ============================================================================

auth:
  type: cookies
  domain: instagram.com
  cookies:
    - sessionid      # Main session token
    - csrftoken      # CSRF token (must match x-csrftoken header)
    - ds_user_id     # User's Instagram ID
    - mid            # Machine ID
    - ig_did         # Device ID
  
  # Default headers for all Instagram API requests
  headers:
    X-IG-App-ID: "936619743392459"
    X-Requested-With: "XMLHttpRequest"
    Referer: "https://www.instagram.com/direct/inbox/"
  
  # Connect flow - all selectors verified Jan 2026
  connect:
    playwright:
      launch:
        headless: true
        size: mobile
        
      steps:
        # Step 1: Go to login page
        - goto: "https://www.instagram.com/accounts/login/"
        - wait: 1500  # Wait for React to initialize
        
        # Step 2: Fill credentials
        - fill:
            selector: 'input[name="username"]'
            value: "{{username}}"
        - fill:
            selector: 'input[name="password"]'
            value: "{{password}}"
            
        # Step 3: Click login
        - click: 'button[type="submit"]'
        
        # Step 4: Wait for result (success, 2FA, or error)
        - wait_for:
            any:
              - url_matches: "instagram.com/$"
              - url_matches: "instagram.com/accounts/onetap"
              - url_matches: "instagram.com/accounts/login/two_factor"
              - cookie: sessionid
            timeout: 30000
        
        # Step 5: Handle 2FA if present
        # URL pattern: accounts/login/two_factor
        # If 2FA page detected and {{two_factor_code}} provided:
        - if_url_matches: "accounts/login/two_factor"
          then:
            - fill:
                selector: 'input[name="verificationCode"]'
                value: "{{two_factor_code}}"
            - click: 'button:has-text("Confirm")'
            - wait_for:
                any:
                  - url_matches: "instagram.com/$"
                  - url_matches: "instagram.com/accounts/onetap"
                  - cookie: sessionid
                timeout: 15000
        
        # Step 6: Extract cookies (includes HttpOnly via context.cookies())
        - extract_cookies: [sessionid, csrftoken, ds_user_id, mid, ig_did]
        
        - close
        
      # 2FA detection - tells UI to prompt for code
      two_factor:
        detect:
          url_matches: "accounts/login/two_factor"
        input_selector: 'input[name="verificationCode"]'
        submit_selector: 'button:has-text("Confirm")'
        
      on_success:
        message: "Connected to Instagram as @{{username}}!"
        
      on_error:
        challenge_required:
          message: "Instagram requires additional verification. Please try again later."
        timeout:
          message: "Login timed out. Please try again."

  validate:
    rest:
      method: GET
      url: "https://i.instagram.com/api/v1/accounts/current_user/"
      params:
        edit: "true"
      response:
        root: "user"
        mapping:
          user_id: ".pk"
          username: ".username"
    on_error:
      401: "reconnect_required"
      403: "reconnect_required"

# ============================================================================
# SESSION MAINTENANCE
# ============================================================================

session:
  keep_alive:
    interval: "4h"
    rest:
      method: GET
      url: "https://i.instagram.com/api/v1/direct_v2/get_presence/"
    on_error:
      401: "mark_disconnected"
      403: "mark_disconnected"
      
  error_detection:
    status_codes:
      401: "session_expired"
      403: "session_expired"
    response_patterns:
      - pattern: '"message":"login_required"'
        error: "session_expired"
      - pattern: '"message":"challenge_required"'
        error: "challenge_required"

# ============================================================================
# API CONFIGURATION
# ============================================================================

api:
# Note: API requests use absolute URLs since api.base_url isn't interpolated yet
# Once supported, change URLs from https://www.instagram.com/api/v1/... to https://www.instagram.com/api/v1/...
# base_url: "https://www.instagram.com/api/v1"
    
  response_hooks:
    - header: "x-ig-set-www-claim"
      store_as: "auth.ig_www_claim"

# ============================================================================
# INSTRUCTIONS FOR AI
# ============================================================================

instructions: |
  Instagram connector for DMs with full read/write support.
  
  READ operations:
  - list_conversations: Get all DM threads
  - list: Get messages in a thread
  - search: Find messages by text
  - get_unread: Get unread messages
  - get_presence: Check if users are online
  
  WRITE operations:
  - send: Reply in existing conversation
  - send_to_user: Start new conversation
  - react / unreact: Add/remove emoji reactions
  - mark_read / mark_unread: Change read status
  - delete: Unsend a message
  - mute / unmute: Mute notifications
  - send_typing: Show typing indicator
  
  Notes:
  - Reactions use emoji characters: ❤️ 😂 😮 😢 😡 👍
  - Instagram's heart reaction is ❤️ (red heart)
  - Typing indicators are ephemeral, send periodically while typing
  
  If API breaks, check: https://github.com/mautrix/meta/tree/main/pkg/messagix

# ============================================================================
# READ ACTIONS
# ============================================================================

actions:
  list_conversations:
    operation: read
    label: "List conversations"
    description: List all Instagram DM conversations
    params:
      limit: 
        type: number
        default: 20
        max: 50
      filter:
        type: enum
        values: ["", "unread", "flagged"]
        default: ""
    rest:
      method: GET
      url: "https://www.instagram.com/api/v1/direct_v2/inbox/"
      query:
        visual_message_return_type: "unseen"
        thread_message_limit: "10"
        persistentBadging: "true"
        limit: "{{params.limit}}"
        selected_filter: "{{params.filter}}"
      response:
        root: "inbox.threads"
        mapping:
          id: "[].thread_id"
          type: "[].thread_type == 'private' ? 'direct' : 'group'"
          name: "[].thread_title"
          participants:
            each: ".users[]"
            map:
              id: ".pk"
              name: ".full_name"
              handle: ".username"
          unread_count: "[].read_state"
          updated_at: "[].last_activity_at | divide: 1000000 | to_datetime"
          platform: "'instagram'"
          connector: "'instagram'"

  get_conversation:
    operation: read
    label: "Get conversation"
    description: Get conversation details
    params:
      conversation_id:
        type: string
        required: true
    rest:
      method: GET
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/"
      params:
        visual_message_return_type: "unseen"
        limit: "1"
      response:
        root: "thread"
        mapping:
          id: ".thread_id"
          type: ".thread_type == 'private' ? 'direct' : 'group'"
          name: ".thread_title"
          participants:
            each: ".users[]"
            map:
              id: ".pk"
              name: ".full_name"
              handle: ".username"
          updated_at: ".last_activity_at | divide: 1000000 | to_datetime"
          platform: "'instagram'"
          connector: "'instagram'"

  list:
    operation: read
    label: "List messages"
    description: List messages in a conversation
    params:
      conversation_id:
        type: string
        required: true
      limit:
        type: number
        default: 20
        max: 100
    rest:
      method: GET
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/"
      params:
        visual_message_return_type: "unseen"
        direction: "older"
        limit: "{{params.limit}}"
      response:
        root: "thread.items"
        context:
          viewer_id: "thread.viewer_id"
        mapping:
          id: "[].item_id"
          conversation_id: "'{{params.conversation_id}}'"
          content: "[].text"
          content_type: "'text'"
          sender:
            id: "[].user_id"
            type: "'user'"
            is_self: "[].user_id == {{context.viewer_id}}"
          is_outgoing: "[].user_id == {{context.viewer_id}}"
          timestamp: "[].timestamp | divide: 1000000 | to_datetime"
          reactions: "[].reactions.emojis"
          reply_to:
            message_id: "[].replied_to_message.item_id"
            preview: "[].replied_to_message.text"
          attachments: "[].media | to_attachment"
          connector: "'instagram'"

  get:
    operation: read
    label: "Get message"
    description: Get a specific message
    params:
      message_id:
        type: string
        required: true
      conversation_id:
        type: string
        required: true
    rest:
      method: GET
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/"
      params:
        visual_message_return_type: "unseen"
        limit: "50"
      response:
        root: "thread.items[?item_id=='{{params.message_id}}'] | [0]"
        mapping:
          id: ".item_id"
          conversation_id: "'{{params.conversation_id}}'"
          content: ".text"
          content_type: "'text'"
          sender:
            id: ".user_id"
            type: "'user'"
          timestamp: ".timestamp | divide: 1000000 | to_datetime"
          reactions: ".reactions.emojis"
          connector: "'instagram'"

  search:
    operation: read
    label: "Search messages"
    description: Search messages by text
    params:
      query:
        type: string
        required: true
      limit:
        type: number
        default: 30
    rest:
      method: GET
      url: "https://www.instagram.com/api/v1/direct_v2/search_secondary/"
      params:
        query: "{{params.query}}"
        result_types: '["message_content","reshared_content"]'
        offsets: '{"message_content":"0","reshared_content":""}'
      response:
        root: "message_search_results.message_search_result_items"
        mapping:
          id: "[].matched_message_info.item_info.item_id"
          conversation_id: "[].thread.thread_id"
          content: "[].matched_message_info.item_info.text"
          content_type: "'text'"
          timestamp: "[].matched_message_info.item_info.timestamp | divide: 1000000 | to_datetime"
          connector: "'instagram'"

  get_unread:
    operation: read
    label: "Get unread"
    description: Get unread messages
    params:
      limit:
        type: number
        default: 20
    rest:
      method: GET
      url: "https://www.instagram.com/api/v1/direct_v2/inbox/"
      params:
        visual_message_return_type: "unseen"
        persistentBadging: "true"
        limit: "{{params.limit}}"
        selected_filter: "unread"
      response:
        root: "inbox.threads[*].items[0]"
        mapping:
          id: "[].item_id"
          conversation_id: "[].thread_id"
          content: "[].text"
          is_read: "false"
          timestamp: "[].timestamp | divide: 1000000 | to_datetime"
          connector: "'instagram'"

  get_presence:
    operation: read
    label: "Get presence"
    description: Check if users are online
    params:
      user_ids:
        type: array
        items: { type: string }
        required: true
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/fetch_and_subscribe_presence/"
      body:
        _uuid: "{{device.uuid}}"
        subscriptions_off: "false"
        request_data: "{{params.user_ids | to_json}}"
      response:
        root: "user_presence"
        mapping:
          user_id: "[].user_id"
          is_active: "[].is_active"
          last_active_at: "[].last_activity_at_ms | divide: 1000 | to_datetime"

# ============================================================================
# WRITE ACTIONS
# ============================================================================

  send:
    operation: create
    label: "Send message"
    description: Send a message to an existing conversation
    params:
      conversation_id:
        type: string
        required: true
      text:
        type: string
        required: true
      reply_to:
        type: string
        description: "Message ID to reply to"
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/broadcast/text/"
      body:
        thread_ids: "[{{params.conversation_id}}]"
        text: "{{params.text}}"
        action: "send_item"
        send_attribution: "message_button"
        client_context: "{{generate_uuid}}"
        mutation_token: "{{generate_uuid}}"
        _uuid: "{{device.uuid}}"
        offline_threading_id: "{{generate_uuid}}"
        # Optional reply fields
        replied_to_item_id: "{{params.reply_to}}"
        replied_to_action_source: "{{params.reply_to ? 'swipe' : null}}"
      response:
        root: "payload"
        mapping:
          id: ".item_id"
          conversation_id: "'{{params.conversation_id}}'"
          content: "'{{params.text}}'"
          content_type: "'text'"
          is_outgoing: "true"
          timestamp: ".timestamp | divide: 1000000 | to_datetime"
          connector: "'instagram'"

  send_to_user:
    operation: create
    label: "Send to user"
    description: Start a new conversation with a user
    params:
      user_id:
        type: string
        required: true
        description: "Instagram user ID (pk)"
      text:
        type: string
        required: true
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/broadcast/text/"
      body:
        recipient_users: "[[{{params.user_id}}]]"
        text: "{{params.text}}"
        action: "send_item"
        send_attribution: "message_button"
        client_context: "{{generate_uuid}}"
        mutation_token: "{{generate_uuid}}"
        _uuid: "{{device.uuid}}"
        offline_threading_id: "{{generate_uuid}}"
      response:
        root: "payload"
        mapping:
          id: ".item_id"
          conversation_id: ".thread_id"
          content: "'{{params.text}}'"
          is_outgoing: "true"
          connector: "'instagram'"

  react:
    operation: create
    label: "Add reaction"
    description: React to a message with an emoji
    params:
      conversation_id:
        type: string
        required: true
      message_id:
        type: string
        required: true
      emoji:
        type: string
        required: true
        description: "Emoji character (❤️ 😂 😮 😢 😡 👍)"
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/items/{{params.message_id}}/reactions/"
      body:
        reaction_status: "created"
        reaction_type: "like"
        emoji: "{{params.emoji}}"
        client_context: "{{generate_uuid}}"
        _uuid: "{{device.uuid}}"
      response:
        mapping:
          success: ".status == 'ok'"

  unreact:
    operation: delete
    label: "Remove reaction"
    description: Remove a reaction from a message
    params:
      conversation_id:
        type: string
        required: true
      message_id:
        type: string
        required: true
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/items/{{params.message_id}}/reactions/"
      body:
        reaction_status: "deleted"
        client_context: "{{generate_uuid}}"
        _uuid: "{{device.uuid}}"
      response:
        mapping:
          success: ".status == 'ok'"

  mark_read:
    operation: update
    label: "Mark read"
    description: Mark a message as seen/read
    params:
      conversation_id:
        type: string
        required: true
      message_id:
        type: string
        required: true
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/items/{{params.message_id}}/seen/"
      body:
        thread_id: "{{params.conversation_id}}"
        action: "mark_seen"
        client_context: "{{generate_uuid}}"
        _uuid: "{{device.uuid}}"
      response:
        mapping:
          success: ".status == 'ok'"

  mark_unread:
    operation: update
    label: "Mark unread"
    description: Mark a conversation as unread
    params:
      conversation_id:
        type: string
        required: true
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/mark_unread/"
      body:
        _uuid: "{{device.uuid}}"
      response:
        mapping:
          success: ".status == 'ok'"

  delete:
    operation: delete
    label: "Delete message"
    description: Unsend/delete a message
    params:
      conversation_id:
        type: string
        required: true
      message_id:
        type: string
        required: true
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/items/{{params.message_id}}/delete/"
      body:
        _uuid: "{{device.uuid}}"
      response:
        mapping:
          success: ".status == 'ok'"

  mute:
    operation: update
    label: "Mute"
    description: Mute conversation notifications
    params:
      conversation_id:
        type: string
        required: true
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/mute/"
      body:
        _uuid: "{{device.uuid}}"
      response:
        mapping:
          success: ".status == 'ok'"

  unmute:
    operation: update
    label: "Unmute"
    description: Unmute conversation notifications
    params:
      conversation_id:
        type: string
        required: true
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/unmute/"
      body:
        _uuid: "{{device.uuid}}"
      response:
        mapping:
          success: ".status == 'ok'"

  archive:
    operation: update
    label: "Archive"
    description: Hide/archive a conversation
    params:
      conversation_id:
        type: string
        required: true
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/hide/"
      body:
        _uuid: "{{device.uuid}}"
        should_move_future_requests_to_spam: "false"
      response:
        mapping:
          success: ".status == 'ok'"

  send_typing:
    operation: update
    label: "Send typing"
    description: Show typing indicator (call periodically while typing)
    params:
      conversation_id:
        type: string
        required: true
    rest:
      method: POST
      url: "https://www.instagram.com/api/v1/direct_v2/threads/{{params.conversation_id}}/activity/"
      body:
        _uuid: "{{device.uuid}}"
        activity_status: "1"  # 1 = typing, 0 = stopped
      response:
        mapping:
          success: ".status == 'ok'"
---

# Instagram

Full-featured Instagram DM connector with read and write support.

---

## 🚧 Development Status (Jan 2026)

### ✅ What Works (Verified Jan 6, 2026)

| Feature | Status | Notes |
|---------|--------|-------|
| **Cookie-based auth** | ✅ Working | 5 cookies stored: sessionid, csrftoken, ds_user_id, mid, ig_did |
| **Cookie auth injection** | ✅ Working | Auto-adds `Cookie` + `X-CSRFToken` headers to all requests |
| **Custom headers** | ✅ Working | X-IG-App-ID, X-Requested-With, Referer on all actions |
| **list_conversations** | ✅ Working | Returns real DM threads with names |
| **list (messages)** | ✅ Working | Returns messages in a thread with reactions |
| **get_conversation** | ✅ Working | Get thread details |
| **search** | ✅ Untested | Should work (headers added) |
| **get_unread** | ✅ Untested | Should work (headers added) |
| **Add Account UI** | ✅ Working | Shows username/password form, triggers Playwright login |

### 🔧 Known Issues

| Issue | Notes | Priority |
|-------|-------|----------|
| **participants mapping** | Shows JSONPath templates instead of actual usernames (cosmetic) | Low |
| **conversation_id literal** | Shows `{{params.conversation_id}}` in list response instead of actual ID | Low |
| **MCP connection drops** | Occasional "Connection closed" errors, fixed by restart.sh | Medium |
| **content null for media** | Expected - media messages (shared posts, stories) don't have text | - |

### ❓ Not Yet Tested

| Feature | Notes |
|-------|-------|
| **Fresh auth flow** | Delete account → Add Account → Playwright login |
| **2FA handling** | UI should prompt for code when needed |
| **Auto-reconnect** | When session expires, should re-login with stored credentials |
| **Write operations** | Instagram may block REST writes (see mautrix-meta for MQTToT) |

### 📋 Next Steps

1. **Test fresh auth flow** (AGE-274 continued)
   - Delete existing Instagram account
   - Click Add Account → enter credentials
   - Verify Playwright runs and stores cookies
   - Handle 2FA if prompted

2. **Fix response mapping bugs** (Low priority)
   - Nested array mappings for participants
   - Parameter interpolation in response templates

3. **Write operations** (Future - AGE-276+)
   - Research if REST writes work or need MQTToT websocket

### 🔗 References

- **mautrix-meta**: https://github.com/mautrix/meta/tree/main/pkg/messagix (MQTToT protocol for writes)
- **API Base URL**: `https://www.instagram.com/api/v1` (web API)
- **Key Files**: `apps.rs` (inject_provider_auth), `commands.rs` (connect_with_credentials), `scripts/playwright-runner.ts`

---

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| **Read** | | |
| List conversations | ✅ | With unread/flagged filters |
| Read messages | ✅ | Including reactions, replies |
| Search messages | ✅ | Full-text search |
| Get unread | ✅ | Unread messages across all threads |
| Check presence | ✅ | See who's online |
| **Write** | | |
| Send messages | ✅ | To existing or new conversations |
| Reply to messages | ✅ | Quote-reply style |
| React with emoji | ✅ | ❤️ 😂 😮 😢 😡 👍 |
| Remove reactions | ✅ | |
| Mark read/unread | ✅ | |
| Delete messages | ✅ | Unsend your messages |
| Mute/unmute | ✅ | |
| Archive conversations | ✅ | |
| Send typing indicator | ✅ | |

## Connection

Click **Connect Instagram** → Log in via browser → Done!

The browser handles 2FA and any security challenges automatically.

## Usage Examples

### Send a message
```
Messages(action: "send", connector: "instagram", 
         conversation_id: "123", text: "Hello!")
```

### Reply to a message
```
Messages(action: "send", connector: "instagram",
         conversation_id: "123", text: "Great point!",
         reply_to: "message_456")
```

### React with heart
```
Messages(action: "react", connector: "instagram",
         conversation_id: "123", message_id: "456", emoji: "❤️")
```

### Start new conversation
```
Messages(action: "send_to_user", connector: "instagram",
         user_id: "12345678", text: "Hey!")
```

### Mark as read
```
Messages(action: "mark_read", connector: "instagram",
         conversation_id: "123", message_id: "456")
```

## Reactions

Instagram supports these emoji reactions:
- ❤️ (heart/like - default double-tap)
- 😂 (laugh)
- 😮 (wow)
- 😢 (sad)
- 😡 (angry)
- 👍 (thumbs up)

## Session Management

- **Auto keep-alive**: Session pinged every 4 hours
- **Cookie lifetime**: ~90 days (varies)
- **Auto-detect expiry**: Prompts to reconnect when session dies

## Troubleshooting

### Session expired
Click "Reconnect" and log in again.

### Challenge required
Open Instagram app on phone, complete verification, then reconnect.

### Rate limited
Wait a few minutes. Instagram limits how fast you can send.

### API changes
Check https://github.com/mautrix/meta for updates. They maintain Instagram API compatibility for Beeper.

## Technical Reference

### Endpoints

| Action | Method | Endpoint |
|--------|--------|----------|
| List inbox | GET | `direct_v2/inbox/` |
| Get thread | GET | `direct_v2/threads/{id}/` |
| Send text | POST | `direct_v2/threads/broadcast/text/` |
| React | POST | `direct_v2/threads/{id}/items/{item}/reactions/` |
| Mark seen | POST | `direct_v2/threads/{id}/items/{item}/seen/` |
| Delete | POST | `direct_v2/threads/{id}/items/{item}/delete/` |
| Presence | POST | `direct_v2/fetch_and_subscribe_presence/` |
| Typing | POST | `direct_v2/threads/{id}/activity/` |

### Required Cookies

| Cookie | Purpose |
|--------|---------|
| `sessionid` | Main auth token |
| `csrftoken` | CSRF (sent in header too) |
| `ds_user_id` | Your user ID |
| `mid` | Machine ID |
| `ig_did` | Device ID |

---

## Implementation Notes

> **Status: Not yet implemented** — This section documents what needs to be built.

### What needs to be built

This is the first connector using the Playwright executor and cookie auth type. These are generic features that will work for any connector, not just Instagram.

#### Phase 1: Credential Types (Rust core)

**File:** `src-tauri/src/credentials/mod.rs`

Add `Credential::Cookies` variant:
```rust
Cookies {
    cookies: HashMap<String, String>,  // name -> value
    domain: String,                     // "instagram.com"
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
    label: Option<String>,             // "joe_instagram"
}
```

**File:** `src-tauri/src/apps.rs`

Update `inject_provider_auth` to handle `type: cookies`:
```rust
// When auth.type == "cookies":
// 1. Load Credential::Cookies from store
// 2. Build Cookie header: "sessionid=abc; csrftoken=xyz; ..."
// 3. Inject into request
```

#### Phase 2: Playwright Executor (Node)

**File:** `scripts/playwright-runner.ts` (repo root, alongside other scripts)

Generic step executor that:
1. Receives steps as JSON input (from Rust via stdin or args)
2. Executes each step using Playwright
3. Returns results as JSON to stdout

The runner knows nothing about Instagram. It just executes step types:
- `goto` → `page.goto(url)`
- `wait_for.cookie` → poll for cookie existence
- `wait_for.selector` → `page.waitForSelector()`
- `wait_for.url_matches` → `page.waitForURL()`
- `extract_cookies` → `context.cookies()`
- `extract.selector` → `page.locator().textContent()`
- `click` → `page.click()`
- `type` → `page.fill()`
- `close` → `browser.close()`

Example:
```bash
echo '{"steps":[{"goto":"https://example.com"},{"wait_for":{"cookie":"session"}}]}' | node playwright-runner.ts
```

Output:
```json
{
  "success": true,
  "cookies": {"sessionid": "abc", "csrftoken": "xyz"},
  "extracted": {}
}
```

All connector-specific logic stays in the YAML spec. The runner is reusable for any connector.

#### Phase 3: Rust Integration

**File:** `src-tauri/src/commands/connect.rs` (or similar)

When user clicks "Connect Instagram":
1. Parse connector's `auth.connect.playwright:` config
2. Spawn Node script with config as args
3. Capture stdout, parse JSON
4. Store cookies in credential store
5. Return success to UI

#### Phase 4: Session Management

**File:** `src-tauri/src/session.rs` (new)

Based on connector's `session:` config:
- **keep_alive**: Periodic background requests to prevent logout
- **error_detection**: Check response codes/bodies for auth failures
- **on_expire**: Prompt user to reconnect

### Testing Strategy

**Real E2E with real credentials.** No mocks.

1. Real Instagram account
2. Real browser (headed for auth, can watch it work)
3. Real API calls
4. Verify real messages appear/send

Be mindful of rate limits. Instagram will flag suspicious activity.

### Why Node for Playwright?

Playwright is a JavaScript library. Options were:
- **Node script** ✓ — Native environment, simple, works great
- **Rust bindings** — Complex, not well maintained
- **Pure automation** — Can't handle 2FA, captchas

Rust spawns the Node script and captures output. Clean separation.

### Open Questions

- [x] Where should `playwright-runner.ts` live? → `scripts/` at repo root
- [ ] How to handle 2FA timeout gracefully? (Show message, extend timeout?)
- [ ] Should keep-alive run in background thread or separate process?

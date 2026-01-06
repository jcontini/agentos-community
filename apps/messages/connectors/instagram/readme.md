---
id: instagram
name: Instagram
description: Read and send Instagram direct messages via private API
icon: icon.png
color: "#E4405F"

website: https://www.instagram.com
platform: all

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
  
  connect:
    playwright:
      launch:
        headless: false
        
      steps:
        - goto: "https://www.instagram.com/accounts/login/"
        
        # Wait for successful login (redirected to home or DMs)
        - wait_for:
            any:
              - url_matches: "instagram.com/$"
              - url_matches: "instagram.com/direct"
              - selector: "[aria-label='Home']"
              - cookie: sessionid
            timeout: 300000
            
        # Extract all the cookies we need
        - extract_cookies: [sessionid, csrftoken, ds_user_id, mid, ig_did]
            
        - close
        
      on_success:
        message: "Connected to Instagram as @{{username}}!"
        
      on_error:
        challenge_required:
          message: "Instagram requires verification. Please complete it in the browser."
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
    label: "List conversations"
    description: List all Instagram DM conversations
    readonly: true
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
      headers:
        X-IG-App-ID: "936619743392459"
        X-Requested-With: "XMLHttpRequest"
        Referer: "https://www.instagram.com/direct/inbox/"
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
            - id: "[].users[].pk"
              name: "[].users[].full_name"
              handle: "[].users[].username"
          unread_count: "[].read_state"
          updated_at: "[].last_activity_at | divide: 1000000 | to_datetime"
          platform: "'instagram'"
          connector: "'instagram'"

  get_conversation:
    label: "Get conversation"
    description: Get conversation details
    readonly: true
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
            - id: ".users[].pk"
              name: ".users[].full_name"
              handle: ".users[].username"
          updated_at: ".last_activity_at | divide: 1000000 | to_datetime"
          platform: "'instagram'"
          connector: "'instagram'"

  list:
    label: "List messages"
    description: List messages in a conversation
    readonly: true
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
    label: "Get message"
    description: Get a specific message
    readonly: true
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
    label: "Search messages"
    description: Search messages by text
    readonly: true
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
    label: "Get unread"
    description: Get unread messages
    readonly: true
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
    label: "Get presence"
    description: Check if users are online
    readonly: true
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

### ✅ What Works Reliably

| Feature | Implementation | Notes |
|---------|---------------|-------|
| **Browser-based login** | `scripts/playwright-runner.ts` | Opens mobile-sized Chromium, user logs in, cookies extracted |
| **Cookie storage** | `~/.agentos/credentials.json` | Stored as `Credential::Cookies` type in JSON store |
| **Reading conversations** | REST API `list_conversations` | Returns real DM threads with participants, unread counts |
| **Cookie auth injection** | `inject_provider_auth()` in apps.rs | Auto-adds `Cookie` + `X-CSRFToken` headers |
| **Custom headers** | `RestExecutor.headers` field | Per-action headers (X-IG-App-ID, X-Requested-With, Referer) |
| **Session refresh** | Re-run Playwright login | Manual process when session expires |

### 🔧 Known Issues to Fix

| Issue | Solution | Priority |
|-------|----------|----------|
| **Cursor MCP credential loading** | Works in standalone mode but fails via Cursor MCP. Likely path or timing issue. | High |
| **Other read actions need headers** | Copy header pattern from `list_conversations` to `get`, `list`, `search`, etc. | Medium |
| **Session expiry detection** | Implement `error_detection` config parsing in Rust | Medium |
| **Full browser window** | Just added mobile size option - needs testing | Low |

### ❓ Research Needed / Unsure

| Topic | Notes |
|-------|-------|
| **Sending messages** | Instagram **blocks REST API writes** (invalidates session immediately). Mautrix-meta uses MQTToT websocket protocol. This is a significant undertaking. |
| **Session lifetime** | Sessions expire quickly with "suspicious" API patterns. Need to understand rate limits. |
| **Native Tauri webview** | Could replace Playwright with Tauri's built-in webview for truly native auth window. Would be reusable for OAuth flows too. |
| **Username/password auth** | Could prompt for credentials in UI, automate login via Playwright. Need to handle 2FA. |

### 📋 Next Steps (Prioritized)

1. **Native Auth Window (UI)**
   - Add `auth_type: cookies` support to AppsView.svelte "Add Account" modal
   - Create Tauri command `open_auth_window(url, size)` that opens native webview
   - Monitor for successful login (cookie appears), extract cookies, close window
   - Much cleaner than spawning Playwright Chromium

2. **Fix Cursor MCP credential loading**
   - Debug why credentials work in standalone but not via Cursor
   - May need to ensure credential file path is absolute

3. **Complete read actions**
   - Add headers to remaining read actions: `get_conversation`, `list`, `get`, `search`, `get_unread`
   - Test each action works

4. **Write operations (future)**
   - Research MQTToT protocol (see mautrix-meta `pkg/messagix/socket/`)
   - May need websocket connection for real-time messaging
   - Alternative: explore if GraphQL endpoints work for writes

### 🔗 Key References

- **mautrix-meta**: https://github.com/mautrix/meta/tree/main/pkg/messagix
  - Uses MQTToT websocket for messaging
  - Has task structures: `SendMessageTask`, `SendReactionTask`, `ThreadMarkReadTask`
  - Error handling for challenges, consent, checkpoints
  
- **API Base URL**: `https://www.instagram.com/api/v1` (web API, not mobile `i.instagram.com`)

- **Required Headers**:
  ```
  Cookie: sessionid=...; csrftoken=...; ds_user_id=...; mid=...; ig_did=...
  X-CSRFToken: <same as csrftoken cookie>
  X-IG-App-ID: 936619743392459
  X-Requested-With: XMLHttpRequest
  Referer: https://www.instagram.com/direct/inbox/
  ```

- **Key Files in AgentOS**:
  - `scripts/playwright-runner.ts` - Generic browser automation
  - `src-tauri/src/credentials/mod.rs` - `Credential::Cookies` type
  - `src-tauri/src/apps.rs` - `inject_provider_auth()`, `RestExecutor.headers`
  - `src-tauri/src/commands.rs` - `connect_connector` command

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

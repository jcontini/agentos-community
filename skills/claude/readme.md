---
id: claude
name: Claude.ai
description: Claude.ai web chat history — browse and search conversations from your personal claude.ai account
icon: icon.png
color: "#D97757"
platforms: [macos]

website: https://claude.ai
privacy_url: https://www.anthropic.com/privacy
terms_url: https://www.anthropic.com/terms-of-service

auth:
  cookies:
    domain: ".claude.ai"
    names: ["sessionKey"]
    session_duration: "30d"
    login:
      account_prompt: "What email do you use for claude.ai?"
      phases:
        - name: request_login
          description: "Submit email on the Claude login page to trigger a magic link email"
          steps:
            - { action: goto, url: "https://claude.ai/login" }
            - { action: fill, selector: "input[type=email]", value: "{{account}}" }
            - { action: click, selector: "button[type=submit]" }
          returns_to_agent: >
            Magic link requested. Check the user's email for a message from Anthropic
            containing a claude.ai/magic-link URL. Use the Gmail skill to search for it,
            or ask the user to paste it.
        - name: complete_login
          description: "Navigate to the magic link URL to complete authentication"
          requires: [magic_link]
          steps:
            - { action: goto, url: "{{magic_link}}" }
            - { action: wait, url_contains: "/new" }
          returns_to_agent: >
            Login complete. The sessionKey cookie is now in the browser.
            Cookie matchmaking will extract it automatically on next API call.
    verify:
      url: "https://claude.ai/api/organizations"
      method: GET
      expect_status: 200

connects_to: claude-ai-web

seed:
  - id: claude-ai-web
    types: [software]
    name: Claude.ai
    data:
      software_type: web_app
      url: https://claude.ai
      platforms: [web, macos, ios, android]
    relationships:
      - role: offered_by
        to: anthropic-inc

  - id: anthropic-inc
    types: [organization]
    name: Anthropic
    data:
      type: company
      url: https://www.anthropic.com
      founded: "2021"

instructions: |
  Claude.ai web chat history. Conversations live server-side only — not in any local file.
  Access requires a valid sessionKey cookie from a logged-in claude.ai browser session.

  ## Authentication

  Cookie matchmaking handles session automatically:
  - `auth.cookies` declares the skill needs `sessionKey` from `.claude.ai`
  - agentOS discovers a cookie provider (Brave Browser reads the cookie DB)
  - The sessionKey is injected into `params.auth.sessionKey` before each call
  - No session file, no manual credential storage

  If the user is NOT logged into claude.ai on Brave Browser, the Playwright
  login flow is needed (auth.cookies.login phases above).

  ## Discovering the User's Account

  DO NOT assume any email address, org UUID, or account name.

  1. Ask the user: "What email do you use for claude.ai?"
  2. Call `conversation.list` with no account param — the org is auto-discovered via API.
  3. If you need to switch orgs, use `list_orgs` to discover available orgs and
     their UUIDs, then pass the UUID via the account param.

  ## Magic Link Extraction from Email

  If you're reading the magic link from a raw email:
  - The raw email body is often base64url-encoded RFC 2822 with quoted-printable HTML
  - Remove QP soft line breaks: replace =\r\n and =\n with ""
  - The link pattern: href=3D"https://claude.ai/magic-link#TOKEN"
  - Replace =3D with = in the extracted URL
  - The helper `extract_magic_link` utility can do this for you

  ## API Architecture

  LOGIN ONLY → Playwright skill (browser control) + Brave Browser skill (cookie extraction)
  ALL OTHER CALLS → claude-api.py (httpx with sessionKey as Cookie header)

  ## Cloudflare / API Headers

  Must include these headers on every request or get 403:
    anthropic-client-version: claude-ai/web@1.1.5368
    Sec-Fetch-Site: same-origin
    Sec-Fetch-Mode: cors
    Sec-Fetch-Dest: empty
    Cookie: sessionKey=sk-ant-sid02-...

testing:
  exempt:
    operations: Requires live claude.ai session — tests in tests/claude.test.ts skip gracefully without one
    utilities: Login utilities require Playwright browser on CDP port 9222

transformers:
  conversation:
    terminology: Conversation
    mapping:
      id: .uuid
      name: .name
      content: .content
      updated_at: .updated_at
      created_at: .created_at
      data.org_uuid: .org_uuid
      data.message_count: .message_count

  message:
    terminology: Message
    mapping:
      id: .id
      conversation_id: .conversation_id
      content: .text
      is_outgoing: '.role == "human"'
      timestamp: .created_at
      url: '"https://claude.ai/chat/" + .conversation_id'
      data.role: .role
      data.conversation_name: .conversation_name

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:
  conversation.list:
    description: >
      List claude.ai web chat conversations, most recently updated first.
      Requires a valid session (run login flow if needed).
    returns: conversation[]
    params:
      account: { type: string, description: "Org UUID to use (omit to use session default). Use list_orgs to discover available orgs." }
      limit: { type: integer, default: 50, description: "Max conversations to return (max 250)" }
      offset: { type: integer, default: 0, description: "Pagination offset" }
    command:
      binary: python3
      args:
        - "/Users/joe/dev/agentos-community/skills/claude/claude-api.py"
        - "--op"
        - "conversations"
        - "--session-key"
        - ".params.auth.sessionKey"
        - if .params.account then "--org" else "" end
        - if .params.account then .params.account else "" end
        - "--limit"
        - ".params.limit"
        - "--offset"
        - ".params.offset"
      timeout: 30

  conversation.get:
    description: >
      Get a full claude.ai web conversation with all messages.
      Returns the complete message history including both human and assistant turns.
    returns: conversation
    params:
      id: { type: string, required: true, description: "Conversation UUID" }
      account: { type: string, description: "Org UUID (omit to use session default)" }
    command:
      binary: python3
      args:
        - "/Users/joe/dev/agentos-community/skills/claude/claude-api.py"
        - "--op"
        - "conversation"
        - "--session-key"
        - ".params.auth.sessionKey"
        - "--id"
        - ".params.id"
        - if .params.account then "--org" else "" end
        - if .params.account then .params.account else "" end
      timeout: 30

  conversation.search:
    description: >
      Search claude.ai web conversations by title/name.
      Fetches up to 250 conversations and filters locally (no server-side search).
      For full content search across message text, use conversation.import first,
      then search({ query: "...", types: ["message"] }) against the Memex FTS index.
    returns: conversation[]
    params:
      query: { type: string, required: true, description: "Text to search for in conversation titles" }
      account: { type: string, description: "Org UUID (omit to use session default)" }
      limit: { type: integer, default: 20, description: "Max results" }
    command:
      binary: python3
      args:
        - "/Users/joe/dev/agentos-community/skills/claude/claude-api.py"
        - "--op"
        - "search"
        - "--session-key"
        - ".params.auth.sessionKey"
        - "--query"
        - ".params.query"
        - if .params.account then "--org" else "" end
        - if .params.account then .params.account else "" end
        - "--limit"
        - ".params.limit"
      timeout: 30

  conversation.import:
    description: >
      Import claude.ai conversations and all their messages into the Memex.
      Each message becomes a message entity with full content FTS-indexed.
      After import, use search({ query: "...", types: ["message"] }) for content search.
      Safe to run repeatedly — deduplicates by message UUID.
      Use limit+offset to page through conversations in batches of 5-10.
    returns: message[]
    params:
      account: { type: string, description: "Org UUID (omit to use session default)" }
      limit: { type: integer, default: 5, description: "Conversations per batch (keep ≤10 to avoid DB lock)" }
      offset: { type: integer, default: 0, description: "Pagination offset" }
    command:
      binary: python3
      args:
        - "/Users/joe/dev/agentos-community/skills/claude/claude-api.py"
        - "--op"
        - "import"
        - "--session-key"
        - ".params.auth.sessionKey"
        - if .params.account then "--org" else "" end
        - if .params.account then .params.account else "" end
        - "--limit"
        - ".params.limit"
        - "--offset"
        - ".params.offset"
      timeout: 60

# ==============================================================================
# UTILITIES
# ==============================================================================

utilities:
  list_orgs:
    description: |
      List all organizations the user has access to.
      Returns org UUIDs, names, and capabilities. Use this to discover
      which org has chat history (look for "chat" in capabilities).
    returns:
      uuid: string
      name: string
      capabilities: array
    command:
      binary: python3
      args:
        - "/Users/joe/dev/agentos-community/skills/claude/claude-api.py"
        - "--op"
        - "organizations"
        - "--session-key"
        - ".params.auth.sessionKey"
      timeout: 15

  extract_magic_link:
    description: |
      Extract the magic link URL from a raw base64url-encoded email body.
      Pass the raw email content (from Gmail's get_raw utility) and this
      will decode it and find the claude.ai magic link.
    params:
      raw_email:
        type: string
        required: true
        description: "Base64url-encoded raw RFC 2822 email content"
    returns:
      magic_link: string
    command:
      binary: python3
      args:
        - "/Users/joe/dev/agentos-community/skills/claude/claude-login.py"
        - "--extract-link-from-raw"
        - ".params.raw_email"
      timeout: 10

---

# Claude.ai

Browse and search your claude.ai web chat conversation history.

## How it works

claude.ai web chat history lives server-side only — unlike Claude Code (CLI) which stores
transcripts locally, web conversations are only accessible via the claude.ai API.

Two phases:
1. **Cookie matchmaking** — agentOS auto-extracts the sessionKey from Brave Browser
   (or falls back to Playwright login if the user isn't logged in)
2. **API calls** — all subsequent calls use `httpx` directly with the injected
   `sessionKey` — no browser needed, no session file

## Capabilities

```
OPERATION             DESCRIPTION
────────────────────  ───────────────────────────────────────────────────
conversation.list     Browse conversations, most recently updated first
conversation.get      Full conversation with all messages
conversation.search   Search conversations by title (client-side filter)
conversation.import   Import messages into Memex for FTS content search
list_orgs             Discover available orgs and capabilities
extract_magic_link    Parse magic link URL from raw email content
```

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

auth: none

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

  ## First-Time Setup

  Before using this skill, you need a session. Check with `session_check` first.
  If no session exists, walk the user through login (see Login Flow below).

  ## Discovering the User's Account

  DO NOT assume any email address, org UUID, or account name.

  1. Ask the user: "What email do you use for claude.ai?"
  2. After login, call `conversation.list` with no account param — the session's
     default org is used automatically.
  3. If you need to switch orgs, use `list_orgs` to discover available orgs and
     their UUIDs, then pass `--org UUID` via the account param.

  ## Auth / Session

  The sessionKey is an HttpOnly cookie — JS document.cookie cannot read it.
  It must be extracted via CDP Network.getAllCookies from a logged-in browser.

  Session is saved to: ~/.config/agentos/claude-session.json
  Sessions last ~30 days. If API calls return 401/403, re-run the login flow.

  ## Login Flow (agent-orchestrated)

  The login requires a real browser and email access. You (the agent) orchestrate
  the steps — the Python scripts handle only the mechanical browser parts.

  1. Ask the user for their claude.ai email address.
  2. Use Playwright to navigate to https://claude.ai/login
   3. Fill the email input (selector: input[type=email]) with the user's email.
     A plain Playwright fill() works. If React doesn't pick it up, use the
     nativeInputValueSetter trick (set value via prototype setter, dispatch input event).
  4. Click submit (selector: button[type=submit])
  5. Tell the user: "I've submitted your email. A magic link should arrive shortly."
  6. Check for the magic link email:
       - If you have access to the user's email (e.g. Gmail skill), search for it:
         query: "from:anthropic", look for emails in the last few minutes
       - Get the raw email content and look for the magic link URL
         Pattern: https://claude.ai/magic-link#TOKEN
       - If you don't have email access, ask the user to paste the magic link URL
  7. Once you have the magic link URL, call the `navigate_magic_link` utility
     with the URL. This navigates the browser and extracts the session.
  8. Verify the session with `session_check`.

  ## Magic Link Extraction from Email

  If you're reading the magic link from a raw email:
  - The raw email body is often base64url-encoded RFC 2822 with quoted-printable HTML
  - Remove QP soft line breaks: replace =\r\n and =\n with ""
  - The link pattern: href=3D"https://claude.ai/magic-link#TOKEN"
  - Replace =3D with = in the extracted URL
  - The helper `extract_magic_link` in claude-login.py can do this for you

  ## API Architecture

  LOGIN ONLY → Playwright (CDP browser)
    - Magic link needs a real browser session to land
    - sessionKey extraction via CDP Network.getAllCookies

  ALL OTHER CALLS → claude-api.py (httpx)
    - No browser needed after login
    - sessionKey passed as Cookie header
    - Required headers to bypass Cloudflare (documented in claude-api.py)

  ## Cloudflare / API Headers

  Must include these headers on every request or get 403:
    anthropic-client-version: claude-ai/web@1.1.5368
    Sec-Fetch-Site: same-origin
    Sec-Fetch-Mode: cors
    Sec-Fetch-Dest: empty
    Cookie: sessionKey=sk-ant-sid02-...

  ## API Endpoints

  GET /api/organizations
    → list of orgs with capabilities array

  GET /api/organizations/{org_uuid}/chat_conversations?limit=50&offset=0
    → list of conversation stubs (uuid, name, updated_at)
    → sorted by updated_at desc
    → there is NO server-side search endpoint — fetch + filter locally

  GET /api/organizations/{org_uuid}/chat_conversations/{conv_uuid}
       ?tree=True&rendering_mode=messages&render_all_tools=true
    → full conversation with chat_messages array
    → each message: { uuid, sender ("human"|"assistant"), content [{type, text}], created_at }

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
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-api.py --op conversations --org '{{params.account}}' --limit {{params.limit}} --offset {{params.offset}} 2>/dev/null"
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
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-api.py --op conversation --id '{{params.id}}' --org '{{params.account}}' 2>/dev/null"
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
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-api.py --op search --query '{{params.query}}' --org '{{params.account}}' --limit {{params.limit}} 2>/dev/null"
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
      offset: { type: integer, default: 0, description: "Conversation offset for pagination" }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-api.py --op import --org '{{params.account}}' --limit {{params.limit}} --offset {{params.offset}} 2>/dev/null"
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
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-api.py --op organizations 2>/dev/null"
      timeout: 15

  navigate_magic_link:
    description: |
      Navigate the browser to a magic link URL and extract the session.
      Use this after obtaining the magic link URL (from email or user).
      Requires a Playwright browser running on CDP port 9222.

      Steps performed:
        1. Navigate to the magic link URL
        2. Wait for redirect to /new (confirms login)
        3. Extract sessionKey via CDP Network.getAllCookies
        4. Call /api/organizations to discover the default org
        5. Save session to ~/.config/agentos/claude-session.json
    params:
      url:
        type: string
        required: true
        description: "The full magic link URL (https://claude.ai/magic-link#TOKEN)"
      port:
        type: integer
        default: 9222
        description: "CDP port"
    returns:
      session_key: string
      org_uuid: string
      org_name: string
      saved_at: string
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-login.py --magic-link '{{params.url}}' --port {{params.port}} --verbose 2>&1 | tail -1"
      timeout: 60

  extract_session:
    description: |
      Extract session cookies from a browser that is already logged into claude.ai.
      Use this if the user logged in manually via their browser.
      Requires a browser running on CDP port 9222 with claude.ai loaded.
    params:
      port:
        type: integer
        default: 9222
        description: "CDP port"
    returns:
      session_key: string
      org_uuid: string
      org_name: string
      saved_at: string
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-login.py --extract-session --port {{params.port}} --verbose 2>&1 | tail -1"
      timeout: 30

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
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-login.py --extract-link-from-raw '{{params.raw_email}}' 2>/dev/null"
      timeout: 10

  session_check:
    description: |
      Check if a valid session exists and return its details.
      Returns the saved session JSON, or an error if no session found.
      Use this before conversation operations to confirm auth is working.
    returns:
      session_key: string
      org_uuid: string
      org_name: string
      saved_at: string
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-login.py --check-session 2>/dev/null"
      timeout: 5

---

# Claude.ai

Browse and search your claude.ai web chat conversation history.

## How it works

claude.ai web chat history lives server-side only — unlike Claude Code (CLI) which stores
transcripts locally, web conversations are only accessible via the claude.ai API.

This skill uses a two-phase approach:
1. **Login** — The agent orchestrates a magic-link login flow using Playwright browser
   automation and email access, then extracts the `sessionKey` HttpOnly cookie via CDP
2. **API calls** — All subsequent calls use `httpx` directly with the saved
   `sessionKey` — no browser needed

## Login

The first time you use this skill, the agent will:
1. Ask for your claude.ai email address
2. Submit it on the login page (via Playwright)
3. Help you find the magic link in your email (or ask you to paste it)
4. Navigate to the magic link to complete login
5. Extract and save the session cookie

Sessions last ~30 days. Use `session_check` to verify auth status.

## Capabilities

```
OPERATION             DESCRIPTION
────────────────────  ───────────────────────────────────────────────────
conversation.list     Browse conversations, most recently updated first
conversation.get      Full conversation with all messages
conversation.search   Search conversations by title (client-side filter)
conversation.import   Import messages into Memex for FTS content search
list_orgs             Discover available orgs and capabilities
navigate_magic_link   Complete login with a magic link URL
extract_session       Extract session from already-logged-in browser
extract_magic_link    Parse magic link URL from raw email content
session_check         Verify current session status
```

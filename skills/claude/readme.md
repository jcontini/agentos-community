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

  ## Accounts

  Two orgs are available under anthropic@contini.co:

  ```
  ACCOUNT         ORG UUID                               CAPABILITIES
  ──────────────  ─────────────────────────────────────  ──────────────
  personal        c10a8db6-c2ed-4750-95ef-a0367a39362c  chat, claude_pro
  third-party     6b0831ae-5799-43af-90c2-4dba40206d35  api (no chat history)
  ```

  Always use account="personal" (or omit — it's the default) for chat history.
  "third-party" is the "A Third Party" API org — has no chat conversations.

  ## Auth / Session

  The sessionKey is an HttpOnly cookie — JS document.cookie cannot read it.
  It must be extracted via CDP Network.getAllCookies from a logged-in Playwright browser.

  Session is saved to: ~/.config/agentos/claude-session.json
  Sessions last ~30 days. If API calls return 401/403, run the login utility.

  ## Login Flow (one-shot, for agents)

  When you need to log in, do this sequence exactly:

  1. Use Playwright to navigate to https://claude.ai/login
  2. Fill the email input: selector = input[type=email], value = anthropic@contini.co
     USE cdp_evaluate with the React-compatible filler (nativeInputValueSetter trick —
     see claude-login.py do_login_flow() for the exact JS). A plain fill() works too.
  3. Click: selector = button[type=submit]
  4. Wait ~5 seconds for the email to arrive
  5. Search Gmail for the magic link:
       skill: gmail
       tool: email.search
       params: { query: "from:anthropic after:YYYY/MM/DD", account: "joe@contini.co" }
       IMPORTANT: joe@contini.co is a CATCH-ALL for *@contini.co — ALL emails sent
       to anthropic@contini.co arrive at joe@contini.co. Always use joe@contini.co.
  6. Get the raw email to extract the magic link:
       skill: gmail
       tool: get_raw
       params: { id: MESSAGE_ID, account: "joe@contini.co" }
     The raw field is base64url-encoded RFC 2822. The magic link is in the HTML body,
     quoted-printable encoded. Extract it with extract_magic_link_from_raw_email()
     in claude-login.py. The pattern is: href=3D"https://claude.ai/magic-link#TOKEN"
     after removing QP soft line breaks (=\r\n). Token format: HEX:BASE64EMAIL
  7. Navigate Playwright to the magic link URL
  8. Wait for URL to change to https://claude.ai/new (3-5 seconds)
  9. Run the login utility to extract sessionKey via CDP and save session

  ## API Architecture

  LOGIN ONLY → Playwright (CDP browser)
    - Magic link needs a real browser session to land
    - sessionKey extraction via CDP Network.getAllCookies (Node.js ws module)

  ALL OTHER CALLS → claude-api.py (httpx / urllib stdlib)
    - No browser needed after login
    - sessionKey passed as Cookie header
    - Required headers to bypass Cloudflare (all documented in claude-api.py HEADERS)

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
    operations: Requires live claude.ai session — tested manually
    utilities: Requires Playwright browser running on CDP port 9222

transformers:
  conversation:
    terminology: Conversation
    mapping:
      id: .uuid
      name: .name
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
      Requires a valid session (run login utility if needed).
    returns: conversation[]
    params:
      account: { type: string, description: "Account to use: 'personal' (default) or 'third-party'" }
      limit: { type: integer, default: 50, description: "Max conversations to return (max 250)" }
      offset: { type: integer, default: 0, description: "Pagination offset" }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-api.py --op conversations --account '{{params.account}}' --limit {{params.limit}} --offset {{params.offset}} 2>/dev/null"
      timeout: 30

  conversation.get:
    description: >
      Get a full claude.ai web conversation with all messages.
      Returns the complete message history including both human and assistant turns.
    returns: conversation
    params:
      id: { type: string, required: true, description: "Conversation UUID" }
      account: { type: string, description: "Account to use: 'personal' (default) or 'third-party'" }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-api.py --op conversation --id '{{params.id}}' --account '{{params.account}}' 2>/dev/null"
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
      account: { type: string, description: "Account to use: 'personal' (default) or 'third-party'" }
      limit: { type: integer, default: 20, description: "Max results" }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-api.py --op search --query '{{params.query}}' --account '{{params.account}}' --limit {{params.limit}} 2>/dev/null"
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
      account: { type: string, description: "Account to use: 'personal' (default) or 'third-party'" }
      limit: { type: integer, default: 5, description: "Conversations per batch (keep ≤10 to avoid DB lock)" }
      offset: { type: integer, default: 0, description: "Conversation offset for pagination" }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-api.py --op import --account '{{params.account}}' --limit {{params.limit}} --offset {{params.offset}} 2>/dev/null"
      timeout: 60

# ==============================================================================
# UTILITIES
# ==============================================================================

utilities:
  login:
    description: |
      Full automated login flow for claude.ai. Orchestrates:
        1. Playwright browser → navigate to /login, fill email, submit
        2. Gmail skill → poll joe@contini.co (catch-all) for magic link email
        3. Extract magic link from raw email (base64url + quoted-printable)
        4. Playwright → navigate to magic link, wait for /new redirect
        5. CDP Network.getAllCookies → extract sessionKey (HttpOnly cookie)
        6. Save to ~/.config/agentos/claude-session.json

      The login utility is an ORCHESTRATION — it requires the agent to:
        a. Use the playwright skill for browser steps
        b. Use the gmail skill for email steps
        c. Call this utility's --magic-link mode once the link is known

      For fully automated login, use the step-by-step instructions in the
      skill instructions block above ("Login Flow (one-shot, for agents)").
      The login utility handles steps 4-6 once you have the magic link URL.

      GMAIL CATCH-ALL NOTE:
        anthropic@contini.co → arrives at joe@contini.co (catch-all for *@contini.co)
        Always search Gmail with account="joe@contini.co", NOT "anthropic@contini.co"
        (anthropic@contini.co is not in Mimestream and has no direct Gmail access)

      MAGIC LINK EXTRACTION:
        1. email.search: query="from:anthropic after:YYYY/MM/DD", account="joe@contini.co"
        2. get_raw: id=MESSAGE_ID, account="joe@contini.co"
        3. The raw.raw field is base64url-encoded RFC 2822
        4. The body is quoted-printable HTML
        5. Remove soft line breaks: replace =\r\n and =\n with ""
        6. Pattern: href=3D"(https://claude\.ai/magic-link#[^"]+)"
        7. Replace =3D with = in the extracted URL

    params:
      magic_link:
        type: string
        description: "Magic link URL from email (skip browser steps if provided)"
      force:
        type: boolean
        description: "Force re-login even if a valid session exists"
    returns:
      session_key: string
      org_uuid: string
      org_name: string
      account_email: string
      saved_at: string
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/claude/claude-login.py --magic-link '{{params.magic_link}}' --verbose 2>&1 | tail -1"
      timeout: 60

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
        - |
          if [ -f ~/.config/agentos/claude-session.json ]; then
            cat ~/.config/agentos/claude-session.json
          else
            echo '{"error": "No session found. Run the login utility."}'
          fi
      timeout: 5

---

# Claude.ai

Browse and search your claude.ai web chat conversation history.

## How it works

claude.ai web chat history lives server-side only — unlike Claude Code (CLI) which stores
transcripts locally, web conversations are only accessible via the claude.ai API.

This skill uses a two-phase approach:
1. **Login** — Playwright browser automation performs the magic-link login flow and extracts
   the `sessionKey` HttpOnly cookie via CDP (Chrome DevTools Protocol)
2. **API calls** — All subsequent calls use `httpx`/`urllib` directly with the saved
   `sessionKey` — no browser needed

## Accounts

| Account | Org | Capabilities |
|---------|-----|-------------|
| `personal` | anthropic@contini.co's Organization | Chat (web history) |
| `third-party` | A Third Party | API only (no web chat history) |

## Login

The login utility automates the full magic-link flow. You'll need:
- Playwright running (port 9222)
- Gmail access via `joe@contini.co` (catch-all for `*@contini.co`)

See the `login` utility documentation for the complete one-shot flow.

## Session

Sessions are saved to `~/.config/agentos/claude-session.json` and last ~30 days.
Use `session_check` to verify auth before making API calls.

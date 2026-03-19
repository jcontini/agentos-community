---
id: claude
name: Claude.ai
description: Claude.ai web chat history — browse and search conversations from your personal claude.ai account
icon: icon.png
color: "#D97757"
website: https://claude.ai
privacy_url: https://www.anthropic.com/privacy
terms_url: https://www.anthropic.com/terms-of-service

connections:
  web:
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
              - { action: fill, selector: "input[type=email]", value: "${ACCOUNT}" }
              - { action: click, selector: "button[type=submit]" }
            returns_to_agent: |
              Magic link requested. Check the user's email for a message from Anthropic
              containing a claude.ai/magic-link URL. Search mail or the graph for that message,
              or ask the user to paste the link.
          - name: complete_login
            description: "Navigate to the magic link URL to complete authentication"
            requires: [magic_link]
            steps:
              - { action: goto, url: "${MAGIC_LINK}" }
              - { action: wait, url_contains: "/new" }
            returns_to_agent: |
              Login complete. The sessionKey cookie is now in the browser.
              Cookie provider matchmaking will extract it automatically on the next API call.
      verify:
        url: "https://claude.ai/api/organizations"
        method: GET
        expect_status: 200
adapters:
  conversation:
    id: .uuid
    name: .name
    text: .content
    content: .content
    datePublished: .updated_at
    data.created_at: .created_at
    data.org_uuid: .org_uuid
    data.message_count: .message_count

  message:
    id: .id
    name: .conversation_name
    text: .text
    content: .text
    url: '"https://claude.ai/chat/" + .conversation_id'
    author: .role
    datePublished: .created_at
    is_outgoing: '.role == "human"'
    timestamp: .created_at
    data.conversation_id: .conversation_id
    data.role: .role
    data.conversation_name: .conversation_name

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:
  list_conversations:
    description: >
      List claude.ai web chat conversations, most recently updated first.
      Requires a valid session (run login flow if needed).
    returns: conversation[]
    params:
      account: { type: string, description: "Org UUID to use (omit to use session default). Use list_orgs to discover available orgs." }
      limit: { type: integer, default: 50, description: "Max conversations to return (max 250)" }
      offset: { type: integer, default: 0, description: "Pagination offset" }
    python:
      module: ./claude-api.py
      function: op_list_conversations
      args:
        session_key: .auth.sessionKey
        account: .params.account
        limit: '.params.limit // 50'
        offset: '.params.offset // 0'
      timeout: 30

  get_conversation:
    description: >
      Get a full claude.ai web conversation with all messages.
      Returns the complete message history including both human and assistant turns.
    returns: conversation
    params:
      id: { type: string, required: true, description: "Conversation UUID" }
      account: { type: string, description: "Org UUID (omit to use session default)" }
    python:
      module: ./claude-api.py
      function: op_get_conversation
      args:
        session_key: .auth.sessionKey
        id: .params.id
        account: .params.account
      timeout: 30

  search_conversations:
    description: >
      Search claude.ai web conversations by title/name.
      Fetches up to 250 conversations and filters locally (no server-side search).
      For full content search across message text, use import_conversation first,
      then search({ query: "...", types: ["message"] }) against the graph FTS index.
    returns: conversation[]
    params:
      query: { type: string, required: true, description: "Text to search for in conversation titles" }
      account: { type: string, description: "Org UUID (omit to use session default)" }
      limit: { type: integer, default: 20, description: "Max results" }
    python:
      module: ./claude-api.py
      function: op_search_conversations
      args:
        session_key: .auth.sessionKey
        query: .params.query
        account: .params.account
        limit: '.params.limit // 20'
      timeout: 30

  import_conversation:
    description: >
      Import claude.ai conversations and all their messages into the graph.
      Each message becomes a message entity with full content FTS-indexed.
      After import, use search({ query: "...", types: ["message"] }) for content search.
      Safe to run repeatedly — deduplicates by message UUID.
      Use limit+offset to page through conversations in batches of 5-10.
    returns: message[]
    params:
      account: { type: string, description: "Org UUID (omit to use session default)" }
      limit: { type: integer, default: 5, description: "Conversations per batch (keep ≤10 to avoid DB lock)" }
      offset: { type: integer, default: 0, description: "Pagination offset" }
    python:
      module: ./claude-api.py
      function: op_import_conversation
      args:
        session_key: .auth.sessionKey
        account: .params.account
        limit: '.params.limit // 5'
        offset: '.params.offset // 0'
      timeout: 60

  list_orgs:
    description: |
      List all organizations the user has access to.
      Returns org UUIDs, names, and capabilities. Use this to discover
      which org has chat history (look for "chat" in capabilities).
    returns:
      uuid: string
      name: string
      capabilities: array
    python:
      module: ./claude-api.py
      function: op_list_orgs
      args:
        session_key: .auth.sessionKey
      timeout: 15

  extract_magic_link:
    description: |
      Extract the magic link URL from a raw base64url-encoded email body.
      Pass the raw RFC 2822 email body (e.g. from whichever integration exposes raw message bytes)
      and this will decode it and find the claude.ai magic link.
    params:
      raw_email:
        type: string
        required: true
        description: "Base64url-encoded raw RFC 2822 email content"
    returns:
      magic_link: string
    python:
      module: ./claude-login.py
      function: op_extract_magic_link
      args:
        raw_email: .params.raw_email
      timeout: 10

---

# Claude.ai

Browse and search your claude.ai web chat conversation history.

## How it works

claude.ai web chat history lives server-side only — unlike Claude Code (CLI) which stores
transcripts locally, web conversations are only accessible via the claude.ai API.

Two phases:
1. **Cookie provider matchmaking** — the runtime resolves who provides `.claude.ai` cookies and injects `sessionKey`.
2. **API calls** — all subsequent calls use `httpx` directly with the injected
   `sessionKey` — no browser needed, no session file

If multiple integrations provide cookies for the same domain, the agent should ask the user
which provider to use instead of guessing.

## Capabilities

```
OPERATION              DESCRIPTION
─────────────────────  ───────────────────────────────────────────────────
list_conversations     Browse conversations, most recently updated first
get_conversation       Full conversation with all messages
search_conversations   Search conversations by title (client-side filter)
import_conversation    Import messages into the graph for FTS content search
list_orgs              Discover available orgs and capabilities
extract_magic_link     Parse magic link URL from raw email content
```

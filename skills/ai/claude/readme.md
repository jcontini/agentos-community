---
id: claude
name: Claude
description: Claude — Anthropic's AI model family. Inference via API or local CLI, plus claude.ai chat history.
color: "#D97757"
website: "https://claude.ai"
privacy_url: "https://www.anthropic.com/privacy"
terms_url: "https://www.anthropic.com/terms-of-service"

product:
  name: Claude
  website: https://claude.ai
  developer: Anthropic

connections:
  api:
    description: Claude API — inference via the Messages API
    base_url: https://api.anthropic.com/v1
    auth:
      type: api_key
      header:
        x-api-key: .auth.key
    label: API Key
    help_url: https://console.anthropic.com/settings/keys

  cli:
    description: Claude Code — local CLI, uses the user's existing auth (no API key)
    # No credentials: the `claude` binary manages its own auth state.

  web:
    description: claude.ai — web chat history via session cookies
    auth:
      type: cookies
      domain: .claude.ai
      names:
      - sessionKey
      account:
        check: check_session
      login:
        account_prompt: What email do you use for claude.ai?
        phases:
        - name: request_login
          description: Submit email on the Claude login page to trigger a magic link email
          steps:
          - action: goto
            url: https://claude.ai/login
          - action: fill
            selector: input[type=email]
            value: ${ACCOUNT}
          - action: click
            selector: button[type=submit]
          returns_to_agent: 'Magic link requested. Check the user''s email for a message from Anthropic

            containing a claude.ai/magic-link URL. Search mail or the graph for that message,

            or ask the user to paste the link.

            '
        - name: complete_login
          description: Navigate to the magic link URL to complete authentication
          requires:
          - magic_link
          steps:
          - action: goto
            url: ${MAGIC_LINK}
          - action: wait
            url_contains: /new
          returns_to_agent: 'Login complete. The sessionKey cookie is now in the browser.

            Cookie provider matchmaking will extract it automatically on the next API call.

            '

test:
  check_session:
    skip: true
---

# Claude

One skill for everything Claude. Four access modalities, one product.

| Connection | File | What it does |
|---|---|---|
| `api` | `claude_api.py` | Inference via the Claude API (Messages endpoint) |
| `cli` | `claude_code.py` | Inference via the local `claude` CLI, plus reads local Claude Code state |
| `web` | `claude_web.py` | Browse/search/import claude.ai chat history |

Models are **never hardcoded**. All operations accept a `model` parameter that is
resolved through the graph (`list_models` on the relevant connection populates it).
See `docs/specs/done/no-hardcoded-models.md` for rationale.

## Usage

### `api` connection — Claude API inference

| Tool | Description |
|---|---|
| `list_models` | Fetch the current model catalog from `api.anthropic.com/v1/models` |
| `chat` | Send a single Messages API request. Supports tools, system prompts, temperature. Returns raw tool_use blocks for the caller to process. |

### `cli` connection — Claude Code

Uses the user's logged-in `claude` binary (no API key required) AND reads local
on-disk state under `~/.claude/projects/`.

| Tool | Description |
|---|---|
| `agent` | Run Claude as an agent via `claude -p`. Full agent loop — tool use + structured output via `--mcp-config` / `--json-schema`. |
| `list_models_cli` | List Claude models via the keychain OAuth token (no API key). Same endpoint as `list_models`, different auth. |
| `list_projects` | List every project directory under `~/.claude/projects/` with conversation counts and last activity. |
| `list_conversations_cli` | List local Claude Code conversations (one per JSONL transcript) as shape-native `conversation[]`. Optional `project` scope, optional `limit`. |
| `read_conversation_cli` | Read a full conversation transcript — returns one `conversation` with a nested `message[]` relation (content, blocks, author, published, tool calls). |

> **Note:** The `cli` connection uses `agent` rather than `chat` because it behaves
> fundamentally differently from the API — it loops internally over tool calls.
> Both still `@provides(llm)` so capability routing can pick either.
>
> The `_cli` suffix on `list_models_cli` / `list_conversations_cli` /
> `read_conversation_cli` is because skill tool names share a flat namespace
> across all `.py` files in the skill, and the same names are already taken by
> the `api` and `web` connections (for the Anthropic API model list and
> claude.ai web chats, respectively).

### `web` connection — claude.ai chat history

| Tool | Description |
|---|---|
| `list_conversations` | Browse conversations, most recent first |
| `get_conversation` | Full conversation with all messages |
| `search_conversations` | Search by title (client-side filter) |
| `import_conversation` | Import messages into graph for FTS |
| `list_orgs` | Discover orgs and capabilities |
| `check_session` | Verify cookies are valid, return identity |
| `extract_magic_link` | Parse magic link from raw email (used during login) |

## Setup

### `api` connection
1. Get an API key from https://console.anthropic.com/settings/keys
2. Add credential in AgentOS Settings → Skills → Claude (API Key)

### `cli` connection
Install Claude Code and log in:
```bash
curl -fsSL https://claude.ai/install.sh | bash    # or: brew install claude-code
claude auth login                                   # opens browser for OAuth
```
Works with Pro/Max/Team/Enterprise subscriptions. Once logged in, `claude_code.py`
uses that auth state directly — no key exchange with agentOS.

### `web` connection
No setup needed if you're logged in to claude.ai in a supported browser (Brave/Firefox).
Cookie provider matchmaking extracts `sessionKey` automatically.

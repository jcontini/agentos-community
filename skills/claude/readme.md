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

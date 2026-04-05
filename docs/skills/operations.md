# Operations

Operations are skill tools — the things agents can call.

## Entity operations

When an operation returns data that maps to an entity type, declare the shape with `returns:`:

```yaml
operations:
  list_emails:
    description: List emails with full content
    returns: email[]        # array of email entities
    python:
      module: ./gmail.py
      function: list_emails
      timeout: 120

  get_email:
    description: Get a specific email
    returns: email           # single email entity
    python:
      module: ./gmail.py
      function: get_email
      timeout: 30
```

`returns: email[]` means "this operation returns an array of records matching the `email` shape." The Python function must return dicts with keys matching the shape's fields (see [Shapes](shapes.md) for field definitions and standard fields).

Rules:

- Use `snake_case` — prefer short, obvious names like `search`, `read_webpage`, `list_tasks`
- Use `returns: entity[]` for list/search results, `returns: entity` for single entities
- The Python module does the field mapping — transform raw API data into shape-native dicts
- Pass caller-provided limits through to the API when the backend supports them
- Use relative `rest.url` paths (e.g. `/tasks/filter`) when the connection has a `base_url`
- Use absolute URLs only when a skill has no connection or the endpoint is on a different domain

## Action operations

Use an inline `returns:` schema when one of these is true:

- The return value is not an entity
- The tool is an action, not a normal entity read/write
- The tool returns a custom inline schema

```yaml
operations:
  send_email:
    description: Send a new email
    returns: email           # still an entity — the sent email
    python:
      module: ./gmail.py
      function: send_email
      timeout: 30

  delete_label:
    description: Delete a Gmail label
    returns:
      status: string         # inline schema — not an entity
    python:
      module: ./gmail.py
      function: delete_label
      timeout: 15
```

Rules:

- Operation names should still be `snake_case`
- Prefer direct, concrete verbs like `send_text`, `focus_tab`, `list_status`
- Test them through `mcp:call` early, because runtime mismatches are easier to miss than YAML mismatches

## Capabilities (dynamic MCP tools)

Skills can surface first-class MCP tools via `provides:`. Each `provides: tool` entry generates a top-level MCP tool (like `web_search`, `web_read`, `flight_search`) that agents see alongside the built-in tools. No hardcoded Rust is needed — the engine reads `provides:` from installed skills at startup.

**Registration is skill-level.** Add a `provides:` list entry with `tool:` (MCP tool name) and `via:` (operation name). Optional `urls:` declares URL patterns for routing (URL-specific providers are preferred over generic ones).

```yaml
# Generic provider — always eligible
provides:
  - tool: web_search
    via: search

# URL-specific provider — preferred when URL matches
provides:
  - tool: web_read
    via: transcript_video
    urls:
      - "youtube.com/*"
      - "youtu.be/*"
```

When multiple skills provide the same tool name, the engine:
1. Intersects params across all providers (only common params appear on the MCP tool)
2. Routes calls by: explicit `skill` param > URL pattern match > credentialed provider > no-auth fallback
3. Adds a note in the tool description pointing to `load()` for provider-specific advanced options

Current dynamic tools (from installed skills):
- `web_search` — brave, exa
- `web_read` — firecrawl, exa, curl (generic); youtube, reddit (URL-specific)
- `flight_search` — serpapi
- `geocoding` — uber (worldwide address geocoding via HERE Maps)

To verify dynamic tools appear:

```bash
cd ~/dev/agentos
node scripts/mcp-test.mjs stdio "./target/release/agentos mcp"
```

Credential and cookie **providers** use the same `provides:` list with `auth:` entries (see [Connections & Auth](connections.md)).

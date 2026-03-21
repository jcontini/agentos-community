# Contributing to AgentOS Community

This file is for **skill authoring**. It is intentionally narrow.

If you're editing `skills/*/skill.yaml` or `skills/*/readme.md`, start here. If you're working on apps, CSS, UI components, or unrelated repo infrastructure, this is the wrong doc.

In development, AgentOS reads skills directly from this repo. Skill YAML changes are picked up on the next skill call. If you changed Rust core in `~/dev/agentos`, restart the engine there before trusting live MCP results.

## Read This First

Current source of truth:

- `CONTRIBUTING.md` — the skill contract and workflow (keep it in sync when the contract changes — see below)
- `skills/exa/skill.yaml` + `skills/exa/readme.md` — canonical entity-returning example
- `skills/kitty/skill.yaml` + `skills/kitty/readme.md` — canonical local-control/action example
- `~/dev/agentos/bin/audit-skills.py` — unknown-key and structural checks against Rust `types.rs` (run via `npm run validate`); duplicate adapter-mapping expressions emit non-blocking `⚠` advisories
- `~/dev/agentos/spec/skill-manifest.target.yaml` — narrative target shape (`provides`, connections, operations); `ProvidesEntry` / auth in `~/dev/agentos/crates/core/src/skills/types.rs`
- `test-skills.cjs` — direct MCP smoke testing (`mcp:call`, `mcp:test`)
- `~/dev/agentos/scripts/mcp-test.mjs` — engine-level MCP test harness (raw JSON-RPC, verifies dynamic tools from `provides:`)
- `docs/reverse-engineering/` — transport, discovery, and auth patterns for building skills against sites without public APIs

Only treat two skills as primary copy-from examples:

- `skills/exa/` for entity-returning skills
- `skills/kitty/` for local-control/action skills

You may inspect other skills for specialized auth or protocol details, but do not treat older mixed-pattern skills as the default scaffold.

## Workflow

Each tool in the workflow proves something different:

```bash
# 1. Edit the live skill definition (manifest is skill.yaml; readme is markdown only)
$EDITOR skills/my-skill/skill.yaml

# 2. Fast structural gate for hooks / local iteration
npm run validate --pre-commit -- my-skill

# 3. Full structural + mapping check
npm run validate -- my-skill

# 4. Semantic lint for legacy patterns and request-template drift
npm run lint:semantic -- my-skill

# 5. Filter large runs while cleaning up families of skills
npm run validate -- --filter browser

# 6. Ground-truth live MCP call through run({ skill, tool, params, account?, remember? })
npm run mcp:call -- \
  --skill exa \
  --tool search \
  --params '{"query":"rust ownership","limit":1}' \
  --format json \
  --detail full

# 7. Strict smoke test for a skill
npm run mcp:test -- exa --verbose
```

What each step means:

- `validate --pre-commit` checks fast structural validity only
- `validate` checks structure, entity refs, and mapping sanity
- `lint:semantic` is an advisory semantic pass for legacy placeholder/auth patterns, dead `api.base_url`, suspicious request roots, returns/adapters drift, mixed executor types, and GraphQL endpoint drift
- Pass `--strict` to `lint:semantic` if you want it to fail on semantic errors
- The pre-push hook runs `lint:semantic --strict` on changed top-level skills, so the main skill set is expected to stay semantically clean
- Step 6 is the ground-truth live `run()` path; `run()` is always live, and `remember` defaults to true when you want imported graph state to reflect the result
- `mcp:call` proves the live runtime can load the skill and execute one real tool
- Pass `--account <name>` to `mcp:call` for multi-account skills that need an explicit account choice
- `mcp:test` is the strict smoke path for explicitly annotated runtime coverage
- Only operations with a `test:` block are included in default smoke
- The only intended skip class is `skip_write` for mutating or human-gated operations
- If a read-safe operation cannot be exercised because required params are unresolved, that is a failure, not a skip

## Keeping CONTRIBUTING in sync

Whenever you change something that affects **how authors write skills** — new or removed YAML fields, connection/auth models, adapter conventions, operation keys, or rules enforced by `audit-skills.py` / `lint:semantic` — **update this document in the same change** (same PR / paired commit across `agentos` and `agentos-community` if both repos move). CONTRIBUTING is the human-readable contract next to the machine checks; letting it drift wastes the next author's time.

Before you push skill-contract work, sanity-check that examples here still parse and that stale patterns (legacy `provides:` shapes, readme-only manifests, etc.) are not left in place.

Important runtime note:

- `agentos mcp` is a proxy to the engine daemon
- If you changed Rust core in `~/dev/agentos`, restart the engine before trusting `mcp:call`
- If Cursor MCP looks stale, use `npm run mcp:call` and `npm run mcp:test` as the ground-truth path while you restart the engine or reconnect the editor

## Python Over Rust

Prefer Python scripts for skill logic. When an API has quirks (list returns stubs only, batch fetching, custom parsing), solve it in a `*.py` helper like Granola does — not by modifying agentOS core. Rust changes are costly to iterate; Python lives in the skill folder and ships with the skill. We’ll revisit what belongs in core later; for now, keep skill-specific behavior in skills.

When Python needs to call authenticated APIs, use `_call` dispatch (see Python Executor Shape below) instead of handling credentials directly. The engine mediates all authenticated calls through sibling operations with full credential injection. Python scripts never see raw tokens.

When Python needs to make HTTP requests directly (scraping, APIs without a REST executor, WAF-sensitive endpoints), use **httpx** with HTTP/2 enabled — not `urllib.request`, not `requests`. httpx handles HTTP/2, connection pooling, and presents a modern TLS fingerprint that avoids CDN bot detection. Install with `pip install "httpx[http2]"` and use `httpx.Client(http2=True)` for session reuse.

## The Short Version

The current skill style is:

- Use `connections:` for external service dependencies (auth, base URLs)
- Use `adapters:` for entity mappings
- Use simple `snake_case` tool names like `search`, `read_webpage`, or `send_text`
- Do not use dotted names like `task.list` or `webpage.read`
- Do not use `transformers:`, `terminology:`, or adapter-level `display:`
- Put canonical fields directly in the adapter body
- Treat the adapter body itself as the default mapping
- Use `operations:` for both entity-returning tools and local-control/action tools
- Use inline `returns:` schemas for non-entity or action-style tools
- Validate live behavior through the direct MCP path, not just by reading YAML


## Folder Shape

Every skill is a folder like:

```text
skills/
  my-skill/
    skill.yaml           # required — executable manifest (connections, adapters, operations, …)
    readme.md            # recommended before ship — markdown instructions for agents (no YAML front matter)
    requirements.md      # recommended — scope out the API, auth model, and entities before writing YAML
    my_helper.py         # optional — Python helper when inline command logic gets complex
```

The runtime loads **only** `skill.yaml` for structure; `readme.md` is merged in as the instruction body. Do not put skill YAML in `readme.md` front matter.

Start with `requirements.md` before writing skill YAML. Use it to scope out what endpoints or data surfaces exist, what auth model the service uses, which entities map to what, and any decisions or trade-offs. This is useful for any skill — not just reverse-engineered ones. For web skills without public APIs, it also becomes the place to log endpoint discoveries, header mysteries, and auth boundary mappings. See `docs/reverse-engineering/` for that playbook.

## Entity Skill Shape

Use this pattern for normal data-fetching or CRUD-ish skills.

```yaml
id: my-skill
name: My Skill
description: One-line description
website: https://example.com

connections:
  api:
    base_url: "https://api.example.com"
    header:
      Authorization: '"Bearer " + .auth.key'
    label: API Key
    help_url: https://example.com/api-keys

adapters:
  result:
    id: .url
    name: .title
    text: .summary
    url: .url
    image: .image
    author: .author
    datePublished: .published_at
    data.score: .score

operations:
  search:
    description: Search the service
    returns: result[]
    params:
      query: { type: string, required: true }
      limit: { type: integer, required: false }
    rest:
      method: POST
      url: /search
      body:
        query: .params.query
        limit: '.params.limit // 10'
      response:
        root: /results
```

## Local Control Shape

Use this pattern for command-backed skills such as terminal, browser, OS, or app control. Local skills have no `connections:` block — they don't need external auth.

```yaml
id: my-local-skill
name: My Local Skill
description: Control a local surface
website: https://example.com

operations:
  list_status:
    description: Inspect local state
    returns:
      ok: boolean
      cwd: string
    command:
      binary: python3
      args:
        - -c
        - |
          import json, os
          print(json.dumps({"ok": True, "cwd": os.getcwd()}))
      timeout: 10
```

If you are starting a new skill from scratch, use `npm run new-skill -- my-skill` for an entity scaffold or `npm run new-skill -- my-skill --local-control` for a local-control scaffold.

## Python Executor Shape

Use this pattern when a skill needs Python logic (parsing, API glue, multi-step flows). The `python:` executor calls a function directly in a Python module — no `binary: python3` boilerplate, no `sys.argv` dispatch, no `| tostring` on every arg.

```yaml
operations:
  get_schedule:
    description: Get today's class schedule
    returns: class[]
    params:
      date: { type: string, required: false }
      location_id: { type: integer, default: 6 }
    python:
      module: ./my_script.py
      function: get_schedule
      args:
        date: .params.date
        location_id: .params.location_id
      timeout: 30
```

The Python function receives keyword arguments and returns JSON-serializable data:

```python
def get_schedule(date: str = None, location_id: int = 6) -> list[dict]:
    ...
    return results
```

Rules:

- `module` is resolved relative to the skill folder (use `./my_script.py`)
- `function` is the function name in the module
- `args` values are jaq expressions resolved against the params context (same as `rest.body`)
- **Shorthand:** When the Python function expects a single `params` dict, use `params: true` instead of `args: { params: .params }`
- Args are passed as typed JSON — integers stay integers, no `| tostring` needed
- `timeout` defaults to 30 seconds
- `response` mapping (root, transform) works the same as `rest:` and `graphql:`
- Auth values are available via `.auth.*` in args expressions
- Functions should not use `print(json.dumps(...))` or `sys.argv` — the runtime handles I/O

Migration note: existing `command:` + `binary: python3` skills can adopt `python:` for cleaner YAML. Examples: `austin-boulder-project`, `goodreads`, `granola`, `cursor`, `here-now`.

### Connection dispatch — multi-backend Python helpers

When a skill has multiple connections that serve the same operations via different transports (SDK vs CLI, live API vs cache), the Python helper receives the active connection and dispatches accordingly:

```yaml
operations:
  list_items:
    description: List items from the service
    returns: item[]
    connection: [sdk, cli]
    python:
      module: ./my_skill.py
      function: list_items
      args:
        vault: .params.vault
        connection: '.connection'
      timeout: 60
```

```python
def list_items(vault, connection=None):
    if connection and connection.get("id") == "sdk":
        return _list_via_sdk(vault, connection["vars"])
    else:
        return _list_via_cli(vault, connection.get("vars", {}))
```

Both code paths normalize output into the same shape so the adapter works regardless of which backend ran. This pattern is useful when a primary path (SDK with batch ops) needs a stable fallback (CLI with subprocess calls). See `skills/granola/` for the `api` + `cache` variant of this pattern.

### `_call` dispatch — calling sibling operations from Python

When a Python operation needs to compose multiple API calls (e.g. list returns stubs, get returns full data), use `_call` to invoke sibling operations. The engine injects `_call` automatically when the function signature accepts it.

```python
def list_emails(query="", limit=20, _call=None):
    stubs = _call("list_email_stubs", {"query": query, "limit": limit})
    return [_call("get_email", {"id": s["id"]}) for s in stubs]
```

The YAML wires the Python function as usual:

```yaml
operations:
  list_emails:
    description: List emails with full content
    returns: email[]
    python:
      module: ./gmail.py
      function: list_emails
      args:
        query: '.params.query // ""'
        limit: '.params.limit // 20'
      timeout: 120

  list_email_stubs:
    description: "Internal: list email IDs only"
    returns: email[]
    rest:
      url: "/messages"
      method: GET
      query:
        maxResults: ".params.limit // 20"
        q: ".params.query"
      response:
        transform: ".messages // []"
```

Rules:

- `_call` can only call operations in the **same skill** — no cross-skill calls
- The engine executes each dispatched call with full credential injection (OAuth, cookies, API keys)
- Python never sees raw credentials — the engine is the only process that touches tokens
- `_call` is synchronous and blocking — each call completes before the next starts
- The same `account` context from the parent call is used for dispatched operations
- If a function's signature does not include `_call` (or `**kwargs`), it is not injected — existing functions work unchanged

Leading by example: `skills/gmail/gmail.py` (list + hydrate pattern with `_call`).

## Adapters

Adapters map raw API responses into AgentOS entities. Define the shape once in `adapters:` and let operations reference it via `returns:`.

### Canonical fields

The renderer (`render.rs`) and markdown previews resolve entity display from a fixed set of **canonical fields**. Every adapter should map as many of these as the source data supports — they are the reason entities look consistent across skills in previews, detail views, and search results.

| Field           | Purpose                                          | Renderer fallback chain                                    |
|-----------------|--------------------------------------------------|------------------------------------------------------------|
| `name`          | Primary label / title                            | `name` → `title` → `conversation_name`                    |
| `text`          | Short summary or snippet for preview rows        | `text` → `description` → `content` → `snippet`            |
| `url`           | Clickable link                                   | —                                                          |
| `image`         | Thumbnail / hero image                           | —                                                          |
| `author`        | Creator / brand / owner                          | —                                                          |
| `datePublished` | Temporal anchor (accepts several date aliases)   | `datePublished` → `date` → `created_at` (see `render.rs`) |

Not every entity has all six — a product may have no `datePublished`, an order may have no `image`. Map what the source provides; skip what doesn't apply.

#### Comment convention

Mark the boundary between canonical and skill-specific fields with comments so the two sections are visually obvious:

```yaml
adapters:
  result:
    # --- Canonical fields (rendered in previews / markdown) ---
    id: .url
    name: .title
    text: '.text // .summary'
    url: .url
    image: .image
    author: .author
    datePublished: .publishedDate
    # --- Skill-specific data ---
    data.score: .score
```

For lightweight relationship entities you can use the shorter `# --- Canonical fields ---` header. The `data.*` section comment is optional when there are only one or two extra fields, but always include the canonical header.

#### Merge rules and deduplication

**Source of truth in core:** `crates/core/src/view/render.rs` — `project_item` (preview) and `canonicalize_full_item` (full/detail JSON) define how raw entity keys map into the stable shape. The fallback chains in the table above are applied at render time, so mapping to the *first* key in the chain is preferred (e.g. `name` over `title`).

**Import / remember / FTS:** `crates/core/src/execution/extraction.rs` — `prepare_node_data` treats **`content`** (and optional **`content_role`**) specially: that string is stored in the **`content` table** (indexed into the FTS **`body`** column). Other scalar fields (including `text`, `description`, `url`, …) become **node vals** and are folded into the FTS **`vals`** column on rebuild. Long or searchable bodies should use **`content`**, not a second copy in `text`/`description`.

Avoid mapping the **same jaq expression** to multiple sibling keys unless you have a deliberate reason (for example, a legacy alias you are phasing out). Duplicates like `name: .title` and `title: .title`, or `text` and `description` both bound to `.summary`, **do not change markdown** (the renderer picks one via the order above) but still **duplicate stored vals** on the graph node — prefer a single source field; put a second exposure under `data.*` only when callers truly need a differently named slot.

`audit-skills.py` emits an **advisory** (non-blocking) warning when two fields in the same adapter object share an identical mapping expression after trimming — use it to catch accidental redundancy.

### Adapter relationships

Adapters can declare relationships between entities. A nested block under a canonical field creates a graph edge from the adapted entity to the related entity:

```yaml
adapters:
  account:
    # --- Canonical fields (rendered in previews / markdown) ---
    id: .id
    name: .title
    # --- Skill-specific data ---
    data.category: .category

    in_vault:
      vault:
        # --- Canonical fields ---
        id: .vault.id
        name: .vault.name
```

This creates an `in_vault` edge from each `account` entity to its parent `vault` entity. The nested adapter (`vault:`) follows the same mapping rules — `id`, `name`, and `data.*` fields. The engine creates or finds the related entity and adds the edge.

Use relationships when entities have a natural containment or ownership structure (items in vaults, messages in conversations, tasks in projects). The relationship name (`in_vault`) becomes the edge label on the graph.

Rules:

- Put canonical fields directly in the adapter body
- Keep default mapping in `adapters.<entity>`
- Use `data.*` for adapter-specific extra fields
- Use `content` only for long body text that should be stored separately (do not also mirror the same long text into `text` unless you mean to)
- Map to an existing entity type whenever possible

Good:

```yaml
adapters:
  result:
    # --- Canonical fields (rendered in previews / markdown) ---
    id: .url
    name: .title
    text: '.text // .summary'
    url: .url
    image: .image
    author: .author
    datePublished: .publishedDate
    # --- Skill-specific data ---
    data.score: .score
```

Bad:

```yaml
transformers:
  result:
    terminology: Search Result
    display:
      title: .title
```

## Operations

Operations are entity-returning skill tools.

Rules:

- Use `snake_case`
- Prefer short, obvious names
- Good: `search`, `read_webpage`, `list_tasks`, `get_task`, `create_task`
- Bad: `task.list`, `webpage.read`
- Use `returns: entity[]` for list/search results
- Use `returns: entity` for single entities
- Do not hardcode misleading low limits
- Pass caller-provided limits through to the API when the backend supports them
- Use relative `rest.url` paths (e.g. `/tasks/filter`) when the connection has a `base_url`
- Use absolute URLs only when a skill has no connection or the endpoint is on a different domain

## Action Operations

Use normal `operations:` with an inline `returns:` schema when one of these is true:

- The return value is not an entity
- The tool is an action, not a normal entity read/write
- The tool returns a custom inline schema

Rules:

- Operation names should still be `snake_case`
- Prefer direct, concrete verbs like `send_text`, `focus_tab`, `list_status`
- Test them through `mcp:call` early, because runtime mismatches are easier to miss than YAML mismatches

## Capabilities (Dynamic MCP Tools)

Skills can surface first-class MCP tools via `provides:`. Each `provides: tool` entry generates a top-level MCP tool (like `web_search`, `web_read`, `flight_search`) that agents see alongside the built-in tools. No hardcoded Rust is needed — the engine reads `provides:` from installed skills at startup.

**Registration is skill-level, not on the operation.** Add a `provides:` list entry with `tool:` (MCP tool name) and `via:` (operation name). Optional `urls:` declares URL patterns for routing (URL-specific providers are preferred over generic ones). Do not put `provides:` under `operations.*`.

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

To verify dynamic tools appear:

```bash
cd ~/dev/agentos
node scripts/mcp-test.mjs stdio "./target/release/agentos mcp"
```

Credential and cookie **providers** use the same `provides:` list with `credentials:` or `cookies:` entries (see Provider auth below).

## Connections

Every skill declares its external service dependencies as **named** `connections:`. Each connection can carry `base_url`, auth (`header` / `query` / `body`, `cookies`, `oauth`), optional `description`, `label`, `help_url`, `optional`, and **local data sources**:

- **`sqlite:`** — path to a SQLite file (tilde-expanded). SQL operations bind to the connection that declares the database; there is **no** top-level `database:` on the skill.
- **`vars:`** — non-secret config (paths, filenames) merged into the executor context (e.g. `params.connection.vars` for Python) so scripts can read local files without hardcoding home-directory paths.

Local skills (no external services) simply omit the `connections:` block.

There is **no** `needs:` key on connections — it was removed from the type (it was never wired into auth resolution). Declare **`cookies:`**, **`oauth:`**, and/or template **`header` / `query` / `body`** on the connection instead; provider matchmaking uses `oauth.service` and cookie domain plus installed skills’ typed `provides`.

Most common pattern — single API key connection:

```yaml
connections:
  api:
    base_url: "https://api.example.com/v1"
    header:
      x-api-key: .auth.key
    label: API Key
    help_url: https://example.com/api-keys
```

Multi-connection pattern — public GraphQL + authenticated web session:

```yaml
connections:
  graphql:
    base_url: "https://api.example.com/graphql"
  web:
    cookies:
      domain: ".example.com"
```

Multi-backend pattern — same service, different transports (e.g. SDK + CLI):

```yaml
connections:
  sdk:
    description: "Python SDK — typed models, batch ops, biometric auth"
    vars:
      account_name: "my-account"
  cli:
    description: "CLI tool — stable JSON contract, fallback path"
    vars:
      binary_path: "/opt/homebrew/bin/mytool"
```

When connections differ by transport rather than service, each operation declares which it supports (`connection: [sdk, cli]`). The Python helper receives `connection` as a param and dispatches to the appropriate backend. Both paths normalize output into the same adapter-compatible shape. Use this when: (a) a v0 SDK needs a stable CLI fallback, (b) read ops work with both but writes need the SDK for batch/typed APIs, or (c) offline/online modes with the same data model.

Rules:

- `base_url` on a connection is used to resolve relative `rest.url` and `graphql.endpoint` values
- Single-connection skills auto-infer the connection — no `connection:` needed on each operation
- Multi-connection skills must declare `connection:` on each operation: either one name (`connection: api`) or a **list** (`connection: [api, cache]`) when the caller may choose the backing source (live API vs local cache, etc.)
- With `connection: [a, b, …]`, the first entry is the default; expose `connection` in `params` and pass it through from Python/`rest`/`graphql` so the runtime resolves the effective connection (see `skills/granola/skill.yaml` for `params.connection` wired into `args`)
- Set `connection: none` on operations that should skip auth entirely
- Use `optional: true` if the skill works anonymously but improves with credentials
- Connections without any auth fields (just `base_url`, `sqlite`, `vars`, and/or `description`) are valid — they serve as service declarations

Connection names are arbitrary. Common conventions:

- `api` — REST API with key/token auth
- `graphql` — GraphQL/AppSync (may or may not have auth)
- `web` — cookie-authenticated website (user session)

### Auth types on connections

Three auth resolution mechanisms exist:

**Template auth** (API keys, tokens) — `header`, `query`, or `body` fields with jaq expressions:

```yaml
connections:
  api:
    header:
      Authorization: '"Bearer " + .auth.key'
    label: API Key
```

**Cookie auth** — extracted from installed browsers via provider skills:

```yaml
connections:
  web:
    cookies:
      domain: ".claude.ai"
      names: ["sessionKey"]
```

**OAuth** — token refresh and provider-based acquisition:

```yaml
connections:
  gmail:
    oauth:
      service: google
      scopes:
        - https://mail.google.com/
```

### Provider auth

Credentials can come from other installed apps (e.g. Mimestream provides Google OAuth tokens, Brave provides browser cookies).

Skill-level `provides:` is a **typed** list: each entry is either `credentials:` (OAuth or API key), `cookies:`, or `tool:` + `via` for discoverable tools. Do not use legacy `capability:` / `accounts_via` shapes.

OAuth provider (excerpt):

```yaml
provides:
  - credentials:
      oauth:
        service: google
        via: credential_get
        account_param: account
        scopes:
          - https://mail.google.com/
```

Cookie provider (excerpt):

```yaml
provides:
  - cookies:
      via: cookie_get
      account_param: domain
      description: "Short human description for discovery"
```

Consumer skills don't name a specific provider — the runtime discovers installed providers automatically.

Example references:

- OAuth consumer: `skills/gmail/skill.yaml`
- OAuth provider: `skills/mimestream/skill.yaml`
- Cookie consumer: `skills/claude/skill.yaml`
- Cookie provider: `skills/brave-browser/skill.yaml`
- Multi-connection: `skills/goodreads/skill.yaml` (graphql + web)

## Sandbox Storage

Skills can persist state across runs using two reserved keys on their graph node:

- **`cache`** — regeneratable state (discovered endpoints, scraped tokens). Can be cleared at any time; the skill re-discovers on next run.
- **`data`** — persistent state (settings, preferences, sync timestamps). Survives cache clears.

If losing it requires user action to recover (re-entering a setting), it's data. If the skill can regenerate it, it's cache.

### Reading

The execution context always includes `.data` and `.cache`:

```json
{ "params": { ... }, "auth": { ... }, "data": { ... }, "cache": { ... } }
```

In YAML expressions:

```yaml
rest:
  url: '(.cache.graphql_endpoint // "https://fallback.example.com/graphql")'
```

In Python, pass `cache` and/or `data` via `args:`:

```yaml
python:
  module: ./my_script.py
  function: search
  args:
    query: .params.query
    cache: .cache
```

### Writing back

Python and command executors write back using reserved keys in their return value:

- `__cache__` — merged into the skill node's cache
- `__data__` — merged into the skill node's data
- `__result__` — the actual result callers see

```python
def discover_endpoint(cache=None, **kwargs):
    if cache and cache.get("graphql_endpoint"):
        return {"endpoint": cache["graphql_endpoint"]}

    endpoint = _discover()
    return {
        "__cache__": {"graphql_endpoint": endpoint},
        "__result__": {"endpoint": endpoint},
    }
```

If neither `__cache__` nor `__data__` is present, the result passes through unchanged. Fully backward compatible.

### `__secrets__` — secret store writes

A third reserved key, `__secrets__`, handles importing secrets from external sources (password managers, payment info, identity documents, etc.) into the credential store. The `__secrets__` handler is pure credential store CRUD — it writes credential rows and strips the key. It does **not** create graph entities or edges; entity creation happens through the normal adapter pipeline processing `__result__`. The two systems are joined by `(issuer, identifier)`.

```python
def import_items(vault, dry_run=False):
    items = fetch_from_source(vault)
    if dry_run:
        return [{"issuer": i["issuer"], "label": i["label"]} for i in items]

    return {
        # Secrets → credential store (engine writes rows, strips key)
        "__secrets__": [
            {
                "item_type": "password",
                "issuer": "github.com",
                "identifier": "joe",
                "label": "GitHub",
                "source": "mymanager",
                "value": {"password": "..."},
                "metadata": {"masked": {"password": "••••••••"}}
            },
            {
                "item_type": "credit_card",
                "issuer": "chase",
                "identifier": "visa-4242",
                "label": "Personal Visa",
                "source": "mymanager",
                "value": {"card_number": "4111111111114242", "cvv": "123"},
                "metadata": {"masked": {"card_number": "••••4242", "cvv": "•••"}}
            }
        ],
        # Entities → shaped by adapters into graph nodes
        "__result__": [
            {"issuer": "github.com", "identifier": "joe", "title": "GitHub",
             "category": "LOGIN", "url": "https://github.com", "username": "joe"},
            {"issuer": "chase", "identifier": "visa-4242", "title": "Personal Visa",
             "category": "CREDIT_CARD", "cardholder": "Joe", "card_type": "Visa",
             "expiry": "12/2027", "masked": {"card_number": "••••4242", "cvv": "•••"}}
        ]
    }
```

The trust model: Python sees secrets (it reads them from the source), the engine intercepts and encrypts them, the agent never sees them — only `metadata` (including `masked` representations). Graph entities carry masked previews ("Visa ending in 4242") so the agent can reason about which card to use without seeing the full number.

See `spec/credential-system.md` and `spec/1password-integration.md` for full design.

**Status:** Implemented (Phase A). The engine intercepts `__secrets__` in `process_storage_writeback()`, writes credential rows to `credentials.sqlite`, creates account entities and `claims` edges on the graph, then strips the key before the MCP response.

Leading by example: `skills/goodreads/public_graph.py` (GraphQL endpoint discovery cached via `__cache__`).

## Expressions

Use one expression style everywhere:

- `rest:`, `graphql:`, `command:`, `python:`, and connection auth fields all use jq/jaq-style expressions
- Resolved credentials are available under `.auth.*` such as `.auth.key` or `.auth.access_token`

Common jq/jaq patterns:

```yaml
url: '"/items/" + .params.id'
query:
  q: .params.query
  limit: .params.limit // 10
body:
  title: .params.title
```

Common command patterns:

```yaml
command:
  binary: python3
  args:
    - ./my_script.py
    - run
  stdin: '.params | tojson'
```

When a `command:` argument or `working_dir:` looks like a relative file path, it is resolved relative to the skill folder. Prefer `./my_script.py` over machine-specific absolute paths.

If you need advanced command, steps, or crypto behavior, copy from an existing skill.

## View Contract

The `run` tool accepts:

```yaml
view:
  detail: preview | full
  format: markdown | json
```

Rules:

- `detail` changes data volume
- `format` changes representation
- Default is markdown preview
- Preview keeps canonical fields and truncates long `text`
- Full returns all mapped fields
- JSON returns a `{ data, meta }` envelope

This is why canonical mapping fields matter.

## Direct MCP Testing

Use direct MCP testing whenever you change a skill. This is the fastest way to verify the real output contract.

### Skill-level testing (community repo)

`mcp:call` and `mcp:test` automatically use the newest built `agentos` binary. Set `AGENTOS_BINARY=/path/to/agentos` if you need to force a specific one.

JSON preview:

```bash
npm run mcp:call -- \
  --skill exa \
  --tool search \
  --params '{"query":"rust ownership","limit":1}' \
  --format json \
  --detail preview
```

JSON full:

```bash
npm run mcp:call -- \
  --skill exa \
  --tool search \
  --params '{"query":"rust ownership","limit":1}' \
  --format json \
  --detail full
```

Markdown full:

```bash
npm run mcp:call -- \
  --skill exa \
  --tool search \
  --params '{"query":"rust ownership","limit":1}' \
  --detail full \
  --raw
```

YAML-driven smoke test:

```bash
npm run mcp:test -- exa --verbose
```

### Engine-level testing (core repo)

The core repo has a generic MCP test harness at `~/dev/agentos/scripts/mcp-test.mjs` that speaks raw JSON-RPC to the engine binary. Use it to verify the full tool surface — including dynamically generated capability tools from `provides:` — without going through the editor.

```bash
cd ~/dev/agentos

# List all MCP tools (built-in + dynamic)
node scripts/mcp-test.mjs stdio "./target/release/agentos mcp"

# Call a dynamic capability tool
node scripts/mcp-test.mjs stdio "./target/release/agentos mcp" call web_search '{"query":"rust"}'

# Call with URL routing
node scripts/mcp-test.mjs stdio "./target/release/agentos mcp" call web_read '{"url":"https://youtube.com/watch?v=abc"}'
```

This is the fastest path when you're changing `provides:` entries, engine routing, or tool schemas. It spawns a fresh MCP process, bypasses the editor, and prints the result directly. Use it before restarting the editor connection.

## Smoke Metadata

Use per-operation `test:` metadata to opt an operation into smoke coverage and provide fixtures, discovery, or explicit write classification.

```yaml
operations:
  get_post:
    description: Get one post
    returns: post
    test:
      mode: read
      discover_from:
        op: list_posts
        params:
          limit: 3
        map:
          id: id

  create_post:
    description: Create one post
    returns: post
    test:
      mode: write
```

Supported fields:

- `test.mode: read | write`
- `test.fixtures: { ... }`
- `test.discover_from: <string | object | array>`
- `test.account: <name>` when a run-level account must be passed to `run()`

Fixture resolution order in `mcp:test`:

1. `test.fixtures`
2. YAML param `default`
3. shared smoke-safe defaults from the runner
4. declared `test.discover_from`

Use `test.mode: write` for:

- mutating operations
- destructive operations
- human-gated flows
- actions that would send messages, emails, follows, votes, registrations, or state changes during smoke testing

If an operation should not be part of default smoke, omit the `test:` block entirely.

Do not add a `tests/` folder by default. For normal validation, use `mcp:call` first.

## Helper Files

Keep skill YAML readable. When executor logic starts looking like real code, extract it into a helper file in the skill folder and have the operation call that file.

Keep in `readme.md` (markdown only — narrative, setup, examples):

- when to use the skill, limitations, and agent-facing notes
- short examples and troubleshooting

Keep in `skill.yaml`:

- `id`, `name`, `connections`, `adapters`, `operations`, executors, and all machine-readable wiring

Move into helper files:

- long AppleScript, Swift, Python, or shell logic
- anything with loops, branching, string escaping, or manual JSON construction
- anything large enough that syntax highlighting, direct local execution, or isolated debugging would help

Preferred patterns:

- use `Swift` helper files for Apple framework integrations like Contacts, EventKit, or other native macOS APIs
- use `Python` helper files for parsing, normalization, and API glue — prefer `python:` executor over `command:` + `binary: python3`
- use `bash` only for thin wrappers or simple pipelines
- keep `AppleScript` inline only when it is truly short; otherwise prefer a helper file

Leading by example:

- `skills/gmail/gmail.py` — `_call` dispatch: list stubs then hydrate via sibling operations
- `skills/goodreads/public_graph.py` — GraphQL discovery, Apollo cache extraction, multi-tier runtime config
- `skills/claude/claude-api.py` — API replay with session cookies and stealth headers
- `skills/austin-boulder-project/abp.py` — bundle config extraction and tenant-namespace auth
- `skills/reddit/comments_post.sh`
- `skills/hackernews/comments_post.sh`
- `skills/facebook/get_community.sh`
- `skills/apple-contacts/accounts.swift`
- `skills/apple-contacts/get_person.swift`

## Validation

Before committing:

- Run `npm run validate`
- Run direct MCP checks for the changed skill
- Run `npm run mcp:test -- <skill> --verbose`
- If you changed the authoring contract, update **this** `CONTRIBUTING.md` in the same change

What `validate` should catch:

- Schema shape and unknown keys (via `audit-skills.py` vs Rust `types.rs`)
- Basic structural problems
- Advisory duplicate adapter mappings (same jaq expression on multiple fields — shown as `⚠`, does not fail the audit)

## Checklist

Before you commit a skill:

- [ ] If the contract or validation rules changed, `CONTRIBUTING.md` is updated in the same PR
- [ ] Uses `adapters:`, not `transformers:`
- [ ] No `terminology:`
- [ ] No adapter `display:` blocks
- [ ] Uses canonical mapping fields where available; adapters have `# --- Canonical fields ---` / `# --- Skill-specific data ---` comment markers; no duplicate jaq expressions on sibling adapter keys without a reason (see audit advisory)
- [ ] Uses simple `snake_case` operation names
- [ ] No unnecessary `response.mapping` overrides
- [ ] Uses inline `returns:` schemas for non-entity or action-style tools
- [ ] Direct MCP preview/full output looks correct
- [ ] Read-safe ops are smoke-testable with `test.fixtures` and/or `test.discover_from`
- [ ] Mutating or human-gated ops declare `test.mode: write`
- [ ] Ops without a sensible default smoke check simply omit `test:`
- [ ] `npm run validate` passes
- [ ] `npm run mcp:test -- <skill> --verbose` passes
- [ ] Uses `connections:` for external service dependencies (not bare `auth:`)
- [ ] Multi-connection skill declares `connection:` on each operation
- [ ] REST URLs are relative when the connection has a `base_url`

## Advanced Stuff

This guide does not try to document every executor or every edge case.

If you need something advanced, copy an existing skill:

- `linear` for GraphQL with connections
- `youtube` for command execution
- `gmail` + `mimestream` for provider-sourced OAuth and `_call` dispatch
- `claude` + `brave-browser` for consumer/provider cookie patterns
- `goodreads` for multi-connection (graphql + web) and sandbox storage
- `granola` for multi-connection (API + cache) with Python connection dispatch
- `onepassword` (planned) for `__secrets__` secret import, adapter relationships, parallel subprocess batch import, and non-account entity mapping
- an existing cookie-provider skill for keychain, crypto, and multi-step extraction

For skills that reverse-engineer web services without public APIs (headless browser stealth, JS bundle extraction, GraphQL discovery, cookie-based auth), see `docs/reverse-engineering/`:

- `1-transport.md` — TLS fingerprinting, WAF bypass, Playwright stealth
- `2-discovery.md` — Next.js/Apollo caches, JS bundle config, GraphQL schema scanning
- `3-auth.md` — session cookies, Cognito, cache+discovery+fallback architecture
- `4-content.md` — pagination strategies, infinite scroll, content extraction
- `5-social.md` — social graph traversal, friend lists, activity feeds
- `6-desktop-apps.md` — Electron asar extraction, native app IPC, plist configs

If a pattern is rare enough that Exa-like skills do not need it, it does not belong in this doc.

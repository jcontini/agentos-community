# Contributing to AgentOS Community

This file is for **skill authoring**. It is intentionally narrow.

If you're editing `skills/*/readme.md`, start here. If you're working on apps, CSS, UI components, or unrelated repo infrastructure, this is the wrong doc.

In development, AgentOS reads skills directly from this repo. Skill YAML changes are picked up on the next skill call. If you changed Rust core in `~/dev/agentos`, restart the engine there before trusting live MCP results.

## Read This First

Current source of truth:

- `CONTRIBUTING.md` — the skill contract and workflow
- `skills/exa/readme.md` — canonical entity-returning example
- `skills/kitty/readme.md` — canonical local-control/action example
- `test-skills.cjs` — direct MCP smoke testing
- `docs/reverse-engineering/` — transport, discovery, and auth patterns for building skills against sites without public APIs

Only treat two skills as primary copy-from examples:

- `skills/exa/readme.md` for entity-returning skills
- `skills/kitty/readme.md` for local-control/action skills

You may inspect other skills for specialized auth or protocol details, but do not treat older mixed-pattern skills as the default scaffold.

## Workflow

Each tool in the workflow proves something different:

```bash
# 1. Edit the live skill definition
$EDITOR skills/my-skill/readme.md

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
    readme.md            # required — skill definition (YAML front matter + markdown docs)
    requirements.md      # recommended — scope out the API, auth model, and entities before writing YAML
    my_helper.py         # optional — Python helper when inline command logic gets complex
```

After the front matter, write normal markdown. That markdown body is the skill's instructions/docs for the agent.

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

Canonical fields for rendering:

- `name`
- `text`
- `url`
- `image`
- `author`
- `datePublished`

Rules:

- Put canonical fields directly in the adapter body
- Keep default mapping in `adapters.<entity>`
- Use `data.*` for adapter-specific extra fields
- Use `content` only for long body text that should be stored separately
- Map to an existing entity type whenever possible

Good:

```yaml
adapters:
  result:
    id: .url
    name: .title
    text: '.text // .summary'
    url: .url
    image: .image
    author: .author
    datePublished: .publishedDate
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

## Capabilities

An operation can declare `provides:` to make itself discoverable by capability name. This lets callers use `run({ capability: "email_lookup", params: { ... } })` without knowing which skill implements it.

```yaml
operations:
  resolve_email:
    provides: email_lookup
    returns: person[]
    params:
      email: { type: string, required: true }
    python:
      module: ./public_graph.py
      function: resolve_email
      args:
        email: .params.email
```

The runtime finds all operations with a matching `provides` value and routes to the first available provider. The caller never names a skill or tool.

Use `provides:` when an operation offers a generic capability that other skills or the agent might want to consume by name — email lookup, web search, phone lookup, etc.

Leading by example: `skills/goodreads/readme.md` (`provides: email_lookup` on `resolve_email`).

## Connections

Every skill declares its external service dependencies as named connections. Connections carry `base_url`, auth configuration, and metadata. Local skills (no external services) simply omit the `connections:` block.

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

Rules:

- `base_url` on a connection is used to resolve relative `rest.url` and `graphql.endpoint` values
- Single-connection skills auto-infer the connection — no `connection:` needed on each operation
- Multi-connection skills must declare `connection: <name>` on each operation
- Set `connection: none` on operations that should skip auth entirely
- Use `optional: true` if the skill works anonymously but improves with credentials
- Connections without any auth fields (just `base_url` and/or `description`) are valid — they serve as service declarations

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

Provider declaration:

```yaml
provides:
  - capability: google
    via: credential_get
    accounts_via: list_accounts
    account_param: account
```

Consumer skills don't name a specific provider — the runtime discovers installed providers automatically.

Example references:

- OAuth consumer: `skills/gmail/readme.md`
- OAuth provider: `skills/mimestream/readme.md`
- Cookie consumer: `skills/claude/readme.md`
- Cookie provider: `skills/brave-browser/readme.md`
- Multi-connection: `skills/goodreads/readme.md` (graphql + web)

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

Keep in `readme.md`:

- skill metadata, connections, adapters, params, returns, and short executor wiring
- short SQL queries and short jq transforms
- simple one-step commands where the logic is still obvious inline

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

What `validate` should catch:

- Required front matter
- Schema shape
- Basic structural problems

## Checklist

Before you commit a skill:

- [ ] Uses `adapters:`, not `transformers:`
- [ ] No `terminology:`
- [ ] No adapter `display:` blocks
- [ ] Uses canonical mapping fields where available
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
- an existing cookie-provider skill for keychain, crypto, and multi-step extraction

For skills that reverse-engineer web services without public APIs (headless browser stealth, JS bundle extraction, GraphQL discovery, cookie-based auth), see `docs/reverse-engineering/`:

- `1-transport.md` — TLS fingerprinting, WAF bypass, Playwright stealth
- `2-discovery.md` — Next.js/Apollo caches, JS bundle config, GraphQL schema scanning
- `3-auth.md` — session cookies, Cognito, cache+discovery+fallback architecture
- `4-content.md` — pagination strategies, infinite scroll, content extraction
- `5-social.md` — social graph traversal, friend lists, activity feeds
- `6-desktop-apps.md` — Electron asar extraction, native app IPC, plist configs

If a pattern is rare enough that Exa-like skills do not need it, it does not belong in this doc.

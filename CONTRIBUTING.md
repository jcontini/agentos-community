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

# 4. Filter large runs while cleaning up families of skills
npm run validate -- --filter browser

# 5. Ground-truth live MCP call through run({ skill, tool, params, account? })
npm run mcp:call -- \
  --skill exa \
  --tool search \
  --params '{"query":"rust ownership","limit":1}' \
  --format json \
  --detail full

# 6. Broader YAML-driven smoke test for a skill
npm run mcp:test -- exa --verbose
```

What each step means:

- `validate --pre-commit` checks fast structural validity only
- `validate` checks structure, entity refs, mapping sanity, and icons
- `mcp:call` proves the live runtime can load the skill and execute one real tool
- Pass `--account <name>` to `mcp:call` for multi-account skills that need an explicit account choice
- `mcp:test` is a broader smoke path, not a substitute for targeted inspection

Important runtime note:

- `agentos mcp` is a proxy to the engine daemon
- If you changed Rust core in `~/dev/agentos`, restart the engine before trusting `mcp:call`
- If Cursor MCP looks stale, use `npm run mcp:call` and `npm run mcp:test` as the ground-truth path while you restart the engine or reconnect the editor

## The Short Version

The current skill style is:

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
    readme.md
    icon.svg
```

After the front matter, write normal markdown. That markdown body is the skill's instructions/docs for the agent.

## Entity Skill Shape

Use this pattern for normal data-fetching or CRUD-ish skills.

```yaml
id: my-skill
name: My Skill
description: One-line description
icon: icon.svg
website: https://example.com
auth:
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
      url: https://api.example.com/search
      body:
        query: .params.query
        limit: '.params.limit // 10'
      response:
        root: /results
```

## Local Control Shape

Use this pattern for command-backed skills such as terminal, browser, OS, or app control.

```yaml
id: my-local-skill
name: My Local Skill
description: Control a local surface
icon: icon.svg
website: https://example.com
auth: none

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

## Action Operations

Use normal `operations:` with an inline `returns:` schema when one of these is true:

- The return value is not an entity
- The tool is an action, not a normal entity read/write
- The tool returns a custom inline schema

Rules:

- Operation names should still be `snake_case`
- Prefer direct, concrete verbs like `send_text`, `focus_tab`, `list_status`
- Test them through `mcp:call` early, because runtime mismatches are easier to miss than YAML mismatches

## Auth

Most skills only need one of these:

- `auth: none`
- header auth
- query auth
- body auth
- provider-sourced OAuth or cookies

Most common pattern:

```yaml
auth:
  header:
    x-api-key: .auth.key
  label: API Key
  help_url: https://example.com/api-keys
```

Useful rules:

- Use `optional: true` if the skill works anonymously but improves with credentials
- Use per-operation `auth: none` for public signup/setup actions inside an otherwise-authenticated skill
- Prefer provider auth when credentials come from another installed app or browser profile
- If multiple installed providers can satisfy the same auth need, the runtime surfaces the options and the agent should ask the user which provider to use
- For cookie auth, retry with `params.cookie_provider` set to the chosen provider id, or persist that choice in account params for repeat use
- `browser:` under `auth.cookies` is legacy compatibility only. Do not rely on it in new skills; prefer cookie provider skills instead
- Prefer `brave-browser` or `firefox` as the concrete cookie-provider examples. Treat `chrome` as a lower-level Chromium keychain/decryption helper unless the runtime and docs explicitly promote it to a provider.
- Today `provides:` is primarily an auth contract. Do not invent broader generic provider/consumer patterns in skill YAML unless the runtime and docs explicitly support them
- For command auth templating or advanced multi-step auth flows, copy an existing skill instead of inventing from scratch

Provider auth patterns:

- OAuth consumer:

```yaml
auth:
  oauth:
    service: google
    scopes:
      - https://mail.google.com/
```

- OAuth provider:

```yaml
provides:
  - service: google
    via: credential_get
    accounts_via: list_accounts
    account_param: account
```

- Cookie consumer:

```yaml
auth:
  cookies:
    domain: ".claude.ai"
    names: ["sessionKey"]
```

- Cookie provider:

```yaml
provides:
  - service: cookies
    via: cookie_get
    account_param: domain
```

Example references:

- OAuth consumer: `skills/gmail/readme.md`
- OAuth provider: `skills/mimestream/readme.md`
- Cookie consumer: `skills/claude/readme.md`
- Cookie provider: `skills/brave-browser/readme.md`, `skills/firefox/readme.md`
- Advanced keychain/crypto/steps: `skills/brave-browser/readme.md`, `skills/chrome/readme.md`

## Expressions

Use one expression style everywhere:

- `rest:`, `graphql:`, `command:`, and `auth:` all use jq/jaq-style expressions
- Resolved credentials are available under `.auth.*` such as `.auth.key` or `.auth.access_token`

Common jq/jaq patterns:

```yaml
url: '"https://api.example.com/items/" + .params.id'
query:
  q: .params.query
  limit: .params.limit // 10
body:
  title: .params.title
auth:
  header:
    Authorization: '"Bearer " + .auth.key'
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

Do not add a `tests/` folder by default. For normal validation, use `mcp:call` first.

## Validation

Before committing:

- Run `npm run validate`
- Run direct MCP checks for the changed skill
- Run `npm run mcp:test -- <skill> --verbose`

What `validate` should catch:

- Required front matter
- Schema shape
- Icon presence
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
- [ ] `npm run validate` passes
- [ ] `npm run mcp:test -- <skill> --verbose` passes

## Advanced Stuff

This guide does not try to document every executor or every edge case.

If you need something advanced, copy an existing skill:

- `linear` for GraphQL
- `youtube` for command execution
- `gmail` + `mimestream` for provider-sourced OAuth
- `claude` + `brave-browser` / `firefox` for cookie consumer/provider patterns
- `brave-browser` / `chrome` for keychain, crypto, and multi-step extraction

If a pattern is rare enough that Exa-like skills do not need it, it does not belong in this doc.

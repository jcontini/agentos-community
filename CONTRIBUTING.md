# Contributing to AgentOS Community

This file is for **skill authoring**. It is intentionally narrow.

If you're editing `skills/*/readme.md`, start here. If you're working on apps, CSS, UI components, or unrelated repo infrastructure, this is the wrong doc.

In development, AgentOS reads skills directly from this repo. Skill YAML changes are picked up on the next skill call. If you changed Rust core in `~/dev/agentos`, run `./restart.sh` there.

## Read This First

Current source of truth:

- `CONTRIBUTING.md` — the skill contract
- `skills/exa/readme.md` — best current example
- `~/dev/agentos/bin/audit-skills.py` — migration guardrail for stale patterns
- `test-skills.cjs` — direct MCP smoke testing

Useful example skills:

- `skills/exa/readme.md` — REST + canonical mapping + good preview/full output
- `skills/todoist/readme.md` — CRUD-ish operations and task-style entities
- `skills/linear/readme.md` — GraphQL
- `skills/youtube/readme.md` — command executor
- `skills/gmail/readme.md` — OAuth example
- `skills/reddit/readme.md` — cookie auth example
- `skills/chrome/readme.md` and `skills/brave-browser/readme.md` — advanced keychain/crypto/steps patterns only if you truly need them

## Workflow

```bash
# 1. Edit the live skill definition
$EDITOR skills/my-skill/readme.md

# 2. Validate schema + coverage
npm run validate

# 3. Directly inspect real MCP output
npm run mcp:call -- \
  --skill exa \
  --tool search \
  --params '{"query":"rust ownership","limit":1}' \
  --format json \
  --detail preview

# 4. Smoke-test the whole skill from its YAML
npm run mcp:test -- exa --verbose

# 5. If you changed Rust core in ~/dev/agentos
(cd ~/dev/agentos && ./restart.sh)
```

`./restart.sh` also nudges Cursor's MCP config. If Cursor still looks stale, manually toggle the `agentOS` MCP connection once.
If the editor MCP path is broken or lagging behind your changes, use `npm run mcp:call` and `npm run mcp:test` as the ground-truth validation path while you restart the engine or reconnect the editor.

## The Short Version

The current skill style is:

- Use `adapters:`, not `transformers:`
- Do not use `terminology:`
- Do not use adapter-level `display:` blocks
- Put canonical display fields directly in the adapter body
- Use simple `snake_case` tool names like `search` or `read_webpage`
- Do not use dotted names like `task.list` or `webpage.read`
- The adapter body is the mapping
- Do not add operation-level `response.mapping` unless the operation truly returns a different shape
- Use `utilities:` for custom actions or non-entity return shapes
- Validate output through the direct MCP path, not just by reading YAML

## Minimal Skill Shape

Every skill is a folder like:

```text
skills/
  my-skill/
    readme.md
    icon.svg
    tests/
```

The `readme.md` starts with YAML front matter:

```yaml
id: my-skill
name: My Skill
description: One-line description
icon: icon.svg
website: https://example.com
auth:
  header:
    Authorization: "Bearer {token}"
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
      limit: { type: integer }
    rest:
      method: POST
      url: https://api.example.com/search
      body:
        query: .params.query
        limit: '.params.limit // 10'
      response:
        root: /results
```

After the front matter, write normal markdown. That markdown body is the skill's instructions/docs for the agent.

## Adapters

Adapters map raw API responses into AgentOS entities. Define the shape once in `adapters:` and let operations reference it via `returns:`.

The adapter body itself is the mapping object.

Canonical fields for rendering:

- `name`
- `text`
- `url`
- `image`
- `author`
- `datePublished`

Rules:

- Put canonical fields directly in the adapter body
- Keep all default mapping in `adapters.<entity>`
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

Operations are the entity-returning skill tools.

Naming rules:

- Use `snake_case`
- Prefer short, obvious names
- Good: `search`, `read_webpage`, `list_tasks`, `get_task`, `create_task`
- Bad: `task.list`, `webpage.read`

Return rules:

- `returns: entity[]` for list/search results
- `returns: entity` for single entities
- If the result is not an entity shape, use `utilities:`

Limit rules:

- Do not hardcode hidden limits
- If a skill accepts `limit`, do not give it a misleading low default
- Pass caller-provided limits through to the API

## Utilities

Use `utilities:` when one of these is true:

- The return value is not an entity
- The tool is an action, not a normal entity read/write
- The tool returns a custom inline schema

Examples:

- `setup`
- `whoami`
- `signup`
- `add_blocker`

Utility names should also be `snake_case`.

## Auth

Most skills only need one of these:

- `auth: none`
- header auth
- query auth
- body auth

Most common pattern:

```yaml
auth:
  header:
    x-api-key: "{token}"
  label: API Key
  help_url: https://example.com/api-keys
```

Useful rules:

- Use `optional: true` if the skill works anonymously but improves with credentials
- Use per-operation `auth: none` for public signup/setup utilities inside an otherwise-authenticated skill
- For cookie auth, OAuth, command auth templating, or advanced multi-step auth flows, copy an existing skill instead of inventing from scratch

Example references:

- Cookie auth: `skills/reddit/readme.md`
- OAuth: `skills/gmail/readme.md`
- Advanced keychain/crypto/steps: `skills/chrome/readme.md`, `skills/brave-browser/readme.md`

## Expressions

You only need two expression styles:

- `rest:` and `graphql:` use jq/jaq-style expressions
- `command:` uses Handlebars-style templates

Common jq/jaq patterns:

```yaml
url: '"https://api.example.com/items/" + .params.id'
query:
  q: .params.query
  limit: '.params.limit | tostring'
body:
  title: .params.title
```

Common command patterns:

```yaml
command:
  binary: bash
  args:
    - "-l"
    - "-c"
    - "my-script --query '{{params.query}}'"
```

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

Use `tests/utils/mcp-client.ts` only when you want reusable Vitest coverage. For quick validation, use `mcp:call` first.

## Validation

Before committing:

- Run `npm run validate`
- Run direct MCP checks for the changed skill
- Run `npm run mcp:test -- <skill> --verbose`
- Run targeted tests if the skill already has them

What `validate` should catch:

- Required front matter
- Schema shape
- Icon presence
- Test coverage references
- Basic structural problems

## Checklist

Before you commit a skill:

- [ ] Uses `adapters:`, not `transformers:`
- [ ] No `terminology:`
- [ ] No adapter `display:` blocks
- [ ] Uses canonical mapping fields where available
- [ ] Uses simple `snake_case` operation names
- [ ] No unnecessary `response.mapping` overrides
- [ ] Uses `utilities:` for non-entity or action-style tools
- [ ] Direct MCP preview/full output looks correct
- [ ] `npm run validate` passes
- [ ] `npm run mcp:test -- <skill> --verbose` passes

## Advanced Stuff

This guide does not try to document every executor or every edge case.

If you need something advanced, copy an existing skill:

- `linear` for GraphQL
- `youtube` for command execution
- `gmail` for OAuth
- `reddit` for cookie auth
- `chrome` / `brave-browser` for keychain, crypto, and multi-step extraction

If a pattern is rare enough that Exa-like skills do not need it, it does not belong in this doc.

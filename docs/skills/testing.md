# Testing & Validation

## Direct MCP testing

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

## Smoke metadata

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

## Validation

Before committing:

- Run `npm run validate`
- Run direct MCP checks for the changed skill
- Run `npm run mcp:test -- <skill> --verbose`
- If you changed the authoring contract, update the book in the same change

What `validate` should catch:

- Schema shape and unknown keys (via `audit-skills.py` vs Rust `types.rs`)
- Basic structural problems
- Advisory duplicate adapter mappings (same jaq expression on multiple fields — shown as `⚠`, does not fail the audit)

## Checklist

Before you commit a skill:

- [ ] `npm run validate` passes
- [ ] `npm run mcp:test -- <skill> --verbose` passes
- [ ] Direct MCP preview/full output looks correct
- [ ] Adapters use canonical mapping fields with `# --- Canonical fields ---` / `# --- Skill-specific data ---` markers
- [ ] Uses inline `returns:` schemas for non-entity or action-style tools
- [ ] Read-safe ops are smoke-testable with `test.fixtures` and/or `test.discover_from`
- [ ] Mutating or human-gated ops declare `test.mode: write`
- [ ] Multi-connection skill declares `connection:` on each operation
- [ ] REST URLs are relative when the connection has a `base_url`
- [ ] If the contract changed, the book is updated in the same PR

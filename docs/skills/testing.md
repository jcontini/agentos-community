# Testing & Validation

## Shape validation: `agentos test`

The primary tool for validating that skill output matches declared shapes. Run it after any skill change.

```bash
agentos test hackernews                    # test all operations
agentos test amazon --op search_products   # test one operation
```

This loads `skill.yaml` and `shapes/*.yaml` from disk, executes each testable operation, and validates the output field-by-field against the shape. No running engine needed.

```
  hackernews
  ──────────
  list_posts (post[])
    ✓ 20 records returned (485ms)
    ✓ author — 20/20 valid
    ✓ datePublished — 20/20 valid
    ✓ name — 20/20 valid
    ✓ url — 20/20 valid
    ⚠ 3 extra fields not in shape: account, engagement, skill
  search_posts (post[]) — skipped (required params missing from test.params)

  4 operations · 1 tested · 3 skipped
```

### Test configuration

Add a `test:` block to operations in `skill.yaml` to provide test params or skip dangerous operations:

```yaml
operations:
  search_products:
    returns: product[]
    test:
      params:                    # input params for test execution
        query: "usb c cable"

  create_order:
    returns: order
    test:
      skip: true                 # has side effects — don't auto-run
```

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `params` | object | `{}` | Params passed to the operation during test |
| `skip` | boolean | `false` | Skip this operation in automated test runs |

**When operations are skipped:**
- `skip: true` — explicitly opted out
- Required params have no defaults and no `test.params`
- `returns` is `void` or an inline schema (not a shape reference)
- The shape referenced in `returns` doesn't exist in the registry

**When operations run:**
- Operations with no params run automatically
- Operations with all-optional params (or params with defaults) run automatically
- Operations with `test.params` covering required params run with those params

## Direct MCP testing

For inspecting the full MCP response (including rendering, entity extraction, and metadata), use direct MCP calls:

### Skill-level testing (community repo)

`mcp:call` and `mcp:test` automatically use the newest built `agentos` binary. Set `AGENTOS_BINARY=/path/to/agentos` if you need to force a specific one.

```bash
# JSON preview
npm run mcp:call -- \
  --skill exa --tool search \
  --params '{"query":"rust ownership","limit":1}' \
  --format json --detail preview

# JSON full
npm run mcp:call -- \
  --skill exa --tool search \
  --params '{"query":"rust ownership","limit":1}' \
  --format json --detail full

# Markdown full (raw MCP response)
npm run mcp:call -- \
  --skill exa --tool search \
  --params '{"query":"rust ownership","limit":1}' \
  --detail full --raw
```

### Engine-level testing (core repo)

The core repo has a generic MCP test harness at `~/dev/agentos/scripts/mcp-test.mjs` that speaks raw JSON-RPC to the engine binary:

```bash
cd ~/dev/agentos

# List all MCP tools (built-in + dynamic)
node scripts/mcp-test.mjs stdio "./target/release/agentos mcp"

# Call a dynamic capability tool
node scripts/mcp-test.mjs stdio "./target/release/agentos mcp" call web_search '{"query":"rust"}'
```

Use this when you're changing `provides:` entries, engine routing, or tool schemas.

### Quick smoke test: `agentos call`

Native Rust MCP client built into the binary — fastest path for one-off checks:

```bash
agentos call boot                                    # verify engine is alive
agentos call run '{"skill":"exa","tool":"search","params":{"query":"test"}}'
```

## Validation

Before committing a skill:

```bash
npm run validate                           # schema + structural checks
agentos test <skill>                       # shape validation
npm run mcp:call -- --skill <skill> ...    # inspect full MCP output
```

What `validate` catches:
- Schema shape and unknown keys (via `audit-skills.py` vs Rust `types.rs`)
- Basic structural problems
- Advisory duplicate adapter mappings

What `agentos test` catches:
- Field type mismatches (value doesn't match declared shape type)
- Extra fields returned but not declared in the shape
- Missing shape fields (info only — fields are optional)
- Relation target validation (nested records checked recursively)

## Checklist

Before you commit a skill:

- [ ] `npm run validate` passes
- [ ] `agentos test <skill>` passes (no field errors)
- [ ] Direct MCP preview/full output looks correct
- [ ] Uses inline `returns:` schemas for non-entity or action-style tools
- [ ] Read-safe ops have `test.params` for automated testing
- [ ] Mutating ops declare `test.skip: true`
- [ ] Multi-connection skill declares `connection:` on each operation
- [ ] REST URLs are relative when the connection has a `base_url`
- [ ] If the contract changed, the book is updated in the same PR

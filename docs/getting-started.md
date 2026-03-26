# Setup & Workflow

## Source of truth

- **This book** — the skill contract and all authoring guidance
- `skills/exa/skill.yaml` + `skills/exa/readme.md` — canonical entity-returning example
- `skills/kitty/skill.yaml` + `skills/kitty/readme.md` — canonical local-control/action example
- `~/dev/agentos/bin/audit-skills.py` — unknown-key and structural checks against Rust `types.rs` (run via `npm run validate`); duplicate adapter-mapping expressions emit non-blocking `⚠` advisories
- `~/dev/agentos/spec/skill-manifest.target.yaml` — narrative target shape (`provides`, connections, operations); `ProvidesEntry` / auth in `~/dev/agentos/crates/core/src/skills/types.rs`
- `agentos test <skill>` — shape validation (validates operation output against declared shapes)
- `test-skills.cjs` — direct MCP smoke testing (`mcp:call`)
- `~/dev/agentos/scripts/mcp-test.mjs` — engine-level MCP test harness (raw JSON-RPC, verifies dynamic tools from `provides:`)

Only treat two skills as primary copy-from examples:

- `skills/exa/` for entity-returning skills
- `skills/kitty/` for local-control/action skills

You may inspect other skills for specialized auth or protocol details, but do not treat older mixed-pattern skills as the default scaffold.

## Setup

```bash
git clone https://github.com/jcontini/agentos-community
cd agentos-community
npm install    # sets up pre-commit hooks
```

In development, AgentOS reads skills directly from this repo. Skill YAML changes are picked up on the next skill call. If you changed Rust core in `~/dev/agentos`, restart the engine there before trusting live MCP results.

## Workflow

Each tool in the workflow proves something different:

```bash
# 1. Edit the live skill definition (manifest is skill.yaml; readme is markdown only)
$EDITOR skills/my-skill/skill.yaml

# 2. Fast structural gate for hooks / local iteration
npm run validate --pre-commit -- my-skill

# 3. Full structural + mapping check
npm run validate -- my-skill

# 4. Semantic lint for request-template consistency
npm run lint:semantic -- my-skill

# 5. Shape validation — does output match declared shapes?
agentos test my-skill

# 6. Ground-truth live MCP call through run({ skill, tool, params, account?, remember? })
npm run mcp:call -- \
  --skill exa \
  --tool search \
  --params '{"query":"rust ownership","limit":1}' \
  --format json \
  --detail full
```

What each step means:

- `validate --pre-commit` checks fast structural validity only
- `validate` checks structure, entity refs, and mapping sanity
- `lint:semantic` is an advisory semantic pass for auth patterns, `base_url` consistency, request roots, returns/adapters drift, executor types, and endpoint consistency
- Pass `--strict` to `lint:semantic` if you want it to fail on semantic errors
- The pre-push hook runs `lint:semantic --strict` on changed top-level skills, so the main skill set is expected to stay semantically clean
- `agentos test` validates that every operation's output matches its declared shape — field types, extra fields, missing fields, relations. See [Testing](skills/testing.md) for details
- `mcp:call` proves the live runtime can load the skill and execute one real tool
- Pass `--account <name>` to `mcp:call` for multi-account skills that need an explicit account choice

## Keeping the book in sync

Whenever you change something that affects **how authors write skills** — new or removed YAML fields, connection/auth models, adapter conventions, operation keys, or rules enforced by `audit-skills.py` / `lint:semantic` — **update this book in the same change** (same PR / paired commit across `agentos` and `agentos-community` if both repos move). The book is the human-readable contract next to the machine checks; letting it drift wastes the next author's time.

Before you push skill-contract work, sanity-check that examples still parse and that stale patterns are not left in place.

## Python over Rust

Prefer Python scripts for skill logic. When an API has quirks (list returns stubs only, batch fetching, custom parsing), solve it in a `*.py` helper like Granola does — not by modifying agentOS core. Rust changes are costly to iterate; Python lives in the skill folder and ships with the skill. We'll revisit what belongs in core later; for now, keep skill-specific behavior in skills.

When Python needs to call authenticated APIs, use `_call` dispatch (see [Python Skills](skills/python.md)) instead of handling credentials directly. The engine mediates all authenticated calls through sibling operations with full credential injection. Python scripts never see raw tokens.

When Python needs to make HTTP requests directly (scraping, APIs without a REST executor, WAF-sensitive endpoints), use **httpx** with HTTP/2 enabled — not `urllib.request`, not `requests`. httpx handles HTTP/2, connection pooling, and presents a modern TLS fingerprint that avoids CDN bot detection. Install with `pip install "httpx[http2]"` and use `httpx.Client(http2=True)` for session reuse.

## Runtime note

- `agentos mcp` is a proxy to the engine daemon
- If you changed Rust core in `~/dev/agentos`, restart the engine before trusting `mcp:call`
- If Cursor MCP looks stale, use `agentos test` and `npm run mcp:call` as the ground-truth path while you restart the engine or reconnect the editor

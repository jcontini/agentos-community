---
name: reverse-engineering
description: Systematically analyze and document how software systems work internally. Use when you need to understand closed-source systems, third-party integrations, or undocumented APIs.
---

# Reverse Engineering Skill

**Load this skill before doing ANY reverse engineering work.** Read the principles below
and the linked docs before writing code. Every violation of these principles costs hours.

## Golden Principles

### 1. Replay, don't reconstruct

**Never build API request payloads yourself.** Capture a working request from the browser
and replay its exact structure. If the browser sends 15 fields, send 15 fields. Don't
"simplify" to the 6 you think matter — you will get it wrong.

**Bad:** Look at the API shape, build a dict with the fields you understand.
**Good:** Capture a working browser request, use it as the template, swap in your data.

This is the #1 cause of subtle bugs. The request "works" (200 OK) but the server
stores degraded data because you sent wrong section UUIDs, missing `sellingOption`,
or fields at the wrong nesting level.

### 2. Trace data provenance, not just shape

When documenting a write endpoint, don't just capture the request body shape. Trace
WHERE each field's value comes from. Which read endpoint provided it? Which field in
that response? Document the data flow:

```
getStoreV1.catalogSectionsMap[].payload.standardItemsPayload.catalogItems[].uuid
  → addItemsToDraftOrderV2.items[].uuid

getStoreV1...catalogItems[].sectionUUID
  → addItemsToDraftOrderV2.items[].sectionUuid
```

If you can't trace a field's provenance, you don't understand the API yet.

### 3. No silent fallbacks on writes

**Never use `or` fallbacks for write operation fields.** If a required field is missing,
fail loudly — don't try an alternative source. Silent fallbacks are the #1 cause of
"it works but the data is wrong" bugs.

```python
# DEADLY — falls back silently to wrong value, API accepts it, items show as unavailable
"sectionUuid": raw.get("sectionUUID") or product.get("_parent_section_uuid", ""),

# CORRECT — fail immediately, error message shows available keys so you spot the casing bug
section = raw.get("sectionUuid")
if not section:
    raise RuntimeError(f"Missing sectionUuid — keys: {list(raw.keys())}")
```

The `or` pattern is fine for display/read operations (show something reasonable). It's
poison for writes (send wrong data that the API silently accepts).

### 4. Compare, don't assume

After making an API call, compare your result against browser-created state
**field by field**. Don't just check "did it return 200" or "are there items in the cart."
Check: do the items have images? Prices? Correct section UUIDs? Can the browser
render them normally?

**The grayed-out-images test:** If the browser shows your data differently than
browser-created data (wrong images, missing prices, broken links), your request
was subtly wrong even though the API accepted it.

### 4. Preserve raw data alongside clean shapes

When extracting data from an API (e.g., building a product catalog from `getStoreV1`),
keep the raw API response data available. Don't lossy-extract into your own shape and
throw away the original. Your clean shape is for display; the raw data is for
downstream operations that need the exact fields the API expects back.

### 5. CDP discovers, engine runs

Use CDP (Chrome DevTools Protocol) to Brave for discovery — capture network traffic,
hook XHR/fetch, inspect DOM, find endpoints. Then implement what you learned as
Python + `agentos.http` in the skill. No browser dependency at runtime.

**Tools:**
- `bin/browse-capture.py` — CDP network capture with response bodies
- `websocket` module for direct CDP control (NOT `websockets` — different package)
- `Runtime.evaluate` with `fetch()` for testing endpoints through the browser
- Hook both `fetch` AND `XMLHttpRequest` — some sites use one, some the other

### 6. Always use `http.headers()` for cookie-auth

The engine sets zero default headers. Cookie-auth requests without browser headers
(UA, sec-ch-*) get rejected by strict endpoints. Always use:
```python
http.post(url, cookies=cookies, json=body,
          **http.headers(waf="cf", accept="json", extra={"x-csrf-token": "x"}))
```

The engine also auto-injects browser defaults when cookies are present but no UA
is set — but don't rely on it. Be explicit.

## Primary Reference

Full methodology in the community repo:

```
~/dev/agentos-community/docs/reverse-engineering/
├── overview.md              # Layer model, core principles
├── 1-transport/index.md     # TLS, headers, WAF bypass, http.headers() rules
├── 2-discovery/index.md     # JS bundle scanning, GraphQL schema, Apollo cache
├── 3-auth/index.md          # Credentials, login flows, cookies, CSRF
├── 4-content/index.md       # HTML scraping, lxml + cssselect, AJAX endpoints
├── 5-social/index.md        # Social graph modeling
├── 6-desktop-apps/index.md  # Electron, native apps
└── 7-mcp/index.md           # Wrapping existing MCP servers
```

Skill authoring docs:

```
~/dev/agentos-community/docs/skills/
├── anatomy.md        # Skill folder structure, YAML shape
├── connections.md    # Auth types, cookie format, provider selection
├── python.md         # Python executor, _call dispatch
├── operations.md     # Operation naming, capabilities
├── sdk.md            # http module, headers(), sessions, cookie jar
├── shapes.md         # Shape design principles, validation
└── testing.md        # Test patterns
```

**Read these before starting.** Especially `sdk.md` for HTTP patterns and
`connections.md` for auth.

## Quick Reference: The Layers

| Layer | What it covers | When you need it |
|-------|---------------|-----------------|
| 1. Transport | TLS fingerprinting, WAF bypass, `http.headers()` | Service blocks automated requests |
| 2. Discovery | JS bundle scanning, CDP network capture, API endpoint inventory | Finding endpoints and data shapes |
| 3. Auth & Runtime | Cookie resolution, `SESSION_EXPIRED:` retry, provider selection | Managing session state |
| 4. Content | lxml + cssselect, data-testid selectors, AJAX endpoints | Extracting data from HTML |
| 5. Social Networks | Social graph traversal, friend lists, activity feeds | Working with social platforms |
| 6. Desktop Apps | Electron asar, native app IPC, SQLite databases | Local apps without web APIs |
| 7. MCP Servers | Wrapping existing MCP servers as skills | Someone already built an MCP server |

## Key Patterns

### Transport

- **All HTTP through `agentos.http`** — never `requests`, `httpx`, `urllib` directly
- **`http.headers(waf="cf", accept="json")`** — always, for every cookie-auth request
- **Engine uses wreq + BoringSSL** — Chrome 145 TLS fingerprint, auto-injected when cookies present
- **Cookie stripping** — `skip_cookies=["csd-key"]` to bypass client-side encryption (Amazon)
- **Vercel: `waf="vercel"`** — sets `http2=False` (Vercel blocks HTTP/2)

### Content

- **`lxml` with `cssselect`** — not BeautifulSoup, not regex on HTML
- **CSS selectors over XPath** — except when you need text content matching
- **`SESSION_EXPIRED:` prefix** — raise this so engine retries with different cookie provider
- **`data-testid` attributes** — stable selectors, less likely to change than classes

### Auth

- Providers: **Brave** (SQLite), **Firefox** (SQLite) — Playwright is deprecated
- Selection: timestamp-based, freshest cookies win
- **Cookies are encrypted in Brave's DB** — use CDP `Network.getCookies` or the engine, never read SQLite directly
- **`SESSION_EXPIRED:` retry** — engine excludes failing provider, retries once

### Write Operations — The Danger Zone

- **Capture a working browser request before implementing.** Hook both XHR and fetch.
- **Compare browser-created vs API-created state field-by-field.** Check images, prices, all metadata.
- **Preserve the raw catalog/source data** so write operations can pass it through verbatim.
- **Trace every field's provenance** — where did the value come from? Which read endpoint?
- **Don't strip fields you don't understand** — they might be required for the write to work correctly.

## Workflow

1. **Read docs** — load this skill, read the RE overview and relevant layer docs
2. **Discover** — CDP to Brave: `browse-capture.py`, XHR/fetch hooks, `Runtime.evaluate`
3. **Capture** — document endpoint shapes AND data provenance in `requirements.md`
4. **Replay** — reproduce with `agentos.http` through the engine. Compare field-by-field against browser.
5. **Implement** — Python skill operation. Raw data preserved for downstream write ops.
6. **Verify** — test through MCP (`agentos call run`). Check browser renders your data normally.

## Lessons Learned (from real bugs)

| Bug | Root cause | Principle violated |
|-----|-----------|-------------------|
| Uber Eats receipt endpoint returned 500 | No User-Agent header on cookie-auth request | #6 — always use `http.headers()` |
| Cart items showed grayed-out images | Wrong `sectionUuid`/`subsectionUuid`, missing `sellingOption` | #1 — reconstructed instead of replaying |
| Name matching bananas→yogurt | Tried fuzzy matching instead of using catalog UUIDs | #2 — didn't trace data provenance |
| `addItemsToDraftOrderV2` returned 400 "empty items" | Built item shape ourselves instead of using browser's format | #1 — reconstructed instead of replaying |

## Reference Skills

| Skill | Key learnings |
|-------|--------------|
| `skills/uber/` | RPC API (not GraphQL), XHR for writes, `createDraftOrderV2` with items inline, CDP discovery |
| `skills/amazon/` | Client hints, Siege bypass, fallback selectors, `SESSION_EXPIRED` |
| `skills/goodreads/` | Apollo cache, GraphQL schema discovery, multi-connection |
| `skills/claude/` | Cloudflare stealth, cookie-based API replay |

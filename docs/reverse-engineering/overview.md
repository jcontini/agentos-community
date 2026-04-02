# Reverse Engineering

How to build skills against web services that don't have public APIs. This is the methodology for extracting data surfaces, auth flows, and content from any website — then packaging them as reliable AgentOS skills.

## The layers

Each layer builds on the previous. Start at transport, work up.

| Layer | What it covers | When you need it |
|-------|---------------|-----------------|
| [1. Transport](1-transport/index.md) | TLS fingerprinting, WAF bypass, Playwright stealth, HTTP/2 | Service blocks automated requests |
| [2. Discovery](2-discovery/index.md) | Next.js/Apollo caches, JS bundle config, GraphQL schema scanning | Finding API endpoints and data shapes |
| [3. Auth & Runtime](3-auth/index.md) | Credential bootstrap, login/signup flows, CSRF, cookies, API key management, network interception | Logging in and managing session state |
| [4. Content](4-content/index.md) | Pagination, infinite scroll, content extraction | Scraping actual data from pages |
| [5. Social Networks](5-social/index.md) | Social graph traversal, friend lists, activity feeds | Working with social platforms |
| [6. Desktop Apps](6-desktop-apps/index.md) | Electron asar extraction, native app IPC, plist configs | Local apps without web APIs |
| [7. MCP Servers](7-mcp/index.md) | Wrapping existing MCP servers as skills | When someone already built an MCP server |

## Core principle

**CDP discovers, `agentos.http` runs.**

Use **`browse capture`** (CDP to a real browser) to investigate — navigate pages, capture every network request with full headers and response bodies, inspect cookies. Then implement what you learned as Python + `agentos.http` in the skill. No browser at runtime.

**Why CDP to real browsers, not Playwright?** Playwright's bundled Chromium has a detectable TLS fingerprint (JA3/JA4) that anti-bot systems flag. CDP to the user's real Brave/Chrome produces authentic TLS fingerprints, real GPU canvas rendering, and uses existing sessions. Sites like Amazon reject Playwright but accept real browsers. See [Transport](1-transport/index.md#headless-browser-stealth) for the full analysis.

Headers are built in Python via `http.headers()` with independent knobs (`waf=`, `accept=`, `mode=`, `extra=`). The Rust engine is pure transport — it sets zero default headers.

The progression:

1. **Search** — check `web_search` for prior art, existing docs, API references.
2. **Discover** — use `browse capture` to probe the live site via CDP. Launch Brave with `--remote-debugging-port=9222 --remote-allow-origins="*"`, then `python3 bin/browse-capture.py <url> --port 9222`. Captures all requests, responses, headers, cookies, and API response bodies automatically.
3. **Extract API surface** — grep the site's JS bundles for endpoint patterns (e.g. `grep -oE 'get[A-Z][a-zA-Z]+V[0-9]+' bundle.js`). This reveals the full API surface without navigating every page.
4. **Replay** — reproduce what you found with `agentos.http` + cookies. Use `http.headers()` for WAF bypass. Test with `agentos browse request <skill> <url>`.
5. **Implement** — write the skill operation in Python with `agentos.http`. No browser dependency at runtime.
6. **Test** — `agentos test-skill <skill>` validates against shapes and expectations.

### Browse toolkit commands

| Command | What it does |
|---------|-------------|
| `agentos browse request <skill> <url>` | Make an authenticated HTTP request (same TLS fingerprint as engine), show full headers, cookies, response |
| `agentos browse cookies <skill>` | Cookie inventory — all cookies from all sources with timestamps and provenance |
| `agentos browse auth <skill>` | Auth resolution trace — which provider won, identity, timing |
| `python3 bin/browse-capture.py <url> --port 9222` | CDP network capture — navigate Brave to a URL, capture every request/response with full headers and bodies |

See [Browse Toolkit spec](../../docs/specs/browse-toolkit.md) for details.

See [Auth & Runtime](3-auth/index.md) for the full methodology, including:
- **Credential Bootstrap Lifecycle** — the five-phase pattern from entry through API key storage
- **Network Interception** — three layers: `capture_network` for page-load, fetch interceptors for user interactions, DOM inspection for native form POSTs
- **Cookie Mechanics** — SameSite, HttpOnly, cross-domain behavior, extraction methods
- **CSRF Patterns** — double-submit cookies, synchronizer tokens, NextAuth CSRF
- **Web Navigation** — redirect chains, interstitials, signup vs login, API key management flows
- **Playwright Gotchas** — `type` vs `fill` for React forms, honeypot fields, and when HTTPX replay fails
- **Vendor guides** — [NextAuth.js](3-auth/nextauth.md), [WorkOS](3-auth/workos.md)

## Write operations — replay, don't reconstruct

Write operations (creating orders, adding to carts, submitting forms) are where most RE bugs hide.
The API accepts your request (200 OK) but stores degraded data because your payload was subtly wrong.

### Principles

**1. Replay, don't reconstruct.** Capture a working browser request and replay its exact structure.
If the browser sends 15 fields on a cart item, send 15 fields. Don't "simplify" to the 6 you think
matter. The 9 you dropped might include section UUIDs, selling options, or measurement types that
the server needs to properly resolve the item.

**2. Trace data provenance.** For every field in a write request, document which read endpoint
provided the value. Don't just document the shape — document the data flow:
```
getStoreV1.catalogSectionsMap[secKey][i].catalogSectionUUID
  → addItemsToDraftOrderV2.items[].sectionUuid

getStoreV1...catalogItems[].sectionUUID
  → addItemsToDraftOrderV2.items[].sectionUuid (different! item-level, not parent)
```

**3. Compare field-by-field.** After making a write call, compare your result against browser-created
state. Don't just check "200 OK" or "items exist." Check: do items have images? Prices? Can the
browser render them normally? Grayed-out images or "Nothing to eat here" means your data was
accepted but degraded.

**4. Preserve raw data.** When extracting from a read endpoint, keep the original response data
alongside your clean shape. Your clean shape is for display; the raw data is for downstream write
operations that need the exact fields the API expects back. Don't lossy-extract into your own
shape and throw away the original.

**5. Hook BOTH fetch AND XHR.** Some sites use `fetch()` for reads but `XMLHttpRequest` for writes
(Uber Eats does this). If you only hook one, you'll miss the write calls entirely.

**6. No silent fallbacks on writes.** Never use `raw.get("X") or alternative_source` for fields
in write operations. If the field is missing, fail loudly — the error message will reveal the
actual bug (wrong casing, wrong nesting, missing data). The `or` pattern is fine for display
but poison for writes: the API silently accepts wrong data and you don't find out until the
UI shows "unavailable" or grayed-out images.

### Real example: Uber Eats cart bug

We captured `addItemsToDraftOrderV2` and built item payloads ourselves. The API returned 200,
items appeared in the cart with correct names and prices. But images were grayed out and clicking
items showed "Nothing to eat here." Root cause: we used the wrong `sectionUuid` and `subsectionUuid`
(same UUID for all items instead of per-item values from the catalog), and omitted `sellingOption`.
The server accepted the items but couldn't resolve them against the catalog properly.

Fix: pass through the raw catalog item data from `getStoreV1` instead of reconstructing it.

## Starting a new reverse-engineered skill

```bash
npm run new-skill -- my-service

# Then start investigating:
# 1. Open the service in Playwright
# 2. capture_network to find API endpoints
# 3. inspect to understand page structure
# 4. Document what you find in requirements.md
# 5. Implement with httpx in Python
```

For detailed examples, see each layer's documentation. Real-world reference implementations:

| Skill | What it demonstrates |
|-------|---------------------|
| `skills/uber/` | **Two completely different APIs on one platform** — rides use GraphQL (`riders.uber.com/graphql`), Eats uses RPC (`ubereats.com/_p/api/`). CDP `browse capture` for API discovery, JS bundle grepping for full endpoint surface (32 endpoints extracted), receipt HTML parsing with `data-testid` selectors, real-time event channels (SSE), separate cookie domains. Reference for CDP-based discovery and RPC API reverse engineering. |
| `skills/amazon/` | Deep anti-bot bypass (client hints, Siege encryption, session warming), session staleness (30-min TTL, CDP session warming), fallback CSS selector chains for resilient HTML parsing, AJAX endpoints for dynamic content, `SESSION_EXPIRED` provider retry convention, tiered cookie architecture. Full reference for [1-transport](1-transport/index.md) and [4-content](4-content/index.md). |
| `skills/exa/` | Full credential bootstrap: NextAuth email code → Playwright form submit → session cookies → API key extraction from dashboard API. Reference for [nextauth.md](3-auth/nextauth.md) |
| `skills/goodreads/` | Multi-tier discovery, Apollo cache extraction, auth boundary mapping, runtime config fallback |
| `skills/claude/` | Cookie-based auth, Cloudflare stealth settings, API replay from browser session |
| `skills/austin-boulder-project/` | JS bundle config extraction, tenant-namespace auth |

# Playwright

**Playwright is a discovery and investigation tool.** Use it to reverse-engineer web flows — figure out redirect chains, find API endpoints, capture cookies, understand page structure. Then implement what you learned with HTTPX in Python for production skill code.

Playwright controls a persistent Chromium session via CDP (Chrome DevTools Protocol). The browser stays running between calls — cookies, sessions, and tabs persist. Each operation connects (~100ms), does one thing, and returns.

## Anti-Detection

Both the persistent browser and the ephemeral runner (`run_flow`) launch with stealth settings applied automatically:

- `--disable-blink-features=AutomationControlled` — removes the `navigator.webdriver=true` flag
- `navigator.webdriver` override via init script (belt-and-suspenders)
- Realistic user-agent (Chrome 131, not `HeadlessChrome`)
- Locale (`en-US`) and timezone (`America/New_York`) to avoid mismatch fingerprinting

These cover the most common detection vectors. For sites with strict bot management (Cloudflare Bot Management, DataDome) that detect CDP-level signals like `Runtime.Enable`, use [`rebrowser-playwright`](https://github.com/rebrowser/rebrowser-patches) as a drop-in replacement. See `docs/reverse-engineering/1-transport/` for the full breakdown of detection layers.

## Do You Need This Skill?

**Most web tasks do NOT need Playwright.** Before using this skill, check:

- **"I need to read a web page"** → Use `webpage.read` (backed by Exa or another provider). Faster, cheaper.
- **"I need to search the web"** → Use `webpage.search`. Playwright is not a search engine.
- **"I already know the endpoint"** → Use HTTPX in Python or shell `curl`. Once the browser has taught you the contract, leave it behind.
- **"I need to check what sites were visited"** → Use an integration that reads local browser history (e.g. Brave), not Playwright.

**Use Playwright when you need to INVESTIGATE in a browser:**

- Reverse-engineer a login flow — watch the redirect chain, find the cookies
- Discover API endpoints — `capture_network` reveals the real backend calls
- Inspect SPAs — `evaluate` to dump `__NEXT_DATA__`, Apollo caches, framework state
- Test auth flows — `run_flow` for scripted step sequences
- Take screenshots for visual verification

**The rule:** Playwright is for learning. HTTPX is for doing. Every skill operation that runs in production should use `httpx` with HTTP/2, not Playwright. See `docs/reverse-engineering/` for the full methodology.

## The progression

1. **Search** — check `webpage.search` for prior art, existing docs, API references.
2. **Discover** — use Playwright to probe the live site: `inspect`, `capture_network`, `evaluate`.
3. **Replay** — reproduce what you found with HTTPX + cookies. Verify it works.
4. **Implement** — write the skill operation in Python with HTTPX. No browser dependency.
5. **Test** — `test-skills.cjs` runs without a browser. If your skill needs Playwright at runtime, reconsider.

## How It Works

Playwright controls Chromium via the Chrome DevTools Protocol (CDP). The browser launches once and **persists** — cookies, sessions, tabs all survive between operations. Each operation connects to the running browser (~100ms), does one thing, and returns. The agent can talk to the user between operations.

```
start → launches Chromium with --remote-debugging-port=9222
        ↓
goto/click/fill/screenshot → connects via CDP, acts, returns (~100ms connect)
        ↓
browser stays alive — sessions, cookies, tabs persist
        ↓
stop → kills the browser process (only when done)
```

## Agent Usage Tips

**Don't use `wait` between operations.** The round-trip latency between agent tool calls (model thinking + MCP overhead) is typically 1-3 seconds — more than enough for pages to settle. Explicit waits are almost never needed. If a page hasn't loaded, just call `screenshot` or `inspect` again rather than inserting `wait` calls. Only use `wait` if you have strong reason to believe async content needs extra time (e.g. a slow API response you're waiting to capture).

**Prefer `inspect` over `screenshot` for understanding pages.** `inspect` returns structured DOM data instantly; `screenshot` is slow and produces large images. Use `screenshot` only when pixels matter or the user explicitly wants visual verification.

## Recommended Workflow

When using Playwright for reverse engineering, prefer this order:

1. `status` or `tabs` to see whether a useful browser session already exists.
2. `goto` to load the target page, or `new_tab` if you want to preserve the current page.
3. `inspect` before `screenshot` to understand the DOM cheaply.
4. `read_webpage` for targeted extraction of a container, script tag, or hidden data block.
5. `evaluate` when the page is framework-heavy and the interesting data is already in JS memory.
6. `capture_network` when you need the real XHR/fetch/GraphQL endpoints.
7. `cookies` only after a login flow that happened in the Playwright browser itself.

Use `screenshot` only when pixels matter or the user explicitly wants visual verification.
Once you have the real endpoint, switch away from Playwright and implement or test the replay with direct HTTP.

## Reverse Engineering Patterns

Playwright is the primary discovery tool for reverse engineering web services. Use it to find the data surfaces, then switch to direct HTTP replay for production skill operations.

For the full methodology — Next.js/Apollo extraction, GraphQL schema discovery, JS bundle scanning, auth boundary mapping — see `docs/reverse-engineering/` (especially `2-discovery.md` and `3-auth.md`). The patterns below are Playwright-specific workflows.

### Pattern: DOM Is Sparse But The Page Is Rich

If `inspect` shows a shallow or placeholder-heavy DOM but the page clearly has rich data, the app is hydrating from framework state. Try these before scraping visible HTML:

- `read_webpage { selector: "script#__NEXT_DATA__", format: "text" }`
- `evaluate { script: "JSON.stringify(window.__NEXT_DATA__ || null)" }`
- `evaluate { script: "JSON.stringify(window.__APOLLO_STATE__ || null)" }`
- `evaluate { script: "JSON.stringify(Object.keys(window).filter(k => /apollo|graphql|next|appsync/i.test(k)))" }`

See `docs/reverse-engineering/2-discovery.md` for how to work with `__NEXT_DATA__`, Apollo normalized caches, and `__ref` pointer resolution once you have the raw data.

### Pattern: GraphQL / AppSync Discovery

Use `capture_network` to find GraphQL endpoints:

- Pattern: `**graphql**` or `**appsync-api**`
- Increase `wait` to `8000`–`15000` for SPAs with deferred calls
- Inspect response bodies for operation names, entity shapes, and auth errors

If a response contains `Not Authorized to access ...`, that's a signal to split public and authenticated slices — not a dead end. See `docs/reverse-engineering/2-discovery.md` for the full boundary mapping technique.

After discovery, replay directly with Python/HTTP. Keep Playwright for discovery, not production reads.

### Pattern: Authenticated Discovery

Use passive cookie providers (integrations that expose cookie lookup for a domain) for runtime auth injection on REST operations. Use Playwright for:

- Login flows and session establishment
- Network capture against already-authenticated pages
- Interactive auth debugging

Do not treat Playwright as the default passive cookie source for other integrations.

### Pattern: Use The Browser To Learn, Then Leave The Browser

The right progression for modern sites:

1. Inspect the page and capture network traffic with Playwright.
2. Extract the GraphQL query, REST URL, headers, cookies, or API key.
3. Reproduce the request outside the browser with direct HTTP.
4. Build the real skill operation on the direct replay, not continued browser automation.

Example pattern: a GraphQL consumer site is often best *discovered* in a real browser, but once the AppSync (or similar) endpoint and query documents are known, direct HTTP replay is usually the better production implementation.

### Pattern: Navigation Is Flaky But Network Capture Works

If `goto`, `read_webpage`, or `evaluate` are inconsistent, `capture_network` often still works:

- Keep the browser running, verify with `status`
- Call `capture_network` directly on the target URL
- Narrow the pattern to reduce noise

This can surface the backend contract even when DOM extraction is unreliable.

## Usage

### goto

Navigate to a URL. Returns the page title and final URL (after redirects).

```
goto { url: "https://example.com" }
→ { url: "https://example.com/", title: "Example Domain" }
```

### read_webpage

Extract text or HTML from the current page or a specific element.

```
read_webpage { }                           → full page text
read_webpage { selector: "h1" }            → text of first h1
read_webpage { selector: "main", format: "html" } → HTML of main element
```

## Additional Operations

### Lifecycle

| Operation | What it does |
|---------|-------------|
| `start` | Launch browser (or confirm it's running). Pass `mode: "headed"` (default, visible window) or `mode: "headless"` (invisible). Optional — other operations auto-launch. |
| `stop` | Kill the browser process. |
| `status` | Check if browser is running, get current URL. |

### Navigation & Inspection

| Operation | What it does |
|---------|-------------|
| `inspect` | **Use this first.** Fast DOM snapshot — structured tree of tags, attributes, text. No pixels, just data. |
| `url` | Get current URL and page title. |
| `errors` | Reload page and capture console errors. |
| `evaluate` | Run JavaScript in the page and return the result. |
| `screenshot` | Capture full page or element screenshot. **Slow — use only when you need visual verification or the user asks.** |

### Interaction

| Operation | What it does |
|---------|-------------|
| `click` | Click an element by CSS selector. |
| `dblclick` | Double-click an element. Required for opening desktop apps (icons need double-click). |
| `fill` | Set an input's value (clears first). |
| `select` | Choose a dropdown option. |
| `type` | Type text character by character (for inputs needing keystrokes). |
| `wait` | Wait for a selector to appear or a timeout. |

### Tabs

| Operation | What it does |
|---------|-------------|
| `tabs` | List all open tabs with URLs and titles. |
| `new_tab` | Open a new tab, optionally navigate to URL. |
| `close_tab` | Close the current tab. |

### Cookies

| Operation | What it does |
|---------|-------------|
| `cookies` | Extract cookies for a domain from the active browser session. Returns HttpOnly cookies too (via CDP, not JS). Use after a login flow to capture session cookies. |

```
cookies { domain: ".claude.ai" }
→ { domain: ".claude.ai", cookies: [{name: "sessionKey", value: "sk-ant-...", httpOnly: true, ...}], count: 1 }

cookies { domain: ".chase.com", names: "JSESSIONID,auth_token" }
→ { domain: ".chase.com", cookies: [...], count: 2 }
```

### Network Capture

| Operation | What it does |
|---------|-------------|
| `capture_network` | Navigate to a URL and capture all XHR/fetch responses. Optionally inject cookies first. Returns URL, method, status, content-type, and parsed JSON body for each matching response. **Use for endpoint discovery on authenticated pages.** |

```
capture_network { url: "https://secure.chase.com/web/auth/dashboard", cookies: [...], wait: 8000 }
→ { captured: [{url: "https://secure.chase.com/svc/rr/...", method: "POST", status: 200, body: {...}}, ...], count: 42 }

capture_network { url: "https://example.com/dashboard", pattern: "**/api/**", wait: 3000 }
→ { captured: [{url: ".../api/user", method: "GET", status: 200, body: {name: "..."}}], count: 1 }
```

Targeted patterns are usually better than `**`:

```text
"**graphql**"         → GraphQL endpoints
"**appsync-api**"     → AWS AppSync backends
"**/api/**"           → REST APIs
"**/svc/**"           → service-style backends
"**/ajax/**"          → older AJAX endpoints
```

If a page makes deferred async requests, increase `wait` before assuming nothing interesting happened.

## Examples: Reverse Engineering

### Example: Next.js Hydration Probe

```text
goto { url: "https://example.com/product/123" }
inspect { selector: "body" }
read_webpage { selector: "script#__NEXT_DATA__", format: "text" }
evaluate { script: "JSON.stringify(window.__NEXT_DATA__?.props?.pageProps ?? null)" }
```

### Example: Apollo Cache Probe

```text
evaluate { script: "JSON.stringify(window.__NEXT_DATA__?.props?.pageProps?.apolloState ?? null)" }
evaluate { script: "JSON.stringify(window.__APOLLO_STATE__ || null)" }
```

### Example: GraphQL Discovery

```text
capture_network {
  url: "https://example.com/dashboard",
  pattern: "**graphql**",
  wait: 10000,
  capture_body: true
}
```

### Example: Next.js + Apollo + AppSync page

Public catalog-style pages are a good example of why you should not jump straight to DOM scraping.

Useful sequence (replace URL with your target):

```text
goto { url: "https://example.com/item/123" }
inspect { selector: "body" }
read_webpage { selector: "script#__NEXT_DATA__", format: "text" }
evaluate { script: "JSON.stringify(window.__NEXT_DATA__?.props?.pageProps?.apolloState ?? null)" }
capture_network {
  url: "https://example.com/item/123",
  pattern: "**appsync-api**",
  wait: 8000,
  capture_body: true
}
```

In practice this surfaces:

- normalized Apollo data already embedded in `__NEXT_DATA__`
- AppSync GraphQL responses for things like genres, similar books, and reviews
- field-level auth errors that help distinguish public data from viewer-only enrichments

## Selectors

All selector parameters accept CSS selectors:

```
"button"                     → first button
"#login-btn"                 → element with id login-btn
".nav-item"                  → first element with class nav-item
"input[type=email]"          → email input
"button:has-text('Submit')"  → Playwright text selector
"[data-testid=submit]"       → by data attribute
```

## Example: Interactive Login Discovery

Use individual operations to walk through a login flow and understand it:

```
start { }
goto { url: "https://app.example.com/login" }
inspect { }
fill { selector: "input[type=email]", value: "user@example.com" }
click { selector: "button[type=submit]" }
capture_network { url: "https://app.example.com/login", pattern: "**/api/**" }
cookies { domain: ".example.com" }
```

Once you understand the flow, implement it with HTTPX.

## Example: Scripted Flow (run_flow)

For repeatable flows, use `run_flow` — launches an ephemeral browser, runs steps, returns results, closes:

```
run_flow {
  steps: [
    { goto: "https://app.example.com/login" },
    { fill: { selector: "input[type=email]", value: "user@example.com" } },
    { fill: { selector: "input[type=password]", value: "..." } },
    { click: "button[type=submit]" },
    { wait_for: { url_matches: "dashboard" } },
    { extract_cookies: ["session", "csrf_token"] }
  ],
  headless: false,
  size: "compact"
}
→ { success: true, cookies: { session: "abc...", csrf_token: "xyz..." } }
```

`run_flow` detects 2FA prompts automatically and returns `needs_2fa: true`. Available step types: `goto`, `click`, `dblclick`, `right_click`, `fill`, `type`, `wait` (ms), `wait_for` (condition), `extract_cookies`, `extract` (selector → named value), `screenshot`, `close`.

## Requirements

Playwright and Chromium must be installed:

```bash
npm install -g playwright
npx playwright install chromium
```

---
id: playwright
name: Playwright
description: Browser automation — navigate, click, fill, screenshot, and inspect web pages via a persistent Chromium session
icon: icon.svg
color: "#2EAD33"

website: https://playwright.dev

connections: {}

adapters:
  webpage:
    id: .url
    name: '.title // .url'
    url: .url

operations:
  get_webpage:
    description: Navigate to a URL and return page info (title, URL)
    returns: webpage
    params:
      url:
        type: string
        required: true
        description: URL to navigate to
      wait_until:
        type: string
        description: "Wait condition: load, domcontentloaded, networkidle (default: networkidle)"
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts goto"]
      working_dir: .
      stdin: '.params | {url: .url, wait_until: (.wait_until // "networkidle")}'
      timeout: 45

  read_webpage:
    description: Extract text or HTML content from the current page or a CSS selector. Useful for reading `script#__NEXT_DATA__` or specific app containers before falling back to screenshots.
    returns: webpage
    params:
      selector:
        type: string
        description: "CSS selector to extract from (default: body)"
      format:
        type: string
        description: "Output format: text or html (default: text)"
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts extract"]
      working_dir: .
      stdin: '.params | {selector: (.selector // "body"), format: (.format // "text")}'
      timeout: 30

  start:
    description: "Launch or connect to a persistent Chromium browser. If already running, returns immediately. Mode: 'headed' (default) shows a visible window, 'headless' runs invisibly."
    params:
      mode:
        type: string
        description: "'headed' (default) — visible browser window. 'headless' — no visible window, runs in background."
      port:
        type: integer
        description: "CDP port (default: 9222)"
    returns:
      status: string
      port: integer
      url: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts start"]
      working_dir: .
      stdin: '.params | {mode: (.mode // "headed"), port: (.port // 9222)}'
      timeout: 30

  stop:
    description: Kill the persistent browser process
    returns: void
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts stop"]
      working_dir: .
      stdin: '.params | {port: (.port // 9222)}'
      timeout: 10

  status:
    description: Check if the browser is running and get current URL
    returns:
      running: boolean
      port: integer
      url: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts status"]
      working_dir: .
      stdin: '.params | {port: (.port // 9222)}'
      timeout: 10

  screenshot:
    description: Capture a screenshot of the full page or a specific element
    params:
      selector:
        type: string
        description: CSS selector for element screenshot (omit for full page)
      path:
        type: string
        description: "Output file path (default: /tmp/screenshot.png)"
      full_page:
        type: boolean
        description: Capture full scrollable page (default for no selector)
    returns:
      path: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts screenshot"]
      working_dir: .
      stdin: '.params | {selector: .selector, path: (.path // "/tmp/screenshot.png"), full_page: (.full_page // false)}'
      timeout: 30

  click:
    description: Click an element by CSS selector
    params:
      selector:
        type: string
        required: true
        description: CSS selector of element to click
    returns:
      selector: string
      url: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts click"]
      working_dir: .
      stdin: '.params | {selector: .selector}'
      timeout: 15

  fill:
    description: Fill an input field with a value (clears existing content first)
    params:
      selector:
        type: string
        required: true
        description: CSS selector of the input field
      value:
        type: string
        required: true
        description: Value to fill
    returns:
      selector: string
      value: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts fill"]
      working_dir: .
      stdin: '.params | {selector: .selector, value: .value}'
      timeout: 15

  select:
    description: Select an option from a dropdown
    params:
      selector:
        type: string
        required: true
        description: CSS selector of the select element
      value:
        type: string
        required: true
        description: Option value to select
    returns:
      selector: string
      value: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts select"]
      working_dir: .
      stdin: '.params | {selector: .selector, value: .value}'
      timeout: 15

  type:
    description: Type text character by character (for inputs that need real keystrokes, not just value setting)
    params:
      selector:
        type: string
        required: true
        description: CSS selector of the input
      text:
        type: string
        required: true
        description: Text to type
    returns:
      selector: string
      text: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts type"]
      working_dir: .
      stdin: '.params | {selector: .selector, text: .text}'
      timeout: 30

  evaluate:
    description: Execute arbitrary JavaScript in the page context and return the result. Useful for dumping `window.__NEXT_DATA__`, Apollo caches, route state, or framework globals.
    params:
      script:
        type: string
        required: true
        description: JavaScript code to execute
    returns:
      result: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts evaluate"]
      working_dir: .
      stdin: '.params | {script: .script}'
      timeout: 30

  url:
    description: Get the current page URL and title
    returns:
      url: string
      title: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts url"]
      working_dir: .
      timeout: 10

  inspect:
    description: "Fast DOM snapshot — returns structured tree of tags, attributes, and text. Use this instead of screenshot to understand page structure."
    params:
      selector:
        type: string
        description: "CSS selector to inspect (default: body)"
    returns:
      url: string
      title: string
      snapshot: object
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts inspect"]
      working_dir: .
      stdin: '.params | {selector: (.selector // "body")}'
      timeout: 15

  errors:
    description: Reload the current page and capture any console errors
    returns:
      errors: array
      count: integer
      url: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts errors"]
      working_dir: .
      timeout: 30

  wait:
    description: Wait for a CSS selector to appear or a timeout to elapse
    params:
      selector:
        type: string
        description: CSS selector to wait for
      timeout:
        type: integer
        description: "Max wait in milliseconds (default: 10000)"
    returns:
      status: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts wait"]
      working_dir: .
      stdin: '.params | {selector: .selector, timeout: (.timeout // 10000)}'
      timeout: 60

  tabs:
    description: List all open browser tabs
    returns:
      tabs: array
      count: integer
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts tabs"]
      working_dir: .
      timeout: 10

  new_tab:
    description: Open a new browser tab, optionally navigating to a URL
    params:
      url:
        type: string
        description: URL to open in the new tab
    returns:
      url: string
      title: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts new_tab"]
      working_dir: .
      stdin: '.params | {url: .url}'
      timeout: 30

  close_tab:
    description: Close the current browser tab
    returns: void
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts close_tab 2>/dev/null"]
      working_dir: .
      timeout: 10

  cookies:
    description: |
      Extract cookies for a domain from the browser's active session via CDP.
      Returns all cookies matching the domain (including HttpOnly cookies that
      JavaScript cannot access). Use this after a login flow to capture session
      cookies for storage. The cookies are returned in Playwright's cookie format
      with name, value, domain, path, expires, httpOnly, secure, sameSite.
    params:
      domain:
        type: string
        required: true
        description: "Cookie domain to match (e.g. '.claude.ai', '.chase.com')"
      names:
        type: string
        description: "Comma-separated cookie names to filter (e.g. 'sessionKey,csrf_token'). Omit for all cookies on the domain."
    returns:
      domain: string
      cookies: array
      count: integer
      url: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts cookies"]
      working_dir: .
      stdin: '.params | {domain: .domain, names: .names}'
      timeout: 15

  clear_cookies:
    description: |
      Clear cookies for a domain. Use when persistent cookies (e.g. from capture_network
      cookie injection) prevent reaching the login form. Preserves cookies for other domains.
    params:
      domain:
        type: string
        required: true
        description: "Domain whose cookies to clear (e.g. '.goodreads.com', '.claude.ai')"
    returns:
      cleared_domain: string
      cleared_count: integer
      kept_count: integer
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts clear_cookies"]
      working_dir: .
      stdin: '.params | {domain: .domain}'
      timeout: 10

  capture_network:
    description: |
      Navigate to a URL and capture all network requests/responses.
      Optionally inject cookies before navigating (useful for authenticated pages).
      Returns every XHR/fetch response matching the pattern, including the parsed
      JSON body for JSON responses. Use this to discover undocumented API endpoints
      that a page calls — e.g. to find the real backend endpoint Chase's dashboard
      hits when it loads account data.

      This is especially useful for GraphQL and AppSync-backed sites. Even when
      request metadata is limited, response bodies often reveal operation names,
      entity shapes, pagination structure, and field-level authorization errors.

      Pattern uses glob syntax: "**" matches everything, "**/svc/**" matches any
      URL with /svc/ in the path. Default pattern captures all non-asset requests.

      Wait time (default 5000ms) controls how long after navigation to keep
      listening — increase for SPAs that make deferred async calls.
    params:
      url:
        type: string
        required: true
        description: "URL to navigate to"
      pattern:
        type: string
        description: "Glob URL pattern to match (default: ** = all non-asset requests)"
      wait:
        type: integer
        description: "Milliseconds to wait after navigation for async requests (default: 5000)"
      cookies:
        type: array
        description: "Cookies to inject before navigating. Each item: {name, value, domain, path}. Use brave-browser cookie_get to get these."
      capture_body:
        type: boolean
        description: "Capture JSON response bodies (default: true)"
    returns:
      url: string
      title: string
      captured: array
      count: integer
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts network_capture"]
      working_dir: .
      stdin: '.params | {url: .url, pattern: (.pattern // "**"), wait: (.wait // 5000), cookies: (.cookies // []), capture_body: (.capture_body // true)}'
      timeout: 60
---

# Playwright

Browser automation via a persistent Chromium session. Control a real browser — navigate, click, fill forms, take screenshots, run JavaScript, inspect pages. The browser stays running between calls.

## Do You Need This Skill?

**Most web tasks do NOT need Playwright.** Before using this skill, check:

- **"I need to read a web page"** → Use **Exa** (`read_webpage`) or **Firecrawl** (`read_webpage`). They're faster, cheaper, and purpose-built for content extraction. Don't launch a browser just to read a page.
- **"I need to search the web"** → Use **Exa** (`search`) or **Brave** (`search`). Playwright is not a search engine.
- **"I need to check what sites were visited"** → Use the **Chrome** or **Firefox** skill (`list_webpages`, `search_webpages`). They read local history databases directly.
- **"I already know the endpoint and just need to replay HTTP"** → Use direct HTTP (`curl` skill, shell `curl`, or a small Python script). Don't keep a browser in the loop once the browser has already taught you the contract.
- **"I need very fast headless HTML/JS fetches"** → Use **Lightpanda** first. It is often better for high-throughput reverse engineering or quick page fetches where you do not need a visible browser or sticky session state.

**Use Playwright when you need to DO things in a browser:**

- Navigate a site interactively (click links, fill forms, submit)
- Automate a login flow or anything requiring a real browser session
- Take screenshots for visual inspection or verification
- Test a web app — check for console errors, verify page state
- Run JavaScript in a live page context
- Interact with SPAs that require JS execution to render
- Anything where cookies/auth/session state must persist across steps

**Rule of thumb:** Reading content = Exa/Firecrawl. Controlling a browser = Playwright.

## Complementary Tools

Playwright is the main browser reverse-engineering tool, but it is not the only one you should consider.

Use these together:

- **Playwright** for login flows, persistent browser sessions, DOM inspection, JS evaluation, and network capture.
- **Lightpanda** for fast headless fetches when you want HTML or rendered content quickly without Chrome overhead.
- **Exa** for web research, finding unofficial docs, GitHub repos, forum threads, and prior art before you start probing blindly.
- **Firecrawl** when a page needs browser rendering but you mostly want content extraction instead of browser control.
- **Curl / direct HTTP** once you know the endpoint, headers, and payload. At that point the browser has done its job.
- **Cookie provider skills** such as `brave-browser` or `firefox` when you need passive cookie access for runtime auth.

Good reverse engineering is usually a progression:

1. Search the web for prior art with Exa or Brave.
2. Probe the live site with Playwright when you need to inspect DOM, hydration state, or network calls.
3. Switch to direct HTTP or small scripts as soon as you have enough information to replay requests reliably.
4. Use Lightpanda or Firecrawl when you need a cheaper or faster page-fetching path than a full browser session.

## How It Works

Playwright controls Chromium via the Chrome DevTools Protocol (CDP). The browser launches once and **persists** — cookies, sessions, tabs all survive between operations. Each operation connects to the running browser (~100ms), does one thing, and returns. The agent can talk to the user between operations.

```
start → launches Chromium with --remote-debugging-port=9222
        ↓
get_webpage/click/fill/screenshot → connects via CDP, acts, returns (~100ms connect)
        ↓
browser stays alive — sessions, cookies, tabs persist
        ↓
stop → kills the browser process (only when done)
```

## Recommended Workflow

When using Playwright for reverse engineering, prefer this order:

1. `status` or `tabs` to see whether a useful browser session already exists.
2. `get_webpage` to load the target page, or `new_tab` if you want to preserve the current page.
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

Use passive cookie provider skills (`brave-browser`, `firefox`) for runtime cookie auth in product skills. Use Playwright for:

- Login flows and session establishment
- Network capture against already-authenticated pages
- Interactive auth debugging

Do not treat Playwright as the default passive cookie source for other skills.

### Pattern: Use The Browser To Learn, Then Leave The Browser

The right progression for modern sites:

1. Inspect the page and capture network traffic with Playwright.
2. Extract the GraphQL query, REST URL, headers, cookies, or API key.
3. Reproduce the request outside the browser with direct HTTP.
4. Build the real skill operation on the direct replay, not continued browser automation.

Goodreads is a good example: pages were best *discovered* with Playwright, but once the AppSync endpoint and query documents were known, direct Python replay was the better implementation.

### Pattern: Navigation Is Flaky But Network Capture Works

If `get_webpage`, `read_webpage`, or `evaluate` are inconsistent, `capture_network` often still works:

- Keep the browser running, verify with `status`
- Call `capture_network` directly on the target URL
- Narrow the pattern to reduce noise

This can surface the backend contract even when DOM extraction is unreliable.

## Operations

### get_webpage

Navigate to a URL. Returns the page title and final URL (after redirects).

```
get_webpage { url: "https://example.com" }
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
get_webpage { url: "https://example.com/product/123" }
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

### Example: Goodreads Public Book Page

Goodreads book pages are a good example of why you should not jump straight to DOM scraping.

Useful sequence:

```text
get_webpage { url: "https://www.goodreads.com/book/show/4934" }
inspect { selector: "body" }
read_webpage { selector: "script#__NEXT_DATA__", format: "text" }
evaluate { script: "JSON.stringify(window.__NEXT_DATA__?.props?.pageProps?.apolloState ?? null)" }
capture_network {
  url: "https://www.goodreads.com/book/show/4934",
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

## Example: Login Flow

```
start { }
get_webpage { url: "https://app.example.com/login" }
fill { selector: "input[type=email]", value: "user@example.com" }
fill { selector: "input[type=password]", value: "..." }
click { selector: "button[type=submit]" }
wait { selector: ".dashboard" }
screenshot { path: "/tmp/logged-in.png" }
```

## Requirements

Playwright and Chromium must be installed:

```bash
npm install -g playwright
npx playwright install chromium
```

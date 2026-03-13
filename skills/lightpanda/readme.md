---
id: lightpanda
name: Lightpanda
description: Fast headless browser for high-throughput scraping and automation — 10x faster and 10x less memory than Chrome. Playwright-compatible via CDP.
icon: icon.svg
color: "#1B3C27"

website: https://lightpanda.io
auth: none
platforms: [macos]

connects_to: lightpanda

seed:
  - id: lightpanda
    types: [software]
    name: Lightpanda
    data:
      software_type: tool
      url: https://lightpanda.io
      launched: "2024"
      platforms: [macos, linux]
      pricing: open_source
    relationships:
      - role: offered_by
        to: lightpanda-io

  - id: lightpanda-io
    types: [organization]
    name: Lightpanda IO
    data:
      type: company
      url: https://lightpanda.io

instructions: |
  WHEN TO USE THIS SKILL vs OTHERS:
  - Need to READ content from a URL quickly (no interactivity)? → Use THIS skill (fetch) or Exa/Firecrawl.
  - Need to SCRAPE many pages at scale with low memory? → Use THIS skill. NOT playwright.
  - Need to CLICK, FILL FORMS, handle auth, or maintain a logged-in session? → Use playwright instead.
  - Need a VISIBLE browser window? → Use playwright. Lightpanda is headless-only.
  - Need to automate a COMPLEX SPA with full Chrome API coverage? → Use playwright for reliability.
  - Need to extract data from many URLs fast and cheaply? → Use THIS skill.

  Lightpanda is a from-scratch headless browser (written in Zig) built for high-throughput
  AI agent workloads: scraping at scale, fast page fetches, and programmatic automation
  where Chrome's overhead is a bottleneck. It exposes a CDP server — Playwright's TypeScript
  client connects to it just like Chromium.

  KEY DIFFERENCES FROM THE PLAYWRIGHT SKILL:
  - Always headless (no visible window).
  - ~10x less memory and ~11x faster than Chrome for fetch-heavy workloads.
  - Instant startup (~100ms vs Chrome's seconds).
  - Beta — some Web APIs and CDP commands are incomplete. If a site fails, fall back to playwright.
  - No persistent session across stops — each `start` is a fresh browser.
  - No cross-call page state via CDP — each operation re-navigates to the last URL saved in
    /tmp/agentos-lightpanda-state.json. This is transparent but means every CDP call costs a
    navigation round-trip. Use `fetch` for read-only work to avoid this overhead.
  - `url` utility returns the last known URL from state (no live browser query).
  - Do NOT use wait_until: networkidle — it causes "Frame detached" errors. Use domcontentloaded.

  The server is PERSISTENT — `start` launches it and it stays running. All operations
  (goto, inspect, extract, evaluate, click, fill) connect to the running server automatically.
  Call `stop` when fully done to free the process.

  Use `fetch` (the fast path) when you just need page content — it uses lightpanda's
  native fetch command (no CDP overhead, no persistent process, fastest possible).
  Use the CDP operations (goto, inspect, click, etc.) when you need interactivity or JS execution.

requires:
  - name: lightpanda
    check: lightpanda version
    install:
      macos: |
        curl -L -o ~/bin/lightpanda https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-aarch64-macos && chmod a+x ~/bin/lightpanda

credits:
  - skill: playwright
    relationship: appreciates
    reason: Complementary — Playwright handles interactive/auth sessions, Lightpanda handles headless scale
  - skill: firecrawl
    relationship: appreciates
    reason: Complementary — Firecrawl reads static content, Lightpanda executes JS headlessly
  - skill: exa
    relationship: appreciates
    reason: Complementary — Exa searches and fetches, Lightpanda automates and interacts

transformers:
  webpage:
    terminology: Page
    mapping:
      url: .url
      title: .title
      id: .url

operations:
  webpage.get:
    description: Navigate to a URL via the CDP session and return page info (title, URL). Executes JavaScript.
    returns: webpage
    params:
      url:
        type: string
        required: true
        description: URL to navigate to
      wait_until:
        type: string
        description: "Wait condition: load, domcontentloaded, networkidle (default: domcontentloaded). Note: networkidle can cause errors with Lightpanda — stick with domcontentloaded unless you have a reason."
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts goto"]
      stdin: '.params | {url: .url, wait_until: (.wait_until // "domcontentloaded")}'
      timeout: 45

  webpage.read:
    description: Extract text or HTML content from the current page or a CSS selector
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts extract"]
      stdin: '.params | {selector: (.selector // "body"), format: (.format // "text")}'
      timeout: 30

utilities:
  fetch:
    description: |
      Fast single-shot page fetch — no persistent process, no CDP overhead.
      Lightpanda fetches the URL, executes JavaScript, and returns the page content.
      Use this for high-throughput scraping or when you just need page content quickly.
      Supports html, markdown, or semantic_tree output formats.
      This is the fastest operation in this skill.
    params:
      url:
        type: string
        required: true
        description: URL to fetch
      format:
        type: string
        description: "Output format: html, markdown, semantic_tree, semantic_tree_text (default: markdown)"
      strip_mode:
        type: string
        description: "Comma-separated tag groups to strip: js, css, ui, full (default: none)"
    returns:
      url: string
      format: string
      content: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts fetch"]
      stdin: '.params | {url: .url, format: (.format // "markdown"), strip_mode: (.strip_mode // "")}'
      timeout: 30

  start:
    description: "Launch the Lightpanda CDP server. Always headless. If already running, returns immediately."
    params:
      port:
        type: integer
        description: "CDP port (default: 9223)"
      timeout:
        type: integer
        description: "Server inactivity timeout in seconds (default: 30). Use 0 for indefinite (not recommended)."
    returns:
      status: string
      port: integer
      url: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts start"]
      stdin: '.params | {port: (.port // 9223), timeout: (.timeout // 30)}'
      timeout: 15

  stop:
    description: Kill the Lightpanda CDP server process
    returns: void
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts stop"]
      stdin: '.params | {port: (.port // 9223)}'
      timeout: 10

  status:
    description: Check if the Lightpanda server is running and get current URL
    returns:
      running: boolean
      port: integer
      url: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts status"]
      stdin: '.params | {port: (.port // 9223)}'
      timeout: 10

  screenshot:
    description: Capture a screenshot of the full page or a specific element
    params:
      selector:
        type: string
        description: CSS selector for element screenshot (omit for full page)
      path:
        type: string
        description: "Output file path (default: /tmp/lp-screenshot.png)"
      full_page:
        type: boolean
        description: Capture full scrollable page (default for no selector)
    returns:
      path: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts screenshot"]
      stdin: '.params | {selector: .selector, path: (.path // "/tmp/lp-screenshot.png"), full_page: (.full_page // false)}'
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts click"]
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts fill"]
      stdin: '.params | {selector: .selector, value: .value}'
      timeout: 15

  evaluate:
    description: Execute arbitrary JavaScript in the page context and return the result
    params:
      script:
        type: string
        required: true
        description: JavaScript code to execute
    returns:
      result: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts evaluate"]
      stdin: '.params | {script: .script}'
      timeout: 30

  url:
    description: Get the current page URL and title
    returns:
      url: string
      title: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts url"]
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts inspect"]
      stdin: '.params | {selector: (.selector // "body")}'
      timeout: 15

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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts wait"]
      stdin: '.params | {selector: .selector, timeout: (.timeout // 10000)}'
      timeout: 60

  network.capture:
    description: |
      Navigate to a URL and capture all network requests/responses.
      Returns every XHR/fetch response matching the pattern, including parsed JSON bodies.
      Use this to discover undocumented API endpoints that a page calls.
      Pattern uses glob syntax: "**" matches everything, "**/api/**" matches any URL with /api/ in the path.
      Wait time (default 5000ms) controls how long after navigation to keep listening.
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/lightpanda/scripts/browser.ts network_capture"]
      stdin: '.params | {url: .url, pattern: (.pattern // "**"), wait: (.wait // 5000), capture_body: (.capture_body // true)}'
      timeout: 60
---

# Lightpanda

Fast headless browser built from scratch for machines, not humans. 10x faster, 10x less memory than Chrome headless. Uses a CDP server that Playwright's client connects to directly.

## Do You Need This Skill?

**Use Lightpanda when you need speed and scale, not interactivity:**

- **Scraping many pages at volume** — minimal memory, instant startup, can run many concurrent instances
- **Fast one-shot page fetches** — use `fetch` utility for sub-second content extraction
- **Automating simple headless flows** — forms, clicks, navigation, JS execution, without Chrome overhead
- **Endpoint discovery** — `network.capture` to find what APIs a page calls
- **AI agent web browsing** — fast browse-and-extract loops where Chrome's cost adds up

**Use the Playwright skill instead when you need:**

- A **visible browser window** (Lightpanda is headless-only)
- **Authenticated sessions that persist** across stops (Playwright's Chromium keeps profile/cookies)
- **Complex SPAs** that rely on Web APIs not yet implemented in Lightpanda
- **Login flows with cookies** that need to survive across agent sessions
- Full **Chrome DevTools Protocol** coverage — Lightpanda's CDP is still maturing (Beta)

**Rule of thumb:** High-throughput headless = Lightpanda. Auth/session/visual = Playwright.

## How It Works

Two modes:

**1. Native fetch** (fastest, no persistent process):
```
fetch { url: "https://example.com", format: "markdown" }
```
Lightpanda fetches the URL, executes JS, dumps content, and exits. No server, no CDP overhead.

**2. CDP server** (interactive, persistent):
```
start → lightpanda serve --host 127.0.0.1 --port 9223
        ↓
goto/click/fill/inspect → Playwright connects via CDP, acts, returns
        ↓
server stays alive for subsequent operations
        ↓
stop → kills the lightpanda process
```

The CDP server uses port **9223** by default (not 9222, to avoid colliding with the Playwright skill's Chromium session).

## Operations

### webpage.get

Navigate to a URL and execute JavaScript. Returns title and final URL.

```
webpage.get { url: "https://news.ycombinator.com" }
→ { url: "https://news.ycombinator.com/", title: "Hacker News" }
```

### webpage.read

Extract text or HTML from the current page or a specific element.

```
webpage.read { }                                   → full page text
webpage.read { selector: "table.itemlist" }        → table text
webpage.read { selector: "body", format: "html" }  → raw HTML
```

## Utilities

### fetch (fastest path)

Single-shot native fetch — no persistent process, no Playwright, just Lightpanda binary:

```
fetch { url: "https://example.com" }
→ { content: "# Example Domain\n...", format: "markdown" }

fetch { url: "https://example.com", format: "html", strip_mode: "js,css" }
→ { content: "<html>...", format: "html" }
```

Formats: `markdown`, `html`, `semantic_tree`, `semantic_tree_text`

### Lifecycle

| Utility | What it does |
|---------|-------------|
| `start` | Launch Lightpanda CDP server (headless always). Auto-launches on first operation. |
| `stop` | Kill the CDP server process. |
| `status` | Check if the server is running. |

### Navigation & Inspection

| Utility | What it does |
|---------|-------------|
| `inspect` | **Use this first.** Fast DOM snapshot — structured tree of tags, attributes, text. |
| `url` | Get current URL and title. |
| `evaluate` | Run JavaScript in the page and return the result. |
| `screenshot` | Capture screenshot (full page or element). Use sparingly — slow. |

### Interaction

| Utility | What it does |
|---------|-------------|
| `click` | Click an element by CSS selector. |
| `fill` | Set an input's value (clears first). |
| `wait` | Wait for a selector to appear or a timeout. |

### Network Capture

| Utility | What it does |
|---------|-------------|
| `network.capture` | Navigate and capture all XHR/fetch responses. Returns URLs, methods, statuses, and JSON bodies. |

```
network.capture { url: "https://news.ycombinator.com", pattern: "**/api/**", wait: 3000 }
→ { captured: [{url: ".../api/items", method: "GET", status: 200, body: {...}}], count: 5 }
```

## Caveats (Beta)

Lightpanda is in Beta. Some sites will fail. When you hit issues:

- Try `fetch` instead of the CDP path — it's more reliable for simple content extraction
- Fall back to the `playwright` skill for complex SPAs or sites that require full Chrome APIs
- Custom Elements, file uploads, and some CDP commands are still incomplete
- macOS arm64 is supported (nightly binary), Linux x86_64 also supported

## Requirements

Lightpanda binary must be in PATH or `~/bin`:

```bash
curl -L -o ~/bin/lightpanda https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-aarch64-macos
chmod a+x ~/bin/lightpanda
```

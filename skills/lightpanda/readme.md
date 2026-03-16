---
id: lightpanda
name: Lightpanda
description: Fast headless browser for high-throughput scraping and automation — 10x faster and 10x less memory than Chrome. Playwright-compatible via CDP.
icon: icon.svg
color: "#1B3C27"

website: https://lightpanda.io
auth: none
adapters:
  webpage:
    id: .url
    name: '.title // .url'
    url: .url

operations:
  get_webpage:
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
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts goto"]
      working_dir: .
      stdin: '.params | {url: .url, wait_until: (.wait_until // "domcontentloaded")}'
      timeout: 45

  read_webpage:
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
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts extract"]
      working_dir: .
      stdin: '.params | {selector: (.selector // "body"), format: (.format // "text")}'
      timeout: 30

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
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts fetch"]
      working_dir: .
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
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts start"]
      working_dir: .
      stdin: '.params | {port: (.port // 9223), timeout: (.timeout // 30)}'
      timeout: 15

  stop:
    description: Kill the Lightpanda CDP server process
    returns: void
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts stop"]
      working_dir: .
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
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts status"]
      working_dir: .
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
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts screenshot"]
      working_dir: .
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

  capture_network:
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
      args: ["-l", "-c", "npx tsx ./scripts/browser.ts network_capture"]
      working_dir: .
      stdin: '.params | {url: .url, pattern: (.pattern // "**"), wait: (.wait // 5000), capture_body: (.capture_body // true)}'
      timeout: 60
---

# Lightpanda

Fast headless browser built from scratch for machines, not humans. 10x faster, 10x less memory than Chrome headless. Uses a CDP server that Playwright's client connects to directly.

## Do You Need This Skill?

**Use Lightpanda when you need speed and scale, not interactivity:**

- **Scraping many pages at volume** — minimal memory, instant startup, can run many concurrent instances
- **Fast one-shot page fetches** — use `fetch` for sub-second content extraction
- **Automating simple headless flows** — forms, clicks, navigation, JS execution, without Chrome overhead
- **Endpoint discovery** — `capture_network` to find what APIs a page calls
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
get_webpage/click/fill/inspect → Playwright connects via CDP, acts, returns
        ↓
server stays alive for subsequent operations
        ↓
stop → kills the lightpanda process
```

The CDP server uses port **9223** by default (not 9222, to avoid colliding with the Playwright skill's Chromium session).

## Operations

### get_webpage

Navigate to a URL and execute JavaScript. Returns title and final URL.

```
get_webpage { url: "https://news.ycombinator.com" }
→ { url: "https://news.ycombinator.com/", title: "Hacker News" }
```

### read_webpage

Extract text or HTML from the current page or a specific element.

```
read_webpage { }                                   → full page text
read_webpage { selector: "table.itemlist" }        → table text
read_webpage { selector: "body", format: "html" }  → raw HTML
```

## Additional Operations

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

| Operation | What it does |
|---------|-------------|
| `start` | Launch Lightpanda CDP server (headless always). Auto-launches on first operation. |
| `stop` | Kill the CDP server process. |
| `status` | Check if the server is running. |

### Navigation & Inspection

| Operation | What it does |
|---------|-------------|
| `inspect` | **Use this first.** Fast DOM snapshot — structured tree of tags, attributes, text. |
| `url` | Get current URL and title. |
| `evaluate` | Run JavaScript in the page and return the result. |
| `screenshot` | Capture screenshot (full page or element). Use sparingly — slow. |

### Interaction

| Operation | What it does |
|---------|-------------|
| `click` | Click an element by CSS selector. |
| `fill` | Set an input's value (clears first). |
| `wait` | Wait for a selector to appear or a timeout. |

### Network Capture

| Operation | What it does |
|---------|-------------|
| `capture_network` | Navigate and capture all XHR/fetch responses. Returns URLs, methods, statuses, and JSON bodies. |

```
capture_network { url: "https://news.ycombinator.com", pattern: "**/api/**", wait: 3000 }
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

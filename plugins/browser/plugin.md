---
id: browser
name: Browser
description: Browser automation with console/network diagnostics for testing and debugging
category: automation
icon: material-symbols:web
color: "#4285F4"

triggers:
  - needs to inspect, click, or automate a webpage

settings:
  headless:
    label: Headless Mode
    description: Run browser invisibly (off = you can watch the browser)
    type: boolean
    default: "true"
  slow_mo:
    label: Slow Motion (ms)
    description: Delay between actions when watching (0 = full speed)
    type: integer
    default: "0"
    min: 0
    max: 2000
  timeout:
    label: Page Timeout (seconds)
    description: How long to wait for page load
    type: integer
    default: "30"
    min: 5
    max: 120
  user_agent:
    label: User Agent
    description: Browser identity to send
    type: enum
    default: "chrome"
    options:
      - chrome
      - firefox
      - safari
      - mobile
  locale:
    label: Language
    description: Browser locale (e.g. en-US, es-ES, pt-BR)
    type: string
    default: "en-US"

requires:
  - name: node
    install:
      macos: brew install node
      linux: sudo apt install -y nodejs
  - name: npx
    install:
      macos: brew install node
      linux: sudo apt install -y nodejs

helpers: |
  # Ensure Playwright browsers are installed (runs once, fast if already done)
  ensure_playwright() {
    cd "$PLUGIN_DIR/scripts" && npx --yes playwright install chromium >&2
  }
  
  # Run browser action
  browser() {
    ensure_playwright
    node "$PLUGIN_DIR/scripts/browser.mjs"
  }

actions:
  inspect:
    readonly: true
    description: Get a diagnostic overview of a page - headings, buttons, inputs, console logs, network activity. Efficient alternative to screenshots.
    params:
      url:
        type: string
        required: true
        description: URL to inspect
      wait_ms:
        type: integer
        default: "1000"
        description: Time to wait after page load (ms)
      screenshot:
        type: boolean
        default: "false"
        description: Also capture a screenshot (expensive, use sparingly)
    run: browser

  console:
    description: Get console logs and errors from a page. Great for debugging JavaScript issues.
    params:
      url:
        type: string
        required: true
        description: URL to check
      wait_ms:
        type: integer
        default: "2000"
        description: Time to wait for console activity (ms)
    run: browser

  network:
    description: Get network requests and errors from a page. Great for debugging API issues.
    params:
      url:
        type: string
        required: true
        description: URL to check
      wait_ms:
        type: integer
        default: "2000"
        description: Time to wait for network activity (ms)
    run: browser

  click:
    description: Click an element on a page. Returns console/network errors if any.
    params:
      url:
        type: string
        required: true
        description: URL to navigate to
      selector:
        type: string
        required: true
        description: CSS selector of element to click
      wait_ms:
        type: integer
        default: "1000"
        description: Time to wait after click (ms)
      screenshot:
        type: boolean
        default: "false"
        description: Capture a screenshot after clicking (expensive)
    run: browser

  type:
    description: Type text into an input field. Returns console/network errors if any.
    params:
      url:
        type: string
        required: true
        description: URL to navigate to
      selector:
        type: string
        required: true
        description: CSS selector of input element
      text:
        type: string
        required: true
        description: Text to type
      wait_ms:
        type: integer
        default: "500"
        description: Time to wait after typing (ms)
      screenshot:
        type: boolean
        default: "false"
        description: Capture a screenshot after typing (expensive)
    run: browser

  get_text:
    description: Get text content from elements matching a selector
    params:
      url:
        type: string
        required: true
        description: URL to navigate to
      selector:
        type: string
        required: true
        description: CSS selector to get text from
      wait_ms:
        type: integer
        default: "1000"
        description: Time to wait after page load (ms)
    run: browser

  evaluate:
    description: Run JavaScript in the page context and return the result
    params:
      url:
        type: string
        required: true
        description: URL to navigate to
      script:
        type: string
        required: true
        description: JavaScript code to evaluate in page context
      wait_ms:
        type: integer
        default: "1000"
        description: Time to wait after page load (ms)
    run: browser

  screenshot:
    description: Take a screenshot of a page. Use sparingly - expensive in tokens. Prefer inspect/console/network.
    params:
      url:
        type: string
        required: true
        description: URL to screenshot
      selector:
        type: string
        description: Optional CSS selector to screenshot a specific element
      wait_ms:
        type: integer
        default: "1000"
        description: Time to wait after page load before screenshot (ms)
    run: browser

  get_html:
    description: Get HTML content from the page or a specific element
    params:
      url:
        type: string
        required: true
        description: URL to navigate to
      selector:
        type: string
        description: Optional CSS selector (returns full page HTML if not specified)
      wait_ms:
        type: integer
        default: "1000"
        description: Time to wait after page load (ms)
    run: browser
---

# Browser

**⚡ Always start with `inspect`** — it's fast, cheap, and gives you everything: page structure, buttons, inputs, console logs, network requests.

## Quick Start

```
tool: inspect
params: {url: "https://example.com"}
```

This returns structured data in seconds. Only use other tools after inspecting.

## Tool Priority

| Priority | Tool | Use when |
|----------|------|----------|
| 1️⃣ | `inspect` | **Always start here** — page overview, console, network |
| 2️⃣ | `console` | Focus on JavaScript errors |
| 2️⃣ | `network` | Focus on failed API calls |
| 3️⃣ | `click` / `type` | Interact with elements |
| 3️⃣ | `get_text` | Extract specific content |
| 4️⃣ | `evaluate` | Run custom JavaScript |
| ⚠️ | `get_html` | Full HTML (can timeout on heavy pages) |
| ⚠️ | `screenshot` | Visual capture (expensive tokens) |

## Tools

### inspect ⚡ (start here)
Page structure, buttons, inputs, console logs, network activity.

```
tool: inspect
params: {url: "https://example.com"}
```

### console
JavaScript console logs and errors.

```
tool: console
params: {url: "https://example.com"}
```

### network
Network requests and failed API calls.

```
tool: network
params: {url: "https://example.com"}
```

### click
Click an element. Returns any console/network errors.

```
tool: click
params: {url: "https://example.com", selector: "text=Submit"}
```

### type
Type into an input field.

```
tool: type
params: {url: "https://example.com", selector: "input[name='email']", text: "hello@example.com"}
```

### get_text
Extract text from elements.

```
tool: get_text
params: {url: "https://example.com", selector: "h1"}
```

### evaluate
Run JavaScript in the page context.

```
tool: evaluate
params: {url: "https://example.com", script: "document.title"}
```

### get_html ⚠️
Full HTML (can timeout on heavy pages — prefer inspect).

```
tool: get_html
params: {url: "https://example.com", selector: "main"}
```

### screenshot ⚠️
Capture screenshot (expensive in tokens — use sparingly).

```
tool: screenshot
params: {url: "https://example.com"}
```

## CSS Selectors

- `text=Click me` — Element containing text
- `#id` — By ID
- `.class` — By class
- `button` — By tag
- `[data-testid="submit"]` — By attribute

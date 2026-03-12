---
id: playwright
name: Playwright
description: Browser automation — navigate, click, fill, screenshot, and inspect web pages via a persistent Chromium session
icon: icon.svg
color: "#2EAD33"

website: https://playwright.dev
auth: none
platforms: [macos]

connects_to: playwright

seed:
  - id: playwright
    types: [software]
    name: Playwright
    data:
      software_type: library
      url: https://playwright.dev
      launched: "2020"
      platforms: [macos, windows, linux]
      pricing: open_source
    relationships:
      - role: offered_by
        to: microsoft-corp

  - id: cdp
    types: [software]
    name: Chrome DevTools Protocol
    data:
      software_type: protocol
      url: https://chromedevtools.github.io/devtools-protocol/

  - id: microsoft-corp
    types: [organization]
    name: Microsoft
    data:
      type: company
      url: https://microsoft.com

provides:
  - service: cookies
    description: "Extract cookies from a live browser session (including HttpOnly). Use after navigating to a logged-in site."
    via: cookies
    account_param: domain

instructions: |
  WHEN TO USE THIS SKILL vs OTHERS:
  - Need to READ a web page's content? → Use Exa (search.create) or Firecrawl (webpage.read). NOT this.
  - Need to SEARCH the web? → Use Exa or Brave. NOT this.
  - Need to check browsing HISTORY? → Use Chrome or Firefox skill. NOT this.
  - Need to CONTROL a browser — click, fill, navigate, screenshot, automate? → Use THIS skill.
  - Need to TEST or INSPECT a web app (console errors, visual state)? → Use THIS skill.
  - Need to do something that requires a LOGGED-IN SESSION (cookies, auth)? → Use THIS skill.

  Playwright provides browser automation — controlling a real Chromium browser via CDP.
  This is for interactive browser control: navigating sites, clicking buttons,
  filling forms, taking screenshots, running JavaScript, and inspecting pages.
  This is NOT for reading web content (Exa/Firecrawl are faster and better for that).

  The browser is PERSISTENT — start it once, and it stays running between calls.
  Cookies, login sessions, and tabs survive across operations. The agent can respond
  to the user between calls — every operation is non-blocking (connect, act, return).

  You do NOT need to call `start` first — any operation auto-launches the browser
  if it's not running. But `start` is useful to pre-launch (e.g., with --headless)
  or to confirm the browser is ready before a sequence of operations.

  To understand the page, use `inspect` first — it returns a fast structured DOM
  snapshot (tag names, attributes, text) that you can reason about immediately.
  Do NOT use `screenshot` unless you're stuck, the user asks for one, or you need
  visual verification. Screenshots are slow and produce images, not actionable data.
  Use `evaluate` as an escape hatch for anything the predefined operations don't cover.

requires:
  - name: playwright
    check: npx playwright --version
    install:
      macos: npm install -g playwright && npx playwright install chromium

credits:
  - entity: webpage
    operations: [read]
    relationship: needs
  - skill: chrome
    relationship: appreciates
    reason: Shared browser domain — Chrome provides history, Playwright provides control
  - skill: firecrawl
    relationship: appreciates
    reason: Complementary — Firecrawl reads content, Playwright controls interaction

transformers:
  webpage:
    terminology: Page
    mapping:
      url: .url
      title: .title
      id: .url

operations:
  webpage.get:
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts goto"]
      stdin: '{"url": "{{params.url}}", "wait_until": "{{params.wait_until}}"}'
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts extract"]
      stdin: '{"selector": "{{params.selector}}", "format": "{{params.format}}"}'
      timeout: 30

utilities:
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts start"]
      stdin: '{"mode": "{{params.mode}}", "port": "{{params.port}}"}'
      timeout: 30

  stop:
    description: Kill the persistent browser process
    returns: void
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts stop"]
      stdin: '{"port": "{{params.port}}"}'
      timeout: 10

  status:
    description: Check if the browser is running and get current URL
    returns:
      running: boolean
      port: integer
      url: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts status"]
      stdin: '{"port": "{{params.port}}"}'
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts screenshot"]
      stdin: '{"selector": "{{params.selector}}", "path": "{{params.path}}", "full_page": "{{params.full_page}}"}'
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts click"]
      stdin: '{"selector": "{{params.selector}}"}'
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts fill"]
      stdin: '{"selector": "{{params.selector}}", "value": "{{params.value}}"}'
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts select"]
      stdin: '{"selector": "{{params.selector}}", "value": "{{params.value}}"}'
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts type"]
      stdin: '{"selector": "{{params.selector}}", "text": "{{params.text}}"}'
      timeout: 30

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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts evaluate"]
      stdin: '{"script": "{{params.script}}"}'
      timeout: 30

  url:
    description: Get the current page URL and title
    returns:
      url: string
      title: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts url"]
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts inspect"]
      stdin: '{"selector": "{{params.selector}}"}'
      timeout: 15

  errors:
    description: Reload the current page and capture any console errors
    returns:
      errors: array
      count: integer
      url: string
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts errors"]
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts wait"]
      stdin: '{"selector": "{{params.selector}}", "timeout": "{{params.timeout}}"}'
      timeout: 60

  tabs:
    description: List all open browser tabs
    returns:
      tabs: array
      count: integer
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts tabs"]
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts new_tab"]
      stdin: '{"url": "{{params.url}}"}'
      timeout: 30

  close_tab:
    description: Close the current browser tab
    returns: void
    command:
      binary: bash
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts close_tab 2>/dev/null"]
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
      args: ["-l", "-c", "npx tsx ~/dev/agentos-community/skills/playwright/scripts/browser.ts cookies"]
      stdin: '{"domain": "{{params.domain}}", "names": "{{params.names}}"}'
      timeout: 15
---

# Playwright

Browser automation via a persistent Chromium session. Control a real browser — navigate, click, fill forms, take screenshots, run JavaScript, inspect pages. The browser stays running between calls.

## Do You Need This Skill?

**Most web tasks do NOT need Playwright.** Before using this skill, check:

- **"I need to read a web page"** → Use **Exa** (`webpage.read`) or **Firecrawl** (`webpage.read`). They're faster, cheaper, and purpose-built for content extraction. Don't launch a browser just to read a page.
- **"I need to search the web"** → Use **Exa** (`search.create`) or **Brave** (`search.create`). Playwright is not a search engine.
- **"I need to check what sites were visited"** → Use the **Chrome** or **Firefox** skill (`webpage.list`, `webpage.search`). They read local history databases directly.

**Use Playwright when you need to DO things in a browser:**

- Navigate a site interactively (click links, fill forms, submit)
- Automate a login flow or anything requiring a real browser session
- Take screenshots for visual inspection or verification
- Test a web app — check for console errors, verify page state
- Run JavaScript in a live page context
- Interact with SPAs that require JS execution to render
- Anything where cookies/auth/session state must persist across steps

**Rule of thumb:** Reading content = Exa/Firecrawl. Controlling a browser = Playwright.

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

## Operations

### webpage.get

Navigate to a URL. Returns the page title and final URL (after redirects).

```
webpage.get { url: "https://example.com" }
→ { url: "https://example.com/", title: "Example Domain" }
```

### webpage.read

Extract text or HTML from the current page or a specific element.

```
webpage.read { }                           → full page text
webpage.read { selector: "h1" }            → text of first h1
webpage.read { selector: "main", format: "html" } → HTML of main element
```

## Utilities

### Lifecycle

| Utility | What it does |
|---------|-------------|
| `start` | Launch browser (or confirm it's running). Pass `mode: "headed"` (default, visible window) or `mode: "headless"` (invisible). Optional — other operations auto-launch. |
| `stop` | Kill the browser process. |
| `status` | Check if browser is running, get current URL. |

### Navigation & Inspection

| Utility | What it does |
|---------|-------------|
| `inspect` | **Use this first.** Fast DOM snapshot — structured tree of tags, attributes, text. No pixels, just data. |
| `url` | Get current URL and page title. |
| `errors` | Reload page and capture console errors. |
| `evaluate` | Run JavaScript in the page and return the result. |
| `screenshot` | Capture full page or element screenshot. **Slow — use only when you need visual verification or the user asks.** |

### Interaction

| Utility | What it does |
|---------|-------------|
| `click` | Click an element by CSS selector. |
| `fill` | Set an input's value (clears first). |
| `select` | Choose a dropdown option. |
| `type` | Type text character by character (for inputs needing keystrokes). |
| `wait` | Wait for a selector to appear or a timeout. |

### Tabs

| Utility | What it does |
|---------|-------------|
| `tabs` | List all open tabs with URLs and titles. |
| `new_tab` | Open a new tab, optionally navigate to URL. |
| `close_tab` | Close the current tab. |

### Cookies

| Utility | What it does |
|---------|-------------|
| `cookies` | Extract cookies for a domain from the active browser session. Returns HttpOnly cookies too (via CDP, not JS). Use after a login flow to capture session cookies. |

```
cookies { domain: ".claude.ai" }
→ { domain: ".claude.ai", cookies: [{name: "sessionKey", value: "sk-ant-...", httpOnly: true, ...}], count: 1 }

cookies { domain: ".chase.com", names: "JSESSIONID,auth_token" }
→ { domain: ".chase.com", cookies: [...], count: 2 }
```

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
webpage.get { url: "https://app.example.com/login" }
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

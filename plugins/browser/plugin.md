---
id: browser
name: Browser
description: Browser automation with console/network diagnostics for testing and debugging
category: automation
icon: material-symbols:web
color: "#4285F4"

topics: [browser automation, webpage inspection, web debugging]

settings:
  recording_format:
    label: Recording Format
    description: "simple = clean action-based format for manual flows, chrome_devtools = detailed format from auto-recording"
    type: enum
    default: "simple"
    options:
      - simple
      - chrome_devtools
  default_playback_mode:
    label: Default Playback Mode
    description: "browser = fast Playwright automation, native = OS-level input (visible to screen recorders)"
    type: enum
    default: "browser"
    options:
      - browser
      - native
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
  color_scheme:
    label: Color Scheme
    description: Browser color scheme preference (affects sites that support dark mode)
    type: enum
    default: "light"
    options:
      - light
      - dark

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
  # Session Management - for interactive development
  start_session:
    description: |
      Start a persistent browser session for interactive development.
      The browser stays open between commands, allowing back-and-forth feedback.
      Use session_id in subsequent actions to control this browser.
    params:
      url:
        type: string
        description: Optional initial URL to navigate to
      recording:
        type: boolean
        default: "false"
        description: Start recording user interactions immediately
    run: browser

  end_session:
    description: Close a persistent browser session
    params:
      session_id:
        type: string
        required: true
        description: Session ID from start_session
    run: browser

  # Regular actions - work standalone or with session_id
  inspect:
    readonly: true
    description: Get a diagnostic overview of a page - headings, buttons, inputs, console logs, network activity. Efficient alternative to screenshots.
    params:
      session_id:
        type: string
        description: Optional session ID to use existing browser instead of launching new one
      url:
        type: string
        description: URL to inspect (required if no session_id)
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
      session_id:
        type: string
        description: Session ID to use existing browser (from start_session)
      url:
        type: string
        description: URL to navigate to (required if no session_id)
      selector:
        type: string
        required: true
        description: CSS selector or text selector (e.g. "text=Click me")
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
      session_id:
        type: string
        description: Session ID to use existing browser (from start_session)
      url:
        type: string
        description: URL to navigate to (required if no session_id)
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

  play_flow:
    description: |
      Play back a browser flow. Auto-detects format.
      
      Simple format (recommended for manual flows):
        [
          {"action": "goto", "url": "https://example.com"},
          {"action": "wait_for", "selector": "text=Login"},
          {"action": "click", "selector": "text=Login"},
          {"action": "type", "selector": "input[name='email']", "text": "user@example.com"},
          {"action": "click", "selector": "text=Submit"}
        ]
      
      Chrome DevTools format (from record_flow or Chrome DevTools Recorder):
        {"title": "...", "steps": [{"type": "navigate", ...}, ...]}
    params:
      session_id:
        type: string
        description: Session ID to use existing browser (from start_session)
      recording:
        type: object
        required: true
        description: |
          Simple format actions: goto, wait_for, click, type, press, hover, scroll
          
          Example (simple):
          [
            {"action": "goto", "url": "https://example.com"},
            {"action": "wait_for", "selector": "role=button[name=\"Login\"]"},
            {"action": "click", "selector": "role=button[name=\"Login\"]"},
            {"action": "type", "selector": "input[name='email']", "text": "user@example.com"},
            {"action": "press", "key": "Enter"}
          ]
      playback_mode:
        type: enum
        description: "Override playback mode: browser = fast Playwright automation, native = OS-level input for screen recordings"
        options:
          - browser
          - native
    run: browser

  record_flow:
    description: |
      Start recording user interactions on a browser session.
      Returns immediately - user can then interact with the browser.
      Use stop_recording to get the recorded flow as Chrome DevTools JSON.
    params:
      session_id:
        type: string
        required: true
        description: Session ID to record on (from start_session)
    run: browser

  stop_recording:
    description: Stop recording and return the captured flow as Chrome DevTools Recorder JSON.
    params:
      session_id:
        type: string
        required: true
        description: Session ID to stop recording
    run: browser

  get_recording:
    description: |
      Get a recording by session ID. Works even if browser was closed (recording auto-saved).
      Returns Chrome DevTools Recorder JSON format.
    params:
      session_id:
        type: string
        required: true
        description: Session ID of the recording
    run: browser
---

# Browser

Browser automation with two modes: **one-shot** actions for quick tasks, and **sessions** for interactive workflows with recording/playback.

## Quick Reference

| Action | Use For |
|--------|---------|
| `inspect` | **Start here** — page structure, buttons, inputs, console, network |
| `start_session` | Open persistent browser for interactive work |
| `record_flow` | Record user interactions as replayable flow |
| `play_flow` | Replay a recorded flow |
| `click` / `type` | Interact with elements |
| `screenshot` | Visual capture (expensive — use sparingly) |

---

## Sessions (Interactive Workflows)

Sessions keep a browser open so you can interact back-and-forth. Essential for recording and multi-step flows.

### Start a Session

```yaml
action: start_session
params:
  url: "https://example.com"     # Optional starting URL
  recording: true                # Optional: start recording immediately
```

Returns `session_id` — use it in all subsequent actions.

### Use Session with Other Actions

```yaml
action: inspect
params:
  session_id: "session_abc123"
```

```yaml
action: click
params:
  session_id: "session_abc123"
  selector: "text=Login"
```

### End Session

```yaml
action: end_session
params:
  session_id: "session_abc123"
```

---

## Recording & Playback

Record user interactions in the browser and replay them. Uses Chrome DevTools Recorder JSON format.

### Record a Flow

**Option 1: Start session with recording**
```yaml
action: start_session
params:
  url: "https://example.com"
  recording: true
```

**Option 2: Start recording on existing session**
```yaml
action: record_flow
params:
  session_id: "session_abc123"
```

The user can now interact with the browser. All clicks, typing, and navigation are captured.

### Stop Recording

```yaml
action: stop_recording
params:
  session_id: "session_abc123"
```

Returns the recorded flow as Chrome DevTools Recorder JSON.

### Get a Past Recording

Recordings are auto-saved to `~/.agentos/browser-recordings/` as `YYYY-MM-DD_HH-MM-SS_domain.json`.

```yaml
action: get_recording
params:
  session_id: "session_abc123"
```

### Play Back a Flow

**Simple format (recommended for building flows manually):**

```yaml
action: play_flow
params:
  session_id: "session_abc123"
  playback_mode: "browser"
  recording:
    - action: goto
      url: "https://example.com"
    - action: wait_for
      selector: "role=button[name=\"Login\"]"
    - action: click
      selector: "role=button[name=\"Login\"]"
    - action: type
      selector: "input[name='email']"
      text: "user@example.com"
    - action: press
      key: "Enter"
```

**Chrome DevTools format (from record_flow or Chrome export):**

```yaml
action: play_flow
params:
  recording:
    title: "Login Flow"
    steps:
      - type: navigate
        url: "https://example.com"
      - type: click
        selectors: [["role=button[name=\"Login\"]"]]
```

### Playback Modes

| Mode | Description | Use When |
|------|-------------|----------|
| `browser` | Fast Playwright automation | Testing, automation |
| `native` | OS-level mouse/keyboard (enigo) | Screen recordings, demos |

### Simple Format Actions (Recommended)

| Action | Description | Params |
|--------|-------------|--------|
| `goto` | Navigate to URL | `url` |
| `wait_for` | Wait for element to appear | `selector` |
| `click` | Click element | `selector` |
| `type` | Type text into input | `selector`, `text` |
| `press` | Press a key | `key` |
| `hover` | Mouse hover | `selector` |
| `scroll` | Scroll page | `x`, `y` |

### Chrome DevTools Step Types

| Type | Description | Key Params |
|------|-------------|------------|
| `navigate` | Go to URL | `url` |
| `click` | Click element | `selectors`, `offsetX`, `offsetY` |
| `change` | Type into input | `selectors`, `value` |
| `keyDown` / `keyUp` | Press/release key | `key` |
| `waitForElement` | Wait for element | `selectors` |

### Selector Priority

The recorder generates multiple selectors per element for reliability:

1. `role=button[name="..."]` — Playwright's native ARIA (most reliable)
2. `[data-testid="..."]` — Test IDs (if present)
3. `text=...` — Text content
4. `#id` — Element ID (if not auto-generated)
5. CSS path with context
6. XPath (fallback)

---

## One-Shot Actions

For quick tasks without needing a persistent session.

### inspect ⚡ (start here)

Page structure, buttons, inputs, console logs, network activity.

```yaml
action: inspect
params:
  url: "https://example.com"
  screenshot: false    # Set true only if you need visual
```

### click

```yaml
action: click
params:
  url: "https://example.com"
  selector: "text=Submit"
```

### type

```yaml
action: type
params:
  url: "https://example.com"
  selector: "input[name='email']"
  text: "hello@example.com"
```

### get_text

```yaml
action: get_text
params:
  url: "https://example.com"
  selector: "h1"
```

### evaluate

```yaml
action: evaluate
params:
  url: "https://example.com"
  script: "document.title"
```

### console / network

```yaml
action: console
params:
  url: "https://example.com"
```

---

## Selectors

Playwright supports multiple selector types:

| Selector | Example | Use For |
|----------|---------|---------|
| Role | `role=button[name="Submit"]` | Buttons, links (most reliable) |
| Text | `text=Click me` | Elements by visible text |
| Test ID | `[data-testid="submit"]` | Test attributes |
| CSS | `#id`, `.class`, `button` | Standard CSS |
| XPath | `xpath=//button[@type="submit"]` | Complex DOM paths |

**Tip:** Role selectors (`role=button[name="..."]`) are most reliable for dynamic SPAs (React, Next.js).

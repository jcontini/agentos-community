---
id: playwright
name: Playwright
description: Browser automation with sessions, recording, and playback
icon: icon.svg

website: https://playwright.dev


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

requires:
  - name: node
    install:
      macos: brew install node
      linux: sudo apt install -y nodejs
  - name: playwright
    install:
      all: npx playwright install chromium

adapters:
  webpage:
    mapping:
      url: .url
      title: .title
      content: .content

operations:
  # Session Management
  webpage.start_session:
    description: Start a persistent browser session for multi-step workflows
    returns: void
    node:
      script: scripts/playwright.mjs
      args: ["start_session", "{{params | json}}"]

  webpage.end_session:
    description: Close a persistent browser session
    params:
      session_id: { type: string, required: true }
    returns: void
    node:
      script: scripts/playwright.mjs
      args: ["end_session", "{{params | json}}"]

  # Page Inspection
  webpage.inspect:
    description: Get page structure, console logs, network activity
    readonly: true
    params:
      session_id: { type: string }
      url: { type: string }
      wait_ms: { type: integer, default: 1000 }
      screenshot: { type: boolean, default: false }
    returns: void
    node:
      script: scripts/playwright.mjs
      args: ["inspect", "{{params | json}}"]

  # Interaction
  webpage.click:
    description: Click an element on a page
    params:
      session_id: { type: string }
      url: { type: string }
      selector: { type: string, required: true }
      wait_ms: { type: integer, default: 1000 }
    returns: void
    node:
      script: scripts/playwright.mjs
      args: ["click", "{{params | json}}"]

  webpage.type:
    description: Type text into an input field
    params:
      session_id: { type: string }
      url: { type: string }
      selector: { type: string, required: true }
      text: { type: string, required: true }
      wait_ms: { type: integer, default: 500 }
    returns: void
    node:
      script: scripts/playwright.mjs
      args: ["type", "{{params | json}}"]

  webpage.screenshot:
    description: Take a screenshot (expensive, use sparingly)
    readonly: true
    params:
      session_id: { type: string }
      url: { type: string }
      selector: { type: string }
      wait_ms: { type: integer, default: 1000 }
    returns: void
    node:
      script: scripts/playwright.mjs
      args: ["screenshot", "{{params | json}}"]

  webpage.evaluate:
    description: Run JavaScript in the page context
    params:
      session_id: { type: string }
      url: { type: string }
      script: { type: string, required: true }
      wait_ms: { type: integer, default: 1000 }
    returns: void
    node:
      script: scripts/playwright.mjs
      args: ["evaluate", "{{params | json}}"]

utilities:
  record_flow:
    description: Start recording user interactions on a browser session
    params:
      session_id: { type: string, required: true }
    returns:
      success: boolean
    node:
      script: scripts/playwright.mjs
      args: ["record_flow", "{{params | json}}"]

  stop_recording:
    description: Stop recording and return the captured flow
    params:
      session_id: { type: string, required: true }
    returns:
      recording: object
    node:
      script: scripts/playwright.mjs
      args: ["stop_recording", "{{params | json}}"]

  play_flow:
    description: Play back a recorded browser flow
    params:
      session_id: { type: string }
      recording: { type: object, required: true }
    returns:
      success: boolean
    node:
      script: scripts/playwright.mjs
      args: ["play_flow", "{{params | json}}"]
---

# Playwright

Full browser automation using Playwright. No API key required — runs locally.

## When to Use

- **Interactive workflows** — login flows, form filling, multi-step processes
- **Sites that block scrapers** — Playwright appears as a real browser
- **JavaScript-heavy pages** — SPAs that exa/firecrawl can't render
- **Sessions** — back-and-forth interaction with browser state

## Comparison with Other Adapters

| Adapter | Speed | JS Rendering | Interactive | Cost |
|--------|-------|--------------|-------------|------|
| **exa** | ⚡ Fast | ❌ No | ❌ No | API key |
| **firecrawl** | Medium | ✅ Yes | ❌ No | API key |
| **playwright** | Slow | ✅ Yes | ✅ Yes | Free |

Use exa/firecrawl for simple search/read. Use Playwright when you need interaction or sessions.

## Sessions

Sessions keep a browser open for multi-step workflows:

```
1. webpage.start_session → returns session_id
2. webpage.click(session_id, selector: "Login")
3. webpage.type(session_id, selector: "input[name=email]", text: "...")
4. webpage.click(session_id, selector: "Submit")
5. webpage.end_session(session_id)
```

## Recording & Playback

Record user interactions and replay them:

```
1. webpage.start_session(recording: true)
2. User interacts with browser...
3. stop_recording(session_id) → returns flow JSON
4. play_flow(recording: {...}) → replays the flow
```

Uses Chrome DevTools Recorder format — compatible with Chrome's built-in recorder.

## Selectors

Playwright supports multiple selector types:

| Selector | Example | Use For |
|----------|---------|---------|
| Role | `role=button[name="Submit"]` | Buttons, links (most reliable) |
| Text | `text=Click me` | Elements by visible text |
| Test ID | `[data-testid="submit"]` | Test attributes |
| CSS | `#id`, `.class`, `button` | Standard CSS |

**Tip:** Role selectors are most reliable for dynamic SPAs.

## Setup

1. Install Node.js (if not already installed)
2. Run `npx playwright install chromium`

Sessions persist in `~/.agentos/playwright-sessions.json`.

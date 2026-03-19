# Lightpanda

Fast headless browser built from scratch for machines, not humans. 10x faster, 10x less memory than Chrome headless. Uses a CDP server that Playwright's client connects to directly.

## Do You Need This Skill?

**Use Lightpanda when you need speed and scale, not interactivity:**

- **Scraping many pages at volume** — minimal memory, instant startup, can run many concurrent instances
- **Fast one-shot page fetches** — use `fetch` for sub-second content extraction
- **Automating simple headless flows** — forms, clicks, navigation, JS execution, without Chrome overhead
- **Endpoint discovery** — `capture_network` to find what APIs a page calls
- **AI agent web browsing** — fast browse-and-extract loops where Chrome's cost adds up

**Use full Chromium automation (persistent profile, optional visible window) when you need:**

- A **visible browser window** (Lightpanda is headless-only)
- **Authenticated sessions that persist** across stops (a long-lived Chromium session keeps profile/cookies)
- **Complex SPAs** that rely on Web APIs not yet implemented in Lightpanda
- **Login flows with cookies** that need to survive across agent sessions
- Broader **Chrome DevTools Protocol** coverage — Lightpanda's CDP is still maturing (Beta)

**Rule of thumb:** High-throughput headless = Lightpanda. Auth/session/visual = persistent Chromium automation.

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
get_webpage/click/fill/inspect → a CDP client connects, acts, returns
        ↓
server stays alive for subsequent operations
        ↓
stop → kills the lightpanda process
```

The CDP server uses port **9223** by default (not 9222, to avoid colliding with other local Chromium debug ports).

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
- Fall back to full Chromium automation for complex SPAs or sites that require complete Chrome APIs
- Custom Elements, file uploads, and some CDP commands are still incomplete
- macOS arm64 is supported (nightly binary), Linux x86_64 also supported

## Requirements

Lightpanda binary must be in PATH or `~/bin`:

```bash
curl -L -o ~/bin/lightpanda https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-aarch64-macos
chmod a+x ~/bin/lightpanda
```

# Playwright Skill

Browser automation for agents. Use this when you need to:
- Extract cookies/credentials from auth flows
- Take screenshots of websites
- Scrape data from pages
- Test UI behavior
- Automate repetitive browser tasks

## Quick Start

```bash
# Run a simple browser automation
echo '{"steps":[{"goto":"https://example.com"},{"screenshot":{"path":"shot.png"}}]}' | \
  npx tsx ~/dev/agentos/scripts/playwright-runner.ts
```

## The Runner

**Location:** `~/dev/agentos/scripts/playwright-runner.ts`

**Input:** JSON config via stdin or `--config` flag
**Output:** JSON result to stdout

```typescript
interface RunnerConfig {
  steps: Step[];
  launch?: {
    headless?: boolean;        // Default: false (shows browser)
    slowMo?: number;           // Slow down for debugging
    size?: 'mobile' | 'compact' | 'full';  // Window size
  };
  credentials?: {
    username?: string;
    password?: string;
    two_factor_code?: string;
  };
}
```

## Available Steps

### Navigation
```json
{"goto": "https://example.com"}
```

### Clicking
```json
{"click": "button.submit"}
{"dblclick": ".icon"}           // Double-click (open apps)
{"right_click": ".item"}        // Context menu
```

### Input
```json
{"fill": {"selector": "input[name=email]", "value": "test@example.com"}}
{"type": {"selector": "input", "value": "slow typing"}}  // Character by character
```

### Waiting
```json
{"wait": 1000}                  // Wait N milliseconds
{"wait_for": {"selector": ".loaded"}}
{"wait_for": {"cookie": "session_id"}}
{"wait_for": {"url_matches": "dashboard"}}
{"wait_for": {"any": [{"selector": ".success"}, {"selector": ".error"}]}}
```

### Extraction
```json
{"extract_cookies": ["session_id", "csrf_token"]}
{"extract": {"selector": "h1", "as": "title"}}
{"extract": {"selector": "a", "attribute": "href", "as": "link"}}
```

### Screenshots
```json
{"screenshot": {"path": "/tmp/page.png"}}
```

### Close
```json
"close"
```

## Window Sizes

| Size | Dimensions | User Agent |
|------|------------|------------|
| `mobile` | 390x844 | iPhone 14 Pro |
| `compact` | 480x720 | Small desktop |
| `full` | 1280x800 | Full desktop |

## Example: Extract Auth Cookies

```bash
npx tsx ~/dev/agentos/scripts/playwright-runner.ts --config '{
  "launch": {"headless": false, "size": "mobile"},
  "steps": [
    {"goto": "https://service.com/login"},
    {"fill": {"selector": "input[name=email]", "value": "user@example.com"}},
    {"fill": {"selector": "input[name=password]", "value": "password123"}},
    {"click": "button[type=submit]"},
    {"wait_for": {"cookie": "session_id", "timeout": 60000}},
    {"extract_cookies": ["session_id", "csrf_token"]},
    "close"
  ]
}'
```

**Output:**
```json
{
  "success": true,
  "cookies": {
    "session_id": "abc123...",
    "csrf_token": "xyz789..."
  }
}
```

## Example: Screenshot a Page

```bash
npx tsx ~/dev/agentos/scripts/playwright-runner.ts --config '{
  "launch": {"headless": true, "size": "full"},
  "steps": [
    {"goto": "https://example.com"},
    {"wait": 2000},
    {"screenshot": {"path": "/tmp/example.png"}},
    "close"
  ]
}'
```

## Example: Extract Data

```bash
npx tsx ~/dev/agentos/scripts/playwright-runner.ts --config '{
  "steps": [
    {"goto": "https://news.site.com"},
    {"wait_for": {"selector": "article h2"}},
    {"extract": {"selector": "article h2", "as": "headline"}},
    {"extract": {"selector": "article a", "attribute": "href", "as": "link"}},
    "close"
  ]
}'
```

**Output:**
```json
{
  "success": true,
  "extracted": {
    "headline": "Breaking News Story",
    "link": "/articles/12345"
  }
}
```

## 2FA Handling

The runner automatically detects 2FA prompts and returns:
```json
{
  "success": false,
  "needs_2fa": true,
  "error": "Two-factor authentication required"
}
```

When this happens, you can:
1. Run again with `credentials.two_factor_code` set
2. Ask the user to complete 2FA manually (non-headless mode)

## Other Scripts

### Browser Check
Quick headless check if UI is rendering:
```bash
npx tsx ~/dev/agentos/scripts/browser-check.ts http://localhost:5173
```

### UI Test
Run UI test suite:
```bash
npx tsx ~/dev/agentos/scripts/ui-test.ts
```

### Visual Test
Compare visual screenshots:
```bash
npx tsx ~/dev/agentos/scripts/visual-test.ts
```

## Tips

1. **Start non-headless** for debugging — see what the browser sees
2. **Use mobile size** for auth flows — simpler UIs, fewer popups
3. **Add wait steps** after navigation — JS apps need time to render
4. **Comma-separate selectors** to try multiple: `"button.submit, input[type=submit]"`
5. **Check for 2FA** in the response before assuming success

## When to Use This

| Task | Use Playwright? |
|------|-----------------|
| Extract cookies from a site | Yes |
| Screenshot a URL | Yes |
| Scrape data from JS-rendered pages | Yes |
| Test AgentOS UI | Yes |
| Call a REST API | No — use curl |
| Read a static page | No — use curl/fetch |
| Automate repetitive form filling | Yes |

---

*This skill documents the Playwright browser automation available in AgentOS. For auth flows, cookie extraction, screenshots, and browser testing.*

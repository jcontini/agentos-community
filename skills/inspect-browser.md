# Inspect Browser Skill

> How to inspect the running AgentOS frontend from AI agents

---

## Capabilities

You can inspect the AgentOS browser/Tauri app without needing a human to open DevTools.

| Method | What it does |
|--------|-------------|
| Playwright headless | Load pages, query DOM, capture errors |
| API queries | Get backend data directly |
| debug.sh | Full diagnostic with browser check |

---

## Playwright Inspection

Run ad-hoc DOM checks with Playwright:

```bash
npx tsx -e "
import { chromium } from 'playwright';
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
  
  // Check for elements
  const hasElement = await page.\$('.your-selector');
  const elementCount = (await page.\$\$('.icon')).length;
  
  // Get text content
  const text = await page.evaluate(() => document.body.innerText.substring(0, 500));
  
  console.log(JSON.stringify({ hasElement: !!hasElement, elementCount }));
  await browser.close();
})();
"
```

### Common Patterns

**Check if component rendered:**
```javascript
const exists = await page.$('.connector-bar');
```

**Count elements:**
```javascript
const icons = await page.$$('.desktop-icons .icon');
console.log(icons.length);
```

**Get element text:**
```javascript
const text = await page.$eval('.app-title', el => el.textContent);
```

**Capture console errors:**
```javascript
const errors = [];
page.on('console', msg => {
  if (msg.type() === 'error') errors.push(msg.text());
});
```

**Wait for specific element:**
```javascript
await page.waitForSelector('.desktop-icons .icon', { timeout: 5000 });
```

---

## API Inspection

Query backend data directly (requires X-Agent header):

```bash
# Get tasks with connector info
curl -s "http://localhost:3456/api/tasks" -H "X-Agent: cursor" | jq

# Check settings
curl -s "http://localhost:3456/api/settings/current_theme" | jq

# Health check
curl -s "http://localhost:3456/api/health" | jq

# List files in drive
curl -s "http://localhost:3456/api/files" -H "X-Agent: cursor" | jq
```

---

## debug.sh

Run full diagnostics from the agentos repo:

```bash
./debug.sh
```

Checks:
- Server status (backend, Vite, Tauri)
- Theme and settings
- Browser render (uses Playwright internally)
- JS errors and failed network requests
- Database status

---

## What You Cannot Do

- **Live DevTools** — No real-time DOM inspection (use snapshots instead)
- **React component state** — Can't see useState/useContext directly  
- **Interactive debugging** — Can't set breakpoints or step through code
- **Click without scripting** — Need Playwright to automate interactions

---

## When to Use This

1. **Debugging UI issues** — "Why isn't the connector-bar showing?"
2. **Verifying renders** — "Did the desktop load correctly?"
3. **Checking for errors** — "Are there JS console errors?"
4. **Testing changes** — Before asking user to manually verify
5. **Inspecting API responses** — Check what data the frontend receives

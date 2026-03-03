/**
 * browser.ts — Persistent headed Chromium session via CDP
 *
 * Launches Chromium once with --remote-debugging-port.
 * Subsequent calls connect to the same browser — tabs, cookies, sessions all persist.
 *
 * Each invocation does one thing and exits. Browser stays alive between calls.
 * Output is always JSON to stdout (parsed by the command executor).
 *
 * Usage:
 *   npx tsx browser.ts <command> [options]
 *
 * Commands:
 *   start [--headless] [--port N]   Launch or connect to browser
 *   stop                            Kill the persistent browser
 *   status                          Check if browser is running
 *   goto <url> [--wait-until X]     Navigate to URL
 *   screenshot [--selector S] [--path P] [--full-page]
 *   click <selector>                Click an element
 *   fill <selector> <value>         Fill an input field
 *   select <selector> <value>       Select dropdown option
 *   type <selector> <text>          Type text character by character
 *   evaluate <script>               Execute JS in page context
 *   url                             Get current URL and title
 *   extract [--selector S] [--format F]  Extract page content
 *   inspect [--selector S]          Fast DOM snapshot (structured, no pixels)
 *   errors                          Reload and capture console errors
 *   wait [--selector S] [--timeout N]    Wait for selector or timeout
 *   tabs                            List open tabs
 *   new_tab [url]                   Open a new tab
 *   close_tab                       Close current tab
 */

import { spawn } from "child_process";
import http from "http";
import { Browser, chromium, Page } from "playwright";

// --- Config ---

const DEFAULT_PORT = 9222;
const USER_DATA_DIR = "/tmp/agentos-playwright-profile";

function getPort(): number {
  const idx = process.argv.indexOf("--port");
  if (idx !== -1 && process.argv[idx + 1]) {
    return parseInt(process.argv[idx + 1], 10);
  }
  return DEFAULT_PORT;
}

// --- Stdin JSON support ---
// When called from AgentOS, params arrive as JSON on stdin.
// Falls back to argv parsing for direct CLI use.

let stdinParams: Record<string, unknown> = {};

async function readStdinParams(): Promise<void> {
  if (process.stdin.isTTY) return;
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString().trim();
  if (raw) {
    try { stdinParams = JSON.parse(raw); } catch { /* not JSON, ignore */ }
  }
}

function getFlag(name: string): boolean {
  // Check stdin params (both kebab-case and snake_case)
  const snakeName = name.replace(/-/g, "_");
  const key = name in stdinParams ? name : snakeName in stdinParams ? snakeName : null;
  if (key) {
    const val = stdinParams[key];
    // Handle string "false"/"true" from template rendering
    if (typeof val === "string") {
      return val.toLowerCase() === "true";
    }
    return !!val;
  }
  return process.argv.includes(`--${name}`);
}

function getOption(name: string): string | undefined {
  // stdin JSON takes precedence (snake_case and kebab-case)
  const snakeName = name.replace(/-/g, "_");
  if (snakeName in stdinParams && stdinParams[snakeName] != null) return String(stdinParams[snakeName]);
  if (name in stdinParams && stdinParams[name] != null) return String(stdinParams[name]);
  // Fall back to argv
  const idx = process.argv.indexOf(`--${name}`);
  if (idx !== -1 && process.argv[idx + 1] && !process.argv[idx + 1].startsWith("--")) {
    return process.argv[idx + 1];
  }
  return undefined;
}

function getPositional(index: number): string | undefined {
  // For positional args (like url, selector, value), check stdin params by name
  return process.argv[index] || undefined;
}

function out(data: unknown): void {
  console.log(JSON.stringify(data));
}

function err(message: string): never {
  out({ error: message });
  process.exit(1);
}

// --- Browser management ---

async function isBrowserRunning(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`http://localhost:${port}/json/version`, (res) => {
      let data = "";
      res.on("data", (chunk: string) => (data += chunk));
      res.on("end", () => {
        try {
          JSON.parse(data);
          resolve(true);
        } catch {
          resolve(false);
        }
      });
    });
    req.on("error", () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function ensureBrowser(port: number, headless: boolean): Promise<void> {
  if (await isBrowserRunning(port)) {
    return;
  }

  const execPath = chromium.executablePath();
  if (!execPath) {
    err("Chromium not found. Run: npx playwright install chromium");
  }

  const args = [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${USER_DATA_DIR}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--window-size=1440,900",
    "--window-position=100,100",
  ];

  if (headless) {
    args.push("--headless=new");
  }

  const child = spawn(execPath, args, {
    detached: true,
    stdio: "ignore",
  });
  child.unref();

  // Wait for browser to be ready
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 500));
    if (await isBrowserRunning(port)) {
      return;
    }
  }
  err("Chromium failed to start within 15 seconds");
}

async function connectBrowser(port: number): Promise<Browser> {
  // Auto-launch if not running — one call, not two
  if (!(await isBrowserRunning(port))) {
    await ensureBrowser(port, false);
  }
  return chromium.connectOverCDP(`http://localhost:${port}`);
}

async function getPage(browser: Browser): Promise<Page> {
  const context = browser.contexts()[0];
  if (!context) {
    err("No browser context found");
  }
  const pages = context.pages();
  return (
    pages.find((p) => p.url() !== "about:blank") ||
    pages[0] ||
    (await context.newPage())
  );
}

async function killBrowser(port: number): Promise<void> {
  const { execSync } = await import("child_process");
  execSync(`lsof -ti :${port} | xargs kill -9 2>/dev/null || true`);
}

// --- Commands ---

async function cmdStart(): Promise<void> {
  const port = getPort();
  // Support both mode="headless"/"headed" and legacy headless=true/false
  const mode = getOption("mode");
  const headless = mode ? mode === "headless" : getFlag("headless");
  await ensureBrowser(port, headless);
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  out({ status: "running", port, mode: headless ? "headless" : "headed", url: page.url() });
  await browser.close();
}

async function cmdStop(): Promise<void> {
  const port = getPort();
  await killBrowser(port);
  out({ status: "stopped" });
}

async function cmdStatus(): Promise<void> {
  const port = getPort();
  const running = await isBrowserRunning(port);
  if (running) {
    try {
      const browser = await connectBrowser(port);
      const page = await getPage(browser);
      out({ running: true, port, url: page.url() });
      await browser.close();
    } catch {
      out({ running: true, port, url: null });
    }
  } else {
    out({ running: false, port, url: null });
  }
}

async function cmdGoto(): Promise<void> {
  const port = getPort();
  const url = (stdinParams.url as string) || process.argv[3];
  if (!url) err("Usage: goto <url>");
  const waitUntil = (getOption("wait-until") || "networkidle") as
    | "load"
    | "domcontentloaded"
    | "networkidle";
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await page.goto(url, { waitUntil, timeout: 30000 });
  const title = await page.title();
  out({ url: page.url(), title });
  await browser.close();
}

async function cmdScreenshot(): Promise<void> {
  const port = getPort();
  const selector = getOption("selector");
  const outPath = getOption("path") || "/tmp/screenshot.png";
  const fullPage = getFlag("full-page");
  const browser = await connectBrowser(port);
  const page = await getPage(browser);

  if (selector) {
    const el = page.locator(selector).first();
    await el.screenshot({ path: outPath });
  } else {
    await page.screenshot({ path: outPath, fullPage });
  }

  out({ path: outPath, url: page.url() });
  await browser.close();
}

async function cmdClick(): Promise<void> {
  const port = getPort();
  const selector = (stdinParams.selector as string) || process.argv[3];
  if (!selector) err("Usage: click <selector>");
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await page.locator(selector).first().click();
  await page.waitForTimeout(500);
  out({ selector, url: page.url(), title: await page.title() });
  await browser.close();
}

async function cmdFill(): Promise<void> {
  const port = getPort();
  const selector = (stdinParams.selector as string) || process.argv[3];
  const value = (stdinParams.value as string) ?? process.argv[4];
  if (!selector || value === undefined) err("Usage: fill <selector> <value>");
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await page.locator(selector).first().fill(value);
  out({ selector, value });
  await browser.close();
}

async function cmdSelect(): Promise<void> {
  const port = getPort();
  const selector = (stdinParams.selector as string) || process.argv[3];
  const value = (stdinParams.value as string) || process.argv[4];
  if (!selector || !value) err("Usage: select <selector> <value>");
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await page.locator(selector).first().selectOption(value);
  out({ selector, value });
  await browser.close();
}

async function cmdType(): Promise<void> {
  const port = getPort();
  const selector = (stdinParams.selector as string) || process.argv[3];
  const text = (stdinParams.text as string) ?? process.argv[4];
  if (!selector || text === undefined) err("Usage: type <selector> <text>");
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await page.locator(selector).first().pressSequentially(text);
  out({ selector, text });
  await browser.close();
}

async function cmdEvaluate(): Promise<void> {
  const port = getPort();
  const script = (stdinParams.script as string) || process.argv[3];
  if (!script) err("Usage: evaluate <script>");
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  const result = await page.evaluate(script);
  out({ result });
  await browser.close();
}

async function cmdUrl(): Promise<void> {
  const port = getPort();
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  out({ url: page.url(), title: await page.title() });
  await browser.close();
}

async function cmdExtract(): Promise<void> {
  const port = getPort();
  const selector = getOption("selector") || "body";
  const format = getOption("format") || "text";
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  const locator = page.locator(selector).first();

  let content: string;
  if (format === "html") {
    content = await locator.innerHTML();
  } else {
    content = await locator.innerText();
  }

  const title = await page.title();
  out({ url: page.url(), title, content, selector, format });
  await browser.close();
}

async function cmdErrors(): Promise<void> {
  const port = getPort();
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  const errors: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));

  await page.reload({ waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(2000);

  out({ errors, count: errors.length, url: page.url() });
  await browser.close();
}

async function cmdWait(): Promise<void> {
  const port = getPort();
  const selector = getOption("selector");
  const timeout = parseInt(getOption("timeout") || "10000", 10);
  const browser = await connectBrowser(port);
  const page = await getPage(browser);

  if (selector) {
    await page.waitForSelector(selector, { timeout });
    out({ status: "visible", selector });
  } else {
    await page.waitForTimeout(timeout);
    out({ status: "timeout_elapsed", timeout });
  }
  await browser.close();
}

async function cmdTabs(): Promise<void> {
  const port = getPort();
  const browser = await connectBrowser(port);
  const context = browser.contexts()[0];
  const pages = context.pages();
  const tabs = await Promise.all(
    pages.map(async (p, i) => ({
      index: i,
      url: p.url(),
      title: await p.title(),
    }))
  );
  out({ tabs, count: tabs.length });
  await browser.close();
}

async function cmdNewTab(): Promise<void> {
  const port = getPort();
  const url = (stdinParams.url as string) || process.argv[3];
  const browser = await connectBrowser(port);
  const context = browser.contexts()[0];
  const page = await context.newPage();
  if (url) {
    await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
  }
  out({ url: page.url(), title: await page.title() });
  await browser.close();
}

async function cmdCloseTab(): Promise<void> {
  const port = getPort();
  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  const url = page.url();
  await page.close();
  out({ closed: url });
  await browser.close();
}

async function cmdInspect(): Promise<void> {
  const port = getPort();
  const selector = getOption("selector") || "body";
  const browser = await connectBrowser(port);
  const page = await getPage(browser);

  // Use string-based evaluate to avoid tsx/esbuild __name decoration issues
  const inspectScript = `
    (function(sel) {
      function desc(el, depth, maxDepth) {
        if (depth > maxDepth) return null;
        var tag = el.tagName.toLowerCase();
        var attrs = {};
        var names = ["id", "class", "href", "src", "type", "name", "value",
          "placeholder", "aria-label", "role", "data-testid", "disabled", "checked"];
        for (var i = 0; i < names.length; i++) {
          var val = el.getAttribute(names[i]);
          if (val) attrs[names[i]] = val.length > 100 ? val.slice(0, 100) + "…" : val;
        }
        var text = "";
        for (var j = 0; j < el.childNodes.length; j++) {
          var node = el.childNodes[j];
          if (node.nodeType === 3) {
            var t = (node.textContent || "").trim();
            if (t) text += (text ? " " : "") + (t.length > 80 ? t.slice(0, 80) + "…" : t);
          }
        }
        var children = [];
        for (var k = 0; k < el.children.length; k++) {
          var child = el.children[k];
          var style = window.getComputedStyle(child);
          if (style.display === "none" || style.visibility === "hidden") continue;
          if (["SCRIPT", "STYLE", "NOSCRIPT", "SVG"].indexOf(child.tagName) >= 0) continue;
          var d = desc(child, depth + 1, maxDepth);
          if (d) children.push(d);
        }
        var result = { tag: tag };
        if (Object.keys(attrs).length) result.attrs = attrs;
        if (text) result.text = text;
        if (children.length) result.children = children;
        return result;
      }
      var root = document.querySelector(sel);
      if (!root) return { error: "Selector not found: " + sel };
      return desc(root, 0, 5);
    })(${JSON.stringify(selector)})
  `;

  const snapshot = await page.evaluate(inspectScript);
  out({ url: page.url(), title: await page.title(), selector, snapshot });
  await browser.close();
}

// --- Dispatch ---

const commands: Record<string, () => Promise<void>> = {
  start: cmdStart,
  stop: cmdStop,
  status: cmdStatus,
  goto: cmdGoto,
  screenshot: cmdScreenshot,
  click: cmdClick,
  fill: cmdFill,
  select: cmdSelect,
  type: cmdType,
  evaluate: cmdEvaluate,
  url: cmdUrl,
  extract: cmdExtract,
  inspect: cmdInspect,
  errors: cmdErrors,
  wait: cmdWait,
  tabs: cmdTabs,
  new_tab: cmdNewTab,
  close_tab: cmdCloseTab,
};

async function main() {
  await readStdinParams();
  const command = process.argv[2];
  if (!command || !commands[command]) {
    out({
      error: command ? `Unknown command: ${command}` : "No command specified",
      commands: Object.keys(commands),
    });
    process.exit(1);
  }
  await commands[command]();
}

main().catch((e) => {
  out({ error: e.message });
  process.exit(1);
});

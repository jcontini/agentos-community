/**
 * browser.ts — Lightpanda headless browser via CDP
 *
 * Lightpanda runs as a persistent CDP server (lightpanda serve --port 9223).
 * Playwright's chromium client connects over CDP just as it does with Chromium.
 * Each invocation does one thing and exits. The server stays alive between calls.
 *
 * Also supports a native `fetch` command that uses Lightpanda's binary directly
 * (no CDP, no persistent process — fastest possible content extraction).
 *
 * Usage:
 *   npx tsx browser.ts <command> [options]
 *
 * Commands:
 *   fetch                           Native lightpanda fetch (fastest, no CDP)
 *   start [--port N] [--timeout N]  Launch lightpanda serve CDP server
 *   stop                            Kill the lightpanda server
 *   status                          Check if server is running
 *   goto <url> [--wait-until X]     Navigate to URL
 *   screenshot [--selector S] [--path P] [--full-page]
 *   click <selector>                Click an element
 *   fill <selector> <value>         Fill an input field
 *   evaluate <script>               Execute JS in page context
 *   url                             Get current URL and title
 *   extract [--selector S] [--format F]  Extract page content
 *   inspect [--selector S]          Fast DOM snapshot
 *   wait [--selector S] [--timeout N]    Wait for selector or timeout
 *   network_capture --url URL       Navigate and capture XHR/fetch responses
 */

import { execSync, spawnSync, spawn } from "child_process";
import { readFileSync, writeFileSync } from "fs";
import * as http from "http";
import { Browser, chromium, Page } from "playwright";

// --- Config ---

const DEFAULT_PORT = 9223; // Use 9223 to avoid colliding with playwright skill's Chromium on 9222
const DEFAULT_TIMEOUT = 30; // seconds
const STATE_FILE = "/tmp/agentos-lightpanda-state.json";

function getLightpandaBin(): string {
  // Check common locations
  for (const p of [
    process.env.LIGHTPANDA_BIN,
    `${process.env.HOME}/bin/lightpanda`,
    "/usr/local/bin/lightpanda",
    "/opt/homebrew/bin/lightpanda",
  ]) {
    if (!p) continue;
    try {
      execSync(`test -x "${p}"`, { stdio: "ignore" });
      return p;
    } catch {
      // not found at this path
    }
  }
  // Fall back to PATH lookup
  try {
    return execSync("which lightpanda", { encoding: "utf8" }).trim();
  } catch {
    return "lightpanda";
  }
}

const LP_BIN = getLightpandaBin();

// --- Stdin JSON support ---

let stdinParams: Record<string, unknown> = {};

async function readStdinParams(): Promise<void> {
  if (process.stdin.isTTY) return;
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString().trim();
  if (raw) {
    try {
      stdinParams = JSON.parse(raw);
    } catch {
      /* not JSON, ignore */
    }
  }
}

function getFlag(name: string): boolean {
  const snakeName = name.replace(/-/g, "_");
  const key =
    name in stdinParams ? name : snakeName in stdinParams ? snakeName : null;
  if (key) {
    const val = stdinParams[key];
    if (typeof val === "string") return val.toLowerCase() === "true";
    return !!val;
  }
  return process.argv.includes(`--${name}`);
}

function getOption(name: string): string | undefined {
  const snakeName = name.replace(/-/g, "_");
  if (snakeName in stdinParams && stdinParams[snakeName] != null)
    return String(stdinParams[snakeName]);
  if (name in stdinParams && stdinParams[name] != null)
    return String(stdinParams[name]);
  const idx = process.argv.indexOf(`--${name}`);
  if (
    idx !== -1 &&
    process.argv[idx + 1] &&
    !process.argv[idx + 1].startsWith("--")
  ) {
    return process.argv[idx + 1];
  }
  return undefined;
}

function getPort(): number {
  const p = getOption("port");
  return p ? parseInt(p, 10) : DEFAULT_PORT;
}

function out(data: unknown): void {
  console.log(JSON.stringify(data));
}

function err(message: string): never {
  out({ error: message });
  process.exit(1);
}

// --- Lightpanda server management ---

async function isServerRunning(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(
      `http://127.0.0.1:${port}/json/version`,
      { timeout: 2000 },
      (res) => {
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
      }
    );
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function ensureServer(port: number, timeoutSecs: number): Promise<void> {
  if (await isServerRunning(port)) return;

  // Start lightpanda serve — do NOT use --timeout 0 (known bug on macOS arm64)
  const child = spawn(
    LP_BIN,
    ["serve", "--host", "127.0.0.1", "--port", String(port), "--timeout", String(timeoutSecs)],
    { detached: true, stdio: "ignore" }
  );
  child.unref();

  // Wait for server to be ready (up to 8 seconds)
  for (let i = 0; i < 16; i++) {
    await new Promise((r) => setTimeout(r, 500));
    if (await isServerRunning(port)) return;
  }
  err(`Lightpanda failed to start on port ${port} within 8 seconds`);
}

async function connectBrowser(port: number): Promise<Browser> {
  // Auto-launch if not running
  if (!(await isServerRunning(port))) {
    await ensureServer(port, DEFAULT_TIMEOUT);
  }
  return chromium.connectOverCDP(`http://127.0.0.1:${port}`);
}

async function getPage(browser: Browser): Promise<Page> {
  // Lightpanda requires a fresh context + new page per connection.
  // Unlike Chromium, it does not expose pre-existing contexts via CDP.
  const context = await browser.newContext();
  return context.newPage();
}

// --- State file (stores last navigated URL across calls) ---

function loadState(): { url: string; port: number } {
  try {
    return JSON.parse(readFileSync(STATE_FILE, "utf8"));
  } catch {
    return { url: "", port: DEFAULT_PORT };
  }
}

function saveState(url: string, port: number): void {
  try {
    writeFileSync(STATE_FILE, JSON.stringify({ url, port }));
  } catch {
    /* non-fatal */
  }
}

function clearState(): void {
  try {
    writeFileSync(STATE_FILE, JSON.stringify({ url: "", port: DEFAULT_PORT }));
  } catch {
    /* non-fatal */
  }
}

// Navigate to the given URL, or re-navigate to last known URL if none provided
async function navigateTo(
  page: Page,
  port: number,
  url?: string,
  waitUntil: "load" | "domcontentloaded" | "networkidle" = "domcontentloaded"
): Promise<void> {
  const target = url || loadState().url;
  if (!target) err("No URL provided and no previous navigation to resume");
  await page.goto(target, { waitUntil, timeout: 30000 });
  saveState(page.url(), port);
}

async function killServer(port: number): Promise<void> {
  try {
    execSync(`lsof -ti :${port} | xargs kill -9 2>/dev/null || true`);
  } catch {
    // ignore
  }
}

// --- Commands ---

async function cmdFetch(): Promise<void> {
  const url = (stdinParams.url as string) || process.argv[3];
  if (!url) err("Usage: fetch --url <url>");

  const format = (getOption("format") || "markdown") as string;
  const stripMode = (getOption("strip-mode") || getOption("strip_mode") || "") as string;

  const validFormats = ["html", "markdown", "semantic_tree", "semantic_tree_text"];
  if (!validFormats.includes(format)) {
    err(`Invalid format: ${format}. Must be one of: ${validFormats.join(", ")}`);
  }

  const args = ["fetch", "--dump", format];
  if (stripMode) args.push("--strip_mode", stripMode);
  args.push(url);

  // Use spawnSync with array args to avoid shell injection on URLs with special chars
  const result = spawnSync(LP_BIN, args, {
    encoding: "utf8",
    timeout: 25000,
    maxBuffer: 10 * 1024 * 1024, // 10MB
  });

  if (result.error) {
    err(`Lightpanda fetch failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    err(`Lightpanda fetch exited ${result.status}: ${result.stderr?.trim() || "no stderr"}`);
  }

  out({ url, format, content: (result.stdout || "").trim() });
}

async function cmdStart(): Promise<void> {
  const port = getPort();
  const timeoutSecs = parseInt(getOption("timeout") || String(DEFAULT_TIMEOUT), 10);
  await ensureServer(port, timeoutSecs);
  // Verify connection works
  const browser = await connectBrowser(port);
  await browser.close();
  const state = loadState();
  out({ status: "running", port, mode: "headless", current_url: state.url || null });
}

async function cmdStop(): Promise<void> {
  const port = getPort();
  await killServer(port);
  clearState();
  out({ status: "stopped", port });
}

async function cmdStatus(): Promise<void> {
  const port = getPort();
  const running = await isServerRunning(port);
  const state = loadState();
  out({ running, port, current_url: state.url || null });
}

async function cmdGoto(): Promise<void> {
  const port = getPort();
  const url = (stdinParams.url as string) || process.argv[3];
  if (!url) err("Usage: goto <url>");

  const waitUntil = (getOption("wait-until") || "domcontentloaded") as
    | "load"
    | "domcontentloaded"
    | "networkidle";

  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await page.goto(url, { waitUntil, timeout: 30000 });
  const finalUrl = page.url();
  const title = await page.title();
  saveState(finalUrl, port);
  out({ url: finalUrl, title });
  await browser.close();
}

async function cmdScreenshot(): Promise<void> {
  const port = getPort();
  const selector = getOption("selector");
  const outPath = getOption("path") || "/tmp/lp-screenshot.png";
  const fullPage = getFlag("full-page");

  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await navigateTo(page, port);

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
  await navigateTo(page, port);
  await page.locator(selector).first().click();
  await page.waitForTimeout(500);
  const finalUrl = page.url();
  saveState(finalUrl, port);
  out({ selector, url: finalUrl, title: await page.title() });
  await browser.close();
}

async function cmdFill(): Promise<void> {
  const port = getPort();
  const selector = (stdinParams.selector as string) || process.argv[3];
  const value = (stdinParams.value as string) ?? process.argv[4];
  if (!selector || value === undefined) err("Usage: fill <selector> <value>");

  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await navigateTo(page, port);
  await page.locator(selector).first().fill(value);
  out({ selector, value });
  await browser.close();
}

async function cmdEvaluate(): Promise<void> {
  const port = getPort();
  const script = (stdinParams.script as string) || process.argv[3];
  if (!script) err("Usage: evaluate <script>");

  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await navigateTo(page, port);
  const result = await page.evaluate(script);
  out({ result });
  await browser.close();
}

async function cmdUrl(): Promise<void> {
  // Return the last known URL from state — no re-navigation needed.
  // Re-navigating just to confirm the URL is wasteful and can cause state drift.
  const state = loadState();
  out({ url: state.url || "", title: null });
}

async function cmdExtract(): Promise<void> {
  const port = getPort();
  const selector = getOption("selector") || "body";
  const format = getOption("format") || "text";

  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await navigateTo(page, port);
  const locator = page.locator(selector).first();

  let content: string;
  if (format === "html") {
    content = await locator.innerHTML();
  } else {
    content = await locator.innerText();
  }

  out({ url: page.url(), title: await page.title(), content, selector, format });
  await browser.close();
}

async function cmdInspect(): Promise<void> {
  const port = getPort();
  const selector = getOption("selector") || "body";

  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await navigateTo(page, port);

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
          if (["SCRIPT", "STYLE", "NOSCRIPT"].indexOf(child.tagName) >= 0) continue;
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

async function cmdWait(): Promise<void> {
  const port = getPort();
  const selector = getOption("selector");
  const timeout = parseInt(getOption("timeout") || "10000", 10);

  const browser = await connectBrowser(port);
  const page = await getPage(browser);
  await navigateTo(page, port);

  if (selector) {
    await page.waitForSelector(selector, { timeout });
    out({ status: "visible", selector });
  } else {
    await page.waitForTimeout(timeout);
    out({ status: "timeout_elapsed", timeout });
  }
  await browser.close();
}

async function cmdNetworkCapture(): Promise<void> {
  const port = getPort();
  const url = (stdinParams.url as string) || process.argv[3];
  if (!url) err("Usage: network_capture --url <url>");

  const pattern = (stdinParams.pattern as string) || getOption("pattern") || "**";
  const waitMs = parseInt(
    (stdinParams.wait as string) || getOption("wait") || "5000",
    10
  );
  const captureBody =
    (stdinParams.capture_body as boolean) ?? getFlag("capture-body") ?? true;

  const browser = await connectBrowser(port);
  const context = await browser.newContext();

  const captured: Array<{
    url: string;
    method: string;
    status: number;
    contentType: string;
    resourceType: string;
    body?: unknown;
    size?: number;
  }> = [];

  // Build glob regex from pattern
  const patternRegex = new RegExp(
    "^" +
      pattern
        .replace(/[.+^${}()|[\]\\]/g, "\\$&")
        .replace(/\*\*/g, "§DOUBLE§")
        .replace(/\*/g, "[^/]*")
        .replace(/§DOUBLE§/g, ".*")
        .replace(/\?/g, "[^/]") +
      "$"
  );

  const page = await context.newPage();

  page.on("response", async (response) => {
    const respUrl = response.url();
    if (!patternRegex.test(respUrl)) return;

    const status = response.status();
    const headers = response.headers();
    const contentType = headers["content-type"] || "";
    const resourceType = response.request().resourceType();

    if (
      pattern === "**" &&
      ["image", "stylesheet", "font", "media"].includes(resourceType)
    )
      return;

    const entry: (typeof captured)[0] = {
      url: respUrl,
      method: response.request().method(),
      status,
      contentType,
      resourceType,
    };

    if (captureBody && contentType.includes("application/json") && status < 400) {
      try {
        entry.body = await response.json();
      } catch {
        try {
          const text = await response.text();
          entry.body = text;
          entry.size = text.length;
        } catch {
          /* skip */
        }
      }
    }

    captured.push(entry);
  });

  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  } catch {
    // Ignore navigation errors — page may still fire requests
  }

  await page.waitForTimeout(waitMs);

  out({
    url: page.url(),
    title: await page.title(),
    captured,
    count: captured.length,
  });
  await browser.close();
}

// --- Dispatch ---

const commands: Record<string, () => Promise<void>> = {
  fetch: cmdFetch,
  start: cmdStart,
  stop: cmdStop,
  status: cmdStatus,
  goto: cmdGoto,
  screenshot: cmdScreenshot,
  click: cmdClick,
  fill: cmdFill,
  evaluate: cmdEvaluate,
  url: cmdUrl,
  extract: cmdExtract,
  inspect: cmdInspect,
  wait: cmdWait,
  network_capture: cmdNetworkCapture,
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
  out({ error: e.message || String(e) });
  process.exit(1);
});

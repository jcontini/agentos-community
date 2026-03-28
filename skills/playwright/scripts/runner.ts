#!/usr/bin/env npx tsx
/**
 * Playwright Runner - Generic browser automation executor
 * 
 * Executes browser automation steps defined in JSON format.
 * Used by AgentOS for cookie-based authentication flows.
 * 
 * Usage:
 *   echo '{"steps":[...]}' | npx tsx scripts/playwright-runner.ts
 *   npx tsx scripts/playwright-runner.ts --config '{"steps":[...]}'
 * 
 * Output:
 *   {"success": true, "cookies": {...}, "extracted": {...}}
 *   {"success": false, "error": "..."}
 */

import { chromium, Browser, BrowserContext, Page } from 'playwright';

// ============================================================================
// Types
// ============================================================================

interface RunnerConfig {
  /** Browser automation steps to execute */
  steps: Step[];
  /** Launch options */
  launch?: {
    /** Run in headless mode (default: false for auth flows) */
    headless?: boolean;
    /** Slow down actions by this many ms (useful for debugging) */
    slowMo?: number;
    /** Window size preset: 'mobile' (iPhone), 'compact', 'full' (default: 'mobile') */
    size?: 'mobile' | 'compact' | 'full';
  };
  /** Credentials for automated login (optional) */
  credentials?: {
    username?: string;
    password?: string;
    two_factor_code?: string;
  };
}

type Step =
  | { goto: string }
  | { click: string }
  | { dblclick: string }  // Double-click for opening icons
  | { right_click: string }  // Right-click for context menus
  | { fill: { selector: string; value: string } }
  | { type: { selector: string; value: string } }
  | { wait_for: WaitCondition }
  | { wait: number }  // Wait for N milliseconds
  | { extract_cookies: string[] | { names: string[] } }
  | { extract: { selector: string; attribute?: string; as: string } }
  | { screenshot: { path: string } }
  | { close: true }
  | 'close';

interface WaitCondition {
  /** Wait for a cookie to exist */
  cookie?: string;
  /** Wait for a selector to appear */
  selector?: string;
  /** Wait for URL to match pattern */
  url_matches?: string;
  /** Wait for any of these conditions */
  any?: WaitCondition[];
  /** Timeout in ms (default: 30000) */
  timeout?: number;
}

interface RunnerResult {
  success: boolean;
  cookies?: Record<string, string>;
  extracted?: Record<string, string>;
  error?: string;
  needs_2fa?: boolean;
}

// ============================================================================
// Step Executors
// ============================================================================

async function executeGoto(page: Page, url: string): Promise<void> {
  console.error(`[runner] goto: ${url}`);
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  // Wait a bit for JS to initialize (important for Instagram's React app)
  await new Promise(r => setTimeout(r, 1500));
}

async function executeClick(page: Page, selector: string): Promise<void> {
  console.error(`[runner] click: ${selector}`);
  
  // Handle comma-separated selectors (try each one)
  const selectors = selector.split(',').map(s => s.trim());
  
  for (const sel of selectors) {
    try {
      const element = page.locator(sel).first();
      if (await element.count() > 0 && await element.isVisible()) {
        await element.click();
        console.error(`[runner] clicked using: ${sel}`);
        // Wait for navigation/response after click
        await new Promise(r => setTimeout(r, 500));
        return;
      }
    } catch {
      // Try next selector
    }
  }
  
  // Fallback: try the original selector as-is
  await page.click(selector);
}

async function executeDblClick(page: Page, selector: string): Promise<void> {
  console.error(`[runner] dblclick: ${selector}`);
  
  // Handle comma-separated selectors (try each one)
  const selectors = selector.split(',').map(s => s.trim());
  
  for (const sel of selectors) {
    try {
      const element = page.locator(sel).first();
      if (await element.count() > 0 && await element.isVisible()) {
        await element.dblclick();
        console.error(`[runner] double-clicked using: ${sel}`);
        // Wait for window to open
        await new Promise(r => setTimeout(r, 500));
        return;
      }
    } catch {
      // Try next selector
    }
  }
  
  // Fallback: try the original selector as-is
  await page.dblclick(selector);
}

async function executeRightClick(page: Page, selector: string): Promise<void> {
  console.error(`[runner] right_click: ${selector}`);
  
  // Handle comma-separated selectors (try each one)
  const selectors = selector.split(',').map(s => s.trim());
  
  for (const sel of selectors) {
    try {
      const element = page.locator(sel).first();
      if (await element.count() > 0 && await element.isVisible()) {
        await element.click({ button: 'right' });
        console.error(`[runner] right-clicked using: ${sel}`);
        // Wait for context menu to appear
        await new Promise(r => setTimeout(r, 300));
        return;
      }
    } catch {
      // Try next selector
    }
  }
  
  // Fallback: try the original selector as-is
  await page.click(selector, { button: 'right' });
}

async function executeFill(page: Page, selector: string, value: string): Promise<void> {
  console.error(`[runner] fill: ${selector}`);
  
  // Handle comma-separated selectors (try each one)
  const selectors = selector.split(',').map(s => s.trim());
  
  for (const sel of selectors) {
    try {
      const element = page.locator(sel).first();
      if (await element.count() > 0) {
        await element.fill(value);
        console.error(`[runner] filled using: ${sel}`);
        // Small delay after fill for Instagram's JS to process
        await new Promise(r => setTimeout(r, 100));
        return;
      }
    } catch {
      // Try next selector
    }
  }
  
  // Fallback: try the original selector as-is
  await page.fill(selector, value);
}

async function executeType(page: Page, selector: string, value: string): Promise<void> {
  console.error(`[runner] type: ${selector}`);
  await page.locator(selector).pressSequentially(value, { delay: 50 });
}

async function executeWaitFor(
  page: Page,
  context: BrowserContext,
  condition: WaitCondition
): Promise<void> {
  const timeout = condition.timeout ?? 300000; // 5 min default for auth
  const startTime = Date.now();

  console.error(`[runner] wait_for: ${JSON.stringify(condition)} (timeout: ${timeout}ms)`);

  // Handle "any" condition (wait for first match)
  if (condition.any && condition.any.length > 0) {
    await Promise.race(
      condition.any.map((c) => executeWaitFor(page, context, { ...c, timeout }))
    );
    return;
  }

  // Poll for condition
  while (Date.now() - startTime < timeout) {
    // Check cookie condition
    if (condition.cookie) {
      const cookies = await context.cookies();
      const found = cookies.find((c) => c.name === condition.cookie);
      if (found) {
        console.error(`[runner] cookie found: ${condition.cookie}`);
        return;
      }
    }

    // Check selector condition
    if (condition.selector) {
      try {
        const element = page.locator(condition.selector);
        if ((await element.count()) > 0) {
          console.error(`[runner] selector found: ${condition.selector}`);
          return;
        }
      } catch {
        // Selector not found yet
      }
    }

    // Check URL condition
    if (condition.url_matches) {
      const currentUrl = page.url();
      const pattern = new RegExp(condition.url_matches);
      if (pattern.test(currentUrl)) {
        console.error(`[runner] URL matches: ${condition.url_matches}`);
        return;
      }
    }

    // Wait before next poll
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(`Timeout waiting for condition: ${JSON.stringify(condition)}`);
}

async function executeExtractCookies(
  context: BrowserContext,
  names: string[]
): Promise<Record<string, string>> {
  console.error(`[runner] extract_cookies: ${names.join(', ')}`);
  const allCookies = await context.cookies();
  const result: Record<string, string> = {};

  for (const name of names) {
    const cookie = allCookies.find((c) => c.name === name);
    if (cookie) {
      result[name] = cookie.value;
    } else {
      console.error(`[runner] warning: cookie not found: ${name}`);
    }
  }

  return result;
}

async function executeExtract(
  page: Page,
  selector: string,
  attribute: string | undefined,
  key: string
): Promise<string | null> {
  console.error(`[runner] extract: ${selector} -> ${key}`);
  try {
    const element = page.locator(selector).first();
    if ((await element.count()) === 0) {
      return null;
    }

    if (attribute === 'textContent' || !attribute) {
      return await element.textContent();
    } else if (attribute === 'innerHTML') {
      return await element.innerHTML();
    } else if (attribute === 'innerText') {
      return await element.innerText();
    } else {
      return await element.getAttribute(attribute);
    }
  } catch (e) {
    console.error(`[runner] extract failed: ${e}`);
    return null;
  }
}

async function executeScreenshot(page: Page, path: string): Promise<void> {
  console.error(`[runner] screenshot: ${path}`);
  await page.screenshot({ path });
}

// ============================================================================
// Main Runner
// ============================================================================

async function run(config: RunnerConfig): Promise<RunnerResult> {
  let browser: Browser | null = null;
  let context: BrowserContext | null = null;
  let page: Page | null = null;

  const cookies: Record<string, string> = {};
  const extracted: Record<string, string> = {};

  try {
    // Launch browser
    const headless = config.launch?.headless ?? false;
    const size = config.launch?.size ?? 'mobile';
    
    // Window size presets
    const sizes = {
      mobile: { width: 390, height: 844 },   // iPhone 14 Pro
      compact: { width: 480, height: 720 },  // Small desktop
      full: { width: 1280, height: 800 },    // Full desktop
    };
    const viewport = sizes[size];
    
    console.error(`[runner] launching browser (headless: ${headless}, size: ${size})`);
    
    browser = await chromium.launch({
      headless,
      slowMo: config.launch?.slowMo,
      args: [
        `--window-size=${viewport.width},${viewport.height + 100}`, // +100 for chrome
        '--window-position=100,100',
        '--disable-infobars',
        '--disable-blink-features=AutomationControlled', // anti-detection: removes navigator.webdriver=true
      ],
    });

    // Anti-detection context: realistic UA, locale, timezone to avoid fingerprint mismatches
    context = await browser.newContext({
      viewport,
      userAgent: size === 'mobile'
        ? 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      isMobile: size === 'mobile',
      hasTouch: size === 'mobile',
      locale: 'en-US',
      timezoneId: 'America/New_York',
    });

    page = await context.newPage();

    // Anti-detection: override navigator.webdriver before any page JS runs
    await context.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => false });
    });

    // Execute steps
    for (const step of config.steps) {
      // Handle 'close' as string
      if (step === 'close') {
        console.error('[runner] close');
        break;
      }

      if ('goto' in step) {
        await executeGoto(page, step.goto);
      } else if ('click' in step) {
        await executeClick(page, step.click);
      } else if ('dblclick' in step) {
        await executeDblClick(page, step.dblclick);
      } else if ('right_click' in step) {
        await executeRightClick(page, step.right_click);
      } else if ('fill' in step) {
        await executeFill(page, step.fill.selector, step.fill.value);
      } else if ('type' in step) {
        await executeType(page, step.type.selector, step.type.value);
      } else if ('wait_for' in step) {
        await executeWaitFor(page, context, step.wait_for);
      } else if ('wait' in step) {
        console.error(`[runner] wait: ${step.wait}ms`);
        await new Promise(r => setTimeout(r, step.wait));
      } else if ('extract_cookies' in step) {
        const names = Array.isArray(step.extract_cookies)
          ? step.extract_cookies
          : step.extract_cookies.names;
        Object.assign(cookies, await executeExtractCookies(context, names));
      } else if ('extract' in step) {
        const value = await executeExtract(
          page,
          step.extract.selector,
          step.extract.attribute,
          step.extract.as
        );
        if (value !== null) {
          extracted[step.extract.as] = value;
        }
      } else if ('screenshot' in step) {
        await executeScreenshot(page, step.screenshot.path);
      } else if ('press' in step) {
        console.error(`[runner] press: ${step.press}`);
        await page.keyboard.press(step.press);
      } else if ('close' in step) {
        console.error('[runner] close');
        break;
      }
      
      // After each step, check for 2FA prompt
      const currentUrl = page.url();
      const twoFactorSelectors = [
        'input[name="verificationCode"]',
        'input[name="approvals_code"]', 
        'input[autocomplete="one-time-code"]',
        '[aria-label*="security code"]',
        '[aria-label*="verification code"]',
      ];
      
      for (const selector of twoFactorSelectors) {
        try {
          if (await page.locator(selector).count() > 0) {
            console.error('[runner] 2FA prompt detected');
            return {
              success: false,
              needs_2fa: true,
              error: 'Two-factor authentication required',
            };
          }
        } catch {
          // Ignore
        }
      }
    }

    // Final check for 2FA before returning success
    const pageContent = await page.content();
    if (pageContent.includes('verificationCode') || 
        pageContent.includes('security code') ||
        pageContent.includes('Enter the code')) {
      return {
        success: false,
        needs_2fa: true,
        error: 'Two-factor authentication required',
      };
    }

    return {
      success: true,
      cookies: Object.keys(cookies).length > 0 ? cookies : undefined,
      extracted: Object.keys(extracted).length > 0 ? extracted : undefined,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`[runner] error: ${message}`);
    return {
      success: false,
      error: message,
    };
  } finally {
    if (browser) {
      console.error('[runner] closing browser');
      await browser.close();
    }
  }
}

// ============================================================================
// CLI Entry Point
// ============================================================================

async function main(): Promise<void> {
  let configJson: string | undefined;

  // Check for --config argument
  const configIdx = process.argv.indexOf('--config');
  if (configIdx !== -1 && process.argv[configIdx + 1]) {
    configJson = process.argv[configIdx + 1];
  }

  // Otherwise read from stdin
  if (!configJson) {
    const chunks: Buffer[] = [];
    for await (const chunk of process.stdin) {
      chunks.push(chunk);
    }
    configJson = Buffer.concat(chunks).toString('utf8').trim();
  }

  if (!configJson) {
    console.error('Usage: echo \'{"steps":[...]}\' | npx tsx scripts/playwright-runner.ts');
    console.error('       npx tsx scripts/playwright-runner.ts --config \'{"steps":[...]}\'');
    process.exit(1);
  }

  let config: RunnerConfig;
  try {
    config = JSON.parse(configJson);
  } catch (e) {
    console.error(`Failed to parse config JSON: ${e}`);
    process.exit(1);
  }

  if (!config.steps || !Array.isArray(config.steps)) {
    console.error('Config must have a "steps" array');
    process.exit(1);
  }

  const result = await run(config);
  
  // Output result as JSON to stdout
  console.log(JSON.stringify(result));
  
  process.exit(result.success ? 0 : 1);
}

main().catch((e) => {
  console.error(`Fatal error: ${e}`);
  process.exit(1);
});

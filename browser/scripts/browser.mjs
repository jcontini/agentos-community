#!/usr/bin/env node
/**
 * Browser automation script using Playwright
 * 
 * Captures console logs, errors, and network activity for debugging.
 * Screenshots are optional and expensive (tokens) - use sparingly.
 * 
 * For play_flow: Plays back Chrome DevTools Recorder JSON format.
 * - playback_mode: "browser" uses Playwright native, "native" uses OS-level input (enigo)
 * 
 * For record_flow: Records user interactions as Chrome DevTools JSON.
 * 
 * Session Management:
 * - start_session: Launch browser server, keep it running
 * - Other actions can use session_id to connect to existing browser
 * - end_session: Close the browser server
 */

import { chromium } from 'playwright';
import { join, dirname } from 'path';
import { homedir } from 'os';
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from 'fs';
import { spawn, execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const action = process.env.PARAM_ACTION || process.argv[2];
const url = process.env.PARAM_URL;
const selector = process.env.PARAM_SELECTOR;
const text = process.env.PARAM_TEXT;
const script = process.env.PARAM_SCRIPT;
const recordingJson = process.env.PARAM_RECORDING;
const sessionId = process.env.PARAM_SESSION_ID;
const waitMs = parseInt(process.env.PARAM_WAIT_MS || '1000', 10);
const includeScreenshot = process.env.PARAM_SCREENSHOT === 'true';
const headless = process.env.SETTING_HEADLESS !== 'false';
const slowMo = parseInt(process.env.SETTING_SLOW_MO || '0', 10);
const timeout = parseInt(process.env.SETTING_TIMEOUT || '30', 10) * 1000;
const locale = process.env.SETTING_LOCALE || 'en-US';
const userAgentSetting = process.env.SETTING_USER_AGENT || 'chrome';
const colorScheme = process.env.SETTING_COLOR_SCHEME || 'light';
// Recording format: simple (action-based) or chrome_devtools
const recordingFormat = process.env.SETTING_RECORDING_FORMAT || 'simple';
// Playback mode: param overrides setting
const playbackMode = process.env.PARAM_PLAYBACK_MODE || process.env.SETTING_DEFAULT_PLAYBACK_MODE || 'browser';

// Recordings storage
const recordingsDir = join(homedir(), '.agentos', 'recordings');

const userAgents = {
  chrome: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  firefox: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
  safari: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
  mobile: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
};

const userAgent = userAgents[userAgentSetting] || userAgents.chrome;
const downloadsDir = process.env.AGENTOS_DOWNLOADS || join(homedir(), 'Downloads');

// Session storage
const sessionsDir = join(homedir(), '.agentos');
const sessionsFile = join(sessionsDir, 'browser-sessions.json');

function loadSessions() {
  try {
    if (existsSync(sessionsFile)) {
      return JSON.parse(readFileSync(sessionsFile, 'utf-8'));
    }
  } catch (e) {
    // Ignore errors, return empty
  }
  return {};
}

function saveSessions(sessions) {
  try {
    if (!existsSync(sessionsDir)) {
      mkdirSync(sessionsDir, { recursive: true });
    }
    writeFileSync(sessionsFile, JSON.stringify(sessions, null, 2));
  } catch (e) {
    console.error('Failed to save sessions:', e.message);
  }
}

function generateSessionId() {
  return 'session_' + Math.random().toString(36).substring(2, 10);
}

/**
 * Start a persistent browser session.
 * Spawns a daemon process that keeps the browser alive.
 */
async function startSession(initialUrl, startRecording = false) {
  const newSessionId = generateSessionId();
  
  // Path to daemon script
  const daemonScript = join(__dirname, 'browser-daemon.mjs');
  
  // Spawn daemon as detached background process
  // Args: session-id [url] [--recording] [--color-scheme=light|dark]
  const args = [daemonScript, newSessionId];
  if (initialUrl) {
    args.push(initialUrl);
  }
  if (startRecording) {
    args.push('--recording');
  }
  if (colorScheme) {
    args.push(`--color-scheme=${colorScheme}`);
  }
  
  const daemon = spawn('node', args, {
    detached: true,
    stdio: 'ignore', // Don't inherit stdio so parent can exit
    cwd: __dirname,
  });
  
  // Unref so parent can exit independently
  daemon.unref();
  
  // Wait for daemon to be ready (poll sessions file)
  const maxWait = 30000; // 30 seconds max (navigation can take time)
  const pollInterval = 300;
  let waited = 0;
  
  while (waited < maxWait) {
    await new Promise(resolve => setTimeout(resolve, pollInterval));
    waited += pollInterval;
    
    const sessions = loadSessions();
    const session = sessions[newSessionId];
    
    // Accept 'ready' or 'active' - both mean browser is running
    if (session && (session.status === 'active' || session.status === 'ready') && session.cdpEndpoint) {
      // Wait a tiny bit more if still navigating
      if (session.status === 'ready' && initialUrl) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      
      let message = initialUrl 
        ? `Browser session started on ${initialUrl}.`
        : `Browser session started.`;
      
      if (startRecording) {
        message += ` Recording is active - interact with the browser, then call stop_recording.`;
      } else {
        message += ` Use session_id "${newSessionId}" for subsequent actions.`;
      }
      
      return {
        success: true,
        session_id: newSessionId,
        cdp_endpoint: session.cdpEndpoint,
        recording: startRecording,
        message,
      };
    }
  }
  
  // Timeout - something went wrong
  return {
    success: false,
    error: `Session ${newSessionId} did not become ready within ${maxWait/1000} seconds. Check if Playwright is installed.`,
  };
}

/**
 * End a persistent browser session.
 * Kills the daemon process and cleans up.
 */
async function endSession(sessionIdToEnd) {
  const sessions = loadSessions();
  const session = sessions[sessionIdToEnd];
  
  if (!session) {
    return {
      success: false,
      error: `Session not found: ${sessionIdToEnd}`
    };
  }
  
  // Kill the daemon process if we have its PID
  if (session.pid) {
    try {
      process.kill(session.pid, 'SIGTERM');
    } catch (e) {
      // Process might already be dead
    }
  }
  
  // Also try to close via CDP in case daemon didn't clean up
  if (session.cdpEndpoint) {
    try {
      const browser = await chromium.connectOverCDP(session.cdpEndpoint);
      await browser.close();
    } catch (e) {
      // Browser might already be closed
    }
  }
  
  // Remove from sessions
  delete sessions[sessionIdToEnd];
  saveSessions(sessions);
  
  return {
    success: true,
    message: `Session ${sessionIdToEnd} closed.`
  };
}

/**
 * Get browser and page for a session, or launch new browser if no session.
 * Returns { browser, page, isSession } or throws error.
 */
async function getBrowserAndPage(sessionIdParam, urlParam) {
  if (sessionIdParam) {
    // Use existing session via CDP - this lets us see the SAME pages
    const sessions = loadSessions();
    const session = sessions[sessionIdParam];
    
    if (!session) {
      throw new Error(`Session not found: ${sessionIdParam}. Start a new session with start_session.`);
    }
    
    try {
      // Connect via CDP - this gives us access to existing pages!
      const browser = await chromium.connectOverCDP(session.cdpEndpoint);
      
      // Update last used
      sessions[sessionIdParam].lastUsed = new Date().toISOString();
      saveSessions(sessions);
      
      // Get existing context and page (the ones the user sees!)
      const contexts = browser.contexts();
      let page;
      
      if (contexts.length > 0) {
        const pages = contexts[0].pages();
        if (pages.length > 0) {
          // Reuse existing page - this is the magic!
          page = pages[0];
        } else {
          page = await contexts[0].newPage();
        }
      } else {
        // Fallback: create new context/page
        const context = await browser.newContext({
          viewport: { width: 1280, height: 800 },
          userAgent,
          locale,
          colorScheme
        });
        page = await context.newPage();
      }
      
      // Navigate only if URL provided AND different from current
      if (urlParam && page.url() !== urlParam && !page.url().includes(urlParam)) {
        await page.goto(urlParam, { waitUntil: 'domcontentloaded', timeout: 15000 });
      }
      
      return { browser, page, isSession: true };
    } catch (e) {
      throw new Error(`Failed to connect to session ${sessionIdParam}: ${e.message}. The browser may have been closed.`);
    }
  } else {
    // Launch new browser (non-session mode)
    const useHeadless = action === 'play_flow' ? false : headless;
    const browser = await chromium.launch({ headless: useHeadless, slowMo });
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      userAgent,
      locale,
      colorScheme
    });
    const page = await context.newPage();
    
    if (urlParam) {
      await page.goto(urlParam, { waitUntil: 'networkidle', timeout: 30000 });
    }
    
    return { browser, page, isSession: false };
  }
}

/**
 * Execute input actions via AgentOS binary (enigo).
 * This performs real OS-level mouse/keyboard input visible to screen recorders.
 */
function executeInputActions(actions) {
  // Find AgentOS binary - check env var first, then common paths
  const agentOsBin = process.env.AGENTOS_BIN 
    || '/Users/joe/dev/agentos/src-tauri/target/release/agentos';
  
  // Escape single quotes in JSON for shell
  const actionsJson = JSON.stringify(actions).replace(/'/g, "'\\''");
  const cmd = `'${agentOsBin}' input --actions '${actionsJson}'`;
  
  try {
    execSync(cmd, { stdio: 'pipe' });
    return { success: true };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

/**
 * Output a line of JSON to stdout (legacy streaming, kept for status messages).
 */
function streamAction(data) {
  process.stdout.write(JSON.stringify(data) + '\n');
}

// Collected diagnostics
const consoleLogs = [];
const consoleErrors = [];
const networkRequests = [];
const networkErrors = [];

/**
 * Get screen coordinates for an element, accounting for window position and browser chrome.
 * @param {Page} page - Playwright page
 * @param {string} selector - CSS selector
 * @param {string} anchor - Where to click: 'center', 'top-left', 'top-right', 'bottom-left', 'bottom-right'
 * @returns {Promise<{screenX: number, screenY: number} | {error: string}>}
 */
async function getScreenCoordinates(page, selector, anchor = 'center') {
  // Use Playwright locator - supports text=, CSS, XPath, etc.
  const element = page.locator(selector).first();
  
  // First ensure element is in view
  try {
    await element.scrollIntoViewIfNeeded({ timeout: 5000 });
  } catch (e) {
    return { error: `Element not found or not scrollable: ${selector}` };
  }

  // Small delay to let scroll settle
  await page.waitForTimeout(100);

  // Get bounding box via Playwright (works with any selector type)
  const box = await element.boundingBox();
  if (!box) {
    return { error: 'Element not visible or has no size' };
  }

  // Get window position and chrome offset via JavaScript
  const windowInfo = await page.evaluate(() => {
    return {
      windowX: window.screenX,
      windowY: window.screenY,
      chromeHeight: window.outerHeight - window.innerHeight,
      chromeWidth: (window.outerWidth - window.innerWidth) / 2,
    };
  });

  // Calculate anchor point within element
  let offsetX, offsetY;
  switch (anchor) {
    case 'top-left':
      offsetX = 5;
      offsetY = 5;
      break;
    case 'top-right':
      offsetX = box.width - 5;
      offsetY = 5;
      break;
    case 'bottom-left':
      offsetX = 5;
      offsetY = box.height - 5;
      break;
    case 'bottom-right':
      offsetX = box.width - 5;
      offsetY = box.height - 5;
      break;
    case 'center':
    default:
      offsetX = box.width / 2;
      offsetY = box.height / 2;
  }

  return {
    screenX: Math.round(windowInfo.windowX + windowInfo.chromeWidth + box.x + offsetX),
    screenY: Math.round(windowInfo.windowY + windowInfo.chromeHeight + box.y + offsetY),
    // Include debug info
    debug: {
      windowPos: { x: windowInfo.windowX, y: windowInfo.windowY },
      chrome: { width: windowInfo.chromeWidth, height: windowInfo.chromeHeight },
      elementBox: { x: box.x, y: box.y, width: box.width, height: box.height },
      anchor: { x: offsetX, y: offsetY }
    }
  };
}

/**
 * Estimate duration of input actions for timing synchronization.
 */
function estimateInputDuration(inputActions) {
  let total = 0;
  for (const action of inputActions) {
    switch (action.input) {
      case 'move':
        total += action.duration_ms || 500;
        break;
      case 'wait':
        total += action.ms || 0;
        break;
      case 'type':
        total += (action.text?.length || 0) * (action.delay_ms || 50);
        break;
      case 'click':
      case 'double_click':
        total += 100; // Small buffer for click
        break;
      default:
        total += 50; // Default small buffer
    }
  }
  return total;
}

/**
 * Get a working selector from Chrome DevTools format selectors array.
 * Tries each selector in order until one works.
 * Chrome DevTools format: [["aria/Submit"], ["#submit-btn"], ["text=Submit"], ["xpath=//button"]]
 */
function getSelector(step) {
  if (!step.selectors || step.selectors.length === 0) {
    throw new Error('No selectors provided in step');
  }
  // Return first selector from first selector array
  // Playwright natively supports: text=, xpath=, css= prefixes
  return step.selectors[0][0];
}

/**
 * Try multiple selectors until one works.
 * Returns the first selector that matches a visible element.
 */
async function findWorkingSelector(page, step, timeout = 3000) {
  if (!step.selectors || step.selectors.length === 0) {
    throw new Error('No selectors provided in step');
  }
  
  for (const selectorArray of step.selectors) {
    const selector = selectorArray[0];
    try {
      const locator = page.locator(selector).first();
      await locator.waitFor({ state: 'visible', timeout });
      return selector;
    } catch (e) {
      // Try next selector
      continue;
    }
  }
  
  // If none worked, return the first one (will likely fail with a clear error)
  return step.selectors[0][0];
}

/**
 * Play a single step in browser mode (Playwright native).
 */
async function playStepBrowserMode(page, step) {
  const actionTimeout = 5000; // 5 second timeout for actions
  
  switch (step.type) {
    case 'setViewport':
      await page.setViewportSize({ width: step.width, height: step.height });
      break;
      
    case 'navigate': {
      // Only navigate if not already on that URL (click may have already triggered navigation)
      const currentUrl = page.url();
      if (currentUrl !== step.url && !currentUrl.includes(new URL(step.url).pathname)) {
        await page.goto(step.url, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(500);
      }
      break;
    }

    case 'click': {
      // Try multiple selectors until one works
      const selector = await findWorkingSelector(page, step, actionTimeout);
      const locator = page.locator(selector).first();
      
      // Wait for element to be visible first (like the old wait_for + click pattern)
      await locator.waitFor({ state: 'visible', timeout: actionTimeout });
      
      const options = { timeout: actionTimeout };
      if (step.offsetX !== undefined && step.offsetY !== undefined) {
        options.position = { x: step.offsetX, y: step.offsetY };
      }
      if (step.button === 'secondary') {
        options.button = 'right';
      }
      await locator.click(options);
      break;
    }
    
    case 'doubleClick': {
      const locator = page.locator(getSelector(step));
      await locator.dblclick();
      break;
    }
    
    case 'change': {
      const locator = page.locator(getSelector(step));
      await locator.fill(step.value);
      break;
    }
    
    case 'keyDown': {
      // Handle modifier combos like "Meta+Enter", "Control+Shift+A"
      if (step.key.includes('+')) {
        const parts = step.key.split('+');
        const mainKey = parts.pop();
        // Hold down all modifiers
        for (const mod of parts) {
          await page.keyboard.down(mod);
        }
        // Press the main key
        await page.keyboard.press(mainKey);
        // Release all modifiers
        for (const mod of parts.reverse()) {
          await page.keyboard.up(mod);
        }
      } else {
        await page.keyboard.down(step.key);
      }
      break;
    }

    case 'keyUp':
      await page.keyboard.up(step.key);
      break;
      
    case 'scroll':
      if (step.selectors) {
        await page.locator(getSelector(step)).scrollIntoViewIfNeeded();
      } else {
        // Smooth scroll with behavior option
        await page.evaluate(({x, y, smooth}) => {
          window.scrollTo({ 
            left: x, 
            top: y, 
            behavior: smooth ? 'smooth' : 'instant' 
          });
        }, { x: step.x || 0, y: step.y || 0, smooth: step.smooth !== false });
        // Wait for smooth scroll to complete
        if (step.smooth !== false) {
          await new Promise(r => setTimeout(r, 500));
        }
      }
      break;

    case 'hover': {
      const locator = page.locator(getSelector(step)).first();
      await locator.hover();
      break;
    }
    
    case 'waitForElement': {
      const locator = page.locator(getSelector(step)).first();
      await locator.waitFor({ 
        state: step.visible !== false ? 'visible' : 'attached',
        timeout: step.timeout || 10000
      });
      break;
    }
    
    case 'waitForExpression':
      await page.waitForFunction(step.expression, { timeout: step.timeout || 10000 });
      break;
      
    case 'close':
      // Skip close in our context - session management handles this
      break;
      
    default:
      console.error(`Unknown step type: ${step.type}, skipping`);
  }
}

/**
 * Play a single step in native mode (OS-level input via enigo).
 */
async function playStepNativeMode(page, step) {
  switch (step.type) {
    case 'setViewport':
      await page.setViewportSize({ width: step.width, height: step.height });
      break;
      
    case 'navigate': {
      // Only navigate if not already on that URL (click may have already triggered navigation)
      const currentUrl = page.url();
      if (currentUrl !== step.url && !currentUrl.includes(new URL(step.url).pathname)) {
        await page.goto(step.url, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(500);
      }
      break;
    }

    case 'click': {
      const selector = getSelector(step);
      const coords = await getScreenCoordinates(page, selector, 'center');
      if (coords.error) {
        throw new Error(`Failed to get coordinates for ${selector}: ${coords.error}`);
      }
      const inputActions = [
        { input: 'move', x: coords.screenX, y: coords.screenY, duration_ms: 500, easing: 'ease_out' },
        { input: 'wait', ms: 50 },
        { input: 'click', button: step.button === 'secondary' ? 'right' : 'left' }
      ];
      executeInputActions(inputActions);
      await page.waitForTimeout(600);
      break;
    }
    
    case 'doubleClick': {
      const selector = getSelector(step);
      const coords = await getScreenCoordinates(page, selector, 'center');
      if (coords.error) {
        throw new Error(`Failed to get coordinates for ${selector}: ${coords.error}`);
      }
      const inputActions = [
        { input: 'move', x: coords.screenX, y: coords.screenY, duration_ms: 500, easing: 'ease_out' },
        { input: 'wait', ms: 50 },
        { input: 'double_click', button: 'left' }
      ];
      executeInputActions(inputActions);
      await page.waitForTimeout(600);
      break;
    }
    
    case 'change': {
      const selector = getSelector(step);
      const coords = await getScreenCoordinates(page, selector, 'center');
      if (coords.error) {
        throw new Error(`Failed to get coordinates for ${selector}: ${coords.error}`);
      }
      const inputActions = [
        { input: 'move', x: coords.screenX, y: coords.screenY, duration_ms: 300, easing: 'ease_out' },
        { input: 'wait', ms: 50 },
        { input: 'click', button: 'left' },
        { input: 'wait', ms: 100 },
        { input: 'key_combo', keys: ['cmd', 'a'] }, // Select all first
        { input: 'wait', ms: 50 },
        { input: 'type', text: step.value, delay_ms: 50 }
      ];
      executeInputActions(inputActions);
      const typingTime = (step.value?.length || 0) * 50 + 500;
      await page.waitForTimeout(typingTime);
      break;
    }
    
    case 'keyDown':
      executeInputActions([{ input: 'key', key: step.key }]);
      await page.waitForTimeout(100);
      break;
      
    case 'keyUp':
      // Native mode combines keyDown/keyUp, so we skip keyUp
      break;
      
    case 'scroll':
      if (step.selectors) {
        await page.locator(getSelector(step)).scrollIntoViewIfNeeded();
      } else {
        executeInputActions([{ input: 'scroll', delta_x: 0, delta_y: step.y || 0 }]);
      }
      await page.waitForTimeout(300);
      break;
      
    case 'hover': {
      const selector = getSelector(step);
      const coords = await getScreenCoordinates(page, selector, 'center');
      if (coords.error) {
        throw new Error(`Failed to get coordinates for ${selector}: ${coords.error}`);
      }
      executeInputActions([
        { input: 'move', x: coords.screenX, y: coords.screenY, duration_ms: 500, easing: 'ease_out' }
      ]);
      await page.waitForTimeout(600);
      break;
    }
    
    case 'waitForElement': {
      const locator = page.locator(getSelector(step)).first();
      await locator.waitFor({ 
        state: step.visible !== false ? 'visible' : 'attached',
        timeout: step.timeout || 10000
      });
      break;
    }
    
    case 'waitForExpression':
      await page.waitForFunction(step.expression, { timeout: step.timeout || 10000 });
      break;
      
    case 'close':
      // Skip close in our context
      break;
      
    default:
      console.error(`Unknown step type: ${step.type}, skipping`);
  }
}

/**
 * Convert a Chrome DevTools step to simple format.
 */
function toSimpleStep(step) {
  // Get the best selector from selectors array
  const getSelector = (s) => {
    if (s.selectors && s.selectors[0] && s.selectors[0][0]) {
      return s.selectors[0][0];
    }
    return s.selector;
  };
  
  switch (step.type) {
    case 'navigate':
      return { action: 'goto', url: step.url };
    case 'click':
      return { action: 'click', selector: getSelector(step) };
    case 'change':
      return { action: 'type', selector: getSelector(step), text: step.value };
    case 'keyDown':
      return { action: 'press', key: step.key };
    case 'waitForElement':
      return { action: 'wait_for', selector: getSelector(step) };
    case 'scroll':
      return { action: 'scroll', x: step.x || 0, y: step.y || 0 };
    case 'hover':
      return { action: 'hover', selector: getSelector(step) };
    case 'setViewport':
      return null; // Skip viewport steps in simple format
    default:
      return null; // Skip unknown steps
  }
}

/**
 * Convert a Chrome DevTools recording to simple format.
 */
function toSimpleFormat(recording) {
  const steps = recording.steps || [];
  return steps
    .map(toSimpleStep)
    .filter(s => s !== null);
}

/**
 * Normalize a step from either format to internal format.
 * 
 * Simple format (action-based):
 *   { action: "goto", url: "..." }
 *   { action: "wait_for", selector: "..." }
 *   { action: "click", selector: "..." }
 *   { action: "type", selector: "...", text: "..." }
 * 
 * Chrome DevTools format (type-based):
 *   { type: "navigate", url: "..." }
 *   { type: "click", selectors: [[...]] }
 *   { type: "change", selectors: [[...]], value: "..." }
 */
function normalizeStep(step) {
  // Already in Chrome DevTools format
  if (step.type) {
    return step;
  }
  
  // Convert simple format to internal format
  switch (step.action) {
    case 'goto':
      return { type: 'navigate', url: step.url };
      
    case 'wait_for':
      return { 
        type: 'waitForElement', 
        selectors: [[step.selector]],
        timeout: step.timeout || 10000
      };
      
    case 'click':
      return { 
        type: 'click', 
        selectors: [[step.selector]]
      };
      
    case 'type':
      return { 
        type: 'change', 
        selectors: [[step.selector]], 
        value: step.text 
      };
      
    case 'press':
      return { type: 'keyDown', key: step.key };
      
    case 'scroll':
      return { type: 'scroll', x: step.x || 0, y: step.y || 0 };
      
    case 'hover':
      return { type: 'hover', selectors: [[step.selector]] };
      
    default:
      console.error(`Unknown action: ${step.action}`);
      return step;
  }
}

/**
 * Process a flow recording.
 * Auto-detects format:
 *   - Simple array: [{ action: "goto", ... }, ...]
 *   - Chrome DevTools: { title: "...", steps: [...] }
 * 
 * Supports both browser mode (Playwright native) and native mode (OS-level input).
 */
async function playFlow(page, recording) {
  // Auto-detect format: array = simple format, object with steps = Chrome DevTools
  let steps;
  if (Array.isArray(recording)) {
    steps = recording;
  } else {
    steps = recording.steps || [];
  }
  
  let stepsProcessed = 0;
  
  for (let i = 0; i < steps.length; i++) {
    const rawStep = steps[i];
    const step = normalizeStep(rawStep);
    const stepDesc = rawStep.action || step.type;
    
    try {
      if (playbackMode === 'browser') {
        await playStepBrowserMode(page, step);
      } else {
        await playStepNativeMode(page, step);
      }
      stepsProcessed++;
    } catch (error) {
      streamAction({ 
        type: 'error', 
        message: `Step ${i} (${stepDesc}) failed: ${error.message}`,
        steps_processed: stepsProcessed
      });
      streamAction({ type: 'done', success: false });
      return {
        success: false,
        error: `Step ${i} (${stepDesc}) failed: ${error.message}`,
        steps_processed: stepsProcessed
      };
    }
  }
  
  streamAction({ type: 'done', success: true });
  
  return {
    success: true,
    steps_processed: stepsProcessed,
    playback_mode: playbackMode
  };
}

/**
 * Load the latest recording for a session from disk.
 * Checks sessions file for lastRecordingFile, falls back to finding latest file.
 */
function loadRecording(sessionIdToLoad) {
  // First check if sessions file has the latest recording info
  const sessions = loadSessions();
  const session = sessions[sessionIdToLoad];
  
  if (session?.lastRecordingFile) {
    const recordingPath = join(recordingsDir, session.lastRecordingFile);
    if (existsSync(recordingPath)) {
      try {
        return JSON.parse(readFileSync(recordingPath, 'utf-8'));
      } catch (e) {
        // Fall through to scan directory
      }
    }
  }
  
  // Fall back to scanning recordings directory for this session
  if (!existsSync(recordingsDir)) return null;
  
  const files = readdirSync(recordingsDir)
    .filter(f => f.startsWith(sessionIdToLoad) && f.endsWith('.json'))
    .sort()
    .reverse();  // Latest first (timestamp-based IDs sort correctly)
  
  if (files.length === 0) return null;
  
  try {
    return JSON.parse(readFileSync(join(recordingsDir, files[0]), 'utf-8'));
  } catch (e) {
    return null;
  }
}

/**
 * Save a recording to disk.
 */
function saveRecordingToDisk(sessionIdToSave, recording) {
  if (!existsSync(recordingsDir)) {
    mkdirSync(recordingsDir, { recursive: true });
  }
  writeFileSync(
    join(recordingsDir, `${sessionIdToSave}.json`),
    JSON.stringify(recording, null, 2)
  );
}

// Parse recording param (for start_session)
const startWithRecording = process.env.PARAM_RECORDING === 'true';

async function run() {
  // Handle session management actions first
  if (action === 'start_session') {
    try {
      const result = await startSession(url, startWithRecording);
      console.log(JSON.stringify(result, null, 2));
    } catch (error) {
      console.log(JSON.stringify({
        success: false,
        error: `Failed to start session: ${error.message}`
      }, null, 2));
      process.exit(1);
    }
    return;
  }
  
  if (action === 'end_session') {
    if (!sessionId) {
      console.log(JSON.stringify({
        success: false,
        error: 'session_id is required for end_session'
      }, null, 2));
      process.exit(1);
    }
    try {
      const result = await endSession(sessionId);
      console.log(JSON.stringify(result, null, 2));
    } catch (error) {
      console.log(JSON.stringify({
        success: false,
        error: `Failed to end session: ${error.message}`
      }, null, 2));
      process.exit(1);
    }
    return;
  }
  
  // Get browser and page (either from session or new launch)
  let browser, page, isSession;
  try {
    ({ browser, page, isSession } = await getBrowserAndPage(sessionId, url));
  } catch (error) {
    console.log(JSON.stringify({
      success: false,
      error: error.message
    }, null, 2));
    process.exit(1);
  }
  
  // Capture console messages
  page.on('console', msg => {
    const entry = { type: msg.type(), text: msg.text() };
    if (msg.type() === 'error') {
      consoleErrors.push(entry);
    }
    consoleLogs.push(entry);
  });
  
  // Capture page errors (uncaught exceptions)
  page.on('pageerror', error => {
    consoleErrors.push({ type: 'exception', text: error.message });
  });
  
  // Capture network requests
  page.on('requestfailed', request => {
    networkErrors.push({
      url: request.url(),
      method: request.method(),
      failure: request.failure()?.errorText || 'Unknown error'
    });
  });
  
  page.on('response', response => {
    const status = response.status();
    if (status >= 400) {
      networkErrors.push({
        url: response.url(),
        status,
        statusText: response.statusText()
      });
    }
    // Only track non-asset requests to reduce noise
    const respUrl = response.url();
    if (!respUrl.match(/\.(png|jpg|jpeg|gif|svg|css|woff|woff2|ttf|ico)(\?|$)/)) {
      networkRequests.push({
        url: respUrl.length > 100 ? respUrl.substring(0, 100) + '...' : respUrl,
        status,
        method: response.request().method()
      });
    }
  });
  
  try {
    // getBrowserAndPage already handles navigation, just wait if needed
    if (url && action !== 'play_flow') {
      await page.waitForTimeout(waitMs);
    }
    
    let result = { success: true };
    
    // Include session info in result if using a session
    if (isSession && sessionId) {
      result.session_id = sessionId;
    }
    
    // Helper to add diagnostics to result
    const addDiagnostics = () => {
      if (consoleErrors.length > 0) {
        result.console_errors = consoleErrors.slice(-10); // Last 10 errors
      }
      if (networkErrors.length > 0) {
        result.network_errors = networkErrors.slice(-10); // Last 10 errors
      }
    };
    
    // Helper to optionally add screenshot
    const maybeScreenshot = async (prefix) => {
      if (includeScreenshot) {
        const screenshotPath = join(downloadsDir, `browser-${prefix}-${Date.now()}.png`);
        await page.screenshot({ path: screenshotPath, fullPage: false });
        result.screenshot = screenshotPath;
      }
    };
    
    switch (action) {
      case 'play_flow': {
        if (!recordingJson) {
          throw new Error('recording parameter is required for play_flow');
        }
        
        let recording;
        try {
          recording = JSON.parse(recordingJson);
        } catch (e) {
          throw new Error(`Invalid recording JSON: ${e.message}`);
        }
        
        // Validate: must be array (simple format) or object with steps (Chrome DevTools)
        if (!Array.isArray(recording) && (!recording.steps || !Array.isArray(recording.steps))) {
          throw new Error('recording must be an array (simple format) or have a steps array (Chrome DevTools format)');
        }
        
        // Play the recording (playFlow auto-detects format)
        result = await playFlow(page, recording);
        if (isSession && sessionId) {
          result.session_id = sessionId;
        }
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'record_flow': {
        if (!sessionId) {
          throw new Error('session_id is required for record_flow - start a session first');
        }
        
        // Tell daemon to start recording (via sessions file signal)
        const sessions = loadSessions();
        const session = sessions[sessionId];
        if (!session) {
          throw new Error(`Session not found: ${sessionId}`);
        }
        
        session.recording = true;
        session.recordingStarted = new Date().toISOString();
        saveSessions(sessions);
        
        result.message = `Recording started on session ${sessionId}. Interact with the browser, then call stop_recording.`;
        result.session_id = sessionId;
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'stop_recording': {
        if (!sessionId) {
          throw new Error('session_id is required for stop_recording');
        }
        
        const sessions = loadSessions();
        const session = sessions[sessionId];
        if (!session) {
          throw new Error(`Session not found: ${sessionId}`);
        }
        
        // Get recording from daemon (stored in sessions file or recordings dir)
        let recording = loadRecording(sessionId);
        
        // Clear recording state
        session.recording = false;
        session.recordingStarted = null;
        saveSessions(sessions);
        
        if (recording) {
          const stepCount = recording.steps?.length || 0;
          // Convert to simple format if setting is 'simple'
          if (recordingFormat === 'simple') {
            result.recording = toSimpleFormat(recording);
            result.format = 'simple';
          } else {
            result.recording = recording;
            result.format = 'chrome_devtools';
          }
          result.message = `Recording stopped. Captured ${stepCount} steps.`;
        } else {
          result.recording = recordingFormat === 'simple' ? [] : { title: `Recording ${sessionId}`, steps: [] };
          result.format = recordingFormat;
          result.message = 'Recording stopped (no events captured).';
        }
        result.session_id = sessionId;
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'get_recording': {
        if (!sessionId) {
          throw new Error('session_id is required for get_recording');
        }
        
        let recording = loadRecording(sessionId);
        if (recording) {
          const stepCount = recording.steps?.length || 0;
          // Convert to simple format if setting is 'simple'
          if (recordingFormat === 'simple') {
            result.recording = toSimpleFormat(recording);
            result.format = 'simple';
          } else {
            result.recording = recording;
            result.format = 'chrome_devtools';
          }
          result.message = `Found recording with ${stepCount} steps.`;
        } else {
          result.success = false;
          result.error = `No recording found for session ${sessionId}`;
        }
        result.session_id = sessionId;
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'inspect': {
        // Diagnostic overview without screenshot
        result.title = await page.title();
        result.url = page.url();
        
        // Get visible text summary
        const bodyText = await page.locator('body').textContent();
        result.text_preview = bodyText?.trim().substring(0, 500) + (bodyText?.length > 500 ? '...' : '');
        
        // Get all headings for structure
        const headings = await page.locator('h1, h2, h3').allTextContents();
        if (headings.length > 0) {
          result.headings = headings.slice(0, 10).map(h => h.trim()).filter(Boolean);
        }
        
        // Get all buttons and links for interactivity
        const buttons = await page.locator('button, [role="button"]').allTextContents();
        if (buttons.length > 0) {
          result.buttons = buttons.slice(0, 15).map(b => b.trim()).filter(Boolean);
        }
        
        // Get form inputs
        const inputs = await page.locator('input, textarea, select').evaluateAll(els => 
          els.map(el => ({
            type: el.type || el.tagName.toLowerCase(),
            name: el.name || el.id || el.placeholder || null,
            value: el.value ? (el.value.length > 50 ? el.value.substring(0, 50) + '...' : el.value) : null
          })).filter(i => i.name)
        );
        if (inputs.length > 0) {
          result.inputs = inputs.slice(0, 10);
        }
        
        // Add console/network diagnostics
        if (consoleLogs.length > 0) {
          result.console_logs = consoleLogs.slice(-15);
        }
        result.network_requests = networkRequests.slice(-20);
        addDiagnostics();
        
        await maybeScreenshot('inspect');
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'console': {
        // Just get console logs
        result.title = await page.title();
        result.console_logs = consoleLogs;
        result.console_errors = consoleErrors;
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'network': {
        // Just get network activity
        result.title = await page.title();
        result.requests = networkRequests;
        result.errors = networkErrors;
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'screenshot': {
        const screenshotPath = join(downloadsDir, `browser-screenshot-${Date.now()}.png`);
        if (selector) {
          const element = await page.locator(selector).first();
          await element.screenshot({ path: screenshotPath });
        } else {
          await page.screenshot({ path: screenshotPath, fullPage: false });
        }
        result.screenshot = screenshotPath;
        result.title = await page.title();
        result.url = page.url();
        addDiagnostics();
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'click': {
        if (!selector) throw new Error('selector is required for click action');
        const clickLocator = page.locator(selector).first();
        await clickLocator.waitFor({ state: 'visible', timeout: 10000 });
        await clickLocator.click();
        await page.waitForTimeout(waitMs);
        result.clicked = selector;
        result.title = await page.title();
        result.url = page.url();
        addDiagnostics();
        await maybeScreenshot('click');
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'type': {
        if (!selector) throw new Error('selector is required for type action');
        if (!text) throw new Error('text is required for type action');
        await page.locator(selector).first().fill(text);
        await page.waitForTimeout(waitMs);
        result.typed = { selector, text };
        result.title = await page.title();
        result.url = page.url();
        addDiagnostics();
        await maybeScreenshot('type');
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'get_text': {
        if (!selector) throw new Error('selector is required for get_text action');
        const elements = await page.locator(selector).all();
        const texts = await Promise.all(elements.map(el => el.textContent()));
        result.texts = texts.map(t => t?.trim()).filter(Boolean);
        result.count = result.texts.length;
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'evaluate': {
        if (!script) throw new Error('script is required for evaluate action');
        const evalResult = await page.evaluate(script);
        result.result = evalResult;
        addDiagnostics();
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      case 'get_html': {
        const html = selector 
          ? await page.locator(selector).first().innerHTML()
          : await page.content();
        result.html = html;
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
      default:
        throw new Error(`Unknown action: ${action}`);
    }
    
  } catch (error) {
    console.log(JSON.stringify({ 
      success: false, 
      error: error.message,
      console_errors: consoleErrors,
      network_errors: networkErrors
    }, null, 2));
    process.exit(1);
  } finally {
    if (isSession) {
      // Disconnect without closing - browser stays open via daemon
      await browser.disconnect?.() || browser.close?.();
    } else {
      // Close browser for non-session mode
      await browser.close();
    }
  }
}

run();

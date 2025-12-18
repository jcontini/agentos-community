#!/usr/bin/env node
/**
 * Browser Daemon - Runs as a background process to keep browser alive.
 * 
 * Usage: node browser-daemon.mjs <session-id> [initial-url]
 * 
 * This script:
 * 1. Launches Chrome with remote debugging enabled (CDP)
 * 2. Writes the CDP endpoint to the sessions file
 * 3. Stays running until killed
 * 4. Other scripts can connect via connectOverCDP and see the SAME pages
 * 5. Supports recording user interactions via injected script
 */

import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { homedir } from 'os';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Recording storage
const recordingsDir = join(homedir(), '.agentos', 'recordings');

const sessionId = process.argv[2];
// Parse args: session-id [url] [--recording]
const hasRecordingFlag = process.argv.includes('--recording');
const initialUrl = process.argv[3] && !process.argv[3].startsWith('--') ? process.argv[3] : null;

if (!sessionId) {
  console.error('Usage: node browser-daemon.mjs <session-id> [initial-url] [--recording]');
  process.exit(1);
}

const sessionsDir = join(homedir(), '.agentos');
const sessionsFile = join(sessionsDir, 'browser-sessions.json');

// Find an available port for CDP
async function findAvailablePort(startPort = 9222) {
  const net = await import('net');
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(startPort, () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', () => {
      resolve(findAvailablePort(startPort + 1));
    });
  });
}

function loadSessions() {
  try {
    if (existsSync(sessionsFile)) {
      return JSON.parse(readFileSync(sessionsFile, 'utf-8'));
    }
  } catch (e) {}
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

// Recording state for this session
let recording = null;  // { title, steps: [] } or null
let recordingActive = false;
let recordingFilename = null;  // e.g., "2025-12-17_20-45-30_adavia.com.json"

/**
 * Generate a recording filename: yyyy-mm-dd_hh-mm-ss_domain.json
 */
function generateRecordingFilename(url) {
  const now = new Date();
  const date = now.toISOString().split('T')[0];  // yyyy-mm-dd
  const time = now.toTimeString().split(' ')[0].replace(/:/g, '-');  // hh-mm-ss
  
  let domain = 'recording';
  try {
    if (url) {
      domain = new URL(url).hostname.toLowerCase().replace(/^www\./, '');
    }
  } catch (e) {}
  
  return `${date}_${time}_${domain}.json`;
}

/**
 * Save recording to disk.
 */
function saveRecording() {
  if (!recording || recording.steps.length === 0) return;
  
  if (!existsSync(recordingsDir)) {
    mkdirSync(recordingsDir, { recursive: true });
  }
  
  const filename = recordingFilename || `${sessionId}.json`;
  writeFileSync(
    join(recordingsDir, filename),
    JSON.stringify(recording, null, 2)
  );
  console.error(`[browser-daemon] Recording saved: ${recording.steps.length} steps -> ${filename}`);
  
  // Also update sessions file with latest recording info
  const sessions = loadSessions();
  if (sessions[sessionId]) {
    sessions[sessionId].lastRecordingFile = filename;
    saveSessions(sessions);
  }
}

/**
 * Handle a recorded event from the injected script.
 */
function handleRecordedEvent(step) {
  if (!recordingActive || !recording) return;
  recording.steps.push(step);
  console.error(`[browser-daemon] Recorded: ${step.type}`);
  // Save incrementally to avoid data loss
  saveRecording();
}

/**
 * Load the recorder.js script.
 */
function loadRecorderScript() {
  const recorderPath = join(__dirname, 'recorder.js');
  if (existsSync(recorderPath)) {
    return readFileSync(recorderPath, 'utf-8');
  }
  // Fallback inline recorder if file not found
  return `
    (function() {
      if (window.__agentosRecorderActive) return;
      window.__agentosRecorderActive = true;
      
      const getSelector = (el) => {
        if (!el || el === document.body) return null;
        // Try various selector strategies
        if (el.id) return '#' + el.id;
        if (el.getAttribute('data-testid')) return '[data-testid="' + el.getAttribute('data-testid') + '"]';
        if (el.getAttribute('aria-label')) return '[aria-label="' + el.getAttribute('aria-label') + '"]';
        const text = el.textContent?.trim().slice(0, 30);
        if (text && el.matches('button, a, [role="button"]')) return 'text=' + text;
        const tag = el.tagName.toLowerCase();
        const classes = el.className?.split?.(' ').filter(c => c && !c.startsWith('_')).slice(0, 2).join('.');
        return classes ? tag + '.' + classes : tag;
      };
      
      document.addEventListener('click', (e) => {
        const sel = getSelector(e.target);
        if (sel) window.__agentosRecord?.({ type: 'click', selectors: [[sel]], offsetX: e.offsetX, offsetY: e.offsetY });
      }, true);
      
      document.addEventListener('input', (e) => {
        const sel = getSelector(e.target);
        if (sel && e.target.value !== undefined) {
          window.__agentosRecord?.({ type: 'change', selectors: [[sel]], value: e.target.value });
        }
      }, true);
      
      document.addEventListener('keydown', (e) => {
        if (['Enter', 'Tab', 'Escape', 'Backspace', 'Delete', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
          window.__agentosRecord?.({ type: 'keyDown', key: e.key });
        }
      }, true);
    })();
  `;
}

async function main() {
  console.error(`[browser-daemon] Starting session ${sessionId}...`);
  
  // Find available port for CDP
  const cdpPort = await findAvailablePort(9222);
  console.error(`[browser-daemon] Using CDP port ${cdpPort}`);
  
  // Launch browser with remote debugging enabled
  // This allows other scripts to connect and see the SAME pages
  const browser = await chromium.launch({
    headless: false,
    args: [
      `--remote-debugging-port=${cdpPort}`,
    ],
  });
  
  const cdpEndpoint = `http://localhost:${cdpPort}`;
  console.error(`[browser-daemon] Browser launched with CDP: ${cdpEndpoint}`);
  
  // Create a context and page
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  
  // Expose function for recording - must be done before any page is created
  await context.exposeFunction('__agentosRecord', (step) => {
    handleRecordedEvent(step);
  });
  
  const page = await context.newPage();
  
  // Save session info immediately (status: ready)
  const sessions = loadSessions();
  sessions[sessionId] = {
    cdpEndpoint,
    pid: process.pid,
    startedAt: new Date().toISOString(),
    lastUsed: new Date().toISOString(),
    status: 'ready',
    initialUrl: initialUrl || null,
    recording: hasRecordingFlag,  // Start recording if --recording flag passed
  };
  saveSessions(sessions);

  // Navigate to initial URL if provided
  if (initialUrl) {
    console.error(`[browser-daemon] Navigating to ${initialUrl}...`);
    try {
      await page.goto(initialUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
      console.error(`[browser-daemon] Navigation complete`);
    } catch (e) {
      console.error(`[browser-daemon] Navigation error (continuing): ${e.message}`);
    }
  }
  
  // If --recording flag, start recording immediately
  if (hasRecordingFlag) {
    console.error(`[browser-daemon] Starting recording immediately...`);
    recordingActive = true;
    recordingFilename = generateRecordingFilename(initialUrl);
    recording = {
      title: recordingFilename.replace('.json', ''),
      steps: [
        { type: 'setViewport', width: 1280, height: 800 }
      ]
    };
    
    // Add navigate step for initial URL
    if (initialUrl) {
      recording.steps.push({ type: 'navigate', url: initialUrl });
    }
    
    // Inject recorder script
    const recorderScript = loadRecorderScript();
    await context.addInitScript(recorderScript);
    
    // Inject into current page
    try {
      await page.evaluate(recorderScript);
    } catch (e) {
      console.error(`[browser-daemon] Failed to inject recorder: ${e.message}`);
    }
    
    console.error(`[browser-daemon] Recording started`);
  }
  
  // Update status to active
  const sessions2 = loadSessions();
  if (sessions2[sessionId]) {
    sessions2[sessionId].status = 'active';
    sessions2[sessionId].lastUsed = new Date().toISOString();
    saveSessions(sessions2);
  }
  
  console.error(`[browser-daemon] Session ${sessionId} ready. CDP: ${cdpEndpoint}`);
  
  // Handle graceful shutdown - save recording if active
  const cleanup = async () => {
    console.error(`[browser-daemon] Shutting down...`);
    
    // Save recording if we have one
    if (recording && recording.steps.length > 0) {
      console.error(`[browser-daemon] Saving recording before exit...`);
      saveRecording();
    }
    
    try {
      await browser.close();
    } catch (e) {}
    const sessions = loadSessions();
    delete sessions[sessionId];
    saveSessions(sessions);
    process.exit(0);
  };
  
  // Also save recording if browser disconnects unexpectedly
  browser.on('disconnected', () => {
    console.error(`[browser-daemon] Browser disconnected`);
    if (recording && recording.steps.length > 0) {
      saveRecording();
    }
  });
  
  process.on('SIGTERM', cleanup);
  process.on('SIGINT', cleanup);
  
  // Monitor sessions file for recording state changes
  setInterval(async () => {
    const sessions = loadSessions();
    const session = sessions[sessionId];
    
    if (session) {
      session.lastUsed = new Date().toISOString();
      saveSessions(sessions);
      
      // Check if recording was started via browser.mjs
      if (session.recording && !recordingActive) {
        console.error(`[browser-daemon] Starting recording...`);
        recordingActive = true;
        
        // Get current URL for filename
        let currentUrl = null;
        const currentPages = context.pages();
        if (currentPages.length > 0) {
          currentUrl = currentPages[0].url();
        }
        recordingFilename = generateRecordingFilename(currentUrl);
        
        recording = {
          title: recordingFilename.replace('.json', ''),
          steps: [
            { type: 'setViewport', width: 1280, height: 800 }
          ]
        };
        
        // Inject recorder script into current page and all future pages
        const recorderScript = loadRecorderScript();
        await context.addInitScript(recorderScript);
        
        // Also inject into current page
        const pages = context.pages();
        for (const p of pages) {
          try {
            await p.evaluate(recorderScript);
          } catch (e) {
            console.error(`[browser-daemon] Failed to inject recorder: ${e.message}`);
          }
        }
        
        // Add navigate step for current URL
        if (pages.length > 0) {
          const currentUrl = pages[0].url();
          if (currentUrl && currentUrl !== 'about:blank') {
            recording.steps.push({ type: 'navigate', url: currentUrl });
          }
        }
        
        console.error(`[browser-daemon] Recording started`);
      }
      
      // Check if recording was stopped
      if (!session.recording && recordingActive) {
        console.error(`[browser-daemon] Stopping recording...`);
        recordingActive = false;
        saveRecording();
      }
    }
  }, 500); // Check every 500ms for responsive recording start
}

main().catch(err => {
  console.error(`[browser-daemon] Fatal error: ${err.message}`);
  process.exit(1);
});



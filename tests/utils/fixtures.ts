/**
 * Test Fixtures and Helpers
 * 
 * Common utilities for integration tests.
 */

import { getAgentOS, AgentOS } from './mcp-client';

/** Test data prefix for easy identification and cleanup */
export const TEST_PREFIX = '[TEST]';

/** Generate a unique test identifier */
export function testId(prefix = ''): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  return prefix ? `${prefix}_${timestamp}_${random}` : `${timestamp}_${random}`;
}

/** Check if a string is test data */
export function isTestData(str: string): boolean {
  return str.startsWith(TEST_PREFIX);
}

/** Generate test content with unique ID */
export function testContent(description = 'test item'): string {
  return `${TEST_PREFIX} ${description} ${testId()}`;
}

/** Get the global AgentOS instance */
export function aos(): AgentOS {
  return getAgentOS();
}

/**
 * Clean up test data created during tests
 * Call this in afterAll() to remove test records
 */
export async function cleanupTestData(
  app: string,
  filterFn: (item: any) => boolean = (item) => isTestData(item.title || item.name || '')
): Promise<number> {
  const agentOS = getAgentOS();
  
  try {
    const items = await agentOS.call(app, { action: 'list', params: { limit: 1000 } });
    const testItems = (items || []).filter(filterFn);
    
    let deleted = 0;
    for (const item of testItems) {
      try {
        // Note: execute: true required for write actions
        await agentOS.call(app, { action: 'delete', params: { id: item.id }, execute: true });
        deleted++;
      } catch (e) {
        console.warn(`Failed to delete ${app} item ${item.id}:`, e);
      }
    }
    
    return deleted;
  } catch (e) {
    console.warn(`Failed to cleanup ${app}:`, e);
    return 0;
  }
}

/**
 * Wait for a condition to be true
 */
export async function waitFor(
  condition: () => Promise<boolean> | boolean,
  options: { timeout?: number; interval?: number; message?: string } = {}
): Promise<void> {
  const { timeout = 10000, interval = 100, message = 'Condition not met' } = options;
  const start = Date.now();

  while (Date.now() - start < timeout) {
    if (await condition()) return;
    await sleep(interval);
  }

  throw new Error(`${message} (timeout after ${timeout}ms)`);
}

/** Sleep for specified milliseconds */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Retry a function with backoff
 */
export async function retry<T>(
  fn: () => Promise<T>,
  options: { retries?: number; delay?: number; backoff?: number } = {}
): Promise<T> {
  const { retries = 3, delay = 1000, backoff = 2 } = options;
  let lastError: Error | undefined;
  let currentDelay = delay;

  for (let i = 0; i <= retries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (i < retries) {
        await sleep(currentDelay);
        currentDelay *= backoff;
      }
    }
  }

  throw lastError;
}

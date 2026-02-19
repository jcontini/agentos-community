/**
 * Brave Search Adapter Tests
 * 
 * Tests for privacy-focused web search.
 * Requires: BRAVE_API_KEY or configured credential in AgentOS.
 * 
 * Coverage:
 * - webpage.search (web search)
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'brave';

// Skip tests if no credentials configured
let skipTests = false;

describe('Brave Search Adapter', () => {
  beforeAll(async () => {
    // Check if Brave is configured by trying a simple search
    try {
      await aos().call('UseAdapter', {
        adapter,
        tool: 'webpage.search',
        params: { query: 'test', limit: 1 },
      });
    } catch (e: unknown) {
      const error = e as Error;
      if (error.message?.includes('No credentials configured') || error.message?.includes('Credential not found')) {
        console.log('  ⏭ Skipping Brave tests: no credentials configured');
        skipTests = true;
      } else {
        throw e;
      }
    }
  });

  // ===========================================================================
  // webpage.search
  // ===========================================================================
  describe('webpage.search', () => {
    it('returns an array of search results', async () => {
      if (skipTests) return;
      
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'webpage.search',
        params: { query: 'rust programming', limit: 5 },
      });

      expect(Array.isArray(results)).toBe(true);
      expect((results as unknown[]).length).toBeLessThanOrEqual(5);
    });

    it('results have required fields', async () => {
      if (skipTests) return;
      
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'webpage.search',
        params: { query: 'javascript frameworks', limit: 3 },
      }) as Array<{ url: string; title: string; content: string; adapter: string }>;

      expect(results.length).toBeGreaterThan(0);
      
      for (const result of results) {
        expect(result.url).toBeDefined();
        expect(typeof result.url).toBe('string');
        expect(result.url).toMatch(/^https?:\/\//);
        
        expect(result.title).toBeDefined();
        expect(typeof result.title).toBe('string');
        
        // Content is the description/snippet
        expect(result.content).toBeDefined();
        
        expect(result.adapter).toBe(adapter);
      }
    });

    it('respects limit parameter', async () => {
      if (skipTests) return;
      
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'webpage.search',
        params: { query: 'python tutorial', limit: 3 },
      }) as unknown[];

      expect(results.length).toBeLessThanOrEqual(3);
    });
  });
});

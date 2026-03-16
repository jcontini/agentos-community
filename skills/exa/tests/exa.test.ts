/**
 * Exa Adapter Tests
 *
 * Tests for semantic web search and content extraction.
 * Requires: EXA_API_KEY or configured credential in AgentOS.
 *
 * Coverage:
 * - search
 * - read_webpage
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'exa';

// Skip tests if no credentials configured
let skipTests = false;

describe('Exa Adapter', () => {
  beforeAll(async () => {
    // Check if Exa is configured by trying a simple search
    try {
      await aos().call('UseAdapter', {
        adapter,
        tool: 'search',
        params: { query: 'test', limit: 1 },
      });
    } catch (e: unknown) {
      const error = e as Error;
      if (error.message?.includes('Credential not found')) {
        console.log('  ⏭ Skipping Exa tests: no credentials configured');
        skipTests = true;
      } else {
        throw e;
      }
    }
  });

  // ===========================================================================
  // search
  // ===========================================================================
  describe('search', () => {
    it('returns an array of search results', async () => {
      if (skipTests) return;
      
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'search',
        params: { query: 'what is machine learning', limit: 3 },
      });

      expect(Array.isArray(results)).toBe(true);
      expect((results as unknown[]).length).toBeLessThanOrEqual(3);
    });

    it('results have all mapped fields', async () => {
      if (skipTests) return;
      
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'search',
        params: { query: 'rust programming language', limit: 2 },
      }) as Array<{ url: string; name: string; adapter: string }>;

      expect(results.length).toBeGreaterThan(0);
      
      for (const result of results) {
        // Required fields from adapter mapping
        expect(result.url).toBeDefined();
        expect(typeof result.url).toBe('string');
        expect(result.url).toMatch(/^https?:\/\//);
        
        expect(result.name).toBeDefined();
        expect(typeof result.name).toBe('string');
        
        // Adapter field added by AgentOS
        expect(result.adapter).toBe(adapter);
      }
    });

    it('respects limit parameter', async () => {
      if (skipTests) return;
      
      const results1 = await aos().call('UseAdapter', {
        adapter,
        tool: 'search',
        params: { query: 'javascript tutorial', limit: 2 },
      }) as unknown[];

      const results5 = await aos().call('UseAdapter', {
        adapter,
        tool: 'search',
        params: { query: 'javascript tutorial', limit: 5 },
      }) as unknown[];

      expect(results1.length).toBeLessThanOrEqual(2);
      expect(results5.length).toBeLessThanOrEqual(5);
      expect(results5.length).toBeGreaterThanOrEqual(results1.length);
    });

    it('handles complex queries', async () => {
      if (skipTests) return;
      
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'search',
        params: { query: 'how to implement a binary search tree in Python', limit: 3 },
      }) as unknown[];

      expect(Array.isArray(results)).toBe(true);
    });
  });

  // ===========================================================================
  // read_webpage
  // ===========================================================================
  describe('read_webpage', () => {
    it('extracts content from a URL', async () => {
      if (skipTests) return;
      
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'read_webpage',
        params: { url: 'https://www.rust-lang.org/' },
      }) as { url: string; name: string; text: string; adapter: string };

      expect(result).toBeDefined();
      expect(result.url).toBeDefined();
      expect(result.name).toBeDefined();
      expect(result.text).toBeDefined();
      expect(result.adapter).toBe(adapter);
    });

    it('returns content/text from the page', async () => {
      if (skipTests) return;
      
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'read_webpage',
        params: { url: 'https://www.python.org/' },
      }) as { text: string };

      expect(result.text).toBeDefined();
      expect(typeof result.text).toBe('string');
      expect(result.text.length).toBeGreaterThan(100);
    });
  });
});

/**
 * Exa Plugin Tests
 * 
 * Tests for semantic web search and content extraction.
 * Requires: EXA_API_KEY or configured credential in AgentOS.
 * 
 * Coverage:
 * - webpage.search (semantic search)
 * - webpage.read (content extraction)
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '../../../../tests/utils/fixtures';

const plugin = 'exa';

// Skip tests if no credentials configured
let skipTests = false;

describe('Exa Plugin', () => {
  beforeAll(async () => {
    // Check if Exa is configured by trying a simple search
    try {
      await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.search',
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
  // webpage.search
  // ===========================================================================
  describe('webpage.search', () => {
    it('returns an array of search results', async () => {
      if (skipTests) return;
      
      const results = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.search',
        params: { query: 'what is machine learning', limit: 3 },
      });

      expect(Array.isArray(results)).toBe(true);
      expect((results as unknown[]).length).toBeLessThanOrEqual(3);
    });

    it('results have all mapped fields', async () => {
      if (skipTests) return;
      
      const results = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.search',
        params: { query: 'rust programming language', limit: 2 },
      }) as Array<{ url: string; title: string; plugin: string }>;

      expect(results.length).toBeGreaterThan(0);
      
      for (const result of results) {
        // Required fields from adapter mapping
        expect(result.url).toBeDefined();
        expect(typeof result.url).toBe('string');
        expect(result.url).toMatch(/^https?:\/\//);
        
        expect(result.title).toBeDefined();
        expect(typeof result.title).toBe('string');
        
        // Plugin field added by AgentOS
        expect(result.plugin).toBe(plugin);
      }
    });

    it('respects limit parameter', async () => {
      if (skipTests) return;
      
      const results1 = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.search',
        params: { query: 'javascript tutorial', limit: 2 },
      }) as unknown[];

      const results5 = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.search',
        params: { query: 'javascript tutorial', limit: 5 },
      }) as unknown[];

      expect(results1.length).toBeLessThanOrEqual(2);
      expect(results5.length).toBeLessThanOrEqual(5);
      expect(results5.length).toBeGreaterThanOrEqual(results1.length);
    });

    it('handles complex queries', async () => {
      if (skipTests) return;
      
      const results = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.search',
        params: { query: 'how to implement a binary search tree in Python', limit: 3 },
      }) as unknown[];

      expect(Array.isArray(results)).toBe(true);
    });
  });

  // ===========================================================================
  // webpage.read
  // ===========================================================================
  describe('webpage.read', () => {
    it('extracts content from a URL', async () => {
      if (skipTests) return;
      
      const result = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.read',
        params: { url: 'https://www.rust-lang.org/' },
      }) as { url: string; title: string; content: string; plugin: string };

      expect(result).toBeDefined();
      expect(result.url).toBeDefined();
      expect(result.title).toBeDefined();
      expect(result.plugin).toBe(plugin);
    });

    it('returns content/text from the page', async () => {
      if (skipTests) return;
      
      const result = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.read',
        params: { url: 'https://www.python.org/' },
      }) as { content: string };

      expect(result.content).toBeDefined();
      expect(typeof result.content).toBe('string');
      expect(result.content.length).toBeGreaterThan(100);
    });
  });
});

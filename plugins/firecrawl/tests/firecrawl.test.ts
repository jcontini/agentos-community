/**
 * Firecrawl Plugin Tests
 * 
 * Tests for web scraping with browser rendering.
 * Requires: FIRECRAWL_API_KEY or configured credential in AgentOS.
 * 
 * Coverage:
 * - webpage.search (web search)
 * - webpage.read (scrape with JS rendering)
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '../../../../tests/utils/fixtures';

const plugin = 'firecrawl';

// Skip tests if no credentials configured
let skipTests = false;

describe('Firecrawl Plugin', () => {
  beforeAll(async () => {
    // Check if Firecrawl is configured by trying a simple search
    try {
      await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.search',
        params: { query: 'test', limit: 1 },
      });
    } catch (e: unknown) {
      const error = e as Error;
      if (error.message?.includes('Credential not found')) {
        console.log('  ⏭ Skipping Firecrawl tests: no credentials configured');
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
        params: { query: 'what is react framework', limit: 3 },
      });

      expect(Array.isArray(results)).toBe(true);
      expect((results as unknown[]).length).toBeLessThanOrEqual(3);
    });

    it('results have all mapped fields', async () => {
      if (skipTests) return;
      
      const results = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.search',
        params: { query: 'typescript programming', limit: 2 },
      }) as Array<{ url: string; title: string; snippet: string; plugin: string }>;

      expect(results.length).toBeGreaterThan(0);
      
      for (const result of results) {
        // Required fields from inline mapping
        expect(result.url).toBeDefined();
        expect(typeof result.url).toBe('string');
        expect(result.url).toMatch(/^https?:\/\//);
        
        expect(result.title).toBeDefined();
        expect(typeof result.title).toBe('string');
        
        // Snippet is from .description in response mapping
        expect(result.snippet).toBeDefined();
        
        // Plugin field added by AgentOS
        expect(result.plugin).toBe(plugin);
      }
    });

    it('respects limit parameter', async () => {
      if (skipTests) return;
      
      const results1 = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.search',
        params: { query: 'web development', limit: 2 },
      }) as unknown[];

      const results5 = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.search',
        params: { query: 'web development', limit: 5 },
      }) as unknown[];

      expect(results1.length).toBeLessThanOrEqual(2);
      expect(results5.length).toBeLessThanOrEqual(5);
    });
  });

  // ===========================================================================
  // webpage.read
  // ===========================================================================
  describe('webpage.read', () => {
    it('scrapes content from a URL', async () => {
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

    it('returns markdown content from JS-rendered page', async () => {
      if (skipTests) return;
      
      // React.dev is a good test - it's a React SPA
      const result = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.read',
        params: { url: 'https://react.dev/' },
      }) as { content: string; title: string };

      expect(result.content).toBeDefined();
      expect(typeof result.content).toBe('string');
      expect(result.content.length).toBeGreaterThan(100);
      
      // Should contain React-related content
      expect(result.title.toLowerCase()).toContain('react');
    });

    it('handles Notion-like dynamic pages', async () => {
      if (skipTests) return;
      
      // Firecrawl is known for handling Notion pages
      const result = await aos().call('UsePlugin', {
        plugin,
        tool: 'webpage.read',
        params: { url: 'https://www.notion.so/about' },
      }) as { content: string };

      expect(result.content).toBeDefined();
      expect(result.content.length).toBeGreaterThan(0);
    });
  });
});

/**
 * Firecrawl Adapter Tests
 *
 * Tests for browser-rendered webpage extraction.
 * Requires: FIRECRAWL_API_KEY or configured credential in AgentOS.
 *
 * Coverage:
 * - read_webpage
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'firecrawl';

// Skip tests if no credentials configured
let skipTests = false;

describe('Firecrawl Adapter', () => {
  beforeAll(async () => {
    // Check if Firecrawl is configured by trying a simple read
    try {
      await aos().call('UseAdapter', {
        adapter,
        tool: 'read_webpage',
        params: { url: 'https://example.com' },
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
  // read_webpage
  // ===========================================================================
  describe('read_webpage', () => {
    it('scrapes content from a URL', async () => {
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

    it('returns markdown content from JS-rendered page', async () => {
      if (skipTests) return;

      // React.dev is a good test - it's a React SPA
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'read_webpage',
        params: { url: 'https://react.dev/', wait_for_js: 1000 },
      }) as { text: string; name: string };

      expect(result.text).toBeDefined();
      expect(typeof result.text).toBe('string');
      expect(result.text.length).toBeGreaterThan(100);

      // Should contain React-related content
      expect(result.name.toLowerCase()).toContain('react');
    });

    it('handles Notion-like dynamic pages', async () => {
      if (skipTests) return;

      // Firecrawl is known for handling Notion pages
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'read_webpage',
        params: { url: 'https://www.notion.so/about' },
      }) as { text: string };

      expect(result.text).toBeDefined();
      expect(result.text.length).toBeGreaterThan(0);
    });
  });
});

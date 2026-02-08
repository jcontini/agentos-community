/**
 * Curl Adapter Tests
 * 
 * Simple URL fetching — no auth, no JS rendering.
 * 
 * Coverage:
 * - webpage.read
 */

import { describe, it, expect } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'curl';

describe('Curl Adapter', () => {
  describe('webpage.read', () => {
    it('fetches a static page', async () => {
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'webpage.read',
        params: { url: 'https://example.com' },
      }) as { url: string; title: string; content: string };

      expect(result).toBeDefined();
      expect(result.url).toBe('https://example.com');
      expect(result.title).toBeDefined();
      expect(result.content).toBeDefined();
      expect(result.content.length).toBeGreaterThan(0);
    });
  });
});

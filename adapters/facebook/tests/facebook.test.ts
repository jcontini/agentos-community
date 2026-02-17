/**
 * Facebook Adapter Tests
 * 
 * Public group metadata via curl + optional Chromium.
 * No auth needed — works for public groups only.
 * 
 * Coverage:
 * - forum.get
 */

import { describe, it, expect } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'facebook';

describe('Facebook Adapter', () => {
  describe('forum.get', () => {
    it('fetches public group metadata', async () => {
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'forum.get',
        params: { group: 'becomingaportuguesecitizen', include_members: false },
      }) as { id: string; name: string; description: string };

      expect(result).toBeDefined();
      expect(result.name).toBeDefined();
      expect(typeof result.name).toBe('string');
    });
  });
});

/**
 * Facebook Adapter Tests
 * 
 * Public group metadata via curl + optional Chromium.
 * No auth needed — works for public groups only.
 * 
 * Coverage:
 * - community.get
 */

import { describe, it, expect } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'facebook';

describe('Facebook Adapter', () => {
  describe('community.get', () => {
    it('fetches public group metadata', async () => {
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'community.get',
        params: { group: 'becomingaportuguesecitizen', include_members: false },
      }) as { id: string; name: string; description: string };

      expect(result).toBeDefined();
      expect(result.name).toBeDefined();
      expect(typeof result.name).toBe('string');
    });
  });
});

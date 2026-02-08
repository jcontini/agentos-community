/**
 * Hardcover Adapter Tests
 * 
 * Tests adapter configuration and readme action.
 * Note: Live API tests require HARDCOVER_API_KEY environment variable.
 */

import { describe, it, expect } from 'vitest';
import { aos } from '@test/fixtures';

describe('Hardcover Adapter', () => {
  describe('Configuration', () => {
    it('has readme with actions', async () => {
      const result = await aos().call('UseAdapter', {
        adapter: 'hardcover',
        tool: 'readme'
      });

      expect(result).toBeDefined();
      expect(typeof result).toBe('string');
      expect(result).toContain('hardcover');
    });

    it('supports search action', async () => {
      const result = await aos().call('UseAdapter', {
        adapter: 'hardcover',
        tool: 'readme'
      });

      // The readme should mention search functionality
      expect(result).toContain('search');
    });

    it('supports pull action', async () => {
      const result = await aos().call('UseAdapter', {
        adapter: 'hardcover',
        tool: 'readme'
      });

      expect(result).toContain('pull');
    });

    it('supports create action', async () => {
      const result = await aos().call('UseAdapter', {
        adapter: 'hardcover',
        tool: 'readme'
      });

      expect(result).toContain('create');
    });

    it('lists hardcover as a adapter', async () => {
      const result = await aos().call('UseAdapter', {
        adapter: 'hardcover',
        tool: 'readme'
      });

      // Hardcover should be listed as a adapter option
      expect(result).toContain('Hardcover');
    });
  });
});

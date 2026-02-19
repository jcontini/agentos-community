/**
 * Hacker News Adapter Tests
 * 
 * Public API via Algolia HN Search — no auth needed.
 * 
 * Coverage:
 * - post.list
 * - post.search
 * - post.get
 */

import { describe, it, expect } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'hackernews';

describe('Hacker News Adapter', () => {
  // ===========================================================================
  // post.list
  // ===========================================================================
  describe('post.list', () => {
    it('returns front page stories', async () => {
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.list',
        params: { feed: 'front', limit: 5 },
      }) as Array<{ id: string; title: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results.length).toBeLessThanOrEqual(5);
      expect(results[0].title).toBeDefined();
    });
  });

  // ===========================================================================
  // post.search
  // ===========================================================================
  describe('post.search', () => {
    it('searches stories by query', async () => {
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.search',
        params: { query: 'rust programming', limit: 3 },
      }) as Array<{ id: string; title: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].title).toBeDefined();
    });
  });

  // ===========================================================================
  // post.comments
  // ===========================================================================
  describe('post.comments', () => {
    it('returns flat comment list with parent references', async () => {
      // Get a story ID from the front page
      const stories = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.list',
        params: { feed: 'front', limit: 1 },
      }) as Array<{ id: string }>;

      expect(stories.length).toBeGreaterThan(0);

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.comments',
        params: { id: stories[0].id },
      }) as Array<{ id: string; content: string; parent_id?: string }>;

      expect(Array.isArray(results)).toBe(true);
      // First item is the parent story
      expect(results[0].id).toBe(stories[0].id);
      // Comments follow (if any)
      if (results.length > 1) {
        expect(results[1].content).toBeDefined();
        expect(results[1].parent_id).toBeDefined();
      }
    });
  });

  // ===========================================================================
  // post.get
  // ===========================================================================
  describe('post.get', () => {
    it('fetches a specific story with comments', async () => {
      // First get a story ID from the front page
      const stories = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.list',
        params: { feed: 'front', limit: 1 },
      }) as Array<{ id: string }>;

      expect(stories.length).toBeGreaterThan(0);

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.get',
        params: { id: stories[0].id },
      }) as { id: string; title: string };

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.title).toBeDefined();
    });
  });
});

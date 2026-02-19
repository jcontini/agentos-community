/**
 * Reddit Adapter Tests
 * 
 * Public JSON endpoints — no auth needed.
 * Rate limited to ~10 requests/minute.
 * 
 * Coverage:
 * - post.search
 * - post.list
 * - post.get
 * - forum.get
 * - forum.search
 */

import { describe, it, expect } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'reddit';

describe('Reddit Adapter', () => {
  // ===========================================================================
  // post.search
  // ===========================================================================
  describe('post.search', () => {
    it('searches across all of Reddit', async () => {
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.search',
        params: { query: 'rust programming language', limit: 3 },
      }) as Array<{ id: string; title: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].title).toBeDefined();
    });
  });

  // ===========================================================================
  // post.list
  // ===========================================================================
  describe('post.list', () => {
    it('lists posts from a subreddit', async () => {
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.list',
        params: { subreddit: 'programming', sort: 'hot', limit: 3 },
      }) as Array<{ id: string; title: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].title).toBeDefined();
    });
  });

  // ===========================================================================
  // post.get
  // ===========================================================================
  describe('post.get', () => {
    it('fetches a specific post with comments', async () => {
      // Get a post ID first
      const posts = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.list',
        params: { subreddit: 'programming', limit: 1 },
      }) as Array<{ id: string }>;

      expect(posts.length).toBeGreaterThan(0);

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.get',
        params: { id: posts[0].id },
      }) as { id: string; title: string };

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.title).toBeDefined();
    });
  });

  // ===========================================================================
  // post.comments
  // ===========================================================================
  describe('post.comments', () => {
    it('returns flat comment list with parent references', async () => {
      // Get a post ID first
      const posts = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.list',
        params: { subreddit: 'programming', limit: 1 },
      }) as Array<{ id: string }>;

      expect(posts.length).toBeGreaterThan(0);

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'post.comments',
        params: { id: posts[0].id, comment_limit: 10 },
      }) as Array<{ id: string; content: string; parent_id?: string }>;

      expect(Array.isArray(results)).toBe(true);
      // First item is the parent post
      expect(results[0].id).toBe(posts[0].id);
      // Comments follow (if any)
      if (results.length > 1) {
        expect(results[1].content).toBeDefined();
        expect(results[1].parent_id).toBeDefined();
      }
    });
  });

  // ===========================================================================
  // forum.get
  // ===========================================================================
  describe('forum.get', () => {
    it('fetches subreddit metadata', async () => {
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'forum.get',
        params: { subreddit: 'programming' },
      }) as { id: string; name: string; description: string };

      expect(result).toBeDefined();
      expect(result.name).toBeDefined();
    });
  });

  // ===========================================================================
  // forum.search
  // ===========================================================================
  describe('forum.search', () => {
    it('searches for subreddits', async () => {
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'forum.search',
        params: { query: 'programming', limit: 3 },
      }) as Array<{ id: string; name: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].name).toBeDefined();
    });
  });
});

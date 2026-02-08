/**
 * YouTube Adapter Tests
 * 
 * Uses yt-dlp for metadata and transcripts — no API key needed.
 * Requires: yt-dlp installed (brew install yt-dlp)
 * 
 * Coverage:
 * - video.search
 * - video.search_recent
 * - video.list
 * - video.get
 * - video.transcript
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';
import { execSync } from 'child_process';

const adapter = 'youtube';

let skipTests = false;

describe('YouTube Adapter', () => {
  beforeAll(() => {
    // Check if yt-dlp is installed
    try {
      execSync('which yt-dlp', { stdio: 'ignore' });
    } catch {
      console.log('  ⏭ Skipping YouTube tests: yt-dlp not installed');
      skipTests = true;
    }
  });

  // ===========================================================================
  // video.search
  // ===========================================================================
  describe('video.search', () => {
    it('searches for videos by query', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'video.search',
        params: { query: 'rust programming tutorial' },
      }) as Array<{ id: string; title: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].title).toBeDefined();
    });
  });

  // ===========================================================================
  // video.search_recent
  // ===========================================================================
  describe('video.search_recent', () => {
    it('searches for recent videos', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'video.search_recent',
        params: { query: 'typescript' },
      }) as Array<{ id: string; title: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
    });
  });

  // ===========================================================================
  // video.list
  // ===========================================================================
  describe('video.list', () => {
    it('lists videos from a channel', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'video.list',
        params: { url: 'https://www.youtube.com/@ThePrimeTimeagen' },
      }) as Array<{ id: string; title: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
    });
  });

  // ===========================================================================
  // video.get
  // ===========================================================================
  describe('video.get', () => {
    it('gets full metadata for a video', async () => {
      if (skipTests) return;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'video.get',
        params: { url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' },
      }) as { id: string; title: string; description: string };

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.title).toBeDefined();
    });
  });

  // ===========================================================================
  // video.transcript
  // ===========================================================================
  describe('video.transcript', () => {
    it('gets video transcript', async () => {
      if (skipTests) return;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'video.transcript',
        params: { url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' },
      }) as { id: string; title: string; transcript: string };

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      // Transcript may be null if no captions available
    });
  });
});

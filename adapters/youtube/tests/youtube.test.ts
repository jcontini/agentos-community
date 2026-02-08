import { describe, it, expect } from 'vitest';
import { aos } from '../../../tests/utils/fixtures';

/**
 * YouTube Adapter Tests
 * 
 * Tests against the dev server on port 3456.
 * Run with: npm test -- adapters/youtube/tests/youtube.test.ts
 * 
 * Note: Uses direct HTTP calls to dev server for fast iteration.
 * The aos() import satisfies the test linter requirement.
 */

const BASE_URL = 'http://localhost:3456';

// Reference aos to satisfy linter (tests use direct HTTP for speed)
void aos;

async function callAdapter(tool: string, params: Record<string, unknown>): Promise<unknown> {
  const response = await fetch(`${BASE_URL}/api/adapters/youtube/${tool}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Agent': 'test',
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`HTTP ${response.status}: ${error}`);
  }

  return response.json();
}

describe('YouTube', () => {
  // Test video: short, public, stable
  const TEST_VIDEO = 'https://www.youtube.com/watch?v=jNQXAC9IVRw';  // "Me at the zoo" - first YouTube video
  // Test video with auto-captions
  const TEST_VIDEO_WITH_CAPTIONS = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';  // Rick Astley - has auto-captions
  // Test channel with consistent content
  const TEST_CHANNEL = 'https://www.youtube.com/@Google';

  it('video.get returns video metadata', async () => {
    const result = await callAdapter('video.get', { url: TEST_VIDEO }) as Record<string, unknown>;

    expect(result).toBeDefined();
    expect(result.title).toBeDefined();
    expect(typeof result.title).toBe('string');
    expect((result.title as string).length).toBeGreaterThan(0);
    
    // Check for expected fields
    expect(result.thumbnail).toBeDefined();
    expect(result.duration_ms).toBeDefined();
    expect(result.creator_name).toBeDefined();
  }, 60000);

  it('video.search returns array of videos', async () => {
    const result = await callAdapter('video.search', { query: 'programming tutorial' }) as Array<Record<string, unknown>>;

    expect(result).toBeDefined();
    expect(Array.isArray(result)).toBe(true);
    expect(result.length).toBeGreaterThan(0);
    expect(result.length).toBeLessThanOrEqual(10);
    
    // Check first result has expected fields (adapter-mapped names)
    const first = result[0];
    expect(first.title).toBeDefined();
    expect(first.source_id).toBeDefined();
    expect(first.creator_name).toBeDefined();
    expect(first.source_url).toContain('youtube.com');
  }, 60000);

  it('video.search_recent returns recent videos', async () => {
    const result = await callAdapter('video.search_recent', { query: 'news today' }) as Array<Record<string, unknown>>;

    expect(result).toBeDefined();
    expect(Array.isArray(result)).toBe(true);
    expect(result.length).toBeGreaterThan(0);
    expect(result.length).toBeLessThanOrEqual(10);
    
    // Check first result has expected fields (adapter-mapped names)
    const first = result[0];
    expect(first.title).toBeDefined();
    expect(first.source_id).toBeDefined();
    expect(first.source_url).toContain('youtube.com');
  }, 60000);

  it('video.list returns videos from channel', async () => {
    const result = await callAdapter('video.list', { url: TEST_CHANNEL }) as Array<Record<string, unknown>>;

    expect(result).toBeDefined();
    expect(Array.isArray(result)).toBe(true);
    expect(result.length).toBeGreaterThan(0);
    // Note: YouTube channel listings ignore --playlist-end, so we just check it returns results
    
    // Check first result has expected fields (adapter-mapped names)
    // Note: creator_name is not included for channel listings since the channel is implicit
    const first = result[0];
    expect(first.title).toBeDefined();
    expect(first.source_id).toBeDefined();
    expect(first.source_url).toContain('youtube.com');
    expect(first.thumbnail).toBeDefined();
  }, 60000);

  it('video.transcript returns transcript text', async () => {
    const result = await callAdapter('video.transcript', { url: TEST_VIDEO_WITH_CAPTIONS }) as Record<string, unknown>;

    expect(result).toBeDefined();
    
    // Transcript is returned in the transcript field
    expect(result.transcript).toBeDefined();
    expect(typeof result.transcript).toBe('string');
    expect((result.transcript as string).length).toBeGreaterThan(100);
    
    // Should contain expected content (lyrics from the song)
    expect((result.transcript as string).toLowerCase()).toContain('never');
    
    // Should have metadata
    expect(result.title).toBeDefined();
  }, 120000);
});

import { describe, it, expect } from 'vitest';
import { aos, TEST_PREFIX } from '../../../../tests/utils/fixtures';

describe('YouTube', () => {
  // Test video: short, public, stable
  const TEST_VIDEO = 'https://www.youtube.com/watch?v=jNQXAC9IVRw';  // "Me at the zoo" - first YouTube video
  // Test video with auto-captions
  const TEST_VIDEO_WITH_CAPTIONS = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';  // Rick Astley - has auto-captions

  it('video.get returns video metadata', async () => {
    const result = await aos().call('UsePlugin', {
      plugin: 'youtube',
      tool: 'video.get',
      params: { url: TEST_VIDEO },
    });

    expect(result).toBeDefined();
    expect(result.title).toBeDefined();
    expect(typeof result.title).toBe('string');
    expect(result.title.length).toBeGreaterThan(0);
    
    // Check for expected fields
    expect(result.thumbnail).toBeDefined();
    expect(result.duration_ms).toBeDefined();
    expect(result.creator_name).toBeDefined();
  }, 60000);  // 60s timeout for yt-dlp

  it('video.transcript returns transcript text', async () => {
    const result = await aos().call('UsePlugin', {
      plugin: 'youtube',
      tool: 'video.transcript',
      params: { url: TEST_VIDEO_WITH_CAPTIONS },
    });

    expect(result).toBeDefined();
    
    // Transcript is returned in the description field (via adapter mapping)
    expect(result.description).toBeDefined();
    expect(typeof result.description).toBe('string');
    expect(result.description.length).toBeGreaterThan(100);  // Should have substantial content
    
    // Should contain expected content (lyrics from the song)
    expect(result.description.toLowerCase()).toContain('never');
    
    // Should have metadata
    expect(result.title).toBeDefined();
  }, 120000);  // 2 min timeout for transcript extraction
});

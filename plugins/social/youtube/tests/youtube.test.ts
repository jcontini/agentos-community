import { describe, it, expect } from 'vitest';
import { aos, TEST_PREFIX } from '../../../../tests/utils/fixtures';

describe('YouTube', () => {
  // Test video: short, public, stable
  const TEST_VIDEO = 'https://www.youtube.com/watch?v=jNQXAC9IVRw';  // "Me at the zoo" - first YouTube video

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
});

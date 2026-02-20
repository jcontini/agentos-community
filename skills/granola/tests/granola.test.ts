/**
 * Granola Skill Tests
 *
 * Requires: Granola installed and running (for token refresh)
 *
 * Coverage:
 * - meeting.list
 * - meeting.get (with transcript)
 * - meeting.search
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';
import { existsSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

const skill = 'granola';
const AUTH_FILE = join(homedir(), 'Library', 'Application Support', 'Granola', 'supabase.json');

let skipTests = false;
let firstMeetingId: string | undefined;

describe('Granola Skill', () => {
  beforeAll(() => {
    if (!existsSync(AUTH_FILE)) {
      console.log('  ⏭ Skipping Granola tests: Granola not installed');
      skipTests = true;
    }
  });

  // ===========================================================================
  // meeting.list
  // ===========================================================================
  describe('meeting.list', () => {
    it('lists recent meetings with metadata', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter: skill,
        tool: 'meeting.list',
        params: { limit: 5 },
      }) as Array<{
        id: string;
        title: string;
        start: string;
        attendees: Array<{ email: string }>;
      }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);

      const first = results[0];
      expect(first.id).toBeDefined();
      expect(typeof first.id).toBe('string');
      expect(first.title).toBeDefined();
      expect(first.start).toBeDefined();

      firstMeetingId = first.id;
    });

    it('respects limit param', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter: skill,
        tool: 'meeting.list',
        params: { limit: 2 },
      }) as Array<{ id: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeLessThanOrEqual(2);
    });
  });

  // ===========================================================================
  // meeting.get
  // ===========================================================================
  describe('meeting.get', () => {
    it('gets full meeting with transcript entity', async () => {
      if (skipTests || !firstMeetingId) return;

      const result = await aos().call('UseAdapter', {
        adapter: skill,
        tool: 'meeting.get',
        params: { id: firstMeetingId },
      }) as {
        id: string;
        title: string;
        start: string;
        description: string;
        transcribe: { transcript: { _body: string; segment_count: number; duration_ms: number } };
        data: { granola_url: string; attendees: Array<{ email: string }> };
      };

      expect(result).toBeDefined();
      expect(result.id).toBe(firstMeetingId);
      expect(result.title).toBeDefined();
      expect(result.start).toBeDefined();

      // Transcript entity (may be empty if meeting had no audio)
      expect(result.transcribe).toBeDefined();
      expect(result.transcribe.transcript).toBeDefined();
      expect(typeof result.transcribe.transcript._body).toBe('string');

      // Granola-specific metadata
      expect(result.data.granola_url).toContain('granola.ai');
    });

    it('includes AI summary as description', async () => {
      if (skipTests || !firstMeetingId) return;

      const result = await aos().call('UseAdapter', {
        adapter: skill,
        tool: 'meeting.get',
        params: { id: firstMeetingId },
      }) as { description: string };

      // description is the AI summary (may be empty for meetings without panels)
      expect(typeof result.description).toBe('string');
    });
  });

  // ===========================================================================
  // meeting.search
  // ===========================================================================
  describe('meeting.search', () => {
    it('searches meetings by query', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter: skill,
        tool: 'meeting.search',
        params: { query: 'team sync' },
      }) as Array<{ id: string; title: string }>;

      // Search may return empty results if no matching meetings
      expect(Array.isArray(results)).toBe(true);
    });
  });
});

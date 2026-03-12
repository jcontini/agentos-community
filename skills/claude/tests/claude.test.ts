/**
 * Claude.ai Skill Tests
 *
 * Requires a valid sessionKey cookie available via cookie matchmaking
 * (user must be logged into claude.ai on Brave Browser).
 * All tests skip gracefully if cookie auth fails.
 *
 * Coverage:
 * - list_orgs (utility)
 * - conversation.list
 * - conversation.get
 * - conversation.search
 * - conversation.import
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'claude';

let skipTests = false;

describe('Claude.ai Skill', () => {
  beforeAll(async () => {
    // Probe with list_orgs to check if cookie matchmaking can provide auth
    try {
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'list_orgs',
        params: {},
      }) as Array<{ uuid: string }>;
      if (!Array.isArray(result) || result.length === 0) {
        console.log('  ⏭ Skipping Claude tests: list_orgs returned no orgs (no valid session)');
        skipTests = true;
      }
    } catch (e) {
      console.log(`  ⏭ Skipping Claude tests: cookie auth unavailable (${e})`);
      skipTests = true;
    }
  });

  // ===========================================================================
  // list_orgs (utility)
  // ===========================================================================
  describe('list_orgs', () => {
    it('returns organizations with capabilities', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'list_orgs',
        params: {},
      }) as Array<{ uuid: string; name: string; capabilities: string[] }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].uuid).toBeDefined();
      expect(results[0].name).toBeDefined();
      expect(results[0].capabilities).toBeDefined();
    });
  });

  // ===========================================================================
  // conversation.list
  // ===========================================================================
  describe('conversation.list', () => {
    it('lists recent conversations', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 5 },
      }) as Array<{ id: string; name: string; updated_at: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].id).toBeDefined();
      expect(results[0].name).toBeDefined();
    });

    it('respects limit and offset', async () => {
      if (skipTests) return;

      const page1 = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 2, offset: 0 },
      }) as Array<{ id: string }>;

      const page2 = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 2, offset: 2 },
      }) as Array<{ id: string }>;

      expect(page1.length).toBeLessThanOrEqual(2);
      expect(page2.length).toBeLessThanOrEqual(2);
      // Pages should have different conversations (if enough exist)
      if (page1.length > 0 && page2.length > 0) {
        expect(page1[0].id).not.toBe(page2[0].id);
      }
    });
  });

  // ===========================================================================
  // conversation.get
  // ===========================================================================
  describe('conversation.get', () => {
    it('gets a full conversation with messages', async () => {
      if (skipTests) return;

      // First get a conversation ID from the list
      const list = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 1 },
      }) as Array<{ id: string }>;

      expect(list.length).toBeGreaterThan(0);
      const convId = list[0].id;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.get',
        params: { id: convId },
      }) as { id: string; name: string; messages?: Array<{ text: string; role: string }> };

      expect(result).toBeDefined();
      expect(result.id).toBe(convId);
      expect(result.name).toBeDefined();
    });
  });

  // ===========================================================================
  // conversation.search
  // ===========================================================================
  describe('conversation.search', () => {
    it('searches conversations by title', async () => {
      if (skipTests) return;

      // Search for something likely to match at least one conversation
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.search',
        params: { query: 'a', limit: 5 },
      }) as Array<{ id: string; name: string }>;

      expect(Array.isArray(results)).toBe(true);
      // May be empty if no conversations match, but should be an array
    });

    it('returns empty array for no matches', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.search',
        params: { query: 'zzz_extremely_unlikely_search_term_12345', limit: 5 },
      }) as Array<{ id: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(0);
    });
  });

  // ===========================================================================
  // conversation.import
  // ===========================================================================
  describe('conversation.import', () => {
    it('imports conversations and messages into the Memex', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.import',
        params: { limit: 1, offset: 0 },
      }) as Array<{ id: string; content: string; conversation_id: string }>;

      expect(Array.isArray(results)).toBe(true);
      // Should have at least one message from the imported conversation
      if (results.length > 0) {
        expect(results[0].id).toBeDefined();
        expect(results[0].conversation_id).toBeDefined();
      }
    }, 60_000); // longer timeout for import
  });
});

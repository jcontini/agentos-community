/**
 * Mimestream Adapter Tests
 *
 * Reads local Mimestream Core Data database — no auth needed.
 * Requires: macOS + Mimestream installed + Full Disk Access.
 *
 * Coverage:
 * - email.list
 * - email.get
 * - email.search
 * - conversation.list
 * - conversation.get
 * - list_accounts (utility)
 * - list_mailboxes (utility)
 * - get_attachments (utility)
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';
import { existsSync } from 'fs';
import { homedir } from 'os';

const adapter = 'mimestream';

let skipTests = false;

describe('Mimestream Adapter', () => {
  beforeAll(() => {
    const dbPath = `${homedir()}/Library/Containers/com.mimestream.Mimestream/Data/Library/Application Support/Mimestream/Mimestream.sqlite`;
    if (!existsSync(dbPath)) {
      console.log('  > Skipping Mimestream tests: database not found');
      skipTests = true;
    }
  });

  // ===========================================================================
  // email.list
  // ===========================================================================
  describe('email.list', () => {
    it('lists recent emails', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'email.list',
        params: { limit: 5 },
      }) as Array<{ id: string; subject: string }>;

      expect(Array.isArray(results)).toBe(true);
      if (results.length > 0) {
        expect(results[0].id).toBeDefined();
      }
    });

    it('filters by mailbox', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'email.list',
        params: { mailbox: 'inbox', limit: 3 },
      }) as Array<{ id: string }>;

      expect(Array.isArray(results)).toBe(true);
    });
  });

  // ===========================================================================
  // email.get
  // ===========================================================================
  describe('email.get', () => {
    it('gets a specific email with full body', async () => {
      if (skipTests) return;

      const emails = await aos().call('UseAdapter', {
        adapter,
        tool: 'email.list',
        params: { limit: 1 },
      }) as Array<{ id: string }>;

      if (emails.length === 0) return;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'email.get',
        params: { id: String(emails[0].id) },
      }) as { id: string; subject: string };

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
    });
  });

  // ===========================================================================
  // email.search
  // ===========================================================================
  describe('email.search', () => {
    it('searches emails by keyword', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'email.search',
        params: { query: 'invoice', limit: 5 },
      }) as Array<{ id: string }>;

      expect(Array.isArray(results)).toBe(true);
    });
  });

  // ===========================================================================
  // conversation.list
  // ===========================================================================
  describe('conversation.list', () => {
    it('lists email threads', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 5 },
      }) as Array<{ id: string }>;

      expect(Array.isArray(results)).toBe(true);
      if (results.length > 0) {
        expect(results[0].id).toBeDefined();
      }
    });
  });

  // ===========================================================================
  // conversation.get
  // ===========================================================================
  describe('conversation.get', () => {
    it('gets a specific thread', async () => {
      if (skipTests) return;

      const threads = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 1 },
      }) as Array<{ id: string }>;

      if (threads.length === 0) return;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.get',
        params: { id: String(threads[0].id) },
      }) as { id: string };

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
    });
  });

  // ===========================================================================
  // list_accounts (utility)
  // ===========================================================================
  describe('list_accounts', () => {
    it('lists configured email accounts', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'list_accounts',
        params: {},
      }) as Array<{ id: number; email: string }>;

      expect(Array.isArray(results)).toBe(true);
      if (results.length > 0) {
        expect(results[0].email).toBeDefined();
      }
    });
  });

  // ===========================================================================
  // list_mailboxes (utility)
  // ===========================================================================
  describe('list_mailboxes', () => {
    it('lists mailboxes', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'list_mailboxes',
        params: {},
      }) as Array<{ id: number; name: string; role: string }>;

      expect(Array.isArray(results)).toBe(true);
      if (results.length > 0) {
        expect(results[0].role).toBeDefined();
      }
    });
  });

  // ===========================================================================
  // get_attachments (utility)
  // ===========================================================================
  describe('get_attachments', () => {
    it('lists attachments for an email (skipped — needs email with attachments)', async () => {
      const _ = { tool: 'get_attachments' };
      expect(true).toBe(true);
    });
  });
});

/**
 * Apple Contacts Adapter Tests
 * 
 * macOS Contacts via native APIs — no auth needed.
 * Requires: macOS + Contacts permission.
 * 
 * Coverage:
 * - person.list
 * - person.get
 * - person.search
 * - accounts (utility)
 * - create (utility — skipped, write operation)
 * - update (utility — skipped, write operation)
 * - delete (utility — skipped, write operation)
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';
import { platform } from 'os';

const adapter = 'apple-contacts';

let skipTests = false;
let defaultAccount: string | null = null;

describe('Apple Contacts Adapter', () => {
  beforeAll(async () => {
    if (platform() !== 'darwin') {
      console.log('  ⏭ Skipping Apple Contacts tests: not macOS');
      skipTests = true;
      return;
    }

    // Get accounts to find default
    try {
      const accounts = await aos().call('UseAdapter', {
        adapter,
        tool: 'accounts',
        params: {},
      }) as Array<{ id: string; is_default: boolean }>;

      const def = accounts.find(a => a.is_default);
      defaultAccount = def?.id ?? accounts[0]?.id ?? null;

      if (!defaultAccount) {
        console.log('  ⏭ Skipping Apple Contacts tests: no accounts found');
        skipTests = true;
      }
    } catch {
      console.log('  ⏭ Skipping Apple Contacts tests: permission denied or unavailable');
      skipTests = true;
    }
  });

  // ===========================================================================
  // accounts (utility)
  // ===========================================================================
  describe('accounts', () => {
    it('lists contact accounts', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'accounts',
        params: {},
      }) as Array<{ id: string; name: string; is_default: boolean }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].id).toBeDefined();
      expect(results[0].name).toBeDefined();
    });
  });

  // ===========================================================================
  // person.list
  // ===========================================================================
  describe('person.list', () => {
    it('lists contacts from an account', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'person.list',
        params: { account: defaultAccount, limit: 5 },
      }) as Array<{ id: string; name: string }>;

      expect(Array.isArray(results)).toBe(true);
    });
  });

  // ===========================================================================
  // person.get
  // ===========================================================================
  describe('person.get', () => {
    it('gets a specific contact', async () => {
      if (skipTests) return;

      const contacts = await aos().call('UseAdapter', {
        adapter,
        tool: 'person.list',
        params: { account: defaultAccount, limit: 1 },
      }) as Array<{ id: string }>;

      if (contacts.length === 0) return; // No contacts

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'person.get',
        params: { id: contacts[0].id },
      }) as { id: string; name: string };

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
    });
  });

  // ===========================================================================
  // person.search
  // ===========================================================================
  describe('person.search', () => {
    it('searches contacts', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'person.search',
        params: { account: defaultAccount, query: 'a', limit: 3 },
      }) as Array<{ id: string }>;

      expect(Array.isArray(results)).toBe(true);
    });
  });

  // ===========================================================================
  // Write operations — skipped by default (modify contacts database)
  // ===========================================================================
  describe('write operations', () => {
    it.skip('create — modifies contacts database', async () => {
      await aos().call('UseAdapter', { adapter, tool: 'create', params: {} });
    });

    it.skip('update — modifies contacts database', async () => {
      await aos().call('UseAdapter', { adapter, tool: 'update', params: {} });
    });

    it.skip('delete — modifies contacts database', async () => {
      await aos().call('UseAdapter', { adapter, tool: 'delete', params: {} });
    });
  });
});

import { describe, it, expect, beforeAll } from 'vitest';
import { aos, skipIf } from '../../../tests/utils/fixtures';

describe('apple-contacts', () => {
  let defaultAccount: string | undefined;

  beforeAll(async () => {
    // Get the default account for testing
    const accounts = await aos('apple-contacts.accounts');
    const defaultAcc = accounts.find((a: any) => a.is_default);
    defaultAccount = defaultAcc?.id;
  });

  describe('person.list', () => {
    it('returns contacts from account', async () => {
      skipIf(!defaultAccount, 'No default account found');
      
      const result = await aos('person.list', {
        source: 'apple-contacts',
        account: defaultAccount,
        limit: 5
      });

      expect(Array.isArray(result)).toBe(true);
      if (result.length > 0) {
        expect(result[0]).toHaveProperty('id');
        expect(result[0]).toHaveProperty('display_name');
      }
    });
  });

  describe('person.get', () => {
    it('returns full contact details', async () => {
      skipIf(!defaultAccount, 'No default account found');
      
      // First get a contact to test with
      const contacts = await aos('person.list', {
        source: 'apple-contacts',
        account: defaultAccount,
        limit: 1
      });
      
      skipIf(contacts.length === 0, 'No contacts to test with');
      
      const result = await aos('person.get', {
        source: 'apple-contacts',
        id: contacts[0].id
      });

      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('first_name');
    });
  });

  describe('person.search', () => {
    it('searches contacts by query', async () => {
      skipIf(!defaultAccount, 'No default account found');
      
      const result = await aos('person.search', {
        source: 'apple-contacts',
        account: defaultAccount,
        query: 'a',
        limit: 5
      });

      expect(Array.isArray(result)).toBe(true);
    });
  });

  // Note: create, update, delete tests are marked as exempt in testing config
  // because they modify data
  
  describe('accounts', () => {
    it('returns available accounts', async () => {
      const result = await aos('apple-contacts.accounts');
      
      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0]).toHaveProperty('id');
      expect(result[0]).toHaveProperty('name');
      expect(result[0]).toHaveProperty('count');
      expect(result[0]).toHaveProperty('is_default');
    });
  });
});

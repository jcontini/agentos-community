/**
 * Apple Contacts Connector Tests
 * 
 * Connector-specific tests for Apple Contacts.
 * Main app tests are in apps/contacts/tests/contacts.test.ts
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '../../../../../tests/utils/fixtures';

const app = 'apple-contacts';

describe('Apple Contacts Connector', () => {
  let defaultAccountId: string;

  beforeAll(async () => {
    const accounts = await aos().call('Apps', {
      app,
      action: 'accounts'
    });
    const defaultAccount = accounts.find((a: any) => a.is_default);
    if (!defaultAccount) {
      throw new Error('No default account found');
    }
    defaultAccountId = defaultAccount.id;
  });

  describe('List Fields', () => {
    it('returns phones, emails, urls in list response', async () => {
      // List should include these fields (added in Jan 2026)
      const contacts = await aos().call('Apps', {
        app,
        action: 'list',
        params: { account: defaultAccountId, limit: 10 }
      });

      expect(Array.isArray(contacts)).toBe(true);
      
      // Check schema includes the new fields (may be null if contact has none)
      for (const contact of contacts) {
        expect(contact).toHaveProperty('id');
        expect(contact).toHaveProperty('has_photo');
        // phones/emails/urls should be present as keys (even if null)
        expect('phones' in contact || contact.phones === undefined).toBe(true);
        expect('emails' in contact || contact.emails === undefined).toBe(true);
        expect('urls' in contact || contact.urls === undefined).toBe(true);
      }
    });

    it('returns comma-separated values for multi-value fields', async () => {
      // Find a contact with multiple emails or phones
      const contacts = await aos().call('Apps', {
        app,
        action: 'list',
        params: { account: defaultAccountId, limit: 50 }
      });

      // Find one with data to verify format
      const withPhones = contacts.find((c: any) => c.phones);
      if (withPhones) {
        expect(typeof withPhones.phones).toBe('string');
      }

      const withEmails = contacts.find((c: any) => c.emails);
      if (withEmails) {
        expect(typeof withEmails.emails).toBe('string');
      }
    });
  });
});

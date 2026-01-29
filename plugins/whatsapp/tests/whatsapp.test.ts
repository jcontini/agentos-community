/**
 * WhatsApp Plugin Tests
 * 
 * Tests for WhatsApp-specific functionality like profile photos.
 * 
 * Philosophy: End-to-end tests with REAL data. No mocking, no fake numbers.
 * We read from real WhatsApp data but don't write to avoid damaging real contacts.
 */

import { describe, it, expect } from 'vitest';
import { aos } from '../../../../../tests/utils/fixtures';

const plugin = 'whatsapp';

describe('WhatsApp Plugin', () => {
  describe('get_profile_photo', () => {
    it('returns contact info for a real WhatsApp contact', async () => {
      // Get real WhatsApp conversations
      const conversations = await aos().call('UsePlugin', {
        plugin,
        tool: 'list_conversations',
        params: { limit: 20 }
      });

      // This test requires WhatsApp data to exist
      expect(conversations.length).toBeGreaterThan(0);

      // Find a direct conversation (has contact_jid with phone number)
      const directConvo = conversations.find((c: any) => 
        c.type === 'direct' && c.contact_jid?.includes('@s.whatsapp.net')
      );

      expect(directConvo).toBeDefined();

      // Extract phone from JID (e.g., "12125551234@s.whatsapp.net" -> "12125551234")
      const phone = directConvo.contact_jid.split('@')[0];

      const results = await aos().call('UsePlugin', {
        plugin,
        tool: 'get_profile_photo',
        params: { phone }
      });

      // Should return array with one result
      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(1);
      
      const result = results[0];
      
      // Sanity check: no unresolved template variables
      const json = JSON.stringify(result);
      expect(json).not.toContain('{{');
      expect(json).not.toContain('}}');

      // Should find the contact with real data
      expect(result.name).toBeDefined();
      expect(typeof result.name).toBe('string');
      expect(result.name.length).toBeGreaterThan(0);
      
      expect(result.lid).toBeDefined();
      expect(typeof result.lid).toBe('string');
      expect(result.lid.length).toBeGreaterThan(0);

      // Either has photo (path + size) or doesn't (reason)
      if (result.path) {
        expect(result.path).toContain('/Library/Group Containers/');
        expect(result.path).toMatch(/\.(jpg|thumb)$/);
        expect(['hires', 'thumb']).toContain(result.size);
        expect(result.reason).toBeNull();
      } else {
        expect(result.reason).toBe('no_photo_set');
        expect(result.size).toBeNull();
      }
    });

    it('returns expected structure for contact not in WhatsApp contacts DB', async () => {
      // Get a real conversation first to ensure WhatsApp is working
      const conversations = await aos().call('UsePlugin', {
        plugin,
        tool: 'list_conversations',
        params: { limit: 5 }
      });
      expect(conversations.length).toBeGreaterThan(0);

      // Now query with a number that exists in format but not in contacts
      // Use the structure of a real number but with zeros
      const results = await aos().call('UsePlugin', {
        plugin,
        tool: 'get_profile_photo',
        params: { phone: '10000000000' }  // Valid format, unlikely to exist
      });

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(1);
      
      const result = results[0];
      
      // Sanity check: no unresolved template variables
      const json = JSON.stringify(result);
      expect(json).not.toContain('{{');
      expect(json).not.toContain('}}');

      // Contact not found - should have null values and a reason
      expect(result.path).toBeNull();
      expect(['contact_not_on_whatsapp', 'no_photo_set']).toContain(result.reason);
    });
  });
});

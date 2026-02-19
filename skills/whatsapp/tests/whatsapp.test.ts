/**
 * WhatsApp Adapter Tests
 * 
 * Read-only tests against the local WhatsApp database.
 * Requires WhatsApp desktop app installed and logged in.
 */

import { describe, it, expect } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'whatsapp';

describe('WhatsApp Adapter', () => {
  describe('person.list', () => {
    it('returns contacts with person schema fields', async () => {
      const people = await aos().call('UseAdapter', {
        adapter,
        tool: 'person.list',
        params: { limit: 10 }
      });

      expect(Array.isArray(people)).toBe(true);
      
      if (people.length > 0) {
        const person = people[0];
        
        // Required person fields
        expect(person.id).toBeDefined();
        expect(person.name).toBeDefined();
        expect(person.adapter).toBe(adapter);
        
        // Phone should be E.164 format (starts with +)
        if (person.phone) {
          expect(person.phone).toMatch(/^\+/);
        }
      }
    });
  });

  describe('conversation.list', () => {
    it('returns conversations', async () => {
      const conversations = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 10 }
      });

      expect(Array.isArray(conversations)).toBe(true);
      
      if (conversations.length > 0) {
        const convo = conversations[0];
        expect(convo.id).toBeDefined();
        expect(convo.name).toBeDefined();
        expect(convo.adapter).toBe(adapter);
      }
    });
  });

  describe('conversation.get', () => {
    it('returns a specific conversation', async () => {
      // First get a conversation ID
      const conversations = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 1 }
      });

      if (conversations.length === 0) {
        console.log('  Skipping: no conversations');
        return;
      }

      const convo = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.get',
        params: { id: conversations[0].id }
      });

      expect(convo.id).toBe(conversations[0].id);
      expect(convo.name).toBeDefined();
    });
  });

  describe('message.list', () => {
    it('returns messages for a conversation', async () => {
      // First get a conversation ID
      const conversations = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 1 }
      });

      if (conversations.length === 0) {
        console.log('  Skipping: no conversations');
        return;
      }

      const messages = await aos().call('UseAdapter', {
        adapter,
        tool: 'message.list',
        params: { conversation_id: conversations[0].id, limit: 10 }
      });

      expect(Array.isArray(messages)).toBe(true);
      
      if (messages.length > 0) {
        const msg = messages[0];
        expect(msg.id).toBeDefined();
        expect(msg.conversation_id).toBeDefined();
        expect(msg.adapter).toBe(adapter);
      }
    });
  });

  describe('message.get', () => {
    it('returns a specific message', async () => {
      // First get a conversation and message
      const conversations = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 1 }
      });

      if (conversations.length === 0) {
        console.log('  Skipping: no conversations');
        return;
      }

      const messages = await aos().call('UseAdapter', {
        adapter,
        tool: 'message.list',
        params: { conversation_id: conversations[0].id, limit: 1 }
      });

      if (messages.length === 0) {
        console.log('  Skipping: no messages');
        return;
      }

      const msg = await aos().call('UseAdapter', {
        adapter,
        tool: 'message.get',
        params: { id: messages[0].id }
      });

      expect(msg.id).toBe(messages[0].id);
    });
  });

  describe('message.search', () => {
    it('searches messages by content', async () => {
      const messages = await aos().call('UseAdapter', {
        adapter,
        tool: 'message.search',
        params: { query: 'the', limit: 5 }
      });

      expect(Array.isArray(messages)).toBe(true);
      // May or may not find results, just checking it doesn't error
    });
  });

  describe('get_unread', () => {
    it('returns unread messages', async () => {
      const messages = await aos().call('UseAdapter', {
        adapter,
        tool: 'get_unread',
        params: { limit: 10 }
      });

      expect(Array.isArray(messages)).toBe(true);
      // May have no unread messages, just checking it works
    });
  });

  describe('get_participants', () => {
    it('returns participants for a group', async () => {
      // Find a group conversation
      const conversations = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 50 }
      });

      const group = conversations.find((c: any) => c.is_group === true || c.is_group === 1);

      if (!group) {
        console.log('  Skipping: no group conversations');
        return;
      }

      const participants = await aos().call('UseAdapter', {
        adapter,
        tool: 'get_participants',
        params: { conversation_id: group.id }
      });

      expect(Array.isArray(participants)).toBe(true);
    });
  });
});

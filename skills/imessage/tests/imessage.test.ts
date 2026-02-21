/**
 * iMessage Adapter Tests
 * 
 * Reads local macOS Messages database — no auth needed.
 * Sending requires imsg CLI (brew tap steipete/tap && brew install imsg).
 * Requires: macOS + Full Disk Access permission.
 * 
 * Coverage:
 * - conversation.list
 * - conversation.get
 * - message.list
 * - message.get
 * - message.search
 * - message.send
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';
import { existsSync } from 'fs';
import { homedir } from 'os';
import { execSync } from 'child_process';

const adapter = 'imessage';

let skipTests = false;
let skipSendTests = false;

describe('iMessage Adapter', () => {
  beforeAll(() => {
    const dbPath = `${homedir()}/Library/Messages/chat.db`;
    if (!existsSync(dbPath)) {
      console.log('  ⏭ Skipping iMessage tests: Messages database not found');
      skipTests = true;
    }
    try {
      execSync('which imsg', { stdio: 'pipe' });
    } catch {
      console.log('  ⏭ Skipping send tests: imsg not installed (brew tap steipete/tap && brew install imsg)');
      skipSendTests = true;
    }
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
      }) as Array<{ id: string; name: string }>;

      expect(Array.isArray(results)).toBe(true);
    });
  });

  // ===========================================================================
  // conversation.get
  // ===========================================================================
  describe('conversation.get', () => {
    it('gets a specific conversation', async () => {
      if (skipTests) return;

      const conversations = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 1 },
      }) as Array<{ id: string }>;

      if (conversations.length === 0) return; // No conversations

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.get',
        params: { id: conversations[0].id },
      }) as { id: string };

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
    });
  });

  // ===========================================================================
  // message.list
  // ===========================================================================
  describe('message.list', () => {
    it('lists messages in a conversation', async () => {
      if (skipTests) return;

      const conversations = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 1 },
      }) as Array<{ id: string }>;

      if (conversations.length === 0) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'message.list',
        params: { conversation_id: conversations[0].id, limit: 5 },
      }) as Array<{ id: string }>;

      expect(Array.isArray(results)).toBe(true);
    });
  });

  // ===========================================================================
  // message.get
  // ===========================================================================
  describe('message.get', () => {
    it('gets a specific message', async () => {
      if (skipTests) return;

      const conversations = await aos().call('UseAdapter', {
        adapter,
        tool: 'conversation.list',
        params: { limit: 1 },
      }) as Array<{ id: string }>;

      if (conversations.length === 0) return;

      const messages = await aos().call('UseAdapter', {
        adapter,
        tool: 'message.list',
        params: { conversation_id: conversations[0].id, limit: 1 },
      }) as Array<{ id: string }>;

      if (messages.length === 0) return;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'message.get',
        params: { id: messages[0].id },
      }) as { id: string };

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
    });
  });

  // ===========================================================================
  // message.search
  // ===========================================================================
  describe('message.search', () => {
    it('searches messages', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'message.search',
        params: { query: 'hello', limit: 3 },
      }) as Array<{ id: string }>;

      expect(Array.isArray(results)).toBe(true);
    });
  });

  // ===========================================================================
  // message.send
  // ===========================================================================
  describe('message.send', () => {
    it('sends an iMessage', async () => {
      if (skipTests || skipSendTests) return;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'message.send',
        params: {
          to: 'r.humphries2@gmail.com',
          text: 'AgentOS iMessage send test — if you see this, it works!',
          service: 'imessage',
        },
      });

      expect(result).toBeDefined();
    });
  });
});

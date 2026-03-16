/**
 * Kitty Skill Tests
 *
 * Coverage:
 * - list_os_windows
 * - list_tabs
 * - list_panes
 * - launch_tab
 * - focus_tab
 * - focus_os_window
 * - send_text
 * - get_text
 * - close_tab
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'kitty';

type LaunchResult = {
  socket: string;
  os_window_id: number;
  tab_id: number;
  window_id: number;
  title?: string;
};

let launched: LaunchResult;

async function wait(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

describe('Kitty Skill', () => {
  beforeAll(async () => {
    launched = await aos().call('UseAdapter', {
      adapter,
      tool: 'launch_tab',
      params: {
        title: 'agentos-kitty-test',
        cwd: '/Users/joe/dev/agentos-community',
        command: 'printf "__KITTY_READY__\\n"; exec zsh',
        keep_focus: true,
      },
    }) as LaunchResult;

    await wait(500);
  });

  afterAll(async () => {
    if (!launched?.tab_id) return;
    try {
      await aos().call('UseAdapter', {
        adapter,
        tool: 'close_tab',
        params: { socket: launched.socket, tab_id: launched.tab_id },
      });
    } catch {
      // Ignore cleanup failures so the real assertion failures stay visible.
    }
  });

  describe('list_os_windows', () => {
    it('returns Kitty OS windows including the launched test window', async () => {
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'list_os_windows',
        params: { socket: launched.socket },
      }) as Array<{ os_window_id: number; tab_count: number }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.some((item) => item.os_window_id === launched.os_window_id)).toBe(true);
      expect(results.find((item) => item.os_window_id === launched.os_window_id)?.tab_count).toBeGreaterThan(0);
    });
  });

  describe('list_tabs', () => {
    it('returns tabs for a specific OS window', async () => {
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'list_tabs',
        params: { socket: launched.socket, os_window_id: launched.os_window_id },
      }) as Array<{ tab_id: number; os_window_id: number }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.some((item) => item.tab_id === launched.tab_id)).toBe(true);
      expect(results.every((item) => item.os_window_id === launched.os_window_id)).toBe(true);
    });
  });

  describe('list_panes', () => {
    it('returns panes for the launched tab', async () => {
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'list_panes',
        params: { socket: launched.socket, tab_id: launched.tab_id },
      }) as Array<{ window_id: number; tab_id: number; command?: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.some((item) => item.window_id === launched.window_id)).toBe(true);
      expect(results.every((item) => item.tab_id === launched.tab_id)).toBe(true);
    });
  });

  describe('launch_tab', () => {
    it('returns ids for the launched tab and pane', async () => {
      expect(launched.socket).toMatch(/^unix:/);
      expect(launched.os_window_id).toBeGreaterThan(0);
      expect(launched.tab_id).toBeGreaterThan(0);
      expect(launched.window_id).toBeGreaterThan(0);
    });
  });

  describe('focus_tab', () => {
    it('focuses a Kitty tab by id', async () => {
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'focus_tab',
        params: { socket: launched.socket, tab_id: launched.tab_id },
      }) as { ok: boolean; tab_id: number };

      expect(result.ok).toBe(true);
      expect(result.tab_id).toBe(launched.tab_id);
    });
  });

  describe('focus_os_window', () => {
    it('focuses the OS window that contains the launched tab', async () => {
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'focus_os_window',
        params: { socket: launched.socket, os_window_id: launched.os_window_id },
      }) as { ok: boolean; os_window_id: number; tab_id: number };

      expect(result.ok).toBe(true);
      expect(result.os_window_id).toBe(launched.os_window_id);
      expect(result.tab_id).toBeGreaterThan(0);
    });
  });

  describe('send_text', () => {
    it('sends text to the launched pane', async () => {
      const token = `agentos-kitty-send-${Date.now()}`;
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'send_text',
        params: {
          socket: launched.socket,
          window_id: launched.window_id,
          text: `printf "${token}\\n"`,
          press_enter: true,
        },
      }) as { ok: boolean; window_id: number };

      await wait(400);

      expect(result.ok).toBe(true);
      expect(result.window_id).toBe(launched.window_id);
    });
  });

  describe('get_text', () => {
    it('reads visible text from the launched pane', async () => {
      const token = `agentos-kitty-read-${Date.now()}`;

      await aos().call('UseAdapter', {
        adapter,
        tool: 'send_text',
        params: {
          socket: launched.socket,
          window_id: launched.window_id,
          text: `printf "${token}\\n"`,
          press_enter: true,
        },
      });

      await wait(400);

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'get_text',
        params: { socket: launched.socket, window_id: launched.window_id, extent: 'screen' },
      }) as { text: string; window_id: number };

      expect(result.window_id).toBe(launched.window_id);
      expect(result.text).toContain(token);
    });
  });

  describe('close_tab', () => {
    it('closes a newly created Kitty tab', async () => {
      const extra = await aos().call('UseAdapter', {
        adapter,
        tool: 'launch_tab',
        params: {
          socket: launched.socket,
          title: 'agentos-kitty-close-test',
          cwd: '/Users/joe/dev/agentos-community',
          command: 'exec zsh',
          keep_focus: true,
        },
      }) as LaunchResult;

      const closeResult = await aos().call('UseAdapter', {
        adapter,
        tool: 'close_tab',
        params: { socket: launched.socket, tab_id: extra.tab_id },
      }) as { ok: boolean; tab_id: number };

      await wait(300);

      const remainingTabs = await aos().call('UseAdapter', {
        adapter,
        tool: 'list_tabs',
        params: { socket: launched.socket },
      }) as Array<{ tab_id: number }>;

      expect(closeResult.ok).toBe(true);
      expect(closeResult.tab_id).toBe(extra.tab_id);
      expect(remainingTabs.some((item) => item.tab_id === extra.tab_id)).toBe(false);
    });
  });
});

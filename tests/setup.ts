/**
 * Global Test Setup
 *
 * Connects to AgentOS via MCP (stdio) before tests run, disconnects after.
 * Single MCP process shared across all skill tests.
 */

import { beforeAll, afterAll } from 'vitest';
import { AgentOS, setGlobalAgentOS } from './utils/mcp-client';

let aos: AgentOS | null = null;

beforeAll(async () => {
  console.log('\nConnecting to AgentOS MCP...');

  try {
    aos = await AgentOS.connect({
      debug: !!process.env.DEBUG_MCP,
      timeout: 30_000,
    });

    setGlobalAgentOS(aos);
    console.log('AgentOS MCP ready\n');
  } catch (error) {
    console.error('Failed to connect to AgentOS MCP:', error);
    console.error('Make sure the binary is built:');
    console.error('  cd ~/dev/agentos && cargo build\n');
    throw error;
  }
});

afterAll(async () => {
  if (aos) {
    await aos.disconnect();
    setGlobalAgentOS(null);
  }
});

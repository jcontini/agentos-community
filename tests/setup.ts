/**
 * Global Test Setup
 * 
 * Starts the HTTP server before tests run and tears it down after.
 * This runs via vitest's setupFiles in the same process as tests.
 * 
 * Using HTTP instead of MCP:
 * - Simpler (no JSON-RPC or stdio overhead)
 * - Same results (HTTP returns plain data, like MCP after unwrapping)
 * - Transport-agnostic (adapter tests should work regardless of interface)
 */

import { beforeAll, afterAll } from 'vitest';
import { AgentOS, setGlobalAgentOS } from './utils/http-client';

let aos: AgentOS | null = null;

beforeAll(async () => {
  console.log('\n🌐 Connecting to AgentOS HTTP server...');
  
  try {
    aos = await AgentOS.connect({
      debug: !!process.env.DEBUG_HTTP,
      timeout: 30000,
    });
    
    setGlobalAgentOS(aos);
    console.log('✅ AgentOS HTTP server ready\n');
  } catch (error) {
    console.error('❌ Failed to connect to AgentOS:', error);
    console.error('\nMake sure AgentOS is built:');
    console.error('  cd ~/dev/agentos && cargo build\n');
    throw error;
  }
});

afterAll(async () => {
  if (aos) {
    console.log('\n🌐 Shutting down AgentOS HTTP server...');
    await aos.disconnect();
    setGlobalAgentOS(null);
    console.log('✅ AgentOS disconnected\n');
  }
});

/**
 * AgentOS Test Client — MCP
 *
 * Wraps MCPTestClient with the `AgentOS` interface all per-skill tests use.
 * Connects to the agentos binary via stdio MCP.
 *
 * Skill tests call:
 *   aos().call('UseAdapter', { adapter: 'todoist', tool: 'task.list', params: {} })
 *
 * This translates to:
 *   mcp.call('run', { skill: 'todoist', tool: 'task.list', params: {} })
 *
 * Results are unwrapped: operations return plain arrays/objects, utilities
 * return their JSON payload (markdown code fences stripped if present).
 */

import { MCPTestClient } from '../../../agentos/tests/utils/mcp-client';

// ── Result unwrapping ────────────────────────────────────────────────────────
// Operations: MCP client already JSON.parses the text content → plain value
// Utilities:  server wraps in ```json\n...\n``` → strip and parse

function unwrap(raw: unknown): unknown {
  if (typeof raw !== 'string') return raw;
  const m = raw.match(/^```(?:json)?\n([\s\S]*?)\n```$/);
  if (m) {
    try { return JSON.parse(m[1]); } catch { return m[1]; }
  }
  // Bare JSON string (no fences)
  try { return JSON.parse(raw); } catch { return raw; }
}

// ── AgentOS wrapper ──────────────────────────────────────────────────────────

export interface AgentOSOptions {
  debug?: boolean;
  timeout?: number;
}

export class AgentOS {
  private mcp: MCPTestClient;

  constructor(mcp: MCPTestClient) {
    this.mcp = mcp;
  }

  static async connect(options: AgentOSOptions = {}): Promise<AgentOS> {
    const mcp = new MCPTestClient({
      command: `${process.env.HOME}/dev/agentos/target/debug/agentos`,
      debug: options.debug ?? !!process.env.DEBUG_MCP,
      timeout: options.timeout ?? 30_000,
    });
    await mcp.connect();
    return new AgentOS(mcp);
  }

  async disconnect(): Promise<void> {
    await this.mcp.disconnect();
  }

  /**
   * Call a skill tool.
   *
   * Supports the legacy UseAdapter call shape:
   *   call('UseAdapter', { adapter: 'todoist', tool: 'task.list', params: {}, execute: true })
   *
   * Also supports direct run shape:
   *   call('run', { skill: 'todoist', tool: 'task.list', params: {} })
   */
  async call(tool: string, args: Record<string, unknown> = {}): Promise<unknown> {
    let runArgs: Record<string, unknown>;

    if (tool === 'UseAdapter') {
      const { adapter, tool: skillTool, params = {}, execute } = args as {
        adapter: string;
        tool: string;
        params?: Record<string, unknown>;
        execute?: boolean;
      };
      runArgs = { skill: adapter, tool: skillTool, params };
      if (execute) runArgs.execute = true;
    } else {
      // Direct run / any other tool — pass through as-is
      runArgs = args;
    }

    const result = await this.mcp.call('run', runArgs);
    return unwrap(result);
  }
}

// ── Global singleton (set by setup.ts) ──────────────────────────────────────

let globalAos: AgentOS | null = null;

export function getAgentOS(): AgentOS {
  if (!globalAos) {
    throw new Error('AgentOS not initialized. Make sure tests run via vitest (setup.ts).');
  }
  return globalAos;
}

export function setGlobalAgentOS(instance: AgentOS | null): void {
  globalAos = instance;
}

/**
 * AgentOS Test Client — MCP
 *
 * Wraps MCPTestClient with the `AgentOS` interface all per-skill tests use.
 * Connects to the agentos binary via stdio MCP.
 *
 * Skill tests call:
 *   aos().run('exa', 'search', { params: { query: 'rust' } })
 *
 * This translates to:
 *   mcp.call('run', { skill: 'exa', tool: 'search', params: { query: 'rust' } })
 *
 * Results are unwrapped: operations return plain arrays/objects, utilities
 * return their JSON payload (markdown code fences stripped if present).
 */

import { existsSync, statSync } from 'fs';
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

export interface AgentOSRunOptions {
  params?: Record<string, unknown>;
  view?: Record<string, unknown>;
  execute?: boolean;
}

export class AgentOS {
  private mcp: MCPTestClient;

  constructor(mcp: MCPTestClient) {
    this.mcp = mcp;
  }

  static async connect(options: AgentOSOptions = {}): Promise<AgentOS> {
    const agentosRoot = `${process.env.HOME}/dev/agentos`;
    const binary = resolveBinary(agentosRoot);
    const mcp = new MCPTestClient({
      command: binary,
      debug: options.debug ?? !!process.env.DEBUG_MCP,
      timeout: options.timeout ?? 30_000,
    });
    await mcp.connect();
    return new AgentOS(mcp);
  }

  async disconnect(): Promise<void> {
    await this.mcp.disconnect();
  }

  async run(skill: string, tool: string, options: AgentOSRunOptions = {}): Promise<unknown> {
    const { params = {}, ...rest } = options;
    return this.call('run', { skill, tool, params, ...rest });
  }

  /**
   * Call a skill tool.
   *
   * Preferred:
   *   call('run', { skill: 'exa', tool: 'search', params: { query: 'rust' } })
   *
   * Legacy compatibility:
   *   call('UseAdapter', { adapter: 'todoist', tool: 'list_tasks', params: {}, execute: true })
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

function resolveBinary(agentosRoot: string): string {
  if (process.env.AGENTOS_BINARY) return process.env.AGENTOS_BINARY;

  const debug = `${agentosRoot}/target/debug/agentos`;
  const release = `${agentosRoot}/target/release/agentos`;
  const candidates = [debug, release].filter(path => existsSync(path));

  if (candidates.length === 0) return debug;
  if (candidates.length === 1) return candidates[0];

  return candidates.sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs)[0];
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

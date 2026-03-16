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
 * Results are unwrapped to the stable structured payload used by skill tests.
 */

import { existsSync, statSync } from 'fs';
import { MCPTestClient } from '../../../agentos/tests/utils/mcp-client';

// ── Result unwrapping ────────────────────────────────────────────────────────
// Skill tests want the stable structured payload, not the render envelope.

function unwrap(raw: unknown): unknown {
  if (raw && typeof raw === 'object') {
    const record = raw as Record<string, unknown>;
    const keys = Object.keys(record);
    if (keys.length > 0 && keys.every((key) => key === 'data' || key === 'meta') && 'data' in record) {
      return record.data;
    }
    return raw;
  }

  if (typeof raw !== 'string') return raw;

  const trimmed = raw.trim();
  const m = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/);
  const candidate = m ? m[1].trim() : trimmed;

  try {
    const parsed = JSON.parse(candidate) as Record<string, unknown>;
    const keys = Object.keys(parsed);
    if (keys.length > 0 && keys.every((key) => key === 'data' || key === 'meta') && 'data' in parsed) {
      return parsed.data;
    }
    return parsed;
  } catch {
    return candidate;
  }
}

function normalizeView(view?: Record<string, unknown>): Record<string, unknown> {
  return {
    format: 'json',
    detail: 'full',
    ...(view || {}),
  };
}

function formatRunError(binary: string, runArgs: Record<string, unknown>, error: unknown): Error {
  const message = error instanceof Error ? error.message : String(error);
  const skill = typeof runArgs.skill === 'string' ? runArgs.skill : '<unknown>';
  const tool = typeof runArgs.tool === 'string' ? runArgs.tool : '<unknown>';
  return new Error([
    message,
    '',
    'MCP test client diagnostics:',
    `- Binary: ${binary}`,
    `- Call path: run({ skill: "${skill}", tool: "${tool}", params })`,
  ].join('\n'));
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
  private binary: string;

  constructor(mcp: MCPTestClient, binary: string) {
    this.mcp = mcp;
    this.binary = binary;
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
    return new AgentOS(mcp, binary);
  }

  async disconnect(): Promise<void> {
    await this.mcp.disconnect();
  }

  async run(skill: string, tool: string, options: AgentOSRunOptions = {}): Promise<unknown> {
    const { params = {}, view, ...rest } = options;
    return this.call('run', { skill, tool, params, view: normalizeView(view), ...rest });
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
      const { adapter, tool: skillTool, params = {}, execute, view } = args as {
        adapter: string;
        tool: string;
        params?: Record<string, unknown>;
        execute?: boolean;
        view?: Record<string, unknown>;
      };
      runArgs = { skill: adapter, tool: skillTool, params, view: normalizeView(view) };
      if (execute) runArgs.execute = true;
    } else {
      runArgs = { ...args };
      runArgs.view = normalizeView(runArgs.view as Record<string, unknown> | undefined);
    }

    try {
      const result = await this.mcp.call('run', runArgs);
      return unwrap(result);
    } catch (error) {
      throw formatRunError(this.binary, runArgs, error);
    }
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

/**
 * MCP Test Client for AgentOS Integrations
 * 
 * Connects to AgentOS via stdio MCP protocol for E2E testing.
 * This allows tests to make MCP calls programmatically.
 */

import { spawn, ChildProcess } from 'child_process';
import { createInterface, Interface } from 'readline';
import { EventEmitter } from 'events';

interface PendingRequest {
  resolve: (value: any) => void;
  reject: (error: any) => void;
  timeout: ReturnType<typeof setTimeout>;
}

export class MCPError extends Error {
  code: number;
  data?: any;

  constructor(error: { code: number; message: string; data?: any }) {
    super(error.message);
    this.name = 'MCPError';
    this.code = error.code;
    this.data = error.data;
  }
}

export interface MCPClientOptions {
  /** Path to AgentOS binary (default: finds from PATH or standard location) */
  command?: string;
  /** Request timeout in ms (default: 30000) */
  timeout?: number;
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * Low-level MCP test client
 */
export class MCPTestClient extends EventEmitter {
  private process: ChildProcess | null = null;
  private readline: Interface | null = null;
  private requestId = 0;
  private pending = new Map<number, PendingRequest>();
  private options: Required<MCPClientOptions>;
  private connected = false;

  constructor(options: MCPClientOptions = {}) {
    super();
    this.options = {
      command: options.command || this.findAgentOS(),
      timeout: options.timeout || 30000,
      debug: options.debug || !!process.env.DEBUG_MCP,
    };
  }

  private findAgentOS(): string {
    // Try standard locations
    const locations = [
      // Development build (post-Tauri removal)
      `${process.env.HOME}/dev/agentos/target/debug/agentos`,
      // Release build (post-Tauri removal)
      `${process.env.HOME}/dev/agentos/target/release/agentos`,
      // Installed location
      '/Applications/AgentOS.app/Contents/MacOS/agentos',
    ];
    
    // Return first one that exists (or default to debug)
    return locations[0];
  }

  private log(...args: any[]) {
    if (this.options.debug) {
      console.log(`[MCP ${new Date().toISOString().slice(11, 23)}]`, ...args);
    }
  }

  async connect(): Promise<void> {
    if (this.connected) {
      throw new Error('Already connected');
    }

    return new Promise((resolve, reject) => {
      this.log('Spawning:', this.options.command, ['mcp']);

      this.process = spawn(this.options.command, ['mcp'], {
        env: { 
          ...process.env, 
          AGENTOS_ENV: 'test',
          RUST_BACKTRACE: '1'
        },
        stdio: ['pipe', 'pipe', 'pipe']
      });

      this.process.stderr?.on('data', (data) => {
        const text = data.toString().trim();
        if (text) this.log('stderr:', text);
      });

      this.readline = createInterface({ 
        input: this.process.stdout!,
        crlfDelay: Infinity
      });

      this.readline.on('line', (line) => this.handleLine(line));

      this.process.on('error', (error) => {
        this.log('Process error:', error);
        if (!this.connected) reject(error);
        else this.emit('error', error);
      });

      this.process.on('close', (code) => {
        this.log('Process closed with code:', code);
        this.connected = false;
        this.emit('close', code);
      });

      this.initializeConnection()
        .then(() => {
          this.connected = true;
          resolve();
        })
        .catch(reject);
    });
  }

  private async initializeConnection(): Promise<void> {
    await this.sendRequest('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'integrations-test-client', version: '1.0.0' }
    });
    this.sendNotification('notifications/initialized', {});
  }

  private handleLine(line: string) {
    const trimmed = line.trim();
    if (!trimmed) return;

    this.log('Received:', trimmed.slice(0, 200));

    try {
      const message = JSON.parse(trimmed);
      
      if ('id' in message) {
        const pending = this.pending.get(message.id);
        if (pending) {
          clearTimeout(pending.timeout);
          this.pending.delete(message.id);
          
          if (message.error) {
            pending.reject(new MCPError(message.error));
          } else {
            pending.resolve(message.result);
          }
        }
      } else if ('method' in message) {
        this.emit('notification', message);
      }
    } catch {
      this.log('Non-JSON line:', trimmed);
    }
  }

  private sendRequest(method: string, params: any): Promise<any> {
    return new Promise((resolve, reject) => {
      const id = ++this.requestId;
      
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Request timeout: ${method}`));
      }, this.options.timeout);

      this.pending.set(id, { resolve, reject, timeout });

      const request = JSON.stringify({ jsonrpc: '2.0', id, method, params });
      this.log('Sending:', request.slice(0, 200));
      this.process!.stdin!.write(request + '\n');
    });
  }

  private sendNotification(method: string, params?: any) {
    const notification = JSON.stringify({ jsonrpc: '2.0', method, params });
    this.log('Sending notification:', notification);
    this.process!.stdin!.write(notification + '\n');
  }

  /**
   * Call an MCP tool
   */
  async call(tool: string, args: object = {}): Promise<any> {
    if (!this.connected) throw new Error('Not connected');

    const result = await this.sendRequest('tools/call', { name: tool, arguments: args });

    // Extract text content from MCP response
    if (result?.content && Array.isArray(result.content)) {
      const textContent = result.content.find((c: any) => c.type === 'text');
      if (textContent?.text) {
        try {
          return JSON.parse(textContent.text);
        } catch {
          return textContent.text;
        }
      }
    }

    return result;
  }

  async disconnect(): Promise<void> {
    if (!this.connected && !this.process) return;

    for (const [, pending] of this.pending) {
      clearTimeout(pending.timeout);
      pending.reject(new Error('Client disconnected'));
    }
    this.pending.clear();

    this.readline?.close();
    this.readline = null;

    if (this.process) {
      this.process.kill('SIGTERM');
      await new Promise<void>((resolve) => {
        const timeout = setTimeout(() => {
          this.process?.kill('SIGKILL');
          resolve();
        }, 5000);
        
        this.process!.once('close', () => {
          clearTimeout(timeout);
          resolve();
        });
      });
      this.process = null;
    }

    this.connected = false;
  }

  isConnected(): boolean {
    return this.connected;
  }
}

/**
 * High-level AgentOS test wrapper
 */
export class AgentOS {
  private mcp: MCPTestClient;

  constructor(mcp: MCPTestClient) {
    this.mcp = mcp;
  }

  static async connect(options?: MCPClientOptions): Promise<AgentOS> {
    const mcp = new MCPTestClient(options);
    await mcp.connect();
    return new AgentOS(mcp);
  }

  async disconnect(): Promise<void> {
    await this.mcp.disconnect();
  }

  /**
   * Call any MCP tool directly
   */
  async call(tool: string, args: object = {}): Promise<any> {
    return this.mcp.call(tool, args);
  }

  // Convenience method for UseAdapter
  useAdapter(adapter: string, tool: string, params?: object, execute?: boolean) {
    return this.call('UseAdapter', { adapter, tool, params, execute });
  }
}

// Global instance for tests (set in setup.ts)
let globalAos: AgentOS | null = null;

export function getAgentOS(): AgentOS {
  if (!globalAos) {
    throw new Error('AgentOS not initialized. Did you run tests with vitest?');
  }
  return globalAos;
}

export function setGlobalAgentOS(aos: AgentOS | null) {
  globalAos = aos;
}

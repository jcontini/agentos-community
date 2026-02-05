/**
 * HTTP Test Client for AgentOS Integrations
 * 
 * Connects to AgentOS HTTP server for E2E testing.
 * Lighter weight than MCP client - no JSON-RPC or stdio overhead.
 * 
 * Use for testing:
 * - Plugin execution (operations, utilities)
 * - Activity logging
 * 
 * HTTP API returns plain data (not MCP-wrapped).
 * MCP wrapping happens only in the MCP layer.
 */

import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';

// Test server uses port 3457 to isolate from dev server (3456)
const TEST_PORT = 3457;
const BASE_URL = `http://127.0.0.1:${TEST_PORT}`;
const DEFAULT_TIMEOUT = 30000;

export interface HttpClientOptions {
  /** Start server automatically (default: true) */
  autoStart?: boolean;
  /** Request timeout in ms (default: 30000) */
  timeout?: number;
  /** Enable debug logging */
  debug?: boolean;
}

export interface ToolCallResponse {
  request_id: string;
  result: unknown;
  activity: {
    id?: number;
    entity: string;
    operation: string;
    status: number;
    duration_ms: number;
  };
}

export class HttpError extends Error {
  status: number;
  data?: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
    this.data = data;
  }
}

export class HttpTestClient extends EventEmitter {
  private serverProcess: ChildProcess | null = null;
  private options: Required<HttpClientOptions>;
  private connected = false;

  constructor(options: HttpClientOptions = {}) {
    super();
    this.options = {
      autoStart: options.autoStart ?? true,
      timeout: options.timeout ?? DEFAULT_TIMEOUT,
      debug: options.debug ?? !!process.env.DEBUG_HTTP,
    };
  }

  private log(...args: unknown[]) {
    if (this.options.debug) {
      console.log(`[HTTP ${new Date().toISOString().slice(11, 23)}]`, ...args);
    }
  }

  private findAgentOS(): string {
    // Standard development location
    return `${process.env.HOME}/dev/agentos/target/debug/agentos`;
  }

  /**
   * Connect to the HTTP server (starts it if needed)
   */
  async connect(): Promise<void> {
    if (this.connected) {
      throw new Error('Already connected');
    }

    // Check if server is already running
    if (await this.isServerRunning()) {
      this.log('Server already running');
      this.connected = true;
      return;
    }

    if (!this.options.autoStart) {
      throw new Error('Server not running and autoStart is disabled');
    }

    // Start the server
    await this.startServer();
    this.connected = true;
  }

  private async isServerRunning(): Promise<boolean> {
    try {
      const response = await fetch(`${BASE_URL}/api/health`, {
        signal: AbortSignal.timeout(2000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  private async startServer(): Promise<void> {
    this.log('Starting server...');

    this.serverProcess = spawn(this.findAgentOS(), ['serve'], {
      cwd: `${process.env.HOME}/dev/agentos`,
      env: {
        ...process.env,
        AGENTOS_ENV: 'test',
        AGENTOS_PORT: TEST_PORT.toString(),
        RUST_BACKTRACE: '1',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
    });

    // Log stderr for debugging
    this.serverProcess.stderr?.on('data', (data) => {
      this.log('stderr:', data.toString().trim());
    });

    this.serverProcess.on('error', (error) => {
      this.log('Server process error:', error);
      this.emit('error', error);
    });

    this.serverProcess.on('close', (code) => {
      this.log('Server closed with code:', code);
      this.connected = false;
      this.emit('close', code);
    });

    // Wait for server to be ready
    const maxAttempts = 50;
    const delayMs = 100;
    
    for (let i = 0; i < maxAttempts; i++) {
      if (await this.isServerRunning()) {
        this.log('Server ready');
        return;
      }
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }

    throw new Error('Server failed to start within 5 seconds');
  }

  /**
   * Disconnect and stop the server
   */
  async disconnect(): Promise<void> {
    if (this.serverProcess) {
      this.log('Stopping server...');
      this.serverProcess.kill('SIGTERM');

      // Force kill after 5 seconds
      const forceKillTimeout = setTimeout(() => {
        this.serverProcess?.kill('SIGKILL');
      }, 5000);

      await new Promise<void>((resolve) => {
        if (!this.serverProcess) {
          clearTimeout(forceKillTimeout);
          resolve();
          return;
        }

        this.serverProcess.once('close', () => {
          clearTimeout(forceKillTimeout);
          resolve();
        });
      });

      this.serverProcess = null;
    }

    this.connected = false;
    this.log('Disconnected');
  }

  /**
   * Call a plugin tool via HTTP API
   * 
   * For UsePlugin calls, uses /api/plugins/{plugin}/{tool}
   * Other tools are not supported via HTTP (use MCP)
   */
  async call(tool: string, args: Record<string, unknown> = {}): Promise<unknown> {
    if (!this.connected) {
      throw new Error('Not connected');
    }

    // UsePlugin is the standard way to call plugins
    if (tool === 'UsePlugin') {
      const { plugin, tool: pluginTool, params = {} } = args as {
        plugin: string;
        tool: string;
        params?: Record<string, unknown>;
      };
      
      this.log(`Calling ${plugin}/${pluginTool}:`, JSON.stringify(params).slice(0, 200));

      const response = await fetch(`${BASE_URL}/api/plugins/${plugin}/${pluginTool}`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Agent': 'test-runner',
        },
        body: JSON.stringify(params),
        signal: AbortSignal.timeout(this.options.timeout),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new HttpError(
          (errorData as { error?: string }).error || `HTTP ${response.status}`,
          response.status,
          errorData
        );
      }

      return response.json();
    }

    // Non-UsePlugin tools not supported via HTTP
    throw new Error(`Tool "${tool}" not supported via HTTP API. Use MCP for non-plugin tools.`);
  }

  /**
   * Call UsePlugin tool (convenience method)
   */
  usePlugin(plugin: string, tool: string, params?: object, execute?: boolean): Promise<unknown> {
    return this.call('UsePlugin', { plugin, tool, params, execute });
  }

  isConnected(): boolean {
    return this.connected;
  }
}

/**
 * High-level AgentOS test wrapper
 * 
 * Provides the same interface as MCP client for compatibility.
 */
export class AgentOS {
  private http: HttpTestClient;

  constructor(http: HttpTestClient) {
    this.http = http;
  }

  static async connect(options?: HttpClientOptions): Promise<AgentOS> {
    const http = new HttpTestClient(options);
    await http.connect();
    return new AgentOS(http);
  }

  async disconnect(): Promise<void> {
    await this.http.disconnect();
  }

  /**
   * Call any tool directly
   */
  async call(tool: string, args: object = {}): Promise<unknown> {
    return this.http.call(tool, args);
  }

  /**
   * Call UsePlugin tool (convenience method)
   */
  usePlugin(plugin: string, tool: string, params?: object, execute?: boolean): Promise<unknown> {
    return this.http.usePlugin(plugin, tool, params, execute);
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

export function setGlobalAgentOS(aos: AgentOS | null): void {
  globalAos = aos;
}

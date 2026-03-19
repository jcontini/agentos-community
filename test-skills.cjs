#!/usr/bin/env node
/**
 * test-skills.cjs — direct MCP skill runner and smoke harness
 *
 * One MCP process. Can either:
 * - run coverage-style smoke tests across skill YAML definitions, or
 * - make a single direct `run` call with arbitrary params/view/execute flags.
 *
 * No test runner, no TypeScript compilation, no worker pools.
 *
 * Usage:
 *   node test-skills.cjs                              # test all skills
 *   node test-skills.cjs exa reddit                  # test specific skills
 *   node test-skills.cjs --changed                   # only changed skills
 *   node test-skills.cjs --verbose                   # show params and responses
 *
 *   node test-skills.cjs --call \
 *     --skill exa \
 *     --tool search \
 *     --params '{"query":"rust ownership","limit":1}' \
 *     --account work \
 *     --format json \
 *     --detail preview
 *
 *   node test-skills.cjs --call \
 *     --skill exa \
 *     --tool search \
 *     --params '{"query":"rust ownership","limit":1}' \
 *     --raw
 */

const { spawn } = require('child_process');
const { createInterface } = require('readline');
const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

// ── Config ───────────────────────────────────────────────────────────────────

const SKILLS_DIR = path.join(__dirname, 'skills');
const AGENTOS_ROOT = path.join(process.env.HOME, 'dev/agentos');
const TIMEOUT = 60_000;

function resolveBinary() {
  if (process.env.AGENTOS_BINARY) return process.env.AGENTOS_BINARY;

  const debug = path.join(AGENTOS_ROOT, 'target/debug/agentos');
  const release = path.join(AGENTOS_ROOT, 'target/release/agentos');
  const candidates = [debug, release].filter(p => fs.existsSync(p));

  if (candidates.length === 0) return debug;
  if (candidates.length === 1) return candidates[0];

  return candidates.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0];
}

const BINARY = resolveBinary();

// Shared, smoke-safe fallback fixtures.
// Skill-specific fixtures should live in operation-level `test.fixtures`.
const SHARED_FIXTURES = {
  query: 'test',
  limit: 3,
  lang: 'en',
  format: 'text',
  feed: 'front',
  filter: 'all',
  sort: 'new',
  url: 'https://example.com',
  path: process.env.HOME + '/dev/agentos',
};

// Legacy per-skill fixture overrides for skills not yet migrated
// to operation-level `test.fixtures`.
const SKILL_FIXTURES = {
  youtube: { url: 'https://www.youtube.com/@theo' },
  linear: { account: 'AgentOS' },
  todoist: { filter: 'today | overdue' },
};

// Legacy fallback for skills that have not declared `test.mode`.
const LEGACY_WRITE_OPS = /\.(create|update|delete|send|reply|modify|complete|reopen|trash|untrash|batch|import|pull|backfill|set_|forward|upvote|downvote|follow|unfollow|subscribe|unsubscribe|verify)/;
const SMOKE_VIEW = { format: 'json', detail: 'full' };

// Skills to skip entirely in automated runs
// gmail: needs keychain for OAuth
// brave-browser: massive SQLite scans, hangs
// lightpanda: needs running browser engine
// hardcover: depends on a live personal API token and account data
// icloud: depends on a local pyicloud session plus account-specific params
const SKIP_SKILLS = new Set(['gmail', 'brave-browser', 'lightpanda', 'hardcover', 'icloud']);

// ── CLI args ─────────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const flags = {};
  const positionals = [];

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];

    if (!arg.startsWith('--')) {
      positionals.push(arg);
      continue;
    }

    const eq = arg.indexOf('=');
    if (eq !== -1) {
      const key = arg.slice(2, eq);
      const value = arg.slice(eq + 1);
      flags[key] = value;
      continue;
    }

    const key = arg.slice(2);
    const next = argv[i + 1];
    if (next && !next.startsWith('--')) {
      flags[key] = next;
      i++;
    } else {
      flags[key] = true;
    }
  }

  return { flags, positionals };
}

function parseJsonFlag(raw, fallback, label) {
  if (raw === undefined) return fallback;
  try {
    return JSON.parse(raw);
  } catch (error) {
    console.error(`Invalid JSON for --${label}: ${error.message}`);
    process.exit(1);
  }
}

const parsed = parseArgs(process.argv.slice(2));
const flags = parsed.flags;
const verbose = !!flags.verbose;
const changedOnly = !!flags.changed;
const includeWrite = !!flags.write;
const callMode = !!flags.call;
const rawOutput = !!flags.raw;
const lenient = !!flags.lenient || process.env.MCP_TEST_LENIENT === '1';
const skillFilter = parsed.positionals;

// ── YAML parsing ─────────────────────────────────────────────────────────────

function loadSkill(skillDir) {
  const skillYaml = path.join(skillDir, 'skill.yaml');
  if (fs.existsSync(skillYaml)) {
    try {
      return yaml.load(fs.readFileSync(skillYaml, 'utf8'));
    } catch {
      return null;
    }
  }
  const readme = path.join(skillDir, 'readme.md');
  if (!fs.existsSync(readme)) return null;
  const raw = fs.readFileSync(readme, 'utf8');
  const m = raw.match(/^---\r?\n([\s\S]*?)\n---\r?\n/);
  if (!m) return null;
  try { return yaml.load(m[1]); } catch { return null; }
}

function getChangedSkills() {
  try {
    const { execSync } = require('child_process');
    const files = execSync('git diff --cached --name-only --diff-filter=ACMR', { cwd: __dirname, encoding: 'utf8' });
    const skills = new Set();
    for (const f of files.split('\n')) {
      const m = f.match(/^skills\/([^/]+)\//);
      if (m) skills.add(m[1]);
    }
    return [...skills];
  } catch { return []; }
}

function getTargetSkills() {
  if (skillFilter.length > 0) return skillFilter;
  if (changedOnly) return getChangedSkills();
  // All skills with operations
  return fs.readdirSync(SKILLS_DIR)
    .filter(d => {
      try { return fs.statSync(path.join(SKILLS_DIR, d)).isDirectory() && !d.startsWith('.'); }
      catch { return false; }
    })
    .filter(d => {
      const sk = loadSkill(path.join(SKILLS_DIR, d));
      return sk && sk.operations;
    })
    .filter(d => !SKIP_SKILLS.has(d));
}

// ── MCP client (minimal, synchronous-feeling with promises) ──────────────────

class MCP {
  constructor() {
    this.proc = null;
    this.rl = null;
    this.reqId = 0;
    this.pending = new Map();
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.proc = spawn(BINARY, ['mcp'], {
        cwd: AGENTOS_ROOT,
        env: { ...process.env, RUST_BACKTRACE: '1' },
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      this.proc.on('error', reject);
      this.proc.stderr.on('data', d => {
        if (verbose) process.stderr.write(`  [mcp] ${d}`);
      });
      this.rl = createInterface({ input: this.proc.stdout });
      this.rl.on('line', line => this._onLine(line));

      // Initialize
      this._send('initialize', {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: { name: 'test-skills', version: '1.0.0' },
      }).then(r => {
        this._notify('notifications/initialized', {});
        resolve(r);
      }).catch(reject);
    });
  }

  _onLine(line) {
    try {
      const msg = JSON.parse(line.trim());
      if ('id' in msg && !('method' in msg)) {
        const p = this.pending.get(msg.id);
        if (p) {
          clearTimeout(p.timer);
          this.pending.delete(msg.id);
          if (msg.error) p.reject(new Error(msg.error.message));
          else p.resolve(msg.result);
        }
      } else if ('id' in msg && 'method' in msg) {
        // Server request (roots/list etc) — respond with empty
        const resp = JSON.stringify({ jsonrpc: '2.0', id: msg.id, result: {} });
        this.proc.stdin.write(resp + '\n');
      }
    } catch {}
  }

  _send(method, params) {
    return new Promise((resolve, reject) => {
      const id = ++this.reqId;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`timeout: ${method}`));
      }, TIMEOUT);
      this.pending.set(id, { resolve, reject, timer });
      this.proc.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
    });
  }

  _notify(method, params) {
    this.proc.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n');
  }

  async callTool(name, args = {}, options = {}) {
    const result = await this._send('tools/call', {
      name,
      arguments: args,
    });

    if (result?.content && Array.isArray(result.content)) {
      const text = result.content.find(c => c.type === 'text')?.text;
      if (text) {
        if (options.rawText) return text;

        // Strip markdown fences
        const m = text.match(/^```(?:json)?\n([\s\S]*?)\n```$/);
        const raw = m ? m[1] : text;
        if (options.parse === false) return raw;
        try { return JSON.parse(raw); } catch { return raw; }
      }
    }
    return result;
  }

  async call(skill, tool, params = {}, extra = {}) {
    return this.callTool('run', { skill, tool, params, ...extra });
  }

  async disconnect() {
    for (const [, p] of this.pending) { clearTimeout(p.timer); p.reject(new Error('disconnect')); }
    this.pending.clear();
    this.rl?.close();
    this.proc?.kill('SIGTERM');
    await new Promise(r => { if (this.proc) this.proc.once('close', r); else r(); });
  }
}

// ── Test execution ───────────────────────────────────────────────────────────

function getTestConfig(opDef) {
  return opDef?.test && typeof opDef.test === 'object' ? opDef.test : null;
}

function getOperationMode(opName, opDef) {
  const test = getTestConfig(opDef);
  if (!test) return null;
  if (typeof test.mode === 'string' && test.mode.length > 0) return test.mode;
  return LEGACY_WRITE_OPS.test('.' + opName) ? 'write' : 'read';
}

function getRunOptions(opDef) {
  const test = getTestConfig(opDef);
  const options = {
    view: SMOKE_VIEW,
    remember: false,
  };
  if (test.account) options.account = test.account;
  return options;
}

function buildParams(opDef, skillId) {
  const params = {};
  const missing = [];

  const test = getTestConfig(opDef);
  const explicit = test.fixtures && typeof test.fixtures === 'object' ? test.fixtures : {};
  const shared = SHARED_FIXTURES;
  const legacy = SKILL_FIXTURES[skillId] || {};

  if (!opDef?.params) {
    return { params: { ...explicit }, missing };
  }

  for (const [name, def] of Object.entries(opDef.params)) {
    const d = typeof def === 'object' ? def : {};
    if (Object.prototype.hasOwnProperty.call(explicit, name)) {
      params[name] = explicit[name];
      continue;
    }
    if (d.default !== undefined) {
      params[name] = d.default;
      continue;
    }
    if (Object.prototype.hasOwnProperty.call(shared, name)) {
      params[name] = shared[name];
      continue;
    }
    if (Object.prototype.hasOwnProperty.call(legacy, name)) {
      params[name] = legacy[name];
      continue;
    }
    if (d.required) missing.push(name);
  }
  for (const [name, value] of Object.entries(explicit)) {
    if (!Object.prototype.hasOwnProperty.call(params, name)) {
      params[name] = value;
    }
  }
  return { params, missing };
}

function normalizeDiscoverConfig(discoverFrom) {
  if (!discoverFrom) return [];
  if (Array.isArray(discoverFrom)) {
    return discoverFrom.map(item => typeof item === 'string' ? { op: item } : item).filter(Boolean);
  }
  if (typeof discoverFrom === 'string') return [{ op: discoverFrom }];
  if (typeof discoverFrom === 'object') return [discoverFrom];
  return [];
}

function unwrapSmokeData(result) {
  if (result && typeof result === 'object' && !Array.isArray(result) && 'data' in result && 'meta' in result) {
    return result.data;
  }
  return result;
}

function firstFromCollection(value) {
  if (Array.isArray(value)) return value[0] || null;
  if (!value || typeof value !== 'object') return null;
  if (Array.isArray(value.items)) return value.items[0] || null;
  if (Array.isArray(value.results)) return value.results[0] || null;
  if (Array.isArray(value.posts)) return value.posts[0] || null;
  if (value.requests?.items?.[0]) return value.requests.items[0];
  if (value.conversations?.items?.[0]) return value.conversations.items[0];
  if (value.agent && typeof value.agent === 'object') return value.agent;
  if (value.post && typeof value.post === 'object') return value.post;
  return value;
}

function extractDiscoveredValue(source, targetParam, sourceKey) {
  if (!source || typeof source !== 'object') return undefined;
  const keys = [
    sourceKey,
    targetParam,
    targetParam.endsWith('_id') ? 'id' : null,
    targetParam === 'name' ? 'id' : null,
  ].filter(Boolean);

  for (const key of keys) {
    if (source[key] !== undefined && source[key] !== null && source[key] !== '') {
      return source[key];
    }
  }
  return undefined;
}

async function resolveDiscoveryParams(skillId, opName, opDef, ops, mcp, params, missing, stack) {
  const test = getTestConfig(opDef);
  const discoverConfigs = normalizeDiscoverConfig(test.discover_from);
  const unresolved = [...missing];
  if (unresolved.length === 0 || discoverConfigs.length === 0) {
    return { ok: unresolved.length === 0, params, missing: unresolved };
  }

  for (const discover of discoverConfigs) {
    if (unresolved.length === 0) break;
    const discoverOpName = discover.op;
    const discoverOp = ops[discoverOpName];
    if (!discoverOp) {
      return { ok: false, reason: `discover_from op not found: ${discoverOpName}` };
    }

    const discoverMode = getOperationMode(discoverOpName, discoverOp);
    if (discoverMode !== 'read') {
      return { ok: false, reason: `discover_from op is not smoke-safe: ${discoverOpName}` };
    }

    const discoverInvocation = await resolveSmokeInvocation(
      skillId,
      discoverOpName,
      discoverOp,
      ops,
      mcp,
      stack,
    );
    if (!discoverInvocation.ok) {
      return { ok: false, reason: `discover_from ${discoverOpName} failed: ${discoverInvocation.reason}` };
    }
    const discoverParams = {
      ...discoverInvocation.params,
      ...(discover.params && typeof discover.params === 'object' ? discover.params : {}),
    };

    let discoverResult;
    try {
      discoverResult = await mcp.call(skillId, discoverOpName, discoverParams, discoverInvocation.runOptions);
    } catch (error) {
      return { ok: false, reason: `discover_from ${discoverOpName} failed: ${(error.message || String(error)).slice(0, 120)}` };
    }

    const check = checkResult(discoverResult, discoverOp?.returns);
    if (!check.ok) {
      return { ok: false, reason: `discover_from ${discoverOpName} failed: ${check.reason}` };
    }

    const source = firstFromCollection(unwrapSmokeData(discoverResult));
    if (!source) {
      return { ok: false, reason: `discover_from ${discoverOpName} returned no data` };
    }

    const paramMap = discover.map && typeof discover.map === 'object' ? discover.map : {};
    for (let i = unresolved.length - 1; i >= 0; i--) {
      const targetParam = unresolved[i];
      const sourceKey = paramMap[targetParam];
      const value = extractDiscoveredValue(source, targetParam, sourceKey);
      if (value !== undefined) {
        params[targetParam] = value;
        unresolved.splice(i, 1);
      }
    }
  }

  if (unresolved.length > 0) {
    return { ok: false, reason: `fixture missing for required param(s): ${unresolved.join(', ')}` };
  }

  return { ok: true, params, missing: [] };
}

async function resolveSmokeInvocation(skillId, opName, opDef, ops, mcp, stack = []) {
  if (stack.includes(opName)) {
    return { ok: false, reason: `discover_from cycle: ${[...stack, opName].join(' -> ')}` };
  }
  const nextStack = [...stack, opName];
  const built = buildParams(opDef, skillId);
  if (built.missing.length === 0) {
    return { ok: true, params: built.params, runOptions: getRunOptions(opDef) };
  }

  const discovered = await resolveDiscoveryParams(skillId, opName, opDef, ops, mcp, built.params, built.missing, nextStack);
  if (!discovered.ok) return discovered;
  return { ok: true, params: discovered.params, runOptions: getRunOptions(opDef) };
}

function checkResult(result, returns) {
  const payload = unwrapSmokeData(result);

  if (!returns || returns === 'void') return { ok: true };

  if (typeof payload === 'string') {
    if (payload.includes('Execution failed:') || payload.includes('Skill error:')) {
      return { ok: false, reason: payload.slice(0, 120) };
    }
    return payload.length > 0
      ? { ok: true }
      : { ok: false, reason: 'empty response' };
  }

  if (typeof returns === 'string') {
    const isArray = returns.endsWith('[]');
    if (isArray) {
      if (!Array.isArray(payload)) {
        return { ok: false, reason: `expected array, got ${Array.isArray(payload) ? 'array' : typeof payload}` };
      }
      if (payload.some(item => typeof item !== 'object' || item === null)) {
        return { ok: false, reason: 'array contains non-object items' };
      }
      if (payload.length > 0 && !payload[0].id && !payload[0].name && !payload[0].url) {
        return { ok: false, reason: 'array items missing id/name/url' };
      }
      return { ok: true, count: payload.length };
    }

    if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
      return { ok: false, reason: `expected object, got ${Array.isArray(payload) ? 'array' : typeof payload}` };
    }
    if (returns !== 'object' && !payload.id && !payload.name && !payload.url) {
      return { ok: false, reason: 'entity missing id/name/url' };
    }
    return { ok: true };
  }

  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
    return { ok: false, reason: `expected object, got ${Array.isArray(payload) ? 'array' : typeof payload}` };
  }

  const requiredKeys = Object.keys(returns);
  const missingKeys = requiredKeys.filter(key => payload[key] === undefined);
  if (missingKeys.length > 0) {
    return { ok: false, reason: `object missing key(s): ${missingKeys.join(', ')}` };
  }
  return { ok: true };
}

function pluralize(noun) {
  if (noun.endsWith('s')) return noun;
  if (noun.endsWith('y') && !/[aeiou]y$/.test(noun)) return noun.slice(0, -1) + 'ies';
  return noun + 's';
}

function guessListOperation(opName, ops) {
  const candidates = [];

  if (opName.endsWith('.get')) {
    candidates.push(opName.replace(/\.get$/, '.list'));
  }

  if (opName.startsWith('get_')) {
    const noun = opName.slice(4);
    candidates.push(`list_${pluralize(noun)}`, `list_${noun}`, `search_${noun}`, 'list', 'search');
  }

  return candidates.find(candidate => ops[candidate]);
}

function prettyPrint(value) {
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

function getDeclaredSkill(skillId) {
  const skillDir = path.join(SKILLS_DIR, skillId);
  if (!fs.existsSync(skillDir)) return null;
  return loadSkill(skillDir);
}

function getDeclaredTools(skillId) {
  const skill = getDeclaredSkill(skillId);
  if (!skill) return [];
  return [
    ...Object.keys(skill.operations || {}),
    ...Object.keys(skill.utilities || {}),
  ];
}

function formatRunDiagnostics(skill, tool, error) {
  const declaredTools = getDeclaredTools(skill);
  const message = error?.message || String(error);
  const lines = [
    message,
    '',
    'Diagnostics:',
    `- Binary: ${BINARY}`,
    `- Call path: run({ skill: "${skill}", tool: "${tool}", params })`,
    '- Note: `agentos mcp` is a proxy to the engine daemon; core Rust changes may require an engine restart.',
  ];

  if (declaredTools.length === 0) {
    lines.push(`- Community YAML: no local skill declaration found at ${path.join(SKILLS_DIR, skill)}`);
  } else {
    lines.push(`- Community YAML tools: ${declaredTools.join(', ')}`);
    if (!declaredTools.includes(tool)) {
      lines.push('- Requested tool is not declared in the community YAML.');
    } else if (message.includes(`Tool '${tool}' not found in skill '${skill}'`)) {
      lines.push('- Requested tool is declared in community YAML but missing from the live runtime skill. This usually means the engine daemon is stale or the runtime loader/contract diverged.');
    }
  }

  return new Error(lines.join('\n'));
}

function buildDirectRunArgs() {
  const params = parseJsonFlag(flags.params, {}, 'params');
  const view = parseJsonFlag(flags.view, {}, 'view');

  if (flags.format) view.format = flags.format;
  if (flags.detail) view.detail = flags.detail;

  const skill = flags.skill || parsed.positionals[0];
  const tool = flags.tool || parsed.positionals[1];

  if (!skill || !tool) {
    console.error('Direct call mode requires --skill and --tool (or positional skill/tool).');
    process.exit(1);
  }

  const runArgs = { skill, tool, params };
  if (flags.account) runArgs.account = flags.account;
  if (Object.keys(view).length > 0) runArgs.view = view;
  if (flags.execute) runArgs.execute = true;
  return runArgs;
}

async function runDirectCall() {
  console.log('\nConnecting to MCP...');
  console.log(`Binary: ${BINARY}`);
  console.log('Call path: run({ skill, tool, params, account? }) via MCP proxy -> engine socket.');
  const mcp = new MCP();
  await mcp.connect();
  console.log('MCP ready.\n');

  const runArgs = buildDirectRunArgs();
  if (verbose) {
    console.log(`run(${JSON.stringify(runArgs, null, 2)})\n`);
  }

  try {
    const result = await mcp.callTool('run', runArgs, rawOutput ? { rawText: true } : {});
    process.stdout.write(prettyPrint(result));
    process.stdout.write('\n');
  } catch (error) {
    throw formatRunDiagnostics(runArgs.skill, runArgs.tool, error);
  } finally {
    await mcp.disconnect();
  }
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  if (callMode) {
    await runDirectCall();
    return;
  }

  const targets = getTargetSkills();
  if (targets.length === 0) {
    console.log('No skills to test.');
    process.exit(0);
  }

  console.log(`\nConnecting to MCP...`);
  console.log(`Binary: ${BINARY}`);
  console.log('Call path: run({ skill, tool, params, account? }) via MCP proxy -> engine socket.');
  const mcp = new MCP();
  await mcp.connect();
  console.log(`MCP ready. Testing ${targets.length} skills.\n`);

  if (lenient) {
    console.error('Warning: --lenient is deprecated in strict smoke mode and is currently ignored.');
  }

  let totalPass = 0, totalFail = 0, totalWriteSkip = 0;
  const failures = [];

  for (const skillId of targets.sort()) {
    const skillDir = path.join(SKILLS_DIR, skillId);
    const sk = loadSkill(skillDir);
    if (!sk) { console.log(`  ${skillId}: (no YAML)`); continue; }

    const ops = { ...(sk.operations || {}), ...(sk.utilities || {}) };
    if (Object.keys(ops).length === 0) continue;

    const results = [];

    for (const [opName, opDef] of Object.entries(ops)) {
      if (!getTestConfig(opDef)) {
        continue;
      }
      const mode = getOperationMode(opName, opDef);

      if (!includeWrite && mode === 'write') {
        results.push({ op: opName, status: 'skip_write', reason: 'write' });
        totalWriteSkip++;
        continue;
      }

      const returns = opDef?.returns;
      const invocation = await resolveSmokeInvocation(skillId, opName, opDef, ops, mcp);
      if (!invocation.ok) {
        results.push({ op: opName, status: 'fail', reason: invocation.reason });
        totalFail++;
        failures.push(`${skillId}:${opName} — ${invocation.reason}`);
        continue;
      }

      const { params, runOptions } = invocation;

      if (verbose) console.log(`    ${skillId}:${opName} params=${JSON.stringify(params)}`);

      try {
        const t0 = Date.now();
        const result = await mcp.call(skillId, opName, params, runOptions);
        const ms = Date.now() - t0;

        const check = checkResult(result, returns);

        if (check.ok) {
          const extra = check.count !== undefined ? ` (${check.count})` : '';
          results.push({ op: opName, status: 'pass', ms, extra });
          totalPass++;
        } else {
          results.push({ op: opName, status: 'fail', reason: check.reason, ms });
          totalFail++;
          failures.push(`${skillId}:${opName} — ${check.reason}`);
        }

        if (verbose && result) {
          const s = typeof result === 'string' ? result.slice(0, 200) : JSON.stringify(result).slice(0, 200);
          console.log(`      → ${s}`);
        }
      } catch (e) {
        const message = (e.message || String(e)).slice(0, 160);
        results.push({ op: opName, status: 'fail', reason: message });
        totalFail++;
        failures.push(`${skillId}:${opName} — ${message}`);
      }
    }

    // Print skill summary line
    const pass = results.filter(r => r.status === 'pass').length;
    const fail = results.filter(r => r.status === 'fail').length;
    const skipWrite = results.filter(r => r.status === 'skip_write').length;
    const total = pass + fail;

    let status;
    if (fail > 0) status = `\x1b[31m${pass}/${total} FAIL\x1b[0m`;
    else if (total === 0 && skipWrite > 0) status = `\x1b[33mwrite-only\x1b[0m`;
    else status = `\x1b[32m${pass}/${total} PASS\x1b[0m`;

    const details = results
      .filter(r => r.status === 'fail')
      .map(r => `\x1b[31m✗ ${r.op}: ${r.reason}\x1b[0m`);

    const skipped = results
      .filter(r => r.status === 'skip_write')
      .map(r => `\x1b[33m⊘ ${r.op}: ${r.reason}\x1b[0m`);

    console.log(`  ${skillId}: ${status}${skipWrite > 0 ? ` (${skipWrite} write skipped)` : ''}`);
    for (const d of details) console.log(`    ${d}`);
    if (verbose) for (const s of skipped) console.log(`    ${s}`);
  }

  // Summary
  console.log(`\n${'─'.repeat(50)}`);
  console.log(`${totalPass} passed  ${totalFail} failed  ${totalWriteSkip} write skipped`);

  if (failures.length > 0) {
    console.log(`\nFailures:`);
    for (const f of failures) console.log(`  ✗ ${f}`);
  }

  await mcp.disconnect();
  process.exit(totalFail > 0 ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });

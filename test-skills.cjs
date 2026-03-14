#!/usr/bin/env node
/**
 * test-skills.cjs — YAML-driven skill test runner
 *
 * One MCP process. Reads each skill's YAML. Builds calls from the schema.
 * No vitest, no TypeScript compilation, no worker pools.
 *
 * Usage:
 *   node test-skills.cjs                    # test all skills
 *   node test-skills.cjs hackernews reddit  # test specific skills
 *   node test-skills.cjs --changed          # only skills changed since last commit
 *   node test-skills.cjs --verbose          # show params and responses
 *   node test-skills.cjs --read-only        # skip write ops (default)
 */

const { spawn } = require('child_process');
const { createInterface } = require('readline');
const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

// ── Config ───────────────────────────────────────────────────────────────────

const SKILLS_DIR = path.join(__dirname, 'skills');
const BINARY = path.join(process.env.HOME, 'dev/agentos/target/debug/agentos');
const TIMEOUT = 60_000;

// Default param values keyed by param name
const FIXTURES = {
  query: 'test', limit: 3, lang: 'en', format: 'text',
  feed: 'front', filter: 'today', sort: 'new',
  url: 'https://example.com',
  path: process.env.HOME + '/dev/agentos',
  subreddit: 'programming',
};

// Per-skill fixture overrides
const SKILL_FIXTURES = {
  youtube: { url: 'https://www.youtube.com/@theo' },
  linear: { account: 'AgentOS' },
  todoist: { filter: 'today | overdue' },
};

// Write ops — skip unless --write flag
const WRITE_OPS = /\.(create|update|delete|send|reply|modify|complete|reopen|trash|untrash|batch|import|pull|backfill|set_|forward)/;

// Skills to skip entirely in automated runs
// gmail: needs keychain for OAuth
// brave-browser: massive SQLite scans, hangs
// lightpanda: needs running browser engine
const SKIP_SKILLS = new Set(['gmail', 'brave-browser', 'lightpanda']);
const KEYCHAIN_OPS = new Set([
  'brave-browser:get_cookie_key', 'brave-browser:list_cookies', 'brave-browser:cookie_get', 'brave-browser:list_logins',
  'chrome:get_cookie_key', 'chrome:list_cookies', 'chrome:list_logins',
  'mimestream:credential_get',
]);

// ── CLI args ─────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const verbose = args.includes('--verbose');
const changedOnly = args.includes('--changed');
const includeWrite = args.includes('--write');
const skillFilter = args.filter(a => !a.startsWith('--'));

// ── YAML parsing ─────────────────────────────────────────────────────────────

function loadSkill(skillDir) {
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
  // All skills with operations or utilities
  return fs.readdirSync(SKILLS_DIR)
    .filter(d => {
      try { return fs.statSync(path.join(SKILLS_DIR, d)).isDirectory() && !d.startsWith('.'); }
      catch { return false; }
    })
    .filter(d => {
      const sk = loadSkill(path.join(SKILLS_DIR, d));
      return sk && (sk.operations || sk.utilities);
    });
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
        cwd: path.join(process.env.HOME, 'dev/agentos'),
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

  async call(skill, tool, params = {}) {
    const result = await this._send('tools/call', {
      name: 'run',
      arguments: { skill, tool, params },
    });
    // Unwrap MCP content
    if (result?.content && Array.isArray(result.content)) {
      const text = result.content.find(c => c.type === 'text')?.text;
      if (text) {
        // Strip markdown fences
        const m = text.match(/^```(?:json)?\n([\s\S]*?)\n```$/);
        const raw = m ? m[1] : text;
        try { return JSON.parse(raw); } catch { return raw; }
      }
    }
    return result;
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

function buildParams(opDef, skillId, opName) {
  const params = {};
  if (!opDef?.params) return params;
  const overrides = { ...FIXTURES, ...(SKILL_FIXTURES[skillId] || {}) };

  for (const [name, def] of Object.entries(opDef.params)) {
    const d = typeof def === 'object' ? def : {};
    if (d.required) {
      // Must provide required params
      if (name in overrides) params[name] = overrides[name];
      else if (d.default !== undefined) params[name] = d.default;
      else return null; // Can't satisfy
    } else {
      // Optional: only inject if there's a default in the YAML
      if (d.default !== undefined) params[name] = d.default;
    }
  }
  return params;
}

function checkResult(result, returns) {
  if (!returns || returns === 'void') return { ok: true };
  if (typeof returns !== 'string') return { ok: true };

  const isArray = returns.endsWith('[]');

  if (typeof result === 'string') {
    // Error strings
    if (result.includes('Execution failed:') || result.includes('Skill error:'))
      return { ok: false, reason: result.slice(0, 120) };
    if (result.includes('Credential not found') || result.includes('not found'))
      return { ok: null, reason: 'no credentials' };  // null = skip
    // Might be valid non-JSON response
    if (result.length > 2) return { ok: true };
    return { ok: false, reason: 'empty response' };
  }

  if (isArray) {
    if (!Array.isArray(result))
      return { ok: false, reason: `expected array, got ${typeof result}` };
    if (result.length > 0 && !result[0].id && !result[0].name)
      return { ok: false, reason: 'array items missing id/name' };
    return { ok: true, count: result.length };
  }

  // Single entity
  if (typeof result !== 'object' || result === null)
    return { ok: false, reason: `expected object, got ${typeof result}` };
  return { ok: true };
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const targets = getTargetSkills();
  if (targets.length === 0) {
    console.log('No skills to test.');
    process.exit(0);
  }

  console.log(`\nConnecting to MCP...`);
  const mcp = new MCP();
  await mcp.connect();
  console.log(`MCP ready. Testing ${targets.length} skills.\n`);

  let totalPass = 0, totalFail = 0, totalSkip = 0;
  const failures = [];

  for (const skillId of targets.sort()) {
    const skillDir = path.join(SKILLS_DIR, skillId);
    const sk = loadSkill(skillDir);
    if (!sk) { console.log(`  ${skillId}: (no YAML)`); continue; }

    const ops = { ...(sk.operations || {}), ...(sk.utilities || {}) };
    if (Object.keys(ops).length === 0) continue;

    const results = [];

    for (const [opName, opDef] of Object.entries(ops)) {
      // Skip writes
      if (!includeWrite && WRITE_OPS.test('.' + opName)) {
        results.push({ op: opName, status: 'skip', reason: 'write' });
        totalSkip++;
        continue;
      }

      // Skip blocked skills/ops
      if (SKIP_SKILLS.has(skillId) || KEYCHAIN_OPS.has(`${skillId}:${opName}`)) {
        results.push({ op: opName, status: 'skip', reason: 'keychain' });
        totalSkip++;
        continue;
      }

      const returns = opDef?.returns;
      const params = buildParams(opDef, skillId, opName);

      if (params === null) {
        results.push({ op: opName, status: 'skip', reason: 'missing required param' });
        totalSkip++;
        continue;
      }

      // For .get ops, try to get an id from the corresponding .list first
      if (opName.endsWith('.get') && opDef?.params?.id && !params.id) {
        const listOp = opName.replace(/\.get$/, '.list');
        if (ops[listOp]) {
          try {
            const listParams = buildParams(ops[listOp], skillId, listOp) || {};
            const listResult = await mcp.call(skillId, listOp, listParams);
            if (Array.isArray(listResult) && listResult[0]?.id) {
              params.id = String(listResult[0].id);
            }
          } catch {}
        }
        if (!params.id) {
          results.push({ op: opName, status: 'skip', reason: 'no id from list' });
          totalSkip++;
          continue;
        }
      }

      if (verbose) console.log(`    ${skillId}:${opName} params=${JSON.stringify(params)}`);

      try {
        const t0 = Date.now();
        const result = await mcp.call(skillId, opName, params);
        const ms = Date.now() - t0;

        const check = checkResult(result, returns);

        if (check.ok === null) {
          results.push({ op: opName, status: 'skip', reason: check.reason });
          totalSkip++;
        } else if (check.ok) {
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
        results.push({ op: opName, status: 'fail', reason: e.message.slice(0, 100) });
        totalFail++;
        failures.push(`${skillId}:${opName} — ${e.message.slice(0, 100)}`);
      }
    }

    // Print skill summary line
    const pass = results.filter(r => r.status === 'pass').length;
    const fail = results.filter(r => r.status === 'fail').length;
    const skip = results.filter(r => r.status === 'skip').length;
    const total = pass + fail;

    let status;
    if (fail > 0) status = `\x1b[31m${pass}/${total} FAIL\x1b[0m`;
    else if (pass === 0 && skip > 0) status = `\x1b[33mskipped\x1b[0m`;
    else status = `\x1b[32m${pass}/${total} PASS\x1b[0m`;

    const details = results
      .filter(r => r.status === 'fail')
      .map(r => `\x1b[31m✗ ${r.op}: ${r.reason}\x1b[0m`);

    const skipped = results
      .filter(r => r.status === 'skip' && r.reason !== 'write')
      .map(r => `\x1b[33m⊘ ${r.op}: ${r.reason}\x1b[0m`);

    console.log(`  ${skillId}: ${status}${skip > 0 ? ` (${skip} skipped)` : ''}`);
    for (const d of details) console.log(`    ${d}`);
    if (verbose) for (const s of skipped) console.log(`    ${s}`);
  }

  // Summary
  console.log(`\n${'─'.repeat(50)}`);
  console.log(`${totalPass} passed  ${totalFail} failed  ${totalSkip} skipped`);

  if (failures.length > 0) {
    console.log(`\nFailures:`);
    for (const f of failures) console.log(`  ✗ ${f}`);
  }

  await mcp.disconnect();
  process.exit(totalFail > 0 ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });

#!/usr/bin/env node
/**
 * audit-skills.cjs
 *
 * SOURCE OF TRUTH for skill YAML health. Run before every commit.
 *
 * ── Allowed top-level keys (from crates/core/src/skills/types.rs Skill struct) ──
 *
 *   id, name, description, icon, color, website, privacy_url, terms_url
 *   auth, api, database, sources
 *   adapters
 *   operations, utilities, handles
 *   provides, agent
 *
 * ── Dead / forbidden keys (auto-removed) ────────────────────────────────────
 *
 *   instructions  — put skill instructions in the markdown body after front matter
 *   connects_to   — removed from the runtime contract
 *   seed          — removed from the runtime contract
 *   testing       — replaced by direct MCP smoke checks
 *   platforms     — not in Skill struct, silently ignored by serde
 *   credits       — not in Skill struct, silently ignored by serde
 *   requires      — not in Skill struct, silently ignored by serde
 *
 * ── Any other top-level key not in the allowed list → WARNING ───────────────
 *
 * ── Checks ───────────────────────────────────────────────────────────────────
 *
 *   ERROR (blocks clean audit):
 *     [parse-error]            YAML front matter fails to parse
 *     [missing-id]             No `id` field
 *     [missing-name]           No `name` field
 *     [unknown-key]            Top-level key not in allowed list (after removals)
 *     [bash-missing-dash-dash] bash -c with positional .params args but no "--" separator
 *
 *   WARNING (informational):
 *     [mustache]         {{...}} found — run fix-mustache.cjs
 *     [no-ops]           No operations defined (may be utility-only skill)
 *     [rest-tostring]    REST query param uses | tostring — API probably wants integer
 *     [duplicate-arg]    Same .params.x arg appears twice in non-bash command args
 *
 *   AUTO-FIXED:
 *     [dead-key]      Removes forbidden keys listed above
 *
 * Usage:
 *   node audit-skills.cjs [--dry-run] [file ...]
 *   (no files = all active skills)
 *
 * Exit code: 0 = clean, 1 = errors found
 */

const fs   = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const DRY_RUN = process.argv.includes('--dry-run');
const explicit = process.argv.slice(2).filter(a => !a.startsWith('--'));
const SKILLS_DIR = path.join(__dirname, 'skills');

// ── Keys that map to actual Skill struct fields ───────────────────────────────

const ALLOWED_KEYS = new Set([
  'id', 'name', 'description', 'icon', 'color',
  'website', 'privacy_url', 'terms_url',
  'auth', 'api', 'database', 'sources',
  'adapters',
  'operations', 'utilities', 'handles',
  'provides', 'agent',
]);

// ── Keys that exist in YAMLs but are dead — auto-remove ──────────────────────

const DEAD_KEYS = [
  'instructions',  // use the markdown body after front matter instead
  'connects_to',   // removed from the runtime contract
  'seed',          // removed from the runtime contract
  'testing',       // replaced by direct MCP smoke checks
  'platforms',     // not in Skill struct
  'credits',       // not in Skill struct
  'requires',      // not in Skill struct
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function getActiveSkillFiles() {
  return fs.readdirSync(SKILLS_DIR)
    .filter(d => fs.statSync(path.join(SKILLS_DIR, d)).isDirectory() && !d.startsWith('.'))
    .map(d => path.join(SKILLS_DIR, d, 'readme.md'))
    .filter(f => fs.existsSync(f));
}

/**
 * Remove a top-level YAML key and its entire value block, line-by-line.
 * Preserves all formatting and comments. Returns { content, removed }.
 */
function removeTopLevelKey(content, key) {
  const lines = content.split('\n');
  const out = [];
  let i = 0;
  let removed = false;

  while (i < lines.length) {
    const line = lines[i];
    if (line.match(new RegExp(`^${key}\\s*:`))) {
      removed = true;
      i++;
      while (i < lines.length && (lines[i] === '' || lines[i].match(/^\s+/))) {
        i++;
      }
      // Remove the trailing blank line the deletion leaves behind
      if (out.length > 0 && out[out.length - 1] === '') out.pop();
      continue;
    }
    out.push(line);
    i++;
  }

  return { content: out.join('\n'), removed };
}

/**
 * Parse the YAML front matter (between opening and closing ---).
 */
function parseSkillYaml(content) {
  if (content.startsWith('---')) {
    const end = content.indexOf('\n---', 3);
    if (end !== -1) return yaml.load(content.slice(3, end));
  }
  return yaml.load(content);
}

// ── Main ──────────────────────────────────────────────────────────────────────

const targetFiles = explicit.length > 0 ? explicit : getActiveSkillFiles();

let totalFiles = 0;
let fixedFiles = 0;
let errorCount = 0;
let warnCount  = 0;

const results = [];

for (const f of targetFiles) {
  totalFiles++;
  const relPath = path.relative(__dirname, f);
  let content = fs.readFileSync(f, 'utf8');

  const errors   = [];
  const warnings = [];
  const fixed    = [];

  // ── 1. Auto-remove dead keys ───────────────────────────────────────────────
  for (const key of DEAD_KEYS) {
    const { content: updated, removed } = removeTopLevelKey(content, key);
    if (removed) { content = updated; fixed.push(`removed '${key}'`); }
  }

  // ── 2. Warn on remaining mustache ─────────────────────────────────────────
  const mustacheLines = content.split('\n')
    .map((text, idx) => ({ line: idx + 1, text }))
    .filter(({ text }) => text.includes('{{') && !text.trimStart().startsWith('#'));
  if (mustacheLines.length > 0) {
    warnings.push({
      code: 'mustache',
      msg: `${mustacheLines.length} line(s) still use {{}} — run fix-mustache.cjs`,
      detail: mustacheLines.slice(0, 3).map(({ line, text }) => `L${line}: ${text.trim().slice(0, 80)}`),
    });
  }

  // ── 3. Parse and validate ──────────────────────────────────────────────────
  let parsed = null;
  try {
    parsed = parseSkillYaml(content);
  } catch (e) {
    errors.push({ code: 'parse-error', msg: e.message.split('\n')[0] });
  }

  if (parsed && typeof parsed === 'object') {
    if (!parsed.id)   errors.push({ code: 'missing-id',   msg: 'missing required field: id' });
    if (!parsed.name) errors.push({ code: 'missing-name', msg: 'missing required field: name' });

    // Unknown keys (after dead keys already removed)
    const unknownKeys = Object.keys(parsed).filter(k => !ALLOWED_KEYS.has(k));
    for (const k of unknownKeys) {
      errors.push({ code: 'unknown-key', msg: `unknown top-level key '${k}' — not in Skill struct. Add to ALLOWED_KEYS or DEAD_KEYS.` });
    }

    if (!parsed.operations && !parsed.utilities) {
      warnings.push({ code: 'no-ops', msg: 'no operations or utilities defined' });
    }

    // ── Operation-level checks ───────────────────────────────────────────────
    const ops = parsed.operations || {};
    for (const [opName, op] of Object.entries(ops)) {
      if (!op || typeof op !== 'object') continue;
      // Check 2 (REST): warn on | tostring in query params
      const rest = op.rest;
      if (rest && rest.query && typeof rest.query === 'object') {
        for (const [param, expr] of Object.entries(rest.query)) {
          if (typeof expr === 'string' && expr.includes('| tostring')) {
            warnings.push({
              code: 'rest-tostring',
              msg: `${opName}: REST query param '${param}' uses | tostring — most APIs want a native integer, not a string`,
              detail: [`  ${param}: ${expr}`],
            });
          }
        }
      }

      const cmd = op.command;
      if (!cmd) continue;

      const args = cmd.args;
      if (!Array.isArray(args) || args.length === 0) continue;

      // Check 1: bash -c with positional args must have -- separator
      // Pattern: binary=bash, args=["-c", "script", ..., ".params.x"]
      // The script body is the arg after "-c". If the last args are jaq
      // expressions (.params.*) and there's no "--" before them, args
      // shift at runtime and params land in wrong positions.
      if (cmd.binary === 'bash') {
        const cIdx = args.indexOf('-c');
        if (cIdx !== -1) {
          // Find jaq args (start with . and reference params)
          const jaqArgs = args.filter((a, i) => i > cIdx + 1 && typeof a === 'string' && a.startsWith('.params'));
          if (jaqArgs.length > 0) {
            const hasDash = args.includes('--');
            if (!hasDash) {
              errors.push({
                code: 'bash-missing-dash-dash',
                msg: `${opName}: bash -c with positional .params args but no "--" separator — args will shift at runtime`,
                detail: [`args: ${JSON.stringify(args.slice(0, 6))}${args.length > 6 ? ' ...' : ''}`],
              });
            }
          }
        }
      }

      // Check 3: duplicate jaq args in non-bash commands on the SAME side of --
      // e.g. yt-dlp with .params.url appearing twice before (or twice after) --
      // Legitimate: named flag before -- and positional after -- is fine (imsg pattern).
      if (cmd.binary !== 'bash') {
        const dashIdx = args.indexOf('--');
        const sections = dashIdx === -1
          ? [args]
          : [args.slice(0, dashIdx), args.slice(dashIdx + 1)];
        for (const section of sections) {
          const seen = new Set();
          for (const a of section) {
            if (typeof a === 'string' && a.startsWith('.params')) {
              if (seen.has(a)) {
                warnings.push({
                  code: 'duplicate-arg',
                  msg: `${opName}: jaq arg '${a}' appears more than once on the same side of '--' in non-bash args`,
                  detail: [`binary: ${cmd.binary}`, `args: ${JSON.stringify(args)}`],
                });
                break;
              }
              seen.add(a);
            }
          }
        }
      }
    }
  }

  // ── 4. Write fixes ─────────────────────────────────────────────────────────
  if (fixed.length > 0) {
    fixedFiles++;
    if (!DRY_RUN) fs.writeFileSync(f, content, 'utf8');
  }

  errorCount += errors.length;
  warnCount  += warnings.length;

  if (fixed.length || errors.length || warnings.length) {
    results.push({ file: relPath, fixed, errors, warnings });
  }
}

// ── Output ────────────────────────────────────────────────────────────────────

for (const { file, fixed, errors, warnings } of results) {
  const hasOutput = fixed.length || errors.length || warnings.length;
  if (!hasOutput) continue;

  console.log(`\n${file}`);

  for (const f of fixed) {
    console.log(`  ${DRY_RUN ? '[dry] ' : ''}✓ ${f}`);
  }
  for (const { code, msg, detail } of errors) {
    console.log(`  ✗ [${code}] ${msg}`);
    if (detail) detail.forEach(d => console.log(`      ${d}`));
  }
  for (const { code, msg, detail } of warnings) {
    console.log(`  ⚠ [${code}] ${msg}`);
    if (detail) detail.forEach(d => console.log(`      ${d}`));
  }
}

// Summary
console.log(`\n${'─'.repeat(60)}`);
console.log(`${DRY_RUN ? '[DRY RUN] ' : ''}${totalFiles} files  |  ${fixedFiles} fixed  |  ${errorCount} errors  |  ${warnCount} warnings`);

if (errorCount === 0 && warnCount === 0) {
  console.log('✓ All clear.');
} else if (errorCount > 0) {
  console.log('✗ Audit failed — fix errors above.');
}

process.exit(errorCount > 0 ? 1 : 0);

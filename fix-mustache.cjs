#!/usr/bin/env node
/**
 * fix-mustache.cjs
 *
 * Converts {{params.x}} mustache patterns in skill readme.md files
 * to proper jaq-style expressions the AgentOS engine understands.
 *
 * Rules:
 *
 * 1. YAML list item / key that is ONLY a mustache token:
 *      - "{{params.id}}"        →  - ".params.id"
 *      key: "{{params.url}}"   →  key: ".params.url"
 *      "{{x | default:N}}"     →  ".params.x // N"
 *
 * 2. REST `url:` with embedded mustache:
 *      url: "https://api.x.com/{{params.id}}/sub"
 *      → url: '"https://api.x.com/" + .params.id + "/sub"'
 *
 * 3. Bash script (block scalar or single-line) with inline {{params.x}}:
 *    - Replace tokens with ${PARAM_X} shell var refs
 *    - Prepend PARAM_X="$1"; PARAM_Y="$2" assignment line at top of script
 *    - Append "--", ".params.x", ".params.y" positional args after the script
 *
 * 4. Inline args array: args: ["-c", "script {{params.x}}"]
 *    → args: ["-c", "PARAM_X=\"$1\"; script ${PARAM_X}", "--", ".params.x"]
 *
 * Usage:
 *   node fix-mustache.cjs [--dry-run] [file ...]
 *   (no files = process all active skills)
 */

const fs = require('fs');
const path = require('path');

const DRY_RUN = process.argv.includes('--dry-run');
const explicit = process.argv.slice(2).filter(a => !a.startsWith('--'));
const SKILLS_DIR = path.join(__dirname, 'skills');

function getActiveSkillFiles() {
  return fs.readdirSync(SKILLS_DIR)
    .filter(d => fs.statSync(path.join(SKILLS_DIR, d)).isDirectory() && !d.startsWith('.'))
    .map(d => path.join(SKILLS_DIR, d, 'readme.md'))
    .filter(f => fs.existsSync(f));
}

const targetFiles = explicit.length > 0 ? explicit : getActiveSkillFiles();

// ── Helpers ───────────────────────────────────────────────────────────────────

function extractTokens(s) {
  const re = /\{\{([^{}]+)\}\}/g;
  const tokens = [];
  let m;
  while ((m = re.exec(s)) !== null) tokens.push({ full: m[0], inner: m[1].trim() });
  return tokens;
}

function isOnlyMustache(s) {
  return /^\{\{[^{}]+\}\}$/.test(s.trim());
}

function mustacheToJaq(inner) {
  inner = inner.trim();
  const defM = inner.match(/^(.+?)\s*\|\s*default\s*[:=]?\s*(.+)$/);
  if (defM) {
    const p = defM[1].trim();
    const d = defM[2].trim();
    return `${p.startsWith('.') ? p : '.' + p} // ${d}`;
  }
  return inner.startsWith('.') ? inner : '.' + inner;
}

function urlToJaq(s) {
  const parts = s.split(/\{\{([^{}]+)\}\}/);
  const jaqParts = [];
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 0) { if (parts[i]) jaqParts.push(JSON.stringify(parts[i])); }
    else { jaqParts.push(mustacheToJaq(parts[i])); }
  }
  return jaqParts.join(' + ');
}

function tokenToShellVar(inner) {
  return inner.trim()
    .replace(/\s*\|.*$/, '')   // drop | default... part
    .replace(/^params\./, 'PARAM_')
    .replace(/\./g, '_')
    .toUpperCase();
}

// ── Line-by-line processor ────────────────────────────────────────────────────

function processFile(content) {
  const lines = content.split('\n');
  const out = [];
  let i = 0;
  let changed = false;

  while (i < lines.length) {
    const line = lines[i];

    // `args:` block — must check BEFORE the {{-only fast-exit since the args: line itself has no {{
    if (line.match(/^\s*args:\s*$/)) {
      const result = rewriteArgsBlock(lines, i);
      if (result && result.changed) {
        for (const l of result.lines) out.push(l);
        changed = true;
        i += result.consumed;
        continue;
      }
    }

    if (!line.includes('{{')) { out.push(line); i++; continue; }

    // 1. List item that is only a mustache token: `        - "{{params.id}}"`
    const listM = line.match(/^(\s*-\s+)"(\{\{[^{}]+\}\})"(.*)$/);
    if (listM) {
      const jaq = mustacheToJaq(listM[2].slice(2, -2));
      out.push(`${listM[1]}"${jaq}"${listM[3]}`);
      changed = true; i++; continue;
    }

    // 2. YAML key: value that is only a mustache token
    const kvM = line.match(/^(\s*)([\w][\w.-]*):\s+"(\{\{[^{}]+\}\})"(.*)$/);
    if (kvM) {
      const key = kvM[2];
      if (key === 'web_url') { out.push(line); i++; continue; } // display only
      const jaq = mustacheToJaq(kvM[3].slice(2, -2));
      out.push(`${kvM[1]}${key}: "${jaq}"${kvM[4]}`);
      changed = true; i++; continue;
    }

    // 3. REST `url:` with embedded mustache (but not whole-value — caught above)
    const urlM = line.match(/^(\s*url:\s+)"(.+)"(.*)$/);
    if (urlM && extractTokens(urlM[2]).length > 0) {
      out.push(`${urlM[1]}'${urlToJaq(urlM[2])}'${urlM[3]}`);
      changed = true; i++; continue;
    }

    // 4. `args:` inline array (args: [...] on one line)
    if (line.match(/^\s*args:\s*\[/) && line.includes('{{')) {
      const rewritten = rewriteInlineArgsLine(line);
      if (rewritten !== line) { changed = true; out.push(rewritten); i++; continue; }
    }

    // 6. Fallback: replace remaining {{params.x}} with ${PARAM_X} in any line
    //    (inside block scalars already collected above; this catches stragglers)
    const tokens = extractTokens(line);
    if (tokens.length > 0) {
      let fixed = line;
      for (const tok of tokens) {
        fixed = fixed.split(tok.full).join('${' + tokenToShellVar(tok.inner) + '}');
      }
      if (fixed !== line) { changed = true; out.push(fixed); i++; continue; }
    }

    out.push(line); i++;
  }

  return changed ? out.join('\n') : null;
}

// ── Args block rewriter ───────────────────────────────────────────────────────

/**
 * Parse and rewrite a multi-line `args:` block starting at line index `start`.
 * Returns { lines, consumed, changed } or null if nothing to do.
 */
function rewriteArgsBlock(lines, start) {
  const argsLine = lines[start];
  const baseInd = argsLine.match(/^(\s*)/)[1];
  const itemInd = baseInd + '  ';
  const bodyInd = itemInd + '  ';

  let i = start + 1;
  const elements = []; // { type, lines: [], value? }

  while (i < lines.length) {
    const line = lines[i];
    if (!line.startsWith(itemInd)) break;
    if (line.trim() === '') break;

    const trimmed = line.slice(itemInd.length);

    if (trimmed.startsWith('- ')) {
      const rest = trimmed.slice(2);

      // Block scalar
      if (rest.trim() === '|' || rest.trim() === '|-') {
        const header = line;
        const bodyLines = [];
        i++;
        while (i < lines.length && (lines[i].startsWith(bodyInd) || lines[i].trim() === '')) {
          bodyLines.push(lines[i]);
          i++;
        }
        elements.push({ type: 'block', header, bodyLines });
        continue;
      }

      // Quoted value
      const dqM = rest.match(/^"((?:[^"\\]|\\.)*)"(.*)$/);
      if (dqM) {
        elements.push({ type: 'dq', line, value: dqM[1], suffix: dqM[2] });
        i++; continue;
      }
      const sqM = rest.match(/^'((?:[^'\\]|\\.)*)'(.*)$/);
      if (sqM) {
        elements.push({ type: 'sq', line, value: sqM[1], suffix: sqM[2] });
        i++; continue;
      }

      // Unquoted
      elements.push({ type: 'bare', line, value: rest.trim() });
      i++; continue;
    }

    break;
  }

  const consumed = i - start;
  const hasMustache = elements.some(el => {
    if (el.type === 'block') return el.bodyLines.some(l => l.includes('{{'));
    return (el.value || '').includes('{{');
  });

  if (!hasMustache) return null;

  // Gather all unique param vars across the whole block
  const allTokens = new Map(); // shellVar → jaqExpr
  for (const el of elements) {
    const src = el.type === 'block' ? el.bodyLines.join('\n') : (el.value || '');
    for (const tok of extractTokens(src)) {
      const v = tokenToShellVar(tok.inner);
      if (!allTokens.has(v)) allTokens.set(v, mustacheToJaq(tok.inner));
    }
  }

  const varNames = [...allTokens.keys()];
  const varAssign = varNames.map((v, idx) => `${v}="$${idx + 1}"`).join('; ');
  const jaqArgs = [...allTokens.values()];

  const outLines = [`${baseInd}args:`];
  let anyChanged = false;

  for (const el of elements) {
    if (el.type === 'block') {
      const hasMust = el.bodyLines.some(l => l.includes('{{'));
      outLines.push(el.header);
      if (hasMust) {
        anyChanged = true;
        // Inject var assignments as first line of script body
        const firstContentLine = el.bodyLines.find(l => l.trim() !== '');
        const contentInd = firstContentLine ? firstContentLine.match(/^(\s*)/)[1] : bodyInd;
        outLines.push(`${contentInd}${varAssign}`);
        for (const bl of el.bodyLines) {
          let fixed = bl;
          for (const tok of extractTokens(bl)) {
            fixed = fixed.split(tok.full).join('${' + tokenToShellVar(tok.inner) + '}');
          }
          outLines.push(fixed);
        }
      } else {
        for (const bl of el.bodyLines) outLines.push(bl);
      }
    } else if (el.type === 'dq' || el.type === 'sq') {
      const tokens = extractTokens(el.value);
      if (tokens.length === 0) { outLines.push(el.line); continue; }
      if (isOnlyMustache(el.value)) {
        anyChanged = true;
        outLines.push(`${itemInd}- "${mustacheToJaq(tokens[0].inner)}"${el.suffix || ''}`);
      } else {
        anyChanged = true;
        let fixed = el.value;
        for (const tok of tokens) fixed = fixed.split(tok.full).join('${' + tokenToShellVar(tok.inner) + '}');
        const q = el.type === 'dq' ? '"' : "'";
        outLines.push(`${itemInd}- ${q}${fixed}${q}${el.suffix || ''}`);
      }
    } else {
      // bare
      const tokens = extractTokens(el.value || '');
      if (tokens.length === 0) { outLines.push(el.line); continue; }
      anyChanged = true;
      let fixed = el.value;
      for (const tok of tokens) fixed = fixed.split(tok.full).join('${' + tokenToShellVar(tok.inner) + '}');
      outLines.push(`${itemInd}- ${fixed}`);
    }
  }

  // Append positional args
  if (anyChanged && jaqArgs.length > 0) {
    const alreadyHasDash = elements.some(el => (el.value || '').trim() === '--');
    if (!alreadyHasDash) {
      outLines.push(`${itemInd}- "--"`);
      for (const jaq of jaqArgs) outLines.push(`${itemInd}- "${jaq}"`);
    }
  }

  return { lines: outLines, consumed, changed: anyChanged };
}

// ── Inline args line rewriter ─────────────────────────────────────────────────

function rewriteInlineArgsLine(line) {
  const m = line.match(/^(\s*args:\s*\[)(.+?)(\].*)$/);
  if (!m) return line;

  // Simple parse: extract string elements
  const inner = m[2];
  const elements = [];
  const re = /"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'/g;
  let match;
  while ((match = re.exec(inner)) !== null) {
    const val = match[1] !== undefined ? match[1] : match[2];
    const type = match[1] !== undefined ? 'dq' : 'sq';
    elements.push({ val, type, raw: match[0] });
  }

  const allTokens = new Map();
  for (const el of elements) {
    for (const tok of extractTokens(el.val)) {
      const v = tokenToShellVar(tok.inner);
      if (!allTokens.has(v)) allTokens.set(v, mustacheToJaq(tok.inner));
    }
  }
  if (allTokens.size === 0) return line;

  const varNames = [...allTokens.keys()];
  const varAssign = varNames.map((v, idx) => `${v}="$${idx + 1}"`).join('; ');
  const jaqArgs = [...allTokens.values()];

  const rewritten = elements.map(el => {
    const tokens = extractTokens(el.val);
    if (tokens.length === 0) return el.raw;
    if (isOnlyMustache(el.val)) return `"${mustacheToJaq(tokens[0].inner)}"`;
    let fixed = el.val;
    for (const tok of tokens) fixed = fixed.split(tok.full).join('${' + tokenToShellVar(tok.inner) + '}');
    // Prepend var assignment to the script
    return `"${varAssign}; ${fixed}"`;
  });

  const extras = ['"--"', ...jaqArgs.map(j => `"${j}"`)];
  const newInner = [...rewritten, ...extras].join(', ');
  return `${m[1]}${newInner}${m[3]}`;
}

// ── Main ──────────────────────────────────────────────────────────────────────

let totalFiles = 0;
let changedFiles = 0;

for (const f of targetFiles) {
  const content = fs.readFileSync(f, 'utf8');
  const fixed = processFile(content);
  totalFiles++;
  if (fixed !== null) {
    changedFiles++;
    if (DRY_RUN) {
      console.log(`\n=== ${path.relative(__dirname, f)} ===`);
      const origLines = content.split('\n');
      const fixedLines = fixed.split('\n');
      for (let i = 0; i < Math.max(origLines.length, fixedLines.length); i++) {
        if (origLines[i] !== fixedLines[i]) {
          console.log(`  L${i+1} - ${origLines[i]}`);
          console.log(`  L${i+1} + ${fixedLines[i]}`);
        }
      }
    } else {
      fs.writeFileSync(f, fixed, 'utf8');
      console.log(`Fixed: ${path.relative(__dirname, f)}`);
    }
  }
}

console.log(`\n${DRY_RUN ? '[DRY RUN] ' : ''}Processed ${totalFiles} files, ${changedFiles} changed.`);

if (!DRY_RUN) {
  let remaining = [];
  for (const f of targetFiles) {
    if (fs.readFileSync(f, 'utf8').includes('{{')) remaining.push(path.relative(__dirname, f));
  }
  if (remaining.length) {
    console.log('\nRemaining {{}} (needs manual review):');
    remaining.forEach(f => console.log('  ' + f));
  } else {
    console.log('\nAll clear — no remaining {{}} in active skills.');
  }
}

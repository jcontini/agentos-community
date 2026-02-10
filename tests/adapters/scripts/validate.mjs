#!/usr/bin/env node
/**
 * Adapter validation — validate, report, enforce.
 * 
 * Checks per adapter:
 *   1. Schema  — YAML frontmatter matches adapter.schema.json
 *   2. Entity  — All operations return valid entity types
 *   3. Mapping — Adapter mappings use valid entity properties + jaq syntax
 *   4. Icon    — icon.svg or icon.png exists
 *   5. Seed    — connects_to + seed data (product/org entities)
 *   6. Tests   — Every operation has a test file
 * 
 * Adapters in .needs-work/ are shown separately but never auto-moved.
 * Fix errors, then manually move to adapters/ when ready.
 * 
 * Usage:
 *   node validate.mjs                     # Full validation + enforce
 *   node validate.mjs --filter exa        # Filter to specific adapter
 *   node validate.mjs --verbose           # Show uncovered entities
 *   node validate.mjs --pre-commit        # Quick structural check only (no table, no move)
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse as parseYaml, parseAllDocuments } from 'yaml';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../../..');
const ADAPTERS_DIR = join(ROOT, 'adapters');
const ENTITIES_DIR = join(ROOT, 'entities');
const NEEDS_WORK_DIR = join(ADAPTERS_DIR, '.needs-work');
const SCHEMA_PATH = join(__dirname, '..', 'adapter.schema.json');

// ============================================================================
// ARGS
// ============================================================================

const args = process.argv.slice(2);
const filterValue = args.includes('--filter') ? args[args.indexOf('--filter') + 1] : null;
const preCommit = args.includes('--pre-commit');
const verbose = args.includes('--verbose');

// ============================================================================
// LOAD SCHEMA + ENTITIES
// ============================================================================

const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf-8'));
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const validateSchema = ajv.compile(schema);

function loadEntityIds() {
  const entityIds = new Set();
  function scan(dir) {
    if (!existsSync(dir)) return;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory() && !entry.name.startsWith('.') && entry.name !== 'views') {
        scan(fullPath);
      } else if (entry.name.endsWith('.yaml') && entry.name !== 'icon.yaml') {
        try {
          const docs = parseAllDocuments(readFileSync(fullPath, 'utf-8'));
          for (const doc of docs) {
            const data = doc.toJSON();
            if (data?.id) entityIds.add(data.id);
          }
        } catch {}
      }
    }
  }
  scan(ENTITIES_DIR);
  return entityIds;
}

function loadEntityProperties() {
  const props = {};
  const vocabularies = {};
  function scan(dir) {
    if (!existsSync(dir)) return;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory() && !entry.name.startsWith('.') && entry.name !== 'views') {
        scan(fullPath);
      } else if (entry.name.endsWith('.yaml') && entry.name !== 'icon.yaml') {
        try {
          const docs = parseAllDocuments(readFileSync(fullPath, 'utf-8'));
          for (const doc of docs) {
            const data = doc.toJSON();
            if (data?.id && data?.properties) {
              props[data.id] = Object.keys(data.properties);
              if (data.vocabulary) vocabularies[data.id] = data.vocabulary;
              if (data.extends && props[data.extends]) {
                const vocabulary = vocabularies[data.id] || {};
                // Apply vocabulary overrides when inheriting parent props
                // e.g., vocabulary: { author: sender } renames inherited `author` to `sender`
                const parentProps = props[data.extends].map(
                  prop => vocabulary[prop] || prop
                );
                props[data.id] = [...new Set([...parentProps, ...props[data.id]])];
              }
            }
          }
        } catch {}
      }
    }
  }
  // Scan twice to resolve extends (parent might load after child)
  scan(ENTITIES_DIR);
  scan(ENTITIES_DIR);
  // Inject system properties — every entity gets created_at/updated_at automatically.
  // These are system-managed timestamps, not declared in individual YAMLs.
  for (const id of Object.keys(props)) {
    if (!props[id].includes('created_at')) props[id].push('created_at');
    if (!props[id].includes('updated_at')) props[id].push('updated_at');
  }
  return props;
}

const validEntityIds = loadEntityIds();
const entityProperties = loadEntityProperties();

// ============================================================================
// CHECKS
// ============================================================================

function checkSchema(frontmatter) {
  const valid = validateSchema(frontmatter);
  const ajvErrors = valid ? [] : validateSchema.errors.map(e => `${e.instancePath || '/'}: ${e.message}`);
  
  if (!valid) {
    return {
      pass: false,
      structureValid: false,
      passed: 0,
      total: 1,
      errors: ajvErrors,
    };
  }
  
  const checks = [
    { name: 'valid structure', pass: true },
    { name: 'website', pass: !!frontmatter.website },
    { name: 'color', pass: !!frontmatter.color },
    { name: 'auth', pass: frontmatter.auth !== undefined },
    { name: 'operations or utilities', pass: !!(frontmatter.operations || frontmatter.utilities) },
    { name: 'instructions', pass: !!frontmatter.instructions },
  ];
  
  const passed = checks.filter(c => c.pass).length;
  const total = checks.length;
  const errors = checks.filter(c => !c.pass).map(c => `Missing: ${c.name}`);
  
  return { pass: passed === total, structureValid: true, passed, total, errors };
}

function checkEntities(frontmatter) {
  const errors = [];
  let total = 0;
  let passed = 0;
  
  if (frontmatter.operations) {
    for (const [opName, op] of Object.entries(frontmatter.operations)) {
      total++;
      if (!op.returns || op.returns === 'void') {
        const verb = opName.split('.')[1];
        if (!['create', 'update', 'delete', 'archive', 'complete', 'reopen', 'send'].includes(verb)) {
          errors.push(`'${opName}' returns void — read operations must return an entity`);
        } else {
          passed++;
        }
        continue;
      }
      const entityName = op.returns.replace(/\[\]$/, '');
      if (validEntityIds.has(entityName)) {
        passed++;
      } else {
        errors.push(`'${opName}' returns unknown entity '${entityName}'`);
      }
      // entity[] ops: rest/graphql must have response.root for top-level array
      if (op.returns.endsWith('[]') && (op.rest || op.graphql)) {
        const hasRoot = op.rest?.response?.root || op.graphql?.response?.root;
        if (!hasRoot) {
          errors.push(`'${opName}' returns array — rest/graphql must have response.root pointing to the array`);
        }
      }
    }
  }
  
  return { pass: errors.length === 0, passed, total, errors };
}

function checkMappings(frontmatter) {
  const errors = [];
  let total = 0;
  let passed = 0;
  
  if (!frontmatter.adapters) {
    if (frontmatter.operations && Object.keys(frontmatter.operations).length > 0) {
      errors.push('Has operations but no adapters section — data won\'t flow through entities');
      total = 1;
    }
    return { pass: errors.length === 0, passed, total, errors };
  }
  
  for (const [entityName, adapter] of Object.entries(frontmatter.adapters)) {
    if (!adapter.mapping) {
      total++;
      errors.push(`Adapter '${entityName}' has no mapping`);
      continue;
    }
    
    const validProps = entityProperties[entityName];
    if (!validProps) continue;
    
    for (const [propName, propValue] of Object.entries(adapter.mapping)) {
      if (propName.startsWith('_')) continue;
      if (typeof propValue === 'object' && propValue !== null) continue;
      
      total++;
      const topLevelProp = propName.split('.')[0];
      if (validProps.includes(topLevelProp)) {
        passed++;
      } else {
        errors.push(`'${entityName}' maps unknown property '${topLevelProp}'`);
      }
    }
  }
  
  // Check jaq expressions
  if (frontmatter.adapters) {
    for (const [entityName, adapter] of Object.entries(frontmatter.adapters)) {
      if (!adapter.mapping) continue;
      for (const { path, expr } of collectJaqExpressions(adapter.mapping, entityName)) {
        total++;
        let exprOk = true;
        const singleQuoteMatches = expr.match(/== *'[^']*'|'[^']*' *==|'[^']*' *\?|: *'[^']*'/g);
        if (singleQuoteMatches) {
          errors.push(`${path}: single-quoted string in jaq (use double quotes)`);
          exprOk = false;
        }
        if (/\?\s*["']/.test(expr) && !/\?\/\//.test(expr)) {
          errors.push(`${path}: C-style ternary (use if/then/else/end)`);
          exprOk = false;
        }
        const bareIter = expr.match(/\.(nodes|items|edges)\[\][^?]/);
        if (bareIter) {
          const guard = /\(\s*\([^)]+\/\/\s*\{\s*\}\s*\)\s*\.\s*(nodes|items|edges)\s*\/\/\s*\[\s*\]\s*\)/;
          if (!guard.test(expr)) {
            errors.push(`${path}: bare .${bareIter[1]}[] without null guard`);
            exprOk = false;
          }
        }
        if (exprOk) passed++;
      }
    }
  }
  
  return { pass: errors.length === 0, passed, total, errors };
}

function collectJaqExpressions(mapping, parentPath) {
  const exprs = [];
  for (const [key, value] of Object.entries(mapping)) {
    const path = `${parentPath}.${key}`;
    if (typeof value === 'string') {
      if (value.includes('==') || value.includes('if ') || value.includes('[]') ||
          value.includes('//') || value.includes('|') || value.includes('?') ||
          value.includes("'")) {
        exprs.push({ path, expr: value });
      }
    } else if (typeof value === 'object' && value !== null) {
      exprs.push(...collectJaqExpressions(value, path));
    }
  }
  return exprs;
}

function checkIcon(adapterDir) {
  const hasSvg = existsSync(join(adapterDir, 'icon.svg'));
  const hasPng = existsSync(join(adapterDir, 'icon.png'));
  const format = hasSvg ? 'svg' : hasPng ? 'png' : null;
  return { pass: !!format, format, errors: format ? [] : ['Missing icon.svg or icon.png'] };
}

function checkSeed(frontmatter) {
  const errors = [];
  let total = 0;
  let passed = 0;
  
  // Check connects_to exists
  total++;
  const connectsTo = frontmatter.connects_to;
  if (connectsTo) {
    passed++;
  } else {
    errors.push('Missing connects_to — adapter must declare which product it connects to');
  }
  
  // Check seed data exists
  total++;
  const seed = frontmatter.seed;
  if (seed && seed.length > 0) {
    passed++;
  } else {
    errors.push('Missing seed data — adapter must seed product and organization entities');
  }
  
  // Check connects_to references exist in seed data
  if (connectsTo && seed && seed.length > 0) {
    const seedIds = new Set(seed.map(s => s.id));
    const targets = Array.isArray(connectsTo) ? connectsTo : [connectsTo];
    for (const target of targets) {
      total++;
      if (seedIds.has(target)) {
        passed++;
      } else {
        errors.push(`connects_to '${target}' not found in seed data`);
      }
    }
  }
  
  return { pass: errors.length === 0, passed, total, errors };
}

function checkTests(adapterDir, frontmatter) {
  const tools = [];
  if (frontmatter.operations) tools.push(...Object.keys(frontmatter.operations));
  if (frontmatter.utilities) tools.push(...Object.keys(frontmatter.utilities));
  
  if (tools.length === 0) return { pass: true, errors: [], tested: 0, total: 0 };
  
  const testsDir = join(adapterDir, 'tests');
  const testedTools = new Set();
  if (existsSync(testsDir)) {
    for (const file of readdirSync(testsDir).filter(f => f.endsWith('.test.ts'))) {
      const content = readFileSync(join(testsDir, file), 'utf-8');
      for (const match of content.matchAll(/tool:\s*['"]([^'"]+)['"]/g)) {
        testedTools.add(match[1]);
      }
    }
  }
  
  const untested = tools.filter(t => !testedTools.has(t));
  return {
    pass: untested.length === 0,
    errors: untested.length > 0 ? [`Missing: ${untested.join(', ')}`] : [],
    tested: testedTools.size,
    total: tools.length,
  };
}

// ============================================================================
// DISCOVER ADAPTERS
// ============================================================================

function findAdapters(dir, relativePath = '') {
  const adapters = [];
  if (!existsSync(dir)) return adapters;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name === 'node_modules' || entry.name === 'tests') continue;
    if (entry.name.startsWith('.')) continue;
    const fullPath = join(dir, entry.name);
    const rel = relativePath ? `${relativePath}/${entry.name}` : entry.name;
    if (existsSync(join(fullPath, 'readme.md'))) {
      adapters.push({ name: entry.name, path: rel, dir: fullPath });
    } else {
      adapters.push(...findAdapters(fullPath, rel));
    }
  }
  return adapters;
}

// ============================================================================
// TABLE RENDERING
// ============================================================================

const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const DIM = '\x1b[2m';
const YELLOW = '\x1b[33m';
const RESET = '\x1b[0m';
const BOLD = '\x1b[1m';

const SKIP = `${DIM}·${RESET}`;
const BLOCKED = `${DIM}—${RESET}`;

function pad(str, len) {
  return str.length >= len ? str.slice(0, len) : str + ' '.repeat(len - str.length);
}

function cell(symbol, width) {
  const leftPad = Math.floor((width - 1) / 2);
  const rightPad = width - 1 - leftPad;
  return ' '.repeat(leftPad) + symbol + ' '.repeat(rightPad);
}

function renderTable(sections) {
  const allResults = sections.flatMap(s => s.results);
  if (allResults.length === 0) return;
  
  const nameWidth = Math.max(16, ...allResults.map(r => r.name.length)) + 2;
  const colW = 9;
  const testColW = 9;
  
  function centerText(text, width) {
    const lp = Math.floor((width - text.length) / 2);
    const rp = width - text.length - lp;
    return ' '.repeat(lp) + text + ' '.repeat(rp);
  }
  
  const SEP = `${DIM}│${RESET}`;
  const headerLine = `${SEP} ${BOLD}${pad('Adapter', nameWidth)}${RESET}${SEP}${DIM}${centerText('Schema', colW)}${RESET}${SEP}${DIM}${centerText('Entity', colW)}${RESET}${SEP}${DIM}${centerText('Mapping', colW)}${RESET}${SEP}${DIM}${centerText('Icon', colW)}${RESET}${SEP}${DIM}${centerText('Seed', colW)}${RESET}${SEP}${DIM}${centerText('Tests', testColW)}${RESET}${SEP}`;
  
  const topBorder  = `${DIM}┌${'─'.repeat(nameWidth + 1)}┬${'─'.repeat(colW)}┬${'─'.repeat(colW)}┬${'─'.repeat(colW)}┬${'─'.repeat(colW)}┬${'─'.repeat(colW)}┬${'─'.repeat(testColW)}┐${RESET}`;
  const botBorder  = `${DIM}└${'─'.repeat(nameWidth + 1)}┴${'─'.repeat(colW)}┴${'─'.repeat(colW)}┴${'─'.repeat(colW)}┴${'─'.repeat(colW)}┴${'─'.repeat(colW)}┴${'─'.repeat(testColW)}┘${RESET}`;
  
  function sectionDivider(label) {
    const inner = nameWidth + 1 + colW * 5 + testColW + 6;
    const labelPadded = ` ${label} `;
    const leftLen = 2;
    const rightLen = inner - leftLen - labelPadded.length;
    return `${DIM}├${'─'.repeat(leftLen)}${RESET}${BOLD}${labelPadded}${RESET}${DIM}${'─'.repeat(Math.max(0, rightLen))}┤${RESET}`;
  }
  
  function checkCell(check, width) {
    if (check.total === 0 && !check.pass) return cell(BLOCKED, width);
    if (check.total === 0) return cell(SKIP, width);
    const label = `${check.passed}/${check.total}`;
    const lp = Math.floor((width - label.length) / 2);
    const rp = width - label.length - lp;
    const color = check.pass ? GREEN : check.passed === 0 ? RED : YELLOW;
    return ' '.repeat(lp) + `${color}${label}${RESET}` + ' '.repeat(rp);
  }
  
  function iconCell(check, width) {
    if (!check.pass) {
      const label = '0/1';
      const lp = Math.floor((width - label.length) / 2);
      const rp = width - label.length - lp;
      return ' '.repeat(lp) + `${RED}${label}${RESET}` + ' '.repeat(rp);
    }
    const label = check.format;
    const color = check.format === 'png' ? GREEN : YELLOW;
    const lp = Math.floor((width - label.length) / 2);
    const rp = width - label.length - lp;
    return ' '.repeat(lp) + `${color}${label}${RESET}` + ' '.repeat(rp);
  }
  
  function testCell(r, width) {
    if (r.tests.total === 0 && !r.tests.pass) return cell(BLOCKED, width);
    if (r.tests.total === 0) return cell(SKIP, width);
    const label = `${r.tests.tested}/${r.tests.total}`;
    const lp = Math.floor((width - label.length) / 2);
    const rp = width - label.length - lp;
    const color = r.tests.pass ? GREEN : r.tests.tested === 0 ? RED : YELLOW;
    return ' '.repeat(lp) + `${color}${label}${RESET}` + ' '.repeat(rp);
  }
  
  console.log();
  console.log(topBorder);
  console.log(headerLine);
  
  for (const section of sections) {
    if (section.results.length === 0) continue;
    console.log(sectionDivider(section.label));
    
    for (const r of section.results) {
      const allPass = r.schema.pass && r.entity.pass && r.mapping.pass && r.icon.pass && r.seed.pass && r.tests.pass;
      const critical = !r.schema.structureValid || !r.entity.pass;
      const nameColor = allPass ? GREEN : critical ? RED : YELLOW;
      
      const line = `${SEP} ${nameColor}${pad(r.name, nameWidth)}${RESET}${SEP}` +
        `${checkCell(r.schema, colW)}${SEP}` +
        `${checkCell(r.entity, colW)}${SEP}` +
        `${checkCell(r.mapping, colW)}${SEP}` +
        `${iconCell(r.icon, colW)}${SEP}` +
        `${checkCell(r.seed, colW)}${SEP}` +
        `${testCell(r, testColW)}${SEP}`;
      console.log(line);
    }
  }
  
  console.log(botBorder);
  
  for (const section of sections) {
    if (section.results.length === 0) continue;
    const total = section.results.length;
    const passing = section.results.filter(r => r.schema.pass && r.entity.pass && r.mapping.pass && r.icon.pass && r.seed.pass && r.tests.pass).length;
    const passColor = passing === total ? GREEN : passing > 0 ? YELLOW : RED;
    console.log(`  ${section.icon} ${passColor}${passing}/${total}${RESET} ${section.label}`);
  }
  console.log();
}

function renderErrors(results) {
  const failing = results.filter(r => !r.schema.pass || !r.entity.pass || !r.mapping.pass || !r.icon.pass || !r.seed.pass || !r.tests.pass);
  if (failing.length === 0) return;
  
  for (const r of failing) {
    const allErrors = [];
    if (!r.schema.pass)  allErrors.push(...r.schema.errors.map(e => `schema: ${e}`));
    if (!r.entity.pass)  allErrors.push(...r.entity.errors.map(e => `entity: ${e}`));
    if (!r.mapping.pass) allErrors.push(...r.mapping.errors.map(e => `mapping: ${e}`));
    if (!r.icon.pass)    allErrors.push(...r.icon.errors.map(e => `icon: ${e}`));
    if (!r.seed.pass)    allErrors.push(...r.seed.errors.map(e => `seed: ${e}`));
    if (!r.tests.pass)   allErrors.push(...r.tests.errors.map(e => `tests: ${e}`));
    
    if (allErrors.length > 0) {
      console.log(`  ❌ ${r.name}`);
      for (const err of allErrors) {
        console.log(`     ${err}`);
      }
    }
  }
  console.log();
}

// ============================================================================
// MAIN
// ============================================================================

function parseFrontmatter(content) {
  if (!content.startsWith('---')) return null;
  const endIndex = content.indexOf('\n---', 3);
  if (endIndex === -1) return null;
  return parseYaml(content.slice(4, endIndex));
}

function validateAdapter(adapter) {
  const readmePath = join(adapter.dir, 'readme.md');
  const content = readFileSync(readmePath, 'utf-8');
  const frontmatter = parseFrontmatter(content);
  
  if (!frontmatter) {
    return {
      name: adapter.name,
      schema: { pass: false, structureValid: false, passed: 0, total: 1, errors: ['No YAML frontmatter'] },
      entity: { pass: false, passed: 0, total: 0, errors: ['Cannot check — no frontmatter'] },
      mapping: { pass: false, passed: 0, total: 0, errors: ['Cannot check — no frontmatter'] },
      icon: checkIcon(adapter.dir),
      seed: { pass: false, passed: 0, total: 0, errors: ['Cannot check — no frontmatter'] },
      tests: { pass: false, errors: ['Cannot check — no frontmatter'], tested: 0, total: 0 },
    };
  }
  
  const schemaResult = checkSchema(frontmatter);
  const canCheck = schemaResult.structureValid;
  const entityResult = canCheck ? checkEntities(frontmatter) : { pass: false, passed: 0, total: 0, errors: ['Skipped — schema invalid'] };
  const mappingResult = canCheck ? checkMappings(frontmatter) : { pass: false, passed: 0, total: 0, errors: ['Skipped — schema invalid'] };
  const iconResult = checkIcon(adapter.dir);
  const seedResult = canCheck ? checkSeed(frontmatter) : { pass: false, passed: 0, total: 0, errors: ['Skipped — schema invalid'] };
  const testsResult = canCheck ? checkTests(adapter.dir, frontmatter) : { pass: false, errors: ['Skipped — schema invalid'], tested: 0, total: 0 };
  
  return {
    name: adapter.name,
    schema: schemaResult,
    entity: entityResult,
    mapping: mappingResult,
    icon: iconResult,
    seed: seedResult,
    tests: testsResult,
  };
}

// --- Pre-commit mode: quick structural check, no table, no move ---
if (preCommit) {
  const adapters = findAdapters(ADAPTERS_DIR);
  const filtered = filterValue ? adapters.filter(a => a.name.includes(filterValue)) : adapters;
  const results = filtered.map(a => validateAdapter(a));
  const failures = results.filter(r => !r.schema.structureValid || !r.entity.pass);
  if (failures.length > 0) {
    for (const r of failures) {
      const errs = [...r.schema.errors, ...r.entity.errors];
      console.error(`❌ ${r.name}: ${errs.join('; ')}`);
    }
    process.exit(1);
  }
  process.exit(0);
}

// --- Full validation ---

// 1. Discover
let activeAdapters = findAdapters(ADAPTERS_DIR);
let needsWorkAdapters = findAdapters(NEEDS_WORK_DIR);

if (filterValue) {
  activeAdapters = activeAdapters.filter(a => a.name.includes(filterValue) || a.path.includes(filterValue));
  needsWorkAdapters = needsWorkAdapters.filter(a => a.name.includes(filterValue) || a.path.includes(filterValue));
}

// 2. Validate
const activeResults = activeAdapters.map(a => ({ ...validateAdapter(a), _adapter: a }));
const needsWorkResults = needsWorkAdapters.map(a => ({ ...validateAdapter(a), _adapter: a }));

// Sort: passing first, then by name
const sortResults = (arr) => arr.sort((a, b) => {
  const aPass = a.schema.pass && a.entity.pass && a.mapping.pass && a.icon.pass && a.seed.pass && a.tests.pass;
  const bPass = b.schema.pass && b.entity.pass && b.mapping.pass && b.icon.pass && b.seed.pass && b.tests.pass;
  if (aPass !== bPass) return bPass - aPass;
  return a.name.localeCompare(b.name);
});
sortResults(activeResults);
sortResults(needsWorkResults);

// 3. Collect entity coverage (before moves)
const knownEntities = [...validEntityIds].sort();
const coveredEntities = new Set();
for (const result of activeResults) {
  try {
    const content = readFileSync(join(result._adapter.dir, 'readme.md'), 'utf-8');
    const fm = parseFrontmatter(content);
    if (fm?.operations) {
      for (const op of Object.values(fm.operations)) {
        if (op.returns && op.returns !== 'void') {
          coveredEntities.add(op.returns.replace(/\[\]$/, ''));
        }
      }
    }
  } catch {}
}

// 4. Render table
const sections = [
  { label: `Adapters (${activeResults.length})`, icon: '📦', results: activeResults },
];
if (needsWorkResults.length > 0) {
  sections.push({ label: `Needs Work (${needsWorkResults.length})`, icon: '🔧', results: needsWorkResults });
}
renderTable(sections);

// 5. Error details (always show for active adapters)
renderErrors(activeResults);
if (verbose) renderErrors(needsWorkResults);

// 6. Check for promotable .needs-work adapters
const promotable = needsWorkResults.filter(r =>
  r.schema.pass && r.entity.pass && r.mapping.pass && r.icon.pass && r.seed.pass && r.tests.pass
);
if (promotable.length > 0) {
  console.log(`  🎉 Ready to promote: ${promotable.map(r => r.name).join(', ')}\n`);
}

// 7. Summary
console.log(`📊 Entity coverage: ${coveredEntities.size}/${knownEntities.length} entity types have adapters`);
if (verbose) {
  const uncovered = knownEntities.filter(e => !coveredEntities.has(e));
  if (uncovered.length > 0) {
    console.log(`   Uncovered: ${uncovered.join(', ')}`);
  }
}
console.log();

const allPassing = activeResults.length > 0 && activeResults.every(r => r.schema.pass && r.entity.pass && r.mapping.pass && r.icon.pass && r.seed.pass && r.tests.pass);
if (allPassing) {
  console.log('✅ All adapters fully valid');
} else if (activeResults.length === 0) {
  console.log('📭 No adapters in adapters/');
} else {
  const passing = activeResults.filter(r => r.schema.pass && r.entity.pass && r.mapping.pass && r.icon.pass && r.seed.pass && r.tests.pass).length;
  console.log(`⚠️  ${passing}/${activeResults.length} adapters fully valid — fix errors and run again`);
}

// Exit with error if any active adapters have critical failures
const criticalFailures = activeResults.filter(r => !r.schema.structureValid || !r.entity.pass);
process.exit(criticalFailures.length > 0 ? 1 : 0);

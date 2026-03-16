#!/usr/bin/env node
/**
 * Skill validation — validate, report, enforce.
 * 
 * Checks per skill:
 *   1. Schema  — YAML frontmatter matches skill.schema.json
 *   2. Entity  — All operations return valid entity types
 *   3. Mapping — Adapter mappings use valid entity properties + jaq syntax
 *   4. Icon    — icon.svg or icon.png exists
 *   5. Tests   — Every operation has a test file
 * 
 * Skills in .needs-work/ are shown separately but never auto-moved.
 * Fix errors, then manually move to skills/ when ready.
 * 
 * Usage:
 *   node validate.mjs                     # Full validation of all skills
 *   node validate.mjs whatsapp linear     # Validate specific skills only
 *   node validate.mjs --filter exa        # Filter by substring
 *   node validate.mjs --verbose           # Show uncovered entities
 *   node validate.mjs --pre-commit whatsapp  # Structural YAML check only (used by git hook)
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse as parseYaml, parseAllDocuments } from 'yaml';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../../..');
const SKILLS_DIR = join(ROOT, 'skills');
const NEEDS_WORK_DIR = join(SKILLS_DIR, '.needs-work');
const SCHEMA_PATH = join(__dirname, '..', 'skill.schema.json');

// ============================================================================
// ARGS
// ============================================================================

const args = process.argv.slice(2);
const filterValue = args.includes('--filter') ? args[args.indexOf('--filter') + 1] : null;
const preCommit = args.includes('--pre-commit');
const verbose = args.includes('--verbose');

// Positional args (not flags, not --filter value) are skill names
const flagsWithValues = new Set(['--filter']);
const skillNames = [];
for (let i = 0; i < args.length; i++) {
  if (args[i].startsWith('--')) {
    if (flagsWithValues.has(args[i])) i++; // skip next arg (the value)
    continue;
  }
  skillNames.push(args[i]);
}

// ============================================================================
// LOAD SCHEMA + ENTITIES
// ============================================================================

const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf-8'));
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const validateSchema = ajv.compile(schema);

// Entity types now live in the database (seeded from seed.sql), not YAML files.
// Query the live server to get known types. If server is not running, skip entity checks.
async function loadEntityIdsFromServer() {
  const entityIds = new Set();
  try {
    const resp = await fetch('http://127.0.0.1:3456/mem/_types?limit=500');
    if (!resp.ok) return { ids: entityIds, available: false };
    const data = await resp.json();
    for (const entity of (data.data || [])) {
      // _type entities have their type id in data.id (the entity type slug)
      const typeId = entity.data?.id || entity.id;
      if (typeId && !entity.data?.is_relationship) entityIds.add(typeId);
    }
    return { ids: entityIds, available: true };
  } catch {
    return { ids: entityIds, available: false };
  }
}

async function loadEntityPropertiesFromServer() {
  const props = {};
  try {
    const resp = await fetch('http://127.0.0.1:3456/mem/_types?limit=500');
    if (!resp.ok) return props;
    const data = await resp.json();
    for (const entity of (data.data || [])) {
      const typeId = entity.data?.id || entity.id;
      if (typeId && entity.data?.properties && !entity.data?.is_relationship) {
        props[typeId] = Object.keys(entity.data.properties);
        // Inject system properties
        if (!props[typeId].includes('created_at')) props[typeId].push('created_at');
        if (!props[typeId].includes('updated_at')) props[typeId].push('updated_at');
      }
    }
  } catch {}
  return props;
}

// Load from server (async init, resolved before main runs)
let validEntityIds = new Set();
let entityProperties = {};
let entityServerAvailable = false;
const INLINE_PRIMITIVE_TYPES = new Set(['string', 'number', 'integer', 'boolean', 'object', 'array', 'null']);

async function initEntityData() {
  const result = await loadEntityIdsFromServer();
  validEntityIds = result.ids;
  entityServerAvailable = result.available;
  entityProperties = await loadEntityPropertiesFromServer();
}

function returnsEntity(op) {
  if (!op || typeof op.returns !== 'string') return false;
  if (op.returns === 'void') return false;
  const entityName = op.returns.replace(/\[\]$/, '');
  return !INLINE_PRIMITIVE_TYPES.has(entityName);
}

function returnsEntityArray(op) {
  return returnsEntity(op) && typeof op.returns === 'string' && op.returns.endsWith('[]');
}

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
  
  // Guide-only skills (auth: none, no operations) are exempt from the operations check
  const isGuideOnly = frontmatter.auth === 'none' && !frontmatter.operations;
  // Agent skills run an AI loop instead of a single API call — exempt from service-specific checks
  const isAgentSkill = !!frontmatter.agent;

  const checks = [
    { name: 'valid structure', pass: true },
    { name: 'website', pass: isAgentSkill || isGuideOnly || !!frontmatter.website },
    { name: 'color', pass: !!frontmatter.color },
    { name: 'auth', pass: isAgentSkill || isGuideOnly || frontmatter.auth !== undefined },
    { name: 'operations', pass: isAgentSkill || isGuideOnly || !!frontmatter.operations },
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
  
  // If the server isn't running, we can't validate entity refs — skip gracefully
  if (!entityServerAvailable && validEntityIds.size === 0) {
    return { pass: true, passed: 0, total: 0, errors: [] };
  }
  
  if (frontmatter.operations) {
    for (const [opName, op] of Object.entries(frontmatter.operations)) {
      if (!returnsEntity(op)) {
        continue;
      }
      total++;
      const entityName = op.returns.replace(/\[\]$/, '');
      if (validEntityIds.has(entityName)) {
        passed++;
      } else {
        errors.push(`'${opName}' returns unknown entity '${entityName}'`);
      }
      // entity[] ops: rest/graphql must have response.root or response.transform for top-level array
      if (returnsEntityArray(op) && (op.rest || op.graphql)) {
        const resp = op.rest?.response || op.graphql?.response;
        const hasArrayExtraction = resp?.root || resp?.transform;
        if (!hasArrayExtraction) {
          errors.push(`'${opName}' returns array — rest/graphql must have response.root or response.transform`);
        }
      }
    }
  }
  
  return { pass: errors.length === 0, passed, total, errors };
}

function getAdapters(frontmatter) {
  return frontmatter.adapters || null;
}

function getAdapterMapping(adapter) {
  if (!adapter || typeof adapter !== 'object') return null;
  // Flat structure: adapter body is the mapping
  return adapter;
}

function checkMappings(frontmatter) {
  const errors = [];
  let total = 0;
  let passed = 0;
  const adapters = getAdapters(frontmatter);
  const operations = Object.values(frontmatter.operations || {});
  const hasEntityOperations = operations.some(op => returnsEntity(op));
  
  if (!adapters) {
    if (hasEntityOperations) {
      errors.push('Has operations but no adapters section — data won\'t flow through entities');
      total = 1;
    }
    return { pass: errors.length === 0, passed, total, errors };
  }
  
  for (const [entityName, adapter] of Object.entries(adapters)) {
    const mapping = getAdapterMapping(adapter);
    if (adapter && typeof adapter === 'object' && 'mapping' in adapter) {
      total++;
      errors.push(
        `'${entityName}' uses legacy adapter 'mapping:' wrapper — move fields directly under adapters.${entityName}`
      );
      continue;
    }
    if (!mapping || Object.keys(mapping).length === 0) {
      total++;
      errors.push(`'${entityName}' adapter has no mapping fields`);
      continue;
    }
    
    // Reject _rel in typed references — relationship type comes from
    // the field name, not a metadata block. Rename the field to match
    // the relationship type (e.g., posted_in → upload).
    for (const [fieldName, fieldValue] of Object.entries(mapping)) {
      if (typeof fieldValue === 'object' && fieldValue !== null && '_rel' in fieldValue) {
        total++;
        errors.push(
          `'${entityName}.${fieldName}' has _rel — remove it. ` +
          `Rename the field to the relationship type (e.g., '${fieldName}' → the rel type), ` +
          `the system infers the rest from entity types`
        );
      }
    }
    
    const validProps = entityProperties[entityName];
    if (!validProps) continue;
    
    const RESERVED_ADAPTER_KEYS = new Set(['content', 'content_role']);
    for (const [propName, propValue] of Object.entries(mapping)) {
      if (propName.startsWith('_')) continue;
      if (RESERVED_ADAPTER_KEYS.has(propName)) continue;
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
  if (adapters) {
    for (const [entityName, adapter] of Object.entries(adapters)) {
      const mapping = getAdapterMapping(adapter);
      if (!mapping) continue;
      for (const { path, expr } of collectJaqExpressions(mapping, entityName)) {
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

function collectCoverageExemptions(content) {
  const exemptions = new Map();
  for (const line of content.split(/\r?\n/)) {
    const match = line.match(/coverage-exempt:\s*([a-z0-9_,\s]+?)(?:\s*-\s*(.+))?$/i);
    if (!match) continue;
    const tools = match[1]
      .split(',')
      .map(tool => tool.trim())
      .filter(Boolean);
    const reason = match[2]?.trim() || 'explicit exemption';
    for (const tool of tools) {
      exemptions.set(tool, reason);
    }
  }
  return exemptions;
}

function collectExecutedTools(content) {
  const testedTools = new Set();
  const invocationPatterns = [
    /\.call\(\s*['"]UseAdapter['"]\s*,\s*\{[\s\S]*?\btool:\s*['"]([^'"]+)['"][\s\S]*?\}\s*\)/g,
    /\.call\(\s*['"]run['"]\s*,\s*\{[\s\S]*?\btool:\s*['"]([^'"]+)['"][\s\S]*?\}\s*\)/g,
    /\.run\(\s*[^,]+,\s*['"]([^'"]+)['"]/g,
  ];

  for (const pattern of invocationPatterns) {
    for (const match of content.matchAll(pattern)) {
      testedTools.add(match[1]);
    }
  }

  return testedTools;
}

function checkTests(adapterDir, frontmatter) {
  const tools = [];
  if (frontmatter.operations) tools.push(...Object.keys(frontmatter.operations));
  
  if (tools.length === 0) return { pass: true, errors: [], tested: 0, total: 0 };
  
  const testsDir = join(adapterDir, 'tests');
  const testedTools = new Set();
  const exemptedTools = new Map();
  if (existsSync(testsDir)) {
    for (const file of readdirSync(testsDir).filter(f => f.endsWith('.test.ts'))) {
      const content = readFileSync(join(testsDir, file), 'utf-8');
      for (const [tool, reason] of collectCoverageExemptions(content)) {
        exemptedTools.set(tool, reason);
      }
      for (const tool of collectExecutedTools(content)) {
        testedTools.add(tool);
      }
    }
  }
  
  const missing = tools.filter(t => !testedTools.has(t) && !exemptedTools.has(t));
  const satisfied = new Set([
    ...[...testedTools].filter(tool => tools.includes(tool)),
    ...[...exemptedTools.keys()].filter(tool => tools.includes(tool)),
  ]);

  return {
    pass: missing.length === 0,
    errors: missing.length > 0 ? [`No executed test call found for: ${missing.join(', ')}`] : [],
    tested: satisfied.size,
    total: tools.length,
  };
}

// ============================================================================
// DISCOVER ADAPTERS
// ============================================================================

function findSkills(dir, relativePath = '') {
  const skills = [];
  if (!existsSync(dir)) return skills;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name === 'node_modules' || entry.name === 'tests') continue;
    if (entry.name.startsWith('.')) continue;
    const fullPath = join(dir, entry.name);
    const rel = relativePath ? `${relativePath}/${entry.name}` : entry.name;
    if (existsSync(join(fullPath, 'readme.md'))) {
      skills.push({ name: entry.name, path: rel, dir: fullPath });
    } else {
      skills.push(...findSkills(fullPath, rel));
    }
  }
  return skills;
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
  const headerLine = `${SEP} ${BOLD}${pad('Skill', nameWidth)}${RESET}${SEP}${DIM}${centerText('Schema', colW)}${RESET}${SEP}${DIM}${centerText('Entity', colW)}${RESET}${SEP}${DIM}${centerText('Mapping', colW)}${RESET}${SEP}${DIM}${centerText('Icon', colW)}${RESET}${SEP}${DIM}${centerText('Tests', testColW)}${RESET}${SEP}`;
  
  const topBorder  = `${DIM}┌${'─'.repeat(nameWidth + 1)}┬${'─'.repeat(colW)}┬${'─'.repeat(colW)}┬${'─'.repeat(colW)}┬${'─'.repeat(colW)}┬${'─'.repeat(testColW)}┐${RESET}`;
  const botBorder  = `${DIM}└${'─'.repeat(nameWidth + 1)}┴${'─'.repeat(colW)}┴${'─'.repeat(colW)}┴${'─'.repeat(colW)}┴${'─'.repeat(colW)}┴${'─'.repeat(testColW)}┘${RESET}`;
  
  function sectionDivider(label) {
    const inner = nameWidth + 1 + colW * 4 + testColW + 5;
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
      const allPass = r.schema.pass && r.entity.pass && r.mapping.pass && r.icon.pass && r.tests.pass;
      const critical = !r.schema.structureValid || !r.entity.pass;
      const nameColor = allPass ? GREEN : critical ? RED : YELLOW;
      
      const line = `${SEP} ${nameColor}${pad(r.name, nameWidth)}${RESET}${SEP}` +
        `${checkCell(r.schema, colW)}${SEP}` +
        `${checkCell(r.entity, colW)}${SEP}` +
        `${checkCell(r.mapping, colW)}${SEP}` +
        `${iconCell(r.icon, colW)}${SEP}` +
        `${testCell(r, testColW)}${SEP}`;
      console.log(line);
    }
  }
  
  console.log(botBorder);
  
  for (const section of sections) {
    if (section.results.length === 0) continue;
    const total = section.results.length;
    const passing = section.results.filter(r => r.schema.pass && r.entity.pass && r.mapping.pass && r.icon.pass && r.tests.pass).length;
    const passColor = passing === total ? GREEN : passing > 0 ? YELLOW : RED;
    console.log(`  ${section.icon} ${passColor}${passing}/${total}${RESET} ${section.label}`);
  }
  console.log();
}

function renderErrors(results) {
  const failing = results.filter(r => !r.schema.pass || !r.entity.pass || !r.mapping.pass || !r.icon.pass || !r.tests.pass);
  if (failing.length === 0) return;
  
  for (const r of failing) {
    const allErrors = [];
    if (!r.schema.pass)  allErrors.push(...r.schema.errors.map(e => `schema: ${e}`));
    if (!r.entity.pass)  allErrors.push(...r.entity.errors.map(e => `entity: ${e}`));
    if (!r.mapping.pass) allErrors.push(...r.mapping.errors.map(e => `mapping: ${e}`));
    if (!r.icon.pass)    allErrors.push(...r.icon.errors.map(e => `icon: ${e}`));
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

function validateSkill(skill) {
  const readmePath = join(skill.dir, 'readme.md');
  const content = readFileSync(readmePath, 'utf-8');
  const frontmatter = parseFrontmatter(content);
  
  if (!frontmatter) {
    return {
      name: skill.name,
      schema: { pass: false, structureValid: false, passed: 0, total: 1, errors: ['No YAML frontmatter'] },
      entity: { pass: false, passed: 0, total: 0, errors: ['Cannot check — no frontmatter'] },
      mapping: { pass: false, passed: 0, total: 0, errors: ['Cannot check — no frontmatter'] },
      icon: checkIcon(skill.dir),
      tests: { pass: false, errors: ['Cannot check — no frontmatter'], tested: 0, total: 0 },
    };
  }
  
  const schemaResult = checkSchema(frontmatter);
  const canCheck = schemaResult.structureValid;
  const entityResult = canCheck ? checkEntities(frontmatter) : { pass: false, passed: 0, total: 0, errors: ['Skipped — schema invalid'] };
  const mappingResult = canCheck ? checkMappings(frontmatter) : { pass: false, passed: 0, total: 0, errors: ['Skipped — schema invalid'] };
  const iconResult = checkIcon(skill.dir);
  const testsResult = canCheck ? checkTests(skill.dir, frontmatter) : { pass: false, errors: ['Skipped — schema invalid'], tested: 0, total: 0 };
  
  return {
    name: skill.name,
    schema: schemaResult,
    entity: entityResult,
    mapping: mappingResult,
    icon: iconResult,
    tests: testsResult,
  };
}

// Initialize entity data from server before running validation
await initEntityData();

// --- Pre-commit mode: structural YAML check only, scoped to named skills ---
if (preCommit) {
  const allSkills = findSkills(SKILLS_DIR);
  const filtered = skillNames.length > 0
    ? allSkills.filter(a => skillNames.includes(a.name))
    : filterValue
      ? allSkills.filter(a => a.name.includes(filterValue))
      : allSkills;

  if (filtered.length === 0) {
    process.exit(0);
  }

  const results = filtered.map(a => validateSkill(a));
  // Pre-commit only blocks on structural YAML validity — not entity refs, not test coverage
  const failures = results.filter(r => !r.schema.structureValid);
  if (failures.length > 0) {
    for (const r of failures) {
      console.error(`❌ ${r.name}: ${r.schema.errors.join('; ')}`);
    }
    process.exit(1);
  }
  console.log(`✅ structural pre-commit validation passed: ${filtered.map(r => r.name).join(', ')}`);
  process.exit(0);
}

// --- Full validation ---

// 1. Discover
let activeSkills = findSkills(SKILLS_DIR);
let needsWorkSkills = findSkills(NEEDS_WORK_DIR);

if (skillNames.length > 0) {
  activeSkills = activeSkills.filter(a => skillNames.includes(a.name));
  const matchedActive = new Set(activeSkills.map(a => a.name));
  needsWorkSkills = needsWorkSkills.filter(a => skillNames.includes(a.name) && !matchedActive.has(a.name));
} else if (filterValue) {
  activeSkills = activeSkills.filter(a => a.name.includes(filterValue) || a.path.includes(filterValue));
  needsWorkSkills = needsWorkSkills.filter(a => a.name.includes(filterValue) || a.path.includes(filterValue));
}

// 2. Validate
const activeResults = activeSkills.map(a => ({ ...validateSkill(a), _skill: a }));
const needsWorkResults = needsWorkSkills.map(a => ({ ...validateSkill(a), _skill: a }));

// Sort: passing first, then by name
const sortResults = (arr) => arr.sort((a, b) => {
  const aPass = a.schema.pass && a.entity.pass && a.mapping.pass && a.icon.pass && a.tests.pass;
  const bPass = b.schema.pass && b.entity.pass && b.mapping.pass && b.icon.pass && b.tests.pass;
  if (aPass !== bPass) return bPass - aPass;
  return a.name.localeCompare(b.name);
});
sortResults(activeResults);
sortResults(needsWorkResults);

// 3. Collect entity coverage (before moves)
const knownEntities = [...validEntityIds].filter(id => !['_type'].includes(id)).sort();
const coveredEntities = new Set();
for (const result of activeResults) {
  try {
    const content = readFileSync(join(result._skill.dir, 'readme.md'), 'utf-8');
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
  { label: `Skills (${activeResults.length})`, icon: '📦', results: activeResults },
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
  r.schema.pass && r.entity.pass && r.mapping.pass && r.icon.pass && r.tests.pass
);
if (promotable.length > 0) {
  console.log(`  🎉 Ready to promote: ${promotable.map(r => r.name).join(', ')}\n`);
}

// 7. Summary
console.log(`📊 Entity coverage: ${coveredEntities.size}/${knownEntities.length} entity types have skills`);
if (verbose) {
  const uncovered = knownEntities.filter(e => !coveredEntities.has(e));
  if (uncovered.length > 0) {
    console.log(`   Uncovered: ${uncovered.join(', ')}`);
  }
}
console.log();

const allPassing = activeResults.length > 0 && activeResults.every(r => r.schema.pass && r.entity.pass && r.mapping.pass && r.icon.pass && r.tests.pass);
if (allPassing) {
  console.log('✅ All skills fully valid');
} else if (activeResults.length === 0) {
  console.log('📭 No skills in skills/');
} else {
  const passing = activeResults.filter(r => r.schema.pass && r.entity.pass && r.mapping.pass && r.icon.pass && r.tests.pass).length;
  console.log(`⚠️  ${passing}/${activeResults.length} skills fully valid — fix errors and run again`);
}
console.log('ℹ️  `validate` checks structure, entity refs, mapping sanity, and observed test-call coverage. Use `npm run mcp:call` for live runtime proof and `npm run mcp:test` for broader smoke testing.');

// Exit with error if any active adapters have critical failures
const criticalFailures = activeResults.filter(r => !r.schema.structureValid || !r.entity.pass);
process.exit(criticalFailures.length > 0 ? 1 : 0);

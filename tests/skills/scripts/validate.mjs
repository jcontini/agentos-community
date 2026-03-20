#!/usr/bin/env node
/**
 * Skill validation — validate, report, enforce.
 * 
 * Checks per skill:
 *   1. Schema   — skill.yaml matches skill.schema.json
 *   2. Entity   — All operations return valid entity types
 *   3. Mapping  — Adapter mappings use valid entity properties + jaq syntax
 *   4. Semantic — Warns on structurally valid but logically wrong YAML:
 *        • connection with no auth fields (no runtime effect)
 *        • operation with no executor (rest/graphql/sql/command/python/etc.)
 *        • adapter defined but no operation returns that entity type
 *
 * (Skill image icons were removed; no icon file check.)
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
import { parse as parseYaml } from 'yaml';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../../..');
const SKILLS_DIR = join(ROOT, 'skills');
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
  const ajvErrors = valid ? [] : normalizeSchemaErrors(frontmatter, validateSchema.errors || []);
  
  if (!valid) {
    return {
      pass: false,
      structureValid: false,
      passed: 0,
      total: 1,
      errors: ajvErrors,
    };
  }
  
  const actions = frontmatter.actions && typeof frontmatter.actions === 'object'
    ? Object.keys(frontmatter.actions).length
    : 0;
  const hasActions = actions > 0;

  // Guide-only skills (no auth deps, no operations/actions) are exempt from the operations check
  const hasNoAuthDeps = frontmatter.auth === 'none' || (frontmatter.auth === undefined && (!frontmatter.connections || Object.keys(frontmatter.connections).length === 0));
  const isGuideOnly = hasNoAuthDeps && !frontmatter.operations && !hasActions;
  // Agent skills run an AI loop instead of a single API call — exempt from service-specific checks
  const isAgentSkill = !!frontmatter.agent;

  const checks = [
    { name: 'valid structure', pass: true },
    { name: 'tags', pass: frontmatter.tags === undefined },
    { name: 'website', pass: isAgentSkill || isGuideOnly || !!frontmatter.website },
    { name: 'color', pass: !!frontmatter.color },
    { name: 'auth', pass: isAgentSkill || isGuideOnly || frontmatter.auth !== undefined || frontmatter.connections !== undefined },
    {
      name: 'operations/actions/agent',
      pass: isAgentSkill || isGuideOnly || !!frontmatter.operations || hasActions,
    },
  ];

  const passed = checks.filter(c => c.pass).length;
  const total = checks.length;
  let errors = checks.filter(c => !c.pass).map(c => `Missing: ${c.name}`);

  // Connections vs auth: mutual exclusion and operation.connection consistency
  const connectionErrors = checkConnections(frontmatter);
  if (connectionErrors.length > 0) {
    errors = errors.concat(connectionErrors);
  }

  return { pass: passed === total && connectionErrors.length === 0, structureValid: errors.length === 0, passed, total, errors };
}

/** True when this executor block needs an effective connection (base_url or sqlite path). */
function sqlBlockNeedsConnection(sql) {
  if (!sql || typeof sql !== 'object') return false;
  const d = sql.database;
  return d === undefined || d === null || d === '';
}

/** True if a pipeline step uses rest/graphql/sql in a way that resolves via skill.connections. */
function stepNeedsConnection(step) {
  if (!step || typeof step !== 'object') return false;
  if (step.rest || step.graphql) return true;
  if (step.sql) return sqlBlockNeedsConnection(step.sql);
  return false;
}

/**
 * Operations that only use command/python/keychain/etc. do not need connection: even when
 * the skill declares multiple connections (e.g. history vs cookies_db). Require connection
 * when rest/graphql/sql at top level or in steps would use connection.base_url / connection.sqlite.
 */
function operationNeedsExplicitConnection(op) {
  if (!op || typeof op !== 'object') return false;
  if (op.rest || op.graphql) return true;
  if (op.sql) return sqlBlockNeedsConnection(op.sql);
  if (Array.isArray(op.steps)) {
    for (const step of op.steps) {
      if (stepNeedsConnection(step)) return true;
    }
  }
  return false;
}

function checkConnections(frontmatter) {
  const errors = [];
  const hasAuth = frontmatter.auth !== undefined && frontmatter.auth !== null && frontmatter.auth !== 'none';
  const hasConnections = frontmatter.connections && typeof frontmatter.connections === 'object' && Object.keys(frontmatter.connections).length > 0;

  if (hasAuth && hasConnections) {
    errors.push('Skill cannot have both auth: and connections: — use one model or the other');
  }

  if (hasConnections) {
    const connNames = new Set(Object.keys(frontmatter.connections));
    const singleConnection = connNames.size === 1;
    const ops = frontmatter.operations || {};
    for (const [opName, op] of Object.entries(ops)) {
      if (!op || typeof op !== 'object') continue;
      const conn = op.connection;
      const connList =
        conn === undefined || conn === null || conn === ''
          ? []
          : Array.isArray(conn)
            ? conn.map((c) => String(c))
            : [String(conn)];
      if (connList.length === 0) {
        // Auto-inference: when exactly one connection is declared, operations
        // can omit connection: and the runtime infers the sole connection.
        if (!singleConnection && operationNeedsExplicitConnection(op)) {
          errors.push(`'${opName}' must specify connection: when skill has multiple connections (available: ${[...connNames].join(', ')})`);
        }
      } else {
        for (const c of connList) {
          if (!connNames.has(c)) {
            errors.push(`'${opName}' references connection '${c}' which is not in connections: (available: ${[...connNames].join(', ')})`);
          }
        }
      }
    }
  }

  if (hasAuth && !hasConnections) {
    const ops = frontmatter.operations || {};
    for (const [opName, op] of Object.entries(ops)) {
      const hasConn =
        op &&
        typeof op === 'object' &&
        op.connection !== undefined &&
        op.connection !== null &&
        op.connection !== '' &&
        !(Array.isArray(op.connection) && op.connection.length === 0);
      if (hasConn) {
        errors.push(`'${opName}' has connection: but skill uses auth: — use connections: for multi-connection skills`);
      }
    }
  }

  return errors;
}

function findLegacyAdapterMappingWrappers(frontmatter) {
  const adapters = frontmatter?.adapters;
  if (!adapters || typeof adapters !== 'object') return [];
  return Object.entries(adapters)
    .filter(([, adapter]) => adapter && typeof adapter === 'object' && 'mapping' in adapter)
    .map(([entityName]) => entityName);
}

function normalizeSchemaErrors(frontmatter, schemaErrors) {
  const legacyWrappers = findLegacyAdapterMappingWrappers(frontmatter);
  const wrapperBases = legacyWrappers.map(entityName => `/adapters/${entityName}/mapping`);

  const filteredErrors = schemaErrors.filter(error => {
    const instancePath = error.instancePath || '/';
    return !wrapperBases.some(base => instancePath === base || instancePath.startsWith(`${base}/`));
  });

  const normalized = filteredErrors.map(error => `${error.instancePath || '/'}: ${error.message}`);
  for (const entityName of legacyWrappers) {
    normalized.push(
      `/adapters/${entityName}: legacy adapter 'mapping:' wrapper — move fields directly under adapters.${entityName}`
    );
  }

  return [...new Set(normalized)];
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

// ============================================================================
// SEMANTIC CHECKS — structurally valid YAML that is logically wrong or useless
// ============================================================================

const AUTH_FIELDS = new Set(['header', 'query', 'body', 'cookies', 'oauth']);
const EXECUTOR_FIELDS = new Set(['rest', 'graphql', 'sql', 'command', 'swift', 'csv', 'keychain', 'crypto', 'steps', 'python', 'applescript', 'graph', 'plist', 'download']);

function checkSemantics(frontmatter) {
  const warnings = [];
  const ops = frontmatter.operations || {};
  const adapters = frontmatter.adapters || {};
  const connections = frontmatter.connections || {};
  const isAgentSkill = !!frontmatter.agent;

  // 1. Connections are a service permission manifest. Auth-less connections are valid:
  //    they may provide base_url for URL resolution, declare runtime dependencies,
  //    or represent services where auth is handled internally (e.g., runtime-discovered APIs).
  //    No warning needed for connections without explicit auth fields.

  // 2. Operation has no executor — will fail at runtime
  if (!isAgentSkill) {
    for (const [opName, op] of Object.entries(ops)) {
      if (!op || typeof op !== 'object') continue;
      const hasExecutor = [...EXECUTOR_FIELDS].some(f => op[f] !== undefined && op[f] !== null);
      if (!hasExecutor) {
        warnings.push(`'${opName}' has no executor (rest, graphql, sql, command, python, etc.) — will fail at runtime`);
      }
    }
  }

  // 3. Adapter defined but no operation returns that entity type
  if (Object.keys(adapters).length > 0 && Object.keys(ops).length > 0) {
    const returnedTypes = new Set();
    for (const op of Object.values(ops)) {
      if (op && typeof op.returns === 'string' && op.returns !== 'void') {
        returnedTypes.add(op.returns.replace(/\[\]$/, ''));
      }
    }
    for (const entityName of Object.keys(adapters)) {
      if (!returnedTypes.has(entityName)) {
        warnings.push(`adapter '${entityName}' is defined but no operation returns '${entityName}' — unused adapter`);
      }
    }
  }

  return warnings;
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
    if (existsSync(join(fullPath, 'skill.yaml'))) {
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
  
  function centerText(text, width) {
    const lp = Math.floor((width - text.length) / 2);
    const rp = width - text.length - lp;
    return ' '.repeat(lp) + text + ' '.repeat(rp);
  }
  
  const semW = 10;
  const SEP = `${DIM}│${RESET}`;
  const headerLine = `${SEP} ${BOLD}${pad('Skill', nameWidth)}${RESET}${SEP}${DIM}${centerText('Schema', colW)}${RESET}${SEP}${DIM}${centerText('Entity', colW)}${RESET}${SEP}${DIM}${centerText('Mapping', colW)}${RESET}${SEP}${DIM}${centerText('Semantic', semW)}${RESET}${SEP}`;
  
  const topBorder  = `${DIM}┌${'─'.repeat(nameWidth + 1)}┬${'─'.repeat(colW)}┬${'─'.repeat(colW)}┬${'─'.repeat(colW)}┬${'─'.repeat(semW)}┐${RESET}`;
  const botBorder  = `${DIM}└${'─'.repeat(nameWidth + 1)}┴${'─'.repeat(colW)}┴${'─'.repeat(colW)}┴${'─'.repeat(colW)}┴${'─'.repeat(semW)}┘${RESET}`;
  
  function sectionDivider(label) {
    const inner = nameWidth + 1 + colW * 3 + semW + 4;
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
  
  console.log();
  console.log(topBorder);
  console.log(headerLine);
  
  for (const section of sections) {
    if (section.results.length === 0) continue;
    console.log(sectionDivider(section.label));
    
    for (const r of section.results) {
      const warnCount = (r.semanticWarnings || []).length;
      const allPass = r.schema.pass && r.entity.pass && r.mapping.pass;
      const critical = !r.schema.structureValid || !r.entity.pass;
      const nameColor = allPass && warnCount === 0 ? GREEN : allPass && warnCount > 0 ? YELLOW : critical ? RED : YELLOW;
      
      let semCell;
      if (warnCount === 0) {
        semCell = cell(`${GREEN}ok${RESET}`, semW);
      } else {
        const label = `${warnCount} warn`;
        const lp = Math.floor((semW - label.length) / 2);
        const rp = semW - label.length - lp;
        semCell = ' '.repeat(lp) + `${YELLOW}${label}${RESET}` + ' '.repeat(rp);
      }

      const line = `${SEP} ${nameColor}${pad(r.name, nameWidth)}${RESET}${SEP}` +
        `${checkCell(r.schema, colW)}${SEP}` +
        `${checkCell(r.entity, colW)}${SEP}` +
        `${checkCell(r.mapping, colW)}${SEP}` +
        `${semCell}${SEP}`;
      console.log(line);
    }
  }
  
  console.log(botBorder);
  
  for (const section of sections) {
    if (section.results.length === 0) continue;
    const total = section.results.length;
    const passing = section.results.filter(r => r.schema.pass && r.entity.pass && r.mapping.pass).length;
    const passColor = passing === total ? GREEN : passing > 0 ? YELLOW : RED;
    console.log(`  ${section.icon} ${passColor}${passing}/${total}${RESET} ${section.label}`);
  }
  console.log();
}

function renderErrors(results) {
  const failing = results.filter(r => !r.schema.pass || !r.entity.pass || !r.mapping.pass);
  if (failing.length > 0) {
    for (const r of failing) {
      const allErrors = [];
      if (!r.schema.pass)  allErrors.push(...r.schema.errors.map(e => `schema: ${e}`));
      if (!r.entity.pass)  allErrors.push(...r.entity.errors.map(e => `entity: ${e}`));
      if (!r.mapping.pass) allErrors.push(...r.mapping.errors.map(e => `mapping: ${e}`));
      
      if (allErrors.length > 0) {
        console.log(`  ❌ ${r.name}`);
        for (const err of allErrors) {
          console.log(`     ${err}`);
        }
      }
    }
    console.log();
  }

  const withWarnings = results.filter(r => (r.semanticWarnings || []).length > 0);
  if (withWarnings.length > 0) {
    for (const r of withWarnings) {
      console.log(`  ⚠️  ${r.name}`);
      for (const w of r.semanticWarnings) {
        console.log(`     ${YELLOW}warning:${RESET} ${w}`);
      }
    }
    console.log();
  }
}

// ============================================================================
// MAIN
// ============================================================================

function loadSkillManifest(skillDir) {
  const yamlPath = join(skillDir, 'skill.yaml');
  if (!existsSync(yamlPath)) return null;
  try {
    return parseYaml(readFileSync(yamlPath, 'utf-8'));
  } catch {
    return null;
  }
}

function validateSkill(skill) {
  const frontmatter = loadSkillManifest(skill.dir);

  if (!frontmatter) {
    return {
      name: skill.name,
      schema: { pass: false, structureValid: false, passed: 0, total: 1, errors: ['Missing or invalid skill.yaml'] },
      entity: { pass: false, passed: 0, total: 0, errors: ['Cannot check — no manifest'] },
      mapping: { pass: false, passed: 0, total: 0, errors: ['Cannot check — no manifest'] },
    };
  }
  
  const schemaResult = checkSchema(frontmatter);
  const canCheck = schemaResult.structureValid;
  const entityResult = canCheck ? checkEntities(frontmatter) : { pass: false, passed: 0, total: 0, errors: ['Skipped — schema invalid'] };
  const mappingResult = canCheck ? checkMappings(frontmatter) : { pass: false, passed: 0, total: 0, errors: ['Skipped — schema invalid'] };
  const semanticWarnings = canCheck ? checkSemantics(frontmatter) : [];
  
  return {
    name: skill.name,
    schema: schemaResult,
    entity: entityResult,
    mapping: mappingResult,
    semanticWarnings,
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

  const failures = results.filter(r => !r.schema.structureValid);
  if (failures.length > 0) {
    for (const r of failures) {
      console.error(`❌ ${r.name}: ${r.schema.errors.join('; ')}`);
    }
    process.exit(1);
  }

  const withWarnings = results.filter(r => (r.semanticWarnings || []).length > 0);
  if (withWarnings.length > 0) {
    for (const r of withWarnings) {
      for (const w of r.semanticWarnings) {
        console.error(`❌ ${r.name}: ${w}`);
      }
    }
    process.exit(1);
  }

  console.log(`✅ pre-commit validation passed: ${filtered.map(r => r.name).join(', ')}`);
  process.exit(0);
}

// --- Full validation ---

// 1. Discover
let activeSkills = findSkills(SKILLS_DIR);

if (skillNames.length > 0) {
  activeSkills = activeSkills.filter(a => skillNames.includes(a.name));
} else if (filterValue) {
  activeSkills = activeSkills.filter(a => a.name.includes(filterValue) || a.path.includes(filterValue));
}

// 2. Validate
const activeResults = activeSkills.map(a => ({ ...validateSkill(a), _skill: a }));

// Sort: passing first, then by name
const sortResults = (arr) => arr.sort((a, b) => {
  const aPass = a.schema.pass && a.entity.pass && a.mapping.pass;
  const bPass = b.schema.pass && b.entity.pass && b.mapping.pass;
  if (aPass !== bPass) return bPass - aPass;
  return a.name.localeCompare(b.name);
});
sortResults(activeResults);

// 3. Collect entity coverage (before moves)
const knownEntities = [...validEntityIds].filter(id => !['_type'].includes(id)).sort();
const coveredEntities = new Set();
for (const result of activeResults) {
  try {
    const fm = loadSkillManifest(result._skill.dir);
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
renderTable(sections);

// 5. Error details
renderErrors(activeResults);

// 6. Summary
console.log(`📊 Entity coverage: ${coveredEntities.size}/${knownEntities.length} entity types have skills`);
if (verbose) {
  const uncovered = knownEntities.filter(e => !coveredEntities.has(e));
  if (uncovered.length > 0) {
    console.log(`   Uncovered: ${uncovered.join(', ')}`);
  }
}
console.log();

const allPassing = activeResults.length > 0 && activeResults.every(r => r.schema.pass && r.entity.pass && r.mapping.pass);
if (allPassing) {
  console.log('✅ All skills fully valid');
} else if (activeResults.length === 0) {
  console.log('📭 No skills in skills/');
} else {
  const passing = activeResults.filter(r => r.schema.pass && r.entity.pass && r.mapping.pass).length;
  console.log(`⚠️  ${passing}/${activeResults.length} skills fully valid — fix errors and run again`);
}
console.log('ℹ️  `validate` checks structure, entity refs, and mapping sanity. Use `npm run mcp:call` for live runtime proof and `npm run mcp:test` for broader smoke testing.');

// Exit with error if any active adapters have critical failures
const criticalFailures = activeResults.filter(r => !r.schema.structureValid || !r.entity.pass);
process.exit(criticalFailures.length > 0 ? 1 : 0);

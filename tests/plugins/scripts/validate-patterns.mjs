#!/usr/bin/env node
/**
 * Pattern validation for adapter best practices.
 * 
 * This complements validate.mjs (schema + test coverage) with higher-level checks:
 * 
 * 1. TYPED REFERENCES — Adapters should create relationships, not just flat data
 *    - post adapter should have author → person typed reference
 *    - message adapter should have from → person typed reference
 *    - conversation adapter should have participant → person typed reference
 * 
 * 2. DISPLAY FIELDS — Typed refs don't replace display fields
 *    - If you have posted_by: person, you still need author.name for views
 *    - Denormalization is intentional — entities need flat fields for display
 * 
 * 3. EXPRESSION PATTERNS — All mapping expressions reference raw API data
 *    - Typed references use raw paths (e.g., .data.author)
 *    - Not references to other mapped fields
 * 
 * Usage:
 *   node scripts/validate-patterns.mjs                  # Check all plugins
 *   node scripts/validate-patterns.mjs --filter reddit  # Check specific plugin
 *   node scripts/validate-patterns.mjs --strict         # Fail on warnings too
 * 
 * Exit codes:
 *   0 — All checks pass
 *   1 — Errors found (missing required patterns)
 *   2 — Warnings only (suggestions for improvement)
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse as parseYaml } from 'yaml';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../../..');
const PLUGINS_DIR = join(ROOT, 'plugins');
const SKILLS_DIR = join(ROOT, 'skills');

// ============================================================================
// PATTERN RULES
// ============================================================================

/**
 * Expected typed references by entity type.
 * Key: entity type in adapter
 * Value: array of { field, targetEntity, reason }
 */
const EXPECTED_TYPED_REFS = {
  post: [
    { field: 'posted_by', targetEntity: 'person', reason: 'Posts have authors' },
  ],
  message: [
    { field: 'from', targetEntity: 'person', reason: 'Messages have senders' },
  ],
  conversation: [
    { field: 'participant', targetEntity: 'person', reason: 'Conversations have participants' },
  ],
  comment: [
    { field: 'posted_by', targetEntity: 'person', reason: 'Comments have authors' },
  ],
  video: [
    { field: 'creator', targetEntity: 'person', reason: 'Videos have creators' },
  ],
  task: [
    { field: 'assignee', targetEntity: 'person', reason: 'Tasks can have assignees', optional: true },
  ],
  event: [
    { field: 'attendee', targetEntity: 'person', reason: 'Events have attendees', optional: true },
  ],
};

/**
 * Expected display fields when a typed reference exists.
 * If you have posted_by: person, you should also have these display fields.
 * 
 * Note: Message entities use flat 'sender' field (not nested), so 'from'
 * typed refs don't need extra display fields — the 'sender' mapping suffices.
 */
const EXPECTED_DISPLAY_FIELDS = {
  posted_by: ['author.name', 'author.url'],
  created_by: ['creator.name', 'creator.url'],
  from: [], // message.sender is flat string, not nested object
  creator: ['creator.name', 'creator.url'],
  assignee: ['assignee.name'],
  participant: [], // participants are arrays, handled differently
  attendee: [], // attendees are arrays, handled differently
};

// ============================================================================
// HELPERS
// ============================================================================

function parseFrontmatter(content) {
  if (!content.startsWith('---')) return null;
  const endIndex = content.indexOf('\n---', 3);
  if (endIndex === -1) return null;
  const yaml = content.slice(4, endIndex);
  return parseYaml(yaml);
}

function findPlugins(dir, relativePath = '') {
  const plugins = [];
  const entries = readdirSync(dir, { withFileTypes: true });
  
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (entry.name === '.needs-work') continue;
    if (entry.name === 'node_modules') continue;
    if (entry.name === 'tests') continue;
    
    const fullPath = join(dir, entry.name);
    const entryRelativePath = relativePath ? `${relativePath}/${entry.name}` : entry.name;
    
    if (existsSync(join(fullPath, 'readme.md'))) {
      plugins.push({ name: entry.name, path: entryRelativePath, dir: fullPath });
    } else {
      plugins.push(...findPlugins(fullPath, entryRelativePath));
    }
  }
  
  return plugins;
}

/**
 * Check if a value is a typed reference structure.
 * Typed refs look like: { person: { id: ".data.author", name: ".data.author" } }
 */
function isTypedReference(value) {
  if (typeof value !== 'object' || value === null) return false;
  if (Array.isArray(value)) return false;
  
  const keys = Object.keys(value);
  if (keys.length !== 1) return false;
  
  const inner = value[keys[0]];
  if (typeof inner !== 'object' || inner === null) return false;
  
  // Inner object should have identity fields (id, name, phone, email, etc.)
  const innerKeys = Object.keys(inner);
  const identityFields = ['id', 'name', 'phone', 'email', 'username'];
  return innerKeys.some(k => identityFields.includes(k));
}

/**
 * Get the entity type from a typed reference.
 */
function getTypedRefEntityType(value) {
  if (!isTypedReference(value)) return null;
  return Object.keys(value)[0];
}

// ============================================================================
// VALIDATORS
// ============================================================================

function validateAdapter(pluginPath, entityType, adapter) {
  const errors = [];
  const warnings = [];
  const info = [];
  
  const mapping = adapter.mapping || {};
  const mappingKeys = Object.keys(mapping);
  
  // Find existing typed references
  const existingTypedRefs = {};
  for (const [field, value] of Object.entries(mapping)) {
    if (isTypedReference(value)) {
      existingTypedRefs[field] = getTypedRefEntityType(value);
    }
  }
  
  // Check for expected typed references
  const expectedRefs = EXPECTED_TYPED_REFS[entityType] || [];
  for (const expected of expectedRefs) {
    const hasRef = Object.keys(existingTypedRefs).some(field => 
      existingTypedRefs[field] === expected.targetEntity
    );
    
    if (!hasRef) {
      const msg = `Missing typed reference: ${expected.field} → ${expected.targetEntity} (${expected.reason})`;
      if (expected.optional) {
        warnings.push(msg);
      } else {
        errors.push(msg);
      }
    }
  }
  
  // Check for display fields when typed refs exist
  for (const [refField, refEntityType] of Object.entries(existingTypedRefs)) {
    const expectedFields = EXPECTED_DISPLAY_FIELDS[refField] || [];
    const missingDisplayFields = expectedFields.filter(field => !mappingKeys.includes(field));
    
    if (missingDisplayFields.length > 0) {
      warnings.push(
        `Typed ref '${refField}' exists but missing display fields: ${missingDisplayFields.join(', ')}`
      );
    } else if (expectedFields.length > 0) {
      info.push(`✓ ${refField} → ${refEntityType} with display fields`);
    }
  }
  
  // Report found typed refs
  if (Object.keys(existingTypedRefs).length > 0) {
    for (const [field, entityType] of Object.entries(existingTypedRefs)) {
      if (!info.some(i => i.includes(field))) {
        info.push(`✓ ${field} → ${entityType}`);
      }
    }
  }
  
  return { errors, warnings, info };
}

// ============================================================================
// MAIN
// ============================================================================

const args = process.argv.slice(2);
const filterValue = args.includes('--filter') 
  ? args[args.indexOf('--filter') + 1] 
  : null;
const strictMode = args.includes('--strict');
const verbose = args.includes('--verbose');

let plugins = findPlugins(PLUGINS_DIR);

if (filterValue) {
  plugins = plugins.filter(p => p.name.includes(filterValue) || p.path.includes(filterValue));
}

console.log('🔍 Pattern validation for adapter best practices\n');

let totalErrors = 0;
let totalWarnings = 0;
let pluginsWithTypedRefs = 0;

for (const plugin of plugins) {
  const readmePath = join(plugin.dir, 'readme.md');
  const content = readFileSync(readmePath, 'utf-8');
  const frontmatter = parseFrontmatter(content);
  
  if (!frontmatter || !frontmatter.adapters) continue;
  
  let pluginHasIssues = false;
  let pluginHasTypedRefs = false;
  const pluginResults = [];
  
  for (const [entityType, adapter] of Object.entries(frontmatter.adapters)) {
    const result = validateAdapter(plugin.path, entityType, adapter);
    
    if (result.info.length > 0) {
      pluginHasTypedRefs = true;
    }
    
    if (result.errors.length > 0 || result.warnings.length > 0) {
      pluginHasIssues = true;
      pluginResults.push({ entityType, ...result });
    } else if (verbose && result.info.length > 0) {
      pluginResults.push({ entityType, ...result });
    }
    
    totalErrors += result.errors.length;
    totalWarnings += result.warnings.length;
  }
  
  if (pluginHasTypedRefs) {
    pluginsWithTypedRefs++;
  }
  
  // Print results for this plugin
  if (pluginHasIssues || (verbose && pluginResults.length > 0)) {
    const icon = pluginResults.some(r => r.errors.length > 0) ? '❌' : 
                 pluginResults.some(r => r.warnings.length > 0) ? '⚠️' : '✓';
    console.log(`${icon} plugins/${plugin.path}`);
    
    for (const result of pluginResults) {
      for (const err of result.errors) {
        console.log(`   ❌ ${result.entityType}: ${err}`);
      }
      for (const warn of result.warnings) {
        console.log(`   ⚠️  ${result.entityType}: ${warn}`);
      }
      if (verbose) {
        for (const info of result.info) {
          console.log(`   ${info}`);
        }
      }
    }
    console.log();
  }
}

// Summary
console.log('─'.repeat(60));
console.log(`Checked ${plugins.length} plugins`);
console.log(`${pluginsWithTypedRefs} plugins have typed references`);

if (totalErrors > 0) {
  console.log(`\n❌ ${totalErrors} error(s) — missing required patterns`);
}
if (totalWarnings > 0) {
  console.log(`⚠️  ${totalWarnings} warning(s) — suggestions for improvement`);
}

if (totalErrors === 0 && totalWarnings === 0) {
  console.log('\n✅ All patterns valid');
}

// Exit code
if (totalErrors > 0) {
  process.exit(1);
} else if (strictMode && totalWarnings > 0) {
  process.exit(2);
} else {
  process.exit(0);
}

#!/usr/bin/env node
/**
 * Plugin validation for pre-commit hook.
 * 
 * Checks:
 * 1. Schema validation - YAML frontmatter matches plugin.schema.json
 * 2. Test coverage - every operation/utility has a test
 * 
 * Usage: node scripts/validate-schema.mjs [app1] [app2] ...
 *        node scripts/validate-schema.mjs --all
 *        node scripts/validate-schema.mjs --all --filter exa
 *        node scripts/validate-schema.mjs --all --no-move  (skip auto-move, for pre-commit)
 */

import { readFileSync, readdirSync, existsSync, renameSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse as parseYaml, parseAllDocuments } from 'yaml';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../../..');  // tests/plugins/scripts/ -> root
const APPS_DIR = join(ROOT, 'plugins');
const ENTITIES_DIR = join(ROOT, 'entities');
const NEEDS_WORK_DIR = join(APPS_DIR, '.needs-work');
const SCHEMA_PATH = join(__dirname, '..', 'plugin.schema.json');

// Load schema
const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf-8'));
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);

// Load all entity IDs from skills/ folder
// Skills structure: skills/{skill}/{entity}.yaml (e.g., skills/messaging/message.yaml)
function loadEntityIds() {
  const entityIds = new Set();
  
  function scanDir(dir) {
    if (!existsSync(dir)) return;
    const entries = readdirSync(dir, { withFileTypes: true });
    
    for (const entry of entries) {
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory() && !entry.name.startsWith('.') && entry.name !== 'views') {
        scanDir(fullPath);
      } else if (entry.name.endsWith('.yaml') && entry.name !== 'icon.yaml') {
        try {
          const content = readFileSync(fullPath, 'utf-8');
          // Support multi-document YAML files (e.g., skills/common/base.yaml)
          const docs = parseAllDocuments(content);
          for (const doc of docs) {
            const data = doc.toJSON();
            if (data && data.id) {
              entityIds.add(data.id);
            }
          }
        } catch (err) {
          console.warn(`Warning: Failed to parse ${fullPath}: ${err.message}`);
        }
      }
    }
  }
  
  scanDir(ENTITIES_DIR);
  return entityIds;
}

const validEntityIds = loadEntityIds();

// Load entity properties for adapter validation
function loadEntityProperties() {
  const entityProps = {};
  
  function scanDir(dir) {
    if (!existsSync(dir)) return;
    const entries = readdirSync(dir, { withFileTypes: true });
    
    for (const entry of entries) {
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory() && !entry.name.startsWith('.') && entry.name !== 'views') {
        scanDir(fullPath);
      } else if (entry.name.endsWith('.yaml') && entry.name !== 'icon.yaml') {
        try {
          const content = readFileSync(fullPath, 'utf-8');
          // Support multi-document YAML files
          const docs = parseAllDocuments(content);
          for (const doc of docs) {
            const data = doc.toJSON();
            if (data && data.id && data.properties) {
              entityProps[data.id] = Object.keys(data.properties);
            }
          }
        } catch (err) {
          // Skip parse errors
        }
      }
    }
  }
  
  scanDir(ENTITIES_DIR);
  return entityProps;
}

const entityProperties = loadEntityProperties();

// Show loaded entities (only in verbose mode)
if (process.argv.includes('--verbose')) {
  console.log(`📦 Loaded ${validEntityIds.size} entities: ${[...validEntityIds].sort().join(', ')}\n`);
}

// Validate that returns references valid entities
function validateReturns(frontmatter) {
  const errors = [];
  
  // Check operations
  if (frontmatter.operations) {
    for (const [opName, op] of Object.entries(frontmatter.operations)) {
      if (typeof op.returns === 'string' && op.returns !== 'void') {
        const entityName = op.returns.replace(/\[\]$/, '');
        if (!validEntityIds.has(entityName)) {
          errors.push(`Operation '${opName}' returns unknown entity '${entityName}'`);
        }
      }
    }
  }
  
  // Check utilities
  if (frontmatter.utilities) {
    for (const [utilName, util] of Object.entries(frontmatter.utilities)) {
      if (typeof util.returns === 'string' && util.returns !== 'void') {
        const entityName = util.returns.replace(/\[\]$/, '');
        if (!validEntityIds.has(entityName)) {
          errors.push(`Utility '${utilName}' returns unknown entity '${entityName}'`);
        }
      }
    }
  }
  
  if (errors.length > 0) {
    errors.push(`Valid entities: ${[...validEntityIds].sort().join(', ')}`);
  }
  
  return errors;
}

// Validate adapter mappings reference valid entity properties
function validateAdapterMappings(frontmatter) {
  const errors = [];
  
  if (!frontmatter.adapters) return errors;
  
  for (const [entityName, adapter] of Object.entries(frontmatter.adapters)) {
    if (!adapter.mapping) continue;
    
    const validProps = entityProperties[entityName];
    if (!validProps) {
      // Entity not found - already caught by returns validation
      continue;
    }
    
    for (const [propName, propValue] of Object.entries(adapter.mapping)) {
      // Skip internal properties (prefixed with _)
      if (propName.startsWith('_')) continue;
      
      // Skip typed references (objects that create relationships, not properties)
      // Typed references have structure: { entity_type: { identity_field: "jaq expr" } }
      if (typeof propValue === 'object' && propValue !== null) continue;
      
      // For nested props like "author.name", check the top-level "author" exists
      const topLevelProp = propName.split('.')[0];
      
      if (!validProps.includes(topLevelProp)) {
        errors.push(`Adapter '${entityName}' maps unknown property '${topLevelProp}'. Valid: ${validProps.join(', ')}`);
      }
    }
  }
  
  return errors;
}

// Validate jaq expression syntax in adapter mappings
//
// Catches common jaq mistakes:
// 1. Single-quoted strings — jaq only supports double quotes
// 2. C-style ternary (? :) — jaq uses if/then/else/end
// 3. Bare [] on nullable paths — .foo.nodes[].id crashes when .foo is null
function validateJaqExpressions(frontmatter) {
  const errors = [];
  
  if (!frontmatter.adapters) return errors;
  
  for (const [entityName, adapter] of Object.entries(frontmatter.adapters)) {
    if (!adapter.mapping) continue;
    
    // Collect all jaq expressions from mappings (including nested typed references)
    const exprs = collectJaqExpressions(adapter.mapping, `adapters.${entityName}.mapping`);
    
    for (const { path, expr } of exprs) {
      // 1. Single-quoted strings: detect 'word' patterns inside expressions
      //    e.g., .type == 'completed' should be .type == "completed"
      //    Match: quote + word chars + quote, but not at start/end (YAML wrappers)
      const singleQuoteMatches = expr.match(/== *'[^']*'|'[^']*' *==|'[^']*' *\?|: *'[^']*'/g);
      if (singleQuoteMatches) {
        errors.push(
          `${path}: Single-quoted string in jaq expression (jaq requires double quotes): ${singleQuoteMatches[0]}\n` +
          `   Expression: ${expr}`
        );
      }
      
      // 2. C-style ternary: condition ? value : other
      //    jaq uses: if condition then value else other end
      //    Detect: ? "..." : or ? followed by string literal (not ?// which is jaq alternative operator)
      if (/\?\s*["']/.test(expr) && !/\?\/\//.test(expr)) {
        errors.push(
          `${path}: C-style ternary syntax (jaq uses if/then/else/end, not ? :)\n` +
          `   Expression: ${expr}`
        );
      }
      
      // 3. Bare [] on nullable paths: .foo.bar[].baz without null guards
      //    Safe patterns: (.foo // [])[] or (.foo // {}).bar or []?
      //    Unsafe: .foo.nodes[].id (nodes could be null from GraphQL)
      //    Only flag .nodes[] and .items[] patterns (common GraphQL nullable fields)
      const bareIterationMatch = expr.match(/\.(nodes|items|edges)\[\][^?]/);
      if (bareIterationMatch) {
        // Check it's not inside a null-guarded expression like ((.x // {}).nodes // [])[]
        const guardPattern = /\(\s*\([^)]+\/\/\s*\{\s*\}\s*\)\s*\.\s*(nodes|items|edges)\s*\/\/\s*\[\s*\]\s*\)/;
        if (!guardPattern.test(expr)) {
          errors.push(
            `${path}: Bare .${bareIterationMatch[1]}[] without null guard (crashes when parent is null)\n` +
            `   Use: [((.parent // {}).${bareIterationMatch[1]} // [])[] | .field]\n` +
            `   Expression: ${expr}`
          );
        }
      }
    }
  }
  
  return errors;
}

// Recursively collect jaq expression strings from a mapping object
function collectJaqExpressions(mapping, parentPath) {
  const exprs = [];
  
  for (const [key, value] of Object.entries(mapping)) {
    const path = `${parentPath}.${key}`;
    
    if (typeof value === 'string') {
      // Only check expressions that look like jaq (contain dots, operators, or function calls)
      // Skip simple field access like .id, .title (these rarely have issues)
      if (value.includes('==') || value.includes('if ') || value.includes('[]') ||
          value.includes('//') || value.includes('|') || value.includes('?') ||
          value.includes("'")) {
        exprs.push({ path, expr: value });
      }
    } else if (typeof value === 'object' && value !== null) {
      // Recurse into typed references
      exprs.push(...collectJaqExpressions(value, path));
    }
  }
  
  return exprs;
}

// Parse YAML frontmatter
function parseFrontmatter(content) {
  if (!content.startsWith('---')) return null;
  const endIndex = content.indexOf('\n---', 3);
  if (endIndex === -1) return null;
  const yaml = content.slice(4, endIndex);
  return parseYaml(yaml);
}

// Get all tools (operations + utilities) from frontmatter
function getTools(frontmatter) {
  const tools = [];
  if (frontmatter.operations) {
    tools.push(...Object.keys(frontmatter.operations));
  }
  if (frontmatter.utilities) {
    tools.push(...Object.keys(frontmatter.utilities));
  }
  return tools;
}

// Find which tools are tested by parsing test files
function getTestedTools(pluginDir) {
  const testsDir = join(pluginDir, 'tests');
  if (!existsSync(testsDir)) return new Set();
  
  const testedTools = new Set();
  const testFiles = readdirSync(testsDir).filter(f => f.endsWith('.test.ts'));
  
  for (const file of testFiles) {
    const content = readFileSync(join(testsDir, file), 'utf-8');
    // Match tool: 'operation.name' or tool: "operation.name"
    const matches = content.matchAll(/tool:\s*['"]([^'"]+)['"]/g);
    for (const match of matches) {
      testedTools.add(match[1]);
    }
  }
  
  return testedTools;
}

// Ensure .needs-work directory exists
if (!existsSync(NEEDS_WORK_DIR)) {
  mkdirSync(NEEDS_WORK_DIR, { recursive: true });
}

// Move plugin to .needs-work
function moveToNeedsWork(pluginName) {
  const sourcePath = join(APPS_DIR, pluginName);
  const destPath = join(NEEDS_WORK_DIR, pluginName);
  
  if (existsSync(destPath)) {
    console.error(`⚠️  plugins/${pluginName}: Already exists in .needs-work, skipping move`);
    return false;
  }
  
  try {
    renameSync(sourcePath, destPath);
    console.log(`📦 Moved plugins/${pluginName} → plugins/.needs-work/${pluginName}`);
    return true;
  } catch (err) {
    console.error(`❌ Failed to move plugins/${pluginName}: ${err.message}`);
    return false;
  }
}

// Recursively find all plugins (directories with readme.md)
// Returns array of { name: 'pluginName', path: 'category/pluginName' }
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
    
    // Check if this directory is a plugin (has readme.md)
    if (existsSync(join(fullPath, 'readme.md'))) {
      plugins.push({ name: entry.name, path: entryRelativePath });
    } else {
      // It's a category folder, recurse into it
      plugins.push(...findPlugins(fullPath, entryRelativePath));
    }
  }
  
  return plugins;
}

// Get all apps or filter by args
const args = process.argv.slice(2);
const filterIndex = args.indexOf('--filter');
const filterValue = filterIndex !== -1 ? args[filterIndex + 1] : null;
const validateAll = args.includes('--all') || args.length === 0;
const autoMove = !args.includes('--no-move');  // Auto-move by default, disable with --no-move

let plugins = validateAll 
  ? findPlugins(APPS_DIR)
  : args.filter(a => !a.startsWith('--')).map(a => ({ name: a, path: a }));

// Apply filter if specified
if (filterValue) {
  plugins = plugins.filter(p => p.name.includes(filterValue) || p.path.includes(filterValue));
}

let hasErrors = false;
let hasCoverageWarnings = false;
let movedCount = 0;

for (const plugin of plugins) {
  const pluginDir = join(APPS_DIR, plugin.path);
  const readmePath = join(pluginDir, 'readme.md');
  let failed = false;
  let failureReason = '';
  
  const content = readFileSync(readmePath, 'utf-8');
  const frontmatter = parseFrontmatter(content);

  if (!frontmatter) {
    console.error(`❌ plugins/${plugin.path}: No YAML frontmatter found`);
    failureReason = 'No YAML frontmatter found';
    failed = true;
  } else {
    const valid = validate(frontmatter);
    if (!valid) {
      console.error(`❌ plugins/${plugin.path}: Schema validation failed`);
      for (const err of validate.errors) {
        console.error(`   ${err.instancePath || '/'}: ${err.message}`);
      }
      failureReason = 'Schema validation failed';
      failed = true;
    } else {
      // Validate operations and utilities return valid entities
      const entityErrors = validateReturns(frontmatter);
      if (entityErrors.length > 0) {
        console.error(`❌ plugins/${plugin.path}: Invalid entity references`);
        for (const err of entityErrors) {
          console.error(`   ${err}`);
        }
        failureReason = 'Invalid entity references';
        failed = true;
      } else {
        // Validate adapter mappings reference valid entity properties
        const adapterErrors = validateAdapterMappings(frontmatter);
        if (adapterErrors.length > 0) {
          console.error(`❌ plugins/${plugin.path}: Invalid adapter mappings`);
          for (const err of adapterErrors) {
            console.error(`   ${err}`);
          }
          failureReason = 'Invalid adapter mappings';
          failed = true;
        }
        
        // Validate jaq expression syntax (even if adapter mapping check passed)
        const jaqErrors = validateJaqExpressions(frontmatter);
        if (jaqErrors.length > 0) {
          console.error(`❌ plugins/${plugin.path}: Invalid jaq expressions`);
          for (const err of jaqErrors) {
            console.error(`   ${err}`);
          }
          failureReason = 'Invalid jaq expressions';
          failed = true;
        }
        
        if (!failed) {
          // Check icon exists (PNG or SVG)
          const hasIcon = existsSync(join(pluginDir, 'icon.svg')) || existsSync(join(pluginDir, 'icon.png'));
          if (!hasIcon) {
            console.error(`❌ plugins/${plugin.path}: icon.svg or icon.png not found (required)`);
            failureReason = 'icon not found';
            failed = true;
          } else {
            // Check test coverage (only for valid plugins)
            const tools = getTools(frontmatter);
            const testedTools = getTestedTools(pluginDir);
            const untestedTools = tools.filter(t => !testedTools.has(t));
            
            if (untestedTools.length > 0) {
              console.error(`❌ plugins/${plugin.path}: Missing tests for: ${untestedTools.join(', ')}`);
              failureReason = `Missing tests for: ${untestedTools.join(', ')}`;
              failed = true;
            } else if (tools.length > 0) {
              console.log(`✓ plugins/${plugin.path} (${tools.length} tools, all tested)`);
            } else {
              console.log(`✓ plugins/${plugin.path}`);
            }
          }
        }
      }
    }
  }
  
  if (failed) {
    hasErrors = true;
    // Note: auto-move with categories would need more complex logic to preserve category structure
    // For now, just report the error
    if (autoMove) {
      console.log(`   (auto-move disabled for categorized plugins - fix manually)`);
    }
  }
}

if (movedCount > 0) {
  console.log(`\n📦 Moved ${movedCount} plugin(s) to plugins/.needs-work/`);
}

if (hasErrors) {
  console.error('\n❌ Validation failed');
  process.exit(1);
} else {
  console.log('\n✅ All plugins valid');
  process.exit(0);
}

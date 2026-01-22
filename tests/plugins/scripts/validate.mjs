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
import { parse as parseYaml } from 'yaml';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../../..');  // tests/plugins/scripts/ -> root
const APPS_DIR = join(ROOT, 'plugins');
const NEEDS_WORK_DIR = join(APPS_DIR, '.needs-work');
const SCHEMA_PATH = join(__dirname, '..', 'plugin.schema.json');

// Load schema
const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf-8'));
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);

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
        // Check icon.svg exists (required for all plugins)
        const iconPath = join(pluginDir, 'icon.svg');
        if (!existsSync(iconPath)) {
          console.error(`❌ plugins/${plugin.path}: icon.svg not found (required)`);
          failureReason = 'icon.svg not found';
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

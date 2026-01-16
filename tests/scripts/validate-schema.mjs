#!/usr/bin/env node
/**
 * Fast schema validation for pre-commit hook.
 * Validates connector readme.md YAML against JSON Schema.
 * 
 * Usage: node scripts/validate-schema.mjs [app1] [app2] ...
 *        node scripts/validate-schema.mjs --all
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse as parseYaml } from 'yaml';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../..');  // tests/scripts/ -> root
const APPS_DIR = join(ROOT, 'apps');
const SCHEMA_PATH = join(ROOT, 'tests', 'connector.schema.json');

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

// Get all apps or filter by args
const args = process.argv.slice(2);
const validateAll = args.includes('--all') || args.length === 0;

const apps = validateAll 
  ? readdirSync(APPS_DIR, { withFileTypes: true })
      .filter(d => d.isDirectory())
      .map(d => d.name)
  : args.filter(a => a !== '--all');

let hasErrors = false;

for (const app of apps) {
  const readmePath = join(APPS_DIR, app, 'readme.md');
  
  if (!existsSync(readmePath)) {
    console.error(`❌ apps/${app}: readme.md not found`);
    hasErrors = true;
    continue;
  }

  const content = readFileSync(readmePath, 'utf-8');
  const frontmatter = parseFrontmatter(content);

  if (!frontmatter) {
    console.error(`❌ apps/${app}: No YAML frontmatter found`);
    hasErrors = true;
    continue;
  }

  const valid = validate(frontmatter);
  if (!valid) {
    console.error(`❌ apps/${app}: Schema validation failed`);
    for (const err of validate.errors) {
      console.error(`   ${err.instancePath || '/'}: ${err.message}`);
    }
    hasErrors = true;
  } else {
    console.log(`✓ apps/${app}`);
  }
}

if (hasErrors) {
  console.error('\n❌ Schema validation failed');
  process.exit(1);
} else {
  console.log('\n✅ All connectors valid');
  process.exit(0);
}

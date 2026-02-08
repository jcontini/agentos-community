/**
 * Adapter Schema Validation Tests
 * 
 * Validates:
 * - All adapter readme.md files have valid YAML frontmatter conforming to adapter schema
 * - Required files (icon.png) exist
 * - Adapters have operations or utilities
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { parse as parseYaml } from 'yaml';

const INTEGRATIONS_ROOT = join(__dirname, '../..');
const ADAPTERS_DIR = join(INTEGRATIONS_ROOT, 'adapters');
const SCHEMA_PATH = join(__dirname, 'adapter.schema.json');

// Load and compile schema
const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf-8'));
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);

// Recursively find all adapter directories (excluding .needs-work)
// Returns relative paths from ADAPTERS_DIR (e.g., 'tasks/todoist', 'search/exa')
const getAdapters = (): string[] => {
  const adapters: string[] = [];
  
  const scan = (dir: string, relativePath: string = '') => {
    const entries = readdirSync(dir, { withFileTypes: true });
    
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (entry.name === '.needs-work') continue;
      if (entry.name === 'node_modules') continue;
      if (entry.name === 'tests') continue;
      
      const fullPath = join(dir, entry.name);
      const entryRelativePath = relativePath ? `${relativePath}/${entry.name}` : entry.name;
      
      // Check if this directory is a adapter (has readme.md)
      if (existsSync(join(fullPath, 'readme.md'))) {
        adapters.push(entryRelativePath);
      } else {
        // It's a category folder, recurse into it
        scan(fullPath, entryRelativePath);
      }
    }
  };
  
  scan(ADAPTERS_DIR);
  return adapters;
};

// Parse YAML frontmatter from markdown
function parseFrontmatter(content: string): Record<string, unknown> | null {
  if (!content.startsWith('---')) return null;
  const endIndex = content.indexOf('\n---', 3);
  if (endIndex === -1) return null;
  const yaml = content.slice(4, endIndex);
  return parseYaml(yaml);
}

describe('Adapter Schema Validation', () => {
  const adapters = getAdapters();

  it('schema file exists', () => {
    expect(existsSync(SCHEMA_PATH)).toBe(true);
  });

  it('has adapters to validate', () => {
    expect(adapters.length).toBeGreaterThan(0);
  });

  describe.each(adapters)('adapters/%s', (adapterPath) => {
    const readmePath = join(ADAPTERS_DIR, adapterPath, 'readme.md');

    it('has readme.md', () => {
      expect(existsSync(readmePath)).toBe(true);
    });

    it('has valid YAML frontmatter', () => {
      const content = readFileSync(readmePath, 'utf-8');
      const frontmatter = parseFrontmatter(content);
      expect(frontmatter).not.toBeNull();
    });

    it('conforms to adapter schema', () => {
      const content = readFileSync(readmePath, 'utf-8');
      const frontmatter = parseFrontmatter(content);
      if (!frontmatter) {
        throw new Error('No frontmatter found');
      }

      const valid = validate(frontmatter);
      if (!valid) {
        const errors = validate.errors?.map(e => 
          `  ${e.instancePath || '/'}: ${e.message}`
        ).join('\n');
        throw new Error(`Schema validation failed:\n${errors}`);
      }
      expect(valid).toBe(true);
    });

    it('has required icon.svg file', () => {
      const adapterDir = join(ADAPTERS_DIR, adapterPath);
      const files = readdirSync(adapterDir);
      const hasSvgIcon = files.includes('icon.svg');
      expect(hasSvgIcon).toBe(true);
    });
  });
});

describe('Schema Completeness', () => {
  it('no adapters have tags (deprecated)', () => {
    for (const adapterPath of getAdapters()) {
      const content = readFileSync(join(ADAPTERS_DIR, adapterPath, 'readme.md'), 'utf-8');
      const frontmatter = parseFrontmatter(content);
      expect(frontmatter?.tags, `${adapterPath} should not have tags (deprecated)`).toBeUndefined();
    }
  });

  it('all adapters have at least one operation, utility, or action', () => {
    for (const adapterPath of getAdapters()) {
      const content = readFileSync(join(ADAPTERS_DIR, adapterPath, 'readme.md'), 'utf-8');
      const frontmatter = parseFrontmatter(content);
      const operations = frontmatter?.operations as Record<string, unknown> | undefined;
      const utilities = frontmatter?.utilities as Record<string, unknown> | undefined;
      const actions = frontmatter?.actions as Record<string, unknown> | undefined; // Legacy format
      
      // Adapter must have either operations, utilities, or actions (legacy)
      const hasOperations = operations && Object.keys(operations).length > 0;
      const hasUtilities = utilities && Object.keys(utilities).length > 0;
      const hasActions = actions && Object.keys(actions).length > 0; // Legacy support
      
      expect(
        hasOperations || hasUtilities || hasActions,
        `${adapterPath} must have either 'operations', 'utilities', or 'actions' (legacy) with at least one item`
      ).toBe(true);
    }
  });
});

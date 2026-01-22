/**
 * Plugin Schema Validation Tests
 * 
 * Validates:
 * - All plugin readme.md files have valid YAML frontmatter conforming to plugin schema
 * - Required files (icon.png) exist
 * - Plugins have operations or utilities
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { parse as parseYaml } from 'yaml';

const INTEGRATIONS_ROOT = join(__dirname, '../..');
const PLUGINS_DIR = join(INTEGRATIONS_ROOT, 'plugins');
const SCHEMA_PATH = join(__dirname, 'plugin.schema.json');

// Load and compile schema
const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf-8'));
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);

// Recursively find all plugin directories (excluding .needs-work)
// Returns relative paths from PLUGINS_DIR (e.g., 'tasks/todoist', 'search/exa')
const getPlugins = (): string[] => {
  const plugins: string[] = [];
  
  const scan = (dir: string, relativePath: string = '') => {
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
        plugins.push(entryRelativePath);
      } else {
        // It's a category folder, recurse into it
        scan(fullPath, entryRelativePath);
      }
    }
  };
  
  scan(PLUGINS_DIR);
  return plugins;
};

// Parse YAML frontmatter from markdown
function parseFrontmatter(content: string): Record<string, unknown> | null {
  if (!content.startsWith('---')) return null;
  const endIndex = content.indexOf('\n---', 3);
  if (endIndex === -1) return null;
  const yaml = content.slice(4, endIndex);
  return parseYaml(yaml);
}

describe('Plugin Schema Validation', () => {
  const plugins = getPlugins();

  it('schema file exists', () => {
    expect(existsSync(SCHEMA_PATH)).toBe(true);
  });

  it('has plugins to validate', () => {
    expect(plugins.length).toBeGreaterThan(0);
  });

  describe.each(plugins)('plugins/%s', (pluginPath) => {
    const readmePath = join(PLUGINS_DIR, pluginPath, 'readme.md');

    it('has readme.md', () => {
      expect(existsSync(readmePath)).toBe(true);
    });

    it('has valid YAML frontmatter', () => {
      const content = readFileSync(readmePath, 'utf-8');
      const frontmatter = parseFrontmatter(content);
      expect(frontmatter).not.toBeNull();
    });

    it('conforms to plugin schema', () => {
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
      const pluginDir = join(PLUGINS_DIR, pluginPath);
      const files = readdirSync(pluginDir);
      const hasSvgIcon = files.includes('icon.svg');
      expect(hasSvgIcon).toBe(true);
    });
  });
});

describe('Schema Completeness', () => {
  it('all plugins have tags', () => {
    for (const pluginPath of getPlugins()) {
      const content = readFileSync(join(PLUGINS_DIR, pluginPath, 'readme.md'), 'utf-8');
      const frontmatter = parseFrontmatter(content);
      expect(frontmatter?.tags, `${pluginPath} missing tags`).toBeDefined();
      expect(Array.isArray(frontmatter?.tags), `${pluginPath} tags should be array`).toBe(true);
    }
  });

  it('all plugins have at least one operation, utility, or action', () => {
    for (const pluginPath of getPlugins()) {
      const content = readFileSync(join(PLUGINS_DIR, pluginPath, 'readme.md'), 'utf-8');
      const frontmatter = parseFrontmatter(content);
      const operations = frontmatter?.operations as Record<string, unknown> | undefined;
      const utilities = frontmatter?.utilities as Record<string, unknown> | undefined;
      const actions = frontmatter?.actions as Record<string, unknown> | undefined; // Legacy format
      
      // Plugin must have either operations, utilities, or actions (legacy)
      const hasOperations = operations && Object.keys(operations).length > 0;
      const hasUtilities = utilities && Object.keys(utilities).length > 0;
      const hasActions = actions && Object.keys(actions).length > 0; // Legacy support
      
      expect(
        hasOperations || hasUtilities || hasActions,
        `${pluginPath} must have either 'operations', 'utilities', or 'actions' (legacy) with at least one item`
      ).toBe(true);
    }
  });
});

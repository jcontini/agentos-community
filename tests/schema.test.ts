/**
 * Schema Validation Tests
 * 
 * Validates that all connector readme.md files have valid YAML frontmatter
 * that conforms to the connector schema.
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { parse as parseYaml } from 'yaml';

const INTEGRATIONS_ROOT = join(__dirname, '..');
const APPS_DIR = join(INTEGRATIONS_ROOT, 'apps');
const SCHEMA_PATH = join(INTEGRATIONS_ROOT, 'tests', 'connector.schema.json');

// Load and compile schema
const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf-8'));
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);

// Get all app directories (flat structure)
const getApps = () => readdirSync(APPS_DIR, { withFileTypes: true })
  .filter(d => d.isDirectory())
  .map(d => d.name);

// Parse YAML frontmatter from markdown
function parseFrontmatter(content: string): Record<string, unknown> | null {
  if (!content.startsWith('---')) return null;
  const endIndex = content.indexOf('\n---', 3);
  if (endIndex === -1) return null;
  const yaml = content.slice(4, endIndex);
  return parseYaml(yaml);
}

describe('Connector Schema Validation', () => {
  const apps = getApps();

  it('schema file exists', () => {
    expect(existsSync(SCHEMA_PATH)).toBe(true);
  });

  it('has connectors to validate', () => {
    expect(apps.length).toBeGreaterThan(0);
  });

  describe.each(apps)('apps/%s', (app) => {
    const readmePath = join(APPS_DIR, app, 'readme.md');

    it('has readme.md', () => {
      expect(existsSync(readmePath)).toBe(true);
    });

    it('has valid YAML frontmatter', () => {
      const content = readFileSync(readmePath, 'utf-8');
      const frontmatter = parseFrontmatter(content);
      expect(frontmatter).not.toBeNull();
    });

    it('conforms to connector schema', () => {
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

    it('has required icon file', () => {
      const appDir = join(APPS_DIR, app);
      const files = readdirSync(appDir);
      const hasIcon = files.some(f => f.startsWith('icon.'));
      expect(hasIcon).toBe(true);
    });
  });
});

describe('Schema Completeness', () => {
  it('all connectors have tags', () => {
    for (const app of getApps()) {
      const content = readFileSync(join(APPS_DIR, app, 'readme.md'), 'utf-8');
      const frontmatter = parseFrontmatter(content);
      expect(frontmatter?.tags, `${app} missing tags`).toBeDefined();
      expect(Array.isArray(frontmatter?.tags), `${app} tags should be array`).toBe(true);
    }
  });

  it('all connectors have at least one action', () => {
    for (const app of getApps()) {
      const content = readFileSync(join(APPS_DIR, app, 'readme.md'), 'utf-8');
      const frontmatter = parseFrontmatter(content);
      const actions = frontmatter?.actions as Record<string, unknown> | undefined;
      expect(actions, `${app} missing actions`).toBeDefined();
      expect(Object.keys(actions || {}).length, `${app} has no actions`).toBeGreaterThan(0);
    }
  });
});

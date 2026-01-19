/**
 * Schema Validation Tests
 * 
 * Validates:
 * - All plugin readme.md files have valid YAML frontmatter conforming to plugin schema
 * - All entity files have valid structure
 * - graph.yaml references valid entities with no conflicts
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { parse as parseYaml } from 'yaml';

const INTEGRATIONS_ROOT = join(__dirname, '..');
const PLUGINS_DIR = join(INTEGRATIONS_ROOT, 'plugins');
const SCHEMA_PATH = join(INTEGRATIONS_ROOT, 'tests', 'plugin.schema.json');

// Load and compile schema
const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf-8'));
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);

// Get all plugin directories (flat structure)
const getPlugins = () => readdirSync(PLUGINS_DIR, { withFileTypes: true })
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

describe('Plugin Schema Validation', () => {
  const plugins = getPlugins();

  it('schema file exists', () => {
    expect(existsSync(SCHEMA_PATH)).toBe(true);
  });

  it('has plugins to validate', () => {
    expect(plugins.length).toBeGreaterThan(0);
  });

  describe.each(plugins)('plugins/%s', (plugin) => {
    const readmePath = join(PLUGINS_DIR, plugin, 'readme.md');

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

    it('has required icon file', () => {
      const pluginDir = join(PLUGINS_DIR, plugin);
      const files = readdirSync(pluginDir);
      const hasIcon = files.some(f => f.startsWith('icon.'));
      expect(hasIcon).toBe(true);
    });
  });
});

describe('Schema Completeness', () => {
  it('all plugins have tags', () => {
    for (const plugin of getPlugins()) {
      const content = readFileSync(join(PLUGINS_DIR, plugin, 'readme.md'), 'utf-8');
      const frontmatter = parseFrontmatter(content);
      expect(frontmatter?.tags, `${plugin} missing tags`).toBeDefined();
      expect(Array.isArray(frontmatter?.tags), `${plugin} tags should be array`).toBe(true);
    }
  });

  it('all plugins have at least one action or entity operation', () => {
    for (const plugin of getPlugins()) {
      const content = readFileSync(join(PLUGINS_DIR, plugin, 'readme.md'), 'utf-8');
      const frontmatter = parseFrontmatter(content);
      const actions = frontmatter?.actions as Record<string, unknown> | undefined;
      const entities = frontmatter?.entities as Record<string, unknown> | undefined;
      
      // Plugin must have either actions or entities
      const hasActions = actions && Object.keys(actions).length > 0;
      const hasEntities = entities && Object.keys(entities).length > 0;
      
      expect(
        hasActions || hasEntities,
        `${plugin} must have either 'actions' or 'entities' with at least one operation`
      ).toBe(true);
    }
  });
});

// === Entity Schema Validation ===

const ENTITIES_DIR = join(INTEGRATIONS_ROOT, 'entities');
const GRAPH_PATH = join(ENTITIES_DIR, 'graph.yaml');

// Get all entity files (excluding graph.yaml)
const getEntityFiles = () => existsSync(ENTITIES_DIR)
  ? readdirSync(ENTITIES_DIR).filter(f => f.endsWith('.yaml') && f !== 'graph.yaml')
  : [];

describe('Entity Schema Validation', () => {
  const entityFiles = getEntityFiles();

  it('has entity files', () => {
    expect(entityFiles.length).toBeGreaterThan(0);
  });

  it('graph.yaml exists', () => {
    expect(existsSync(GRAPH_PATH)).toBe(true);
  });

  describe.each(entityFiles)('entities/%s', (file) => {
    const filePath = join(ENTITIES_DIR, file);
    let entity: Record<string, unknown>;

    it('is valid YAML', () => {
      const content = readFileSync(filePath, 'utf-8');
      entity = parseYaml(content);
      expect(entity).toBeDefined();
    });

    it('has required fields', () => {
      const content = readFileSync(filePath, 'utf-8');
      entity = parseYaml(content);
      
      expect(entity.id, `${file} missing 'id'`).toBeDefined();
      expect(entity.name, `${file} missing 'name'`).toBeDefined();
      expect(entity.description, `${file} missing 'description'`).toBeDefined();
      expect(entity.properties, `${file} missing 'properties'`).toBeDefined();
      expect(entity.operations, `${file} missing 'operations'`).toBeDefined();
    });

    it('has valid operations list', () => {
      const content = readFileSync(filePath, 'utf-8');
      entity = parseYaml(content);
      
      expect(Array.isArray(entity.operations), `${file} operations should be array`).toBe(true);
      expect((entity.operations as unknown[]).length, `${file} should have at least one operation`).toBeGreaterThan(0);
    });

    it('has properties with types', () => {
      const content = readFileSync(filePath, 'utf-8');
      entity = parseYaml(content);
      
      const properties = entity.properties as Record<string, unknown>;
      expect(typeof properties).toBe('object');
      
      for (const [propName, propDef] of Object.entries(properties)) {
        const def = propDef as Record<string, unknown>;
        expect(def.type, `${file}.properties.${propName} missing 'type'`).toBeDefined();
      }
    });
  });
});

describe('Graph Validation', () => {
  it('graph.yaml is valid YAML', () => {
    const content = readFileSync(GRAPH_PATH, 'utf-8');
    const graph = parseYaml(content);
    expect(graph).toBeDefined();
    expect(graph.relationships).toBeDefined();
  });

  it('all relationship entities exist', () => {
    const graphContent = readFileSync(GRAPH_PATH, 'utf-8');
    const graph = parseYaml(graphContent);
    
    // Get valid entity IDs
    const validEntityIds = new Set<string>();
    for (const file of getEntityFiles()) {
      const content = readFileSync(join(ENTITIES_DIR, file), 'utf-8');
      const entity = parseYaml(content);
      if (entity.id) {
        validEntityIds.add(entity.id);
      }
    }
    
    const errors: string[] = [];
    
    for (const [relId, rel] of Object.entries(graph.relationships as Record<string, { from?: string; to?: string | string[] }>)) {
      if (rel.from && !validEntityIds.has(rel.from)) {
        errors.push(`Relationship '${relId}' references unknown 'from' entity: ${rel.from}`);
      }
      
      if (rel.to) {
        const toEntities = Array.isArray(rel.to) ? rel.to : [rel.to];
        for (const toEntity of toEntities) {
          if (!validEntityIds.has(toEntity)) {
            errors.push(`Relationship '${relId}' references unknown 'to' entity: ${toEntity}`);
          }
        }
      }
    }
    
    if (errors.length > 0) {
      throw new Error(`Graph validation errors:\n${errors.join('\n')}`);
    }
  });

  it('all relationships have required fields', () => {
    const content = readFileSync(GRAPH_PATH, 'utf-8');
    const graph = parseYaml(content);
    const errors: string[] = [];
    
    for (const [relId, rel] of Object.entries(graph.relationships as Record<string, { from?: string; to?: string | string[]; description?: string }>)) {
      if (!rel.from) errors.push(`Relationship '${relId}' missing 'from'`);
      if (!rel.to) errors.push(`Relationship '${relId}' missing 'to'`);
      if (!rel.description) errors.push(`Relationship '${relId}' missing 'description'`);
    }
    
    if (errors.length > 0) {
      throw new Error(`Missing required fields:\n${errors.join('\n')}`);
    }
  });

  it('no duplicate relationship IDs', () => {
    const content = readFileSync(GRAPH_PATH, 'utf-8');
    const graph = parseYaml(content);
    
    const ids = Object.keys(graph.relationships);
    const uniqueIds = new Set(ids);
    
    expect(ids.length).toBe(uniqueIds.size);
  });
});

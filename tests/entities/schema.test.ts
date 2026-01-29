/**
 * Entity Schema Validation Tests
 * 
 * Validates:
 * - All entity files have valid structure
 * - Required fields are present
 * - Properties have types
 * 
 * Supports three formats:
 * 1. Single entity: { id, name, description, properties, operations }
 * 2. Multi-document: Multiple YAML docs separated by ---
 *    - First doc with `domain` = domain metadata
 *    - Docs with `id` = entity definitions
 *    - Doc with `relationships` = relationship definitions
 * 3. Legacy bundle: { domain, entities: { entity_id: {...} } } (deprecated)
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, existsSync } from 'fs';
import { join, relative } from 'path';
import { parseAllDocuments, parse as parseYaml } from 'yaml';

const INTEGRATIONS_ROOT = join(__dirname, '../..');
const ENTITIES_DIR = join(INTEGRATIONS_ROOT, 'entities');

// Files to exclude from entity validation (not entity definitions)
const EXCLUDE_FILES = ['operations.yaml'];

// Recursively get all entity YAML files
const getEntityFiles = (dir: string = ENTITIES_DIR): string[] => {
  if (!existsSync(dir)) return [];
  
  const entries = readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];
  
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...getEntityFiles(fullPath));
    } else if (entry.name.endsWith('.yaml') && !EXCLUDE_FILES.includes(entry.name)) {
      files.push(relative(ENTITIES_DIR, fullPath));
    }
  }
  
  return files;
};

// Parse entity file - handles single doc, multi-doc, and legacy bundle formats
interface EntityDef {
  id: string;
  name: string;
  description: string;
  properties: Record<string, { type: string }>;
  operations: string[];
  [key: string]: unknown;
}

interface ParsedFile {
  domain?: string;
  domainDescription?: string;
  entities: EntityDef[];
  relationships?: unknown[];
}

const parseEntityFile = (content: string): ParsedFile => {
  const docs = parseAllDocuments(content);
  const result: ParsedFile = { entities: [] };
  
  for (const doc of docs) {
    if (doc.errors.length > 0) {
      throw new Error(`YAML parse error: ${doc.errors[0].message}`);
    }
    
    const data = doc.toJS() as Record<string, unknown>;
    if (!data) continue; // Skip empty documents
    
    if ('domain' in data && typeof data.domain === 'string') {
      // Domain metadata document
      result.domain = data.domain;
      result.domainDescription = data.description as string;
    } else if ('id' in data && typeof data.id === 'string') {
      // Entity definition document
      result.entities.push(data as EntityDef);
    } else if ('relationships' in data) {
      // Relationships document
      result.relationships = data.relationships as unknown[];
    } else if ('entities' in data && typeof data.entities === 'object') {
      // Legacy bundle format (deprecated)
      result.domain = data.domain as string;
      result.domainDescription = data.description as string;
      const entities = data.entities as Record<string, Record<string, unknown>>;
      for (const [entityId, entityDef] of Object.entries(entities)) {
        result.entities.push({ id: entityId, ...entityDef } as EntityDef);
      }
      if ('relationships' in data) {
        result.relationships = data.relationships as unknown[];
      }
    }
  }
  
  return result;
};

// Validate a single entity definition
const validateEntity = (entity: EntityDef, file: string) => {
  const prefix = `${file}:${entity.id}`;
  
  expect(entity.id, `${prefix} missing 'id'`).toBeDefined();
  expect(entity.name, `${prefix} missing 'name'`).toBeDefined();
  expect(entity.description, `${prefix} missing 'description'`).toBeDefined();
  expect(entity.properties, `${prefix} missing 'properties'`).toBeDefined();
  expect(entity.operations, `${prefix} missing 'operations'`).toBeDefined();
  
  // Validate operations is array
  expect(Array.isArray(entity.operations), `${prefix} operations should be array`).toBe(true);
  
  // Validate properties have types
  expect(typeof entity.properties).toBe('object');
  
  for (const [propName, propDef] of Object.entries(entity.properties)) {
    expect(propDef.type, `${prefix}.properties.${propName} missing 'type'`).toBeDefined();
  }
};

describe('Entity Schema Validation', () => {
  const entityFiles = getEntityFiles();

  it('has entity files', () => {
    expect(entityFiles.length).toBeGreaterThan(0);
  });

  describe.each(entityFiles)('entities/%s', (file) => {
    const filePath = join(ENTITIES_DIR, file);

    it('is valid YAML', () => {
      const raw = readFileSync(filePath, 'utf-8');
      expect(() => parseEntityFile(raw)).not.toThrow();
    });

    it('has valid entity structure', () => {
      const raw = readFileSync(filePath, 'utf-8');
      const parsed = parseEntityFile(raw);
      
      expect(parsed.entities.length, `${file} should have at least one entity`).toBeGreaterThan(0);
      
      for (const entity of parsed.entities) {
        validateEntity(entity, file);
      }
    });
  });
});

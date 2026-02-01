/**
 * App Models Schema Validation Tests
 * 
 * Validates:
 * - All models.yaml files have valid structure
 * - Required fields are present
 * - Properties have types
 * 
 * Supports multi-document YAML (--- separators):
 * - Each doc with `id` = model definition
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, existsSync } from 'fs';
import { join, relative } from 'path';
import { parseAllDocuments, parse as parseYaml } from 'yaml';

const INTEGRATIONS_ROOT = join(__dirname, '../..');
const APPS_DIR = join(INTEGRATIONS_ROOT, 'apps');

// Files to exclude from model validation (not model definitions)
const EXCLUDE_FILES = ['operations.yaml'];

// Recursively get all models.yaml files
const getModelFiles = (dir: string = APPS_DIR): string[] => {
  if (!existsSync(dir)) return [];
  
  const entries = readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];
  
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...getModelFiles(fullPath));
    } else if (entry.name.endsWith('.yaml') && !EXCLUDE_FILES.includes(entry.name)) {
      files.push(relative(APPS_DIR, fullPath));
    }
  }
  
  return files;
};

// Parse models file - handles multi-doc YAML
interface ModelDef {
  id: string;
  name: string;
  description: string;
  properties: Record<string, { type: string }>;
  operations: string[];
  [key: string]: unknown;
}

interface ParsedFile {
  models: ModelDef[];
  relationships?: unknown[];
}

const parseModelsFile = (content: string): ParsedFile => {
  const docs = parseAllDocuments(content);
  const result: ParsedFile = { models: [] };
  
  for (const doc of docs) {
    if (doc.errors.length > 0) {
      throw new Error(`YAML parse error: ${doc.errors[0].message}`);
    }
    
    const data = doc.toJS() as Record<string, unknown>;
    if (!data) continue; // Skip empty documents
    
    if ('id' in data && typeof data.id === 'string') {
      // Model definition document
      result.models.push(data as ModelDef);
    } else if ('relationships' in data) {
      // Relationships document
      result.relationships = data.relationships as unknown[];
    }
  }
  
  return result;
};

// Validate a single model definition
const validateModel = (model: ModelDef, file: string) => {
  const prefix = `${file}:${model.id}`;
  
  expect(model.id, `${prefix} missing 'id'`).toBeDefined();
  expect(model.name, `${prefix} missing 'name'`).toBeDefined();
  expect(model.description, `${prefix} missing 'description'`).toBeDefined();
  expect(model.properties, `${prefix} missing 'properties'`).toBeDefined();
  expect(model.operations, `${prefix} missing 'operations'`).toBeDefined();
  
  // Validate operations is array
  expect(Array.isArray(model.operations), `${prefix} operations should be array`).toBe(true);
  
  // Validate properties have types
  expect(typeof model.properties).toBe('object');
  
  for (const [propName, propDef] of Object.entries(model.properties)) {
    expect(propDef.type, `${prefix}.properties.${propName} missing 'type'`).toBeDefined();
  }
};

describe('App Models Schema Validation', () => {
  const modelFiles = getModelFiles();

  it('has model files', () => {
    expect(modelFiles.length).toBeGreaterThan(0);
  });

  describe.each(modelFiles)('apps/%s', (file) => {
    const filePath = join(APPS_DIR, file);

    it('is valid YAML', () => {
      const raw = readFileSync(filePath, 'utf-8');
      expect(() => parseModelsFile(raw)).not.toThrow();
    });

    it('has valid model structure', () => {
      const raw = readFileSync(filePath, 'utf-8');
      const parsed = parseModelsFile(raw);
      
      expect(parsed.models.length, `${file} should have at least one model`).toBeGreaterThan(0);
      
      for (const model of parsed.models) {
        validateModel(model, file);
      }
    });
  });
});

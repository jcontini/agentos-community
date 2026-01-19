#!/usr/bin/env node
/**
 * Graph Validation Script
 * 
 * Validates that graph.yaml references valid entities and has no conflicts.
 * 
 * Checks:
 * 1. All entity IDs in relationships exist as entity files
 * 2. All relationship IDs are unique
 * 3. Accessor names don't conflict across relationships
 * 4. Required fields are present (from, to, description)
 * 
 * Usage: node tests/scripts/validate-graph.mjs
 * Exit codes: 0 = valid, 1 = errors found
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse as parseYaml } from 'yaml';

const __dirname = dirname(fileURLToPath(import.meta.url));
const INTEGRATIONS_ROOT = join(__dirname, '..', '..');
const ENTITIES_DIR = join(INTEGRATIONS_ROOT, 'entities');
const GRAPH_PATH = join(ENTITIES_DIR, 'graph.yaml');

// Collect all errors and warnings
const errors = [];
const warnings = [];

function error(msg) {
  errors.push(`❌ ${msg}`);
}

function warn(msg) {
  warnings.push(`⚠️  ${msg}`);
}

// Load all entity IDs from entity files
function getValidEntityIds() {
  const entityIds = new Set();
  
  if (!existsSync(ENTITIES_DIR)) {
    error(`Entities directory not found: ${ENTITIES_DIR}`);
    return entityIds;
  }
  
  const files = readdirSync(ENTITIES_DIR).filter(f => 
    f.endsWith('.yaml') && f !== 'graph.yaml'
  );
  
  for (const file of files) {
    const content = readFileSync(join(ENTITIES_DIR, file), 'utf-8');
    try {
      const entity = parseYaml(content);
      if (entity.id) {
        entityIds.add(entity.id);
      } else {
        warn(`Entity file ${file} has no 'id' field`);
        // Fall back to filename without extension
        entityIds.add(file.replace('.yaml', ''));
      }
    } catch (e) {
      error(`Failed to parse ${file}: ${e.message}`);
    }
  }
  
  return entityIds;
}

// Validate the graph file
function validateGraph(validEntityIds) {
  if (!existsSync(GRAPH_PATH)) {
    error(`Graph file not found: ${GRAPH_PATH}`);
    return;
  }
  
  const content = readFileSync(GRAPH_PATH, 'utf-8');
  let graph;
  
  try {
    graph = parseYaml(content);
  } catch (e) {
    error(`Failed to parse graph.yaml: ${e.message}`);
    return;
  }
  
  if (!graph.relationships) {
    error('graph.yaml must have a "relationships" section');
    return;
  }
  
  const relationshipIds = new Set();
  const accessorsByEntity = new Map(); // entity -> Map<accessor_name, relationship_id>
  
  for (const [relId, rel] of Object.entries(graph.relationships)) {
    // Check for duplicate relationship IDs
    if (relationshipIds.has(relId)) {
      error(`Duplicate relationship ID: ${relId}`);
    }
    relationshipIds.add(relId);
    
    // Check required fields
    if (!rel.from) {
      error(`Relationship '${relId}' missing required field: from`);
    }
    if (!rel.to) {
      error(`Relationship '${relId}' missing required field: to`);
    }
    if (!rel.description) {
      error(`Relationship '${relId}' missing required field: description`);
    }
    
    // Validate 'from' entity exists
    if (rel.from && !validEntityIds.has(rel.from)) {
      error(`Relationship '${relId}' references unknown 'from' entity: ${rel.from}`);
    }
    
    // Validate 'to' entity(s) exist (can be string or array for polymorphic)
    if (rel.to) {
      const toEntities = Array.isArray(rel.to) ? rel.to : [rel.to];
      for (const toEntity of toEntities) {
        if (!validEntityIds.has(toEntity)) {
          error(`Relationship '${relId}' references unknown 'to' entity: ${toEntity}`);
        }
      }
    }
    
    // Check accessor conflicts
    // Default accessors follow the naming convention:
    // - from_side: semantic_name (from relId: {from}_{semantic_name})
    // - to_side: {from}s (plural of from entity)
    const fromAccessor = rel.accessors?.from_side || getDefaultFromAccessor(relId, rel.from);
    const toAccessor = rel.accessors?.to_side || getDefaultToAccessor(relId, rel.from);
    
    // Track from-side accessor on the 'from' entity
    if (rel.from) {
      registerAccessor(accessorsByEntity, rel.from, fromAccessor, relId);
    }
    
    // Track to-side accessor on each 'to' entity
    if (rel.to) {
      const toEntities = Array.isArray(rel.to) ? rel.to : [rel.to];
      for (const toEntity of toEntities) {
        registerAccessor(accessorsByEntity, toEntity, toAccessor, relId);
      }
    }
  }
}

// Get default from-side accessor (e.g., task_project -> project)
function getDefaultFromAccessor(relId, fromEntity) {
  // Strip the entity prefix to get semantic name
  // e.g., "task_project" -> "project", "task_assignee" -> "assignee"
  const prefix = `${fromEntity}_`;
  if (relId.startsWith(prefix)) {
    return relId.slice(prefix.length);
  }
  // Fallback: use full relId
  return relId;
}

// Get default to-side accessor (e.g., task_project -> tasks)
function getDefaultToAccessor(relId, fromEntity) {
  // Default is plural of from entity
  // e.g., from: task -> tasks
  return `${fromEntity}s`;
}

// Register an accessor and check for conflicts
function registerAccessor(accessorsByEntity, entity, accessorName, relId) {
  if (!accessorsByEntity.has(entity)) {
    accessorsByEntity.set(entity, new Map());
  }
  
  const entityAccessors = accessorsByEntity.get(entity);
  
  if (entityAccessors.has(accessorName)) {
    const existingRelId = entityAccessors.get(accessorName);
    if (existingRelId !== relId) {
      error(
        `Accessor conflict on entity '${entity}': ` +
        `'${accessorName}' used by both '${existingRelId}' and '${relId}'`
      );
    }
  } else {
    entityAccessors.set(accessorName, relId);
  }
}

// Main
console.log('🔍 Validating graph.yaml...\n');

const validEntityIds = getValidEntityIds();
console.log(`Found ${validEntityIds.size} entity files: ${[...validEntityIds].join(', ')}\n`);

validateGraph(validEntityIds);

// Print results
if (warnings.length > 0) {
  console.log('Warnings:');
  warnings.forEach(w => console.log(`  ${w}`));
  console.log('');
}

if (errors.length > 0) {
  console.log('Errors:');
  errors.forEach(e => console.log(`  ${e}`));
  console.log(`\n❌ Validation failed with ${errors.length} error(s)`);
  process.exit(1);
} else {
  console.log('✅ graph.yaml is valid');
  process.exit(0);
}

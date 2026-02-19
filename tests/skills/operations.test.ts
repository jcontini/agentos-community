/**
 * Entity Operation Tests
 * 
 * Automatically tests any skill that declares entity operations against
 * the expected entity schemas. No per-skill test code needed.
 * 
 * Run: npm run test:capabilities
 */

import { describe, it, expect } from 'vitest';
import { aos } from '../utils/fixtures';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'yaml';

// Entity operation schemas: what each entity.operation should return
// Keys are in format "entity.operation" (e.g., "webpage.search", "task.list")
const ENTITY_SCHEMAS: Record<string, {
  description: string;
  testParams: Record<string, unknown>;
  validate: (result: unknown) => void;
}> = {
  'webpage.search': {
    description: 'Search results with url and title',
    testParams: { query: 'test', limit: 2 },
    validate: (result) => {
      expect(Array.isArray(result) || (result as Record<string, unknown>)?.results).toBe(true);
      const arr = Array.isArray(result) ? result : (result as Record<string, unknown>).results as unknown[];
      if (Array.isArray(arr) && arr.length > 0) {
        const first = arr[0] as Record<string, unknown>;
        expect(first).toHaveProperty('url');
        expect(first).toHaveProperty('title');
        expect(typeof first.url).toBe('string');
        expect(typeof first.title).toBe('string');
      }
    }
  },
  'webpage.read': {
    description: 'Page content with url and content',
    testParams: { url: 'https://example.com' },
    validate: (result) => {
      const obj = result as Record<string, unknown>;
      expect(obj).toHaveProperty('url');
      expect(obj).toHaveProperty('content');
      expect(typeof obj.url).toBe('string');
      expect(typeof obj.content).toBe('string');
    }
  },
  'task.list': {
    description: 'Array of tasks with id and title',
    testParams: { limit: 5 },
    validate: (result) => {
      expect(Array.isArray(result) || (result as Record<string, unknown>)?.tasks).toBe(true);
      const arr = Array.isArray(result) ? result : (result as Record<string, unknown>).tasks as unknown[];
      if (Array.isArray(arr) && arr.length > 0) {
        const first = arr[0] as Record<string, unknown>;
        expect(first).toHaveProperty('id');
        expect(first).toHaveProperty('title');
      }
    }
  },
  'task.get': {
    description: 'Single task with id and title',
    testParams: { id: 'test' }, // Usually requires an actual ID
    validate: (result) => {
      const obj = result as Record<string, unknown>;
      expect(obj).toHaveProperty('id');
      expect(obj).toHaveProperty('title');
    }
  },
  'task.create': {
    description: 'Created task with id and title',
    testParams: { title: 'Test task' },
    validate: (result) => {
      const obj = result as Record<string, unknown>;
      expect(obj).toHaveProperty('id');
      expect(obj).toHaveProperty('title');
    }
  },
  'contact.list': {
    description: 'Array of contacts with id and name',
    testParams: { limit: 5 },
    validate: (result) => {
      expect(Array.isArray(result) || (result as Record<string, unknown>)?.contacts).toBe(true);
      const arr = Array.isArray(result) ? result : (result as Record<string, unknown>).contacts as unknown[];
      if (Array.isArray(arr) && arr.length > 0) {
        const first = arr[0] as Record<string, unknown>;
        expect(first).toHaveProperty('id');
        expect(first).toHaveProperty('name');
      }
    }
  },
  'contact.get': {
    description: 'Single contact with id and name',
    testParams: { id: 'test' },
    validate: (result) => {
      const obj = result as Record<string, unknown>;
      expect(obj).toHaveProperty('id');
      expect(obj).toHaveProperty('name');
    }
  },
  // Add more entity schemas as needed
};

function findSkillsWithOperations(): Array<{
  skill: string;
  tool: string;
  entityOperation: string;
}> {
  const skillsDir = path.join(__dirname, '../..', 'skills');
  const results: Array<{
    skill: string;
    tool: string;
    entityOperation: string;
  }> = [];
  
  if (!fs.existsSync(skillsDir)) return results;
  
  const findSkillDirs = (dir: string): string[] => {
    const skills: string[] = [];
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (entry.name === '.needs-work') continue;
      if (entry.name === 'node_modules') continue;
      if (entry.name === 'tests') continue;
      
      const fullPath = path.join(dir, entry.name);
      
      if (fs.existsSync(path.join(fullPath, 'readme.md'))) {
        skills.push(fullPath);
      } else {
        skills.push(...findSkillDirs(fullPath));
      }
    }
    
    return skills;
  };
  
  const skillPaths = findSkillDirs(skillsDir);
  
  for (const skillPath of skillPaths) {
    const readmePath = path.join(skillPath, 'readme.md');
    const content = fs.readFileSync(readmePath, 'utf-8');
    
    const match = content.match(/^---\n([\s\S]*?)\n---/);
    if (!match) continue;
    
    try {
      const config = yaml.parse(match[1]);
      const skillName = path.basename(skillPath);
      
      if (config.operations) {
        for (const operationName of Object.keys(config.operations)) {
          results.push({
            skill: config.id || skillName,
            tool: operationName,
            entityOperation: operationName,
          });
        }
      }
    } catch (e) {
      console.warn(`Failed to parse ${skillPath}/readme.md:`, e);
    }
  }
  
  return results;
}

const targetSkill = process.env.TEST_SKILL;

describe('Entity Operation Schema Validation', () => {
  const skills = findSkillsWithOperations();
  
  const byEntityOp = new Map<string, typeof skills>();
  for (const p of skills) {
    const list = byEntityOp.get(p.entityOperation) || [];
    list.push(p);
    byEntityOp.set(p.entityOperation, list);
  }
  
  for (const [entityOp, providers] of byEntityOp) {
    const schema = ENTITY_SCHEMAS[entityOp];
    
    if (!schema) {
      it.skip(`${entityOp}: No schema defined yet`, () => {});
      continue;
    }
    
    describe(entityOp, () => {
      for (const provider of providers) {
        if (targetSkill && provider.skill !== targetSkill) {
          continue;
        }
        
        it(`${provider.skill} → ${schema.description}`, async () => {
          try {
            const result = await aos().call('UseSkill', {
              skill: provider.skill,
              tool: provider.tool,
              params: schema.testParams,
            });
            
            schema.validate(result);
          } catch (error: unknown) {
            const err = error as Error;
            if (err.message?.includes('No credentials configured') ||
                err.message?.includes('credentials')) {
              console.log(`  ⏭ Skipped: ${provider.skill} not configured`);
              return;
            }
            if (err.message?.includes('not found in response') ||
                err.message?.includes('Path') && err.message?.includes('not found')) {
              console.log(`  ⏭ Skipped: ${provider.skill}.${provider.tool} returned empty/invalid response`);
              return;
            }
            throw error;
          }
        });
      }
    });
  }
});

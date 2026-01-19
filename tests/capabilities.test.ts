/**
 * Generic Capability Tests
 * 
 * Automatically tests any connector that declares `provides:` against
 * the expected capability schema. No per-connector test code needed.
 * 
 * Run: npm run test:capabilities
 */

import { describe, it, expect } from 'vitest';
import { aos } from './utils/fixtures';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'yaml';

// Capability schemas: what each capability should return
const CAPABILITY_SCHEMAS: Record<string, {
  description: string;
  testParams: Record<string, unknown>;
  validate: (result: unknown) => void;
}> = {
  web_search: {
    description: 'Search results with url and title',
    testParams: { query: 'test', limit: 2 },
    validate: (result) => {
      expect(Array.isArray(result)).toBe(true);
      const arr = result as Array<Record<string, unknown>>;
      expect(arr.length).toBeGreaterThan(0);
      expect(arr[0]).toHaveProperty('url');
      expect(arr[0]).toHaveProperty('title');
      expect(typeof arr[0].url).toBe('string');
      expect(typeof arr[0].title).toBe('string');
    }
  },
  web_read: {
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
  task_list: {
    description: 'Array of tasks with id and title',
    testParams: { limit: 5 },
    validate: (result) => {
      expect(Array.isArray(result)).toBe(true);
      const arr = result as Array<Record<string, unknown>>;
      if (arr.length > 0) {
        expect(arr[0]).toHaveProperty('id');
        expect(arr[0]).toHaveProperty('title');
      }
    }
  },
  task_get: {
    description: 'Single task with id and title',
    testParams: {}, // Requires id, skip if no tasks
    validate: (result) => {
      const obj = result as Record<string, unknown>;
      expect(obj).toHaveProperty('id');
      expect(obj).toHaveProperty('title');
    }
  },
  book_list: {
    description: 'Array of books with id and title',
    testParams: { limit: 5 },
    validate: (result) => {
      expect(Array.isArray(result)).toBe(true);
      const arr = result as Array<Record<string, unknown>>;
      if (arr.length > 0) {
        expect(arr[0]).toHaveProperty('id');
        expect(arr[0]).toHaveProperty('title');
      }
    }
  },
  // Add more capability schemas as needed
};

// Scan connectors directory to find all connectors with `provides:` declarations
function findConnectorsWithCapabilities(): Array<{
  connector: string;
  action: string;
  capability: string;
  account?: string;
}> {
  const connectorsDir = path.join(__dirname, '..', 'connectors');
  const results: Array<{
    connector: string;
    action: string;
    capability: string;
    account?: string;
  }> = [];
  
  if (!fs.existsSync(connectorsDir)) return results;
  
  const connectorDirs = fs.readdirSync(connectorsDir);
  
  for (const dir of connectorDirs) {
    const readmePath = path.join(connectorsDir, dir, 'readme.md');
    if (!fs.existsSync(readmePath)) continue;
    
    const content = fs.readFileSync(readmePath, 'utf-8');
    
    // Extract YAML frontmatter
    const match = content.match(/^---\n([\s\S]*?)\n---/);
    if (!match) continue;
    
    try {
      const config = yaml.parse(match[1]);
      if (!config.actions) continue;
      
      for (const [actionName, actionConfig] of Object.entries(config.actions)) {
        const action = actionConfig as Record<string, unknown>;
        if (action.provides && typeof action.provides === 'string') {
          results.push({
            connector: config.id || dir,
            action: actionName,
            capability: action.provides,
          });
        }
      }
    } catch (e) {
      console.warn(`Failed to parse ${dir}/readme.md:`, e);
    }
  }
  
  return results;
}

// Filter to only run specific connector if specified
const targetConnector = process.env.TEST_CONNECTOR;

describe('Capability Schema Validation', () => {
  const connectors = findConnectorsWithCapabilities();
  
  // Group by capability for organized output
  const byCapability = new Map<string, typeof connectors>();
  for (const c of connectors) {
    const list = byCapability.get(c.capability) || [];
    list.push(c);
    byCapability.set(c.capability, list);
  }
  
  for (const [capability, providers] of byCapability) {
    const schema = CAPABILITY_SCHEMAS[capability];
    
    if (!schema) {
      it.skip(`${capability}: No schema defined yet`, () => {});
      continue;
    }
    
    describe(capability, () => {
      for (const provider of providers) {
        // Skip if filtering to specific connector
        if (targetConnector && provider.connector !== targetConnector) {
          continue;
        }
        
        it(`${provider.connector}.${provider.action} → ${schema.description}`, async () => {
          try {
            const result = await aos().call('Connect', {
              connector: provider.connector,
              action: provider.action,
              params: schema.testParams,
            });
            
            schema.validate(result);
          } catch (error: unknown) {
            const err = error as Error;
            // Allow credential errors (connector not configured)
            if (err.message?.includes('No credentials configured') ||
                err.message?.includes('credentials')) {
              console.log(`  ⏭ Skipped: ${provider.connector} not configured`);
              return;
            }
            throw error;
          }
        });
      }
    });
  }
});

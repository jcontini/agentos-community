#!/usr/bin/env npx tsx
/**
 * Adapter Scaffold Generator
 * 
 * Creates a new adapter with correct boilerplate including:
 * - readme.md with YAML frontmatter and operation fields
 * - Placeholder icon
 * - Test file with proper patterns (credential handling, cleanup)
 * 
 * Usage:
 *   npm run new-adapter myservice
 *   npm run new-adapter my-service --readonly  # Read-only adapter (no CRUD)
 *   npm run new-adapter my-service --local     # Local adapter (no auth)
 */

import { mkdirSync, writeFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../..');
const ADAPTERS_DIR = join(ROOT, 'adapters');

// =============================================================================
// Argument Parsing
// =============================================================================

const args = process.argv.slice(2);

if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
  console.log(`
Adapter Scaffold Generator

Usage:
  npm run new-adapter <name>              # Full CRUD adapter with auth
  npm run new-adapter <name> --readonly   # Read-only adapter with auth
  npm run new-adapter <name> --local      # Local adapter (no auth)

Examples:
  npm run new-adapter notion              # Creates adapters/notion/
  npm run new-adapter web-search --readonly
  npm run new-adapter my-local-tool --local

Options:
  --readonly    Adapter only reads data (no create/update/delete)
  --local       Adapter doesn't need API credentials
  --help, -h    Show this help
`);
  process.exit(0);
}

const adapterName = args[0];
const isReadonly = args.includes('--readonly');
const isLocal = args.includes('--local');

// Validate name
if (!/^[a-z][a-z0-9-]*$/.test(adapterName)) {
  console.error(`❌ Invalid adapter name: ${adapterName}`);
  console.error('   Must start with lowercase letter, contain only a-z, 0-9, -');
  process.exit(1);
}

const adapterDir = join(ADAPTERS_DIR, adapterName);
if (existsSync(adapterDir)) {
  console.error(`❌ Adapter already exists: ${adapterDir}`);
  process.exit(1);
}

// Convert name to display format: my-service → My Service
const displayName = adapterName
  .split('-')
  .map(w => w.charAt(0).toUpperCase() + w.slice(1))
  .join(' ');

// =============================================================================
// Templates
// =============================================================================

function generateReadme(): string {
  const authBlock = isLocal ? '' : `
auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  label: API Key
  help_url: https://example.com/api-keys
`;

  const crudActions = isReadonly ? '' : `
  create:
    operation: create
    label: "Create item"
    rest:
      method: POST
      url: https://api.example.com/items
      body:
        name: "{{params.title}}"
      response:
        mapping:
          id: ".id"
          title: ".name"
          adapter: "'${adapterName}'"

  update:
    operation: update
    label: "Update item"
    rest:
      method: PATCH
      url: "https://api.example.com/items/{{params.id}}"
      body:
        name: "{{params.title}}"
      response:
        mapping:
          id: ".id"
          title: ".name"
          adapter: "'${adapterName}'"

  delete:
    operation: delete
    label: "Delete item"
    rest:
      method: DELETE
      url: "https://api.example.com/items/{{params.id}}"
      response:
        mapping:
          success: "true"
`;

  return `---
id: ${adapterName}
name: ${displayName}
description: "TODO: Describe what this adapter does"
icon: icon.svg
color: "#000000"

website: https://example.com
${authBlock}
actions:
  list:
    operation: read
    label: "List items"
    rest:
      method: GET
      url: https://api.example.com/items
      query:
        limit: "{{params.limit | default: 50}}"
      response:
        mapping:
          id: "[].id"
          title: "[].name"
          adapter: "'${adapterName}'"

  get:
    operation: read
    label: "Get item"
    rest:
      method: GET
      url: "https://api.example.com/items/{{params.id}}"
      response:
        mapping:
          id: ".id"
          title: ".name"
          adapter: "'${adapterName}'"
${crudActions}---

# ${displayName}

TODO: Human-readable documentation.

## Setup

1. Get your API key from https://example.com/settings/api
2. Add credential in AgentOS Settings → Adapters → ${displayName}

## Features

- List items
- Get item details${isReadonly ? '' : '\n- Create, update, delete items'}
`;
}

function generateTestFile(): string {
  // Local + readonly: minimal test
  if (isLocal && isReadonly) {
    return `/**
 * ${displayName} Adapter Tests
 */

import { describe, it, expect } from 'vitest';
import { aos } from '../../../tests/utils/fixtures';

const adapter = '${adapterName}';

describe('${displayName} Adapter', () => {
  describe('list', () => {
    it('returns an array of items', async () => {
      const items = await aos().call('UseAdapter', {
        adapter,
        tool: 'list',
        params: { limit: 5 },
      });

      expect(Array.isArray(items)).toBe(true);
    });

    it('items have required schema fields', async () => {
      const items = await aos().call('UseAdapter', {
        adapter,
        tool: 'list',
        params: { limit: 5 },
      });

      for (const item of items) {
        expect(item.id).toBeDefined();
        expect(item.title).toBeDefined();
        expect(item.adapter).toBe(adapter);
      }
    });
  });
});
`;
  }

  // API + readonly: credential handling, no cleanup
  if (isReadonly) {
    return `/**
 * ${displayName} Adapter Tests
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '../../../tests/utils/fixtures';

const adapter = '${adapterName}';

// Skip tests if no credentials configured
let skipTests = false;

describe('${displayName} Adapter', () => {
  beforeAll(async () => {
    try {
      await aos().call('UseAdapter', { adapter, tool: 'list', params: { limit: 1 } });
    } catch (e: any) {
      if (e.message?.includes('Credential not found')) {
        console.log('  ⏭ Skipping: no credentials configured');
        skipTests = true;
      } else throw e;
    }
  });

  describe('list', () => {
    it('returns an array of items', async () => {
      if (skipTests) return;

      const items = await aos().call('UseAdapter', {
        adapter,
        tool: 'list',
        params: { limit: 5 },
      });

      expect(Array.isArray(items)).toBe(true);
    });

    it('items have required schema fields', async () => {
      if (skipTests) return;

      const items = await aos().call('UseAdapter', {
        adapter,
        tool: 'list',
        params: { limit: 5 },
      });

      for (const item of items) {
        expect(item.id).toBeDefined();
        expect(item.title).toBeDefined();
        expect(item.adapter).toBe(adapter);
      }
    });
  });
});
`;
  }

  // Local + CRUD: cleanup, no credential handling
  if (isLocal) {
    return `/**
 * ${displayName} Adapter Tests
 */

import { describe, it, expect, afterAll } from 'vitest';
import { aos, testContent, TEST_PREFIX } from '../../../tests/utils/fixtures';

const adapter = '${adapterName}';

// Track created items for cleanup
const createdItems: Array<{ id: string }> = [];

describe('${displayName} Adapter', () => {
  afterAll(async () => {
    for (const item of createdItems) {
      try {
        await aos().call('UseAdapter', {
          adapter,
          tool: 'delete',
          params: { id: item.id },
          execute: true,
        });
      } catch (e) {
        console.warn(\`  Failed to cleanup \${item.id}:\`, e);
      }
    }
  });

  describe('list', () => {
    it('returns an array of items', async () => {
      const items = await aos().call('UseAdapter', {
        adapter,
        tool: 'list',
        params: { limit: 5 },
      });

      expect(Array.isArray(items)).toBe(true);
    });

    it('items have required schema fields', async () => {
      const items = await aos().call('UseAdapter', {
        adapter,
        tool: 'list',
        params: { limit: 5 },
      });

      for (const item of items) {
        expect(item.id).toBeDefined();
        expect(item.title).toBeDefined();
        expect(item.adapter).toBe(adapter);
      }
    });
  });

  describe('create → get → update → delete', () => {
    let createdItem: any;

    it('can create an item', async () => {
      const title = testContent('item');

      createdItem = await aos().call('UseAdapter', {
        adapter,
        tool: 'create',
        params: { title },
        execute: true,
      });

      expect(createdItem).toBeDefined();
      expect(createdItem.id).toBeDefined();

      createdItems.push({ id: createdItem.id });
    });

    it('can get the created item', async () => {
      if (!createdItem?.id) return;

      const item = await aos().call('UseAdapter', {
        adapter,
        tool: 'get',
        params: { id: createdItem.id },
      });

      expect(item).toBeDefined();
      expect(item.id).toBe(createdItem.id);
      expect(item.title).toContain(TEST_PREFIX);
    });

    it('can update the item', async () => {
      if (!createdItem?.id) return;

      const newTitle = testContent('updated item');

      const updated = await aos().call('UseAdapter', {
        adapter,
        tool: 'update',
        params: { id: createdItem.id, title: newTitle },
        execute: true,
      });

      expect(updated).toBeDefined();
    });

    it('can delete the item', async () => {
      if (!createdItem?.id) return;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'delete',
        params: { id: createdItem.id },
        execute: true,
      });

      expect(result).toBeDefined();

      // Remove from cleanup list
      const idx = createdItems.findIndex(i => i.id === createdItem.id);
      if (idx >= 0) createdItems.splice(idx, 1);
    });
  });
});
`;
  }

  // Full: API + CRUD (credential handling + cleanup)
  return `/**
 * ${displayName} Adapter Tests
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { aos, testContent, TEST_PREFIX } from '../../../tests/utils/fixtures';

const adapter = '${adapterName}';

// Track created items for cleanup
const createdItems: Array<{ id: string }> = [];

// Skip tests if no credentials configured
let skipTests = false;

describe('${displayName} Adapter', () => {
  beforeAll(async () => {
    try {
      await aos().call('UseAdapter', { adapter, tool: 'list', params: { limit: 1 } });
    } catch (e: any) {
      if (e.message?.includes('Credential not found')) {
        console.log('  ⏭ Skipping: no credentials configured');
        skipTests = true;
      } else throw e;
    }
  });

  afterAll(async () => {
    for (const item of createdItems) {
      try {
        await aos().call('UseAdapter', {
          adapter,
          tool: 'delete',
          params: { id: item.id },
          execute: true,
        });
      } catch (e) {
        console.warn(\`  Failed to cleanup \${item.id}:\`, e);
      }
    }
  });

  describe('list', () => {
    it('returns an array of items', async () => {
      if (skipTests) return;

      const items = await aos().call('UseAdapter', {
        adapter,
        tool: 'list',
        params: { limit: 5 },
      });

      expect(Array.isArray(items)).toBe(true);
    });

    it('items have required schema fields', async () => {
      if (skipTests) return;

      const items = await aos().call('UseAdapter', {
        adapter,
        tool: 'list',
        params: { limit: 5 },
      });

      for (const item of items) {
        expect(item.id).toBeDefined();
        expect(item.title).toBeDefined();
        expect(item.adapter).toBe(adapter);
      }
    });
  });

  describe('create → get → update → delete', () => {
    let createdItem: any;

    it('can create an item', async () => {
      if (skipTests) return;

      const title = testContent('item');

      createdItem = await aos().call('UseAdapter', {
        adapter,
        tool: 'create',
        params: { title },
        execute: true,
      });

      expect(createdItem).toBeDefined();
      expect(createdItem.id).toBeDefined();

      createdItems.push({ id: createdItem.id });
    });

    it('can get the created item', async () => {
      if (skipTests) return;
      if (!createdItem?.id) return;

      const item = await aos().call('UseAdapter', {
        adapter,
        tool: 'get',
        params: { id: createdItem.id },
      });

      expect(item).toBeDefined();
      expect(item.id).toBe(createdItem.id);
      expect(item.title).toContain(TEST_PREFIX);
    });

    it('can update the item', async () => {
      if (skipTests) return;
      if (!createdItem?.id) return;

      const newTitle = testContent('updated item');

      const updated = await aos().call('UseAdapter', {
        adapter,
        tool: 'update',
        params: { id: createdItem.id, title: newTitle },
        execute: true,
      });

      expect(updated).toBeDefined();
    });

    it('can delete the item', async () => {
      if (skipTests) return;
      if (!createdItem?.id) return;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'delete',
        params: { id: createdItem.id },
        execute: true,
      });

      expect(result).toBeDefined();

      // Remove from cleanup list
      const idx = createdItems.findIndex(i => i.id === createdItem.id);
      if (idx >= 0) createdItems.splice(idx, 1);
    });
  });
});
`;
}

const ICON_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
  <rect width="24" height="24" rx="4" fill="#666"/>
  <text x="12" y="16" text-anchor="middle" fill="white" font-size="10" font-family="system-ui">?</text>
</svg>`;

// =============================================================================
// Main
// =============================================================================

console.log(`Creating adapter: ${adapterName}`);
console.log(`  Type: ${isLocal ? 'local' : 'api'}${isReadonly ? ' (read-only)' : ''}`);
console.log();

// Create directories
mkdirSync(adapterDir, { recursive: true });
mkdirSync(join(adapterDir, 'tests'), { recursive: true });

// Write files
writeFileSync(join(adapterDir, 'readme.md'), generateReadme());
writeFileSync(join(adapterDir, 'icon.svg'), ICON_SVG);
writeFileSync(join(adapterDir, 'tests', `${adapterName}.test.ts`), generateTestFile());

console.log(`✓ Created adapters/${adapterName}/`);
console.log(`  - readme.md`);
console.log(`  - icon.svg`);
console.log(`  - tests/${adapterName}.test.ts`);
console.log();
console.log('Next steps:');
console.log(`  1. Edit adapters/${adapterName}/readme.md with your API details`);
console.log(`  2. Run: npm run lint:tests -- ${adapterName}`);
console.log(`  3. Run: npm test -- adapters/${adapterName}`);

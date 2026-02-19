import { defineConfig } from 'vitest/config';

/**
 * Vitest config for schema-only tests
 * These tests don't require MCP connection - they just validate YAML files
 */
export default defineConfig({
  test: {
    include: [
      'tests/skills/schema.test.ts',
      'tests/entities/schema.test.ts',
    ],
    
    // No setup file - schema tests don't need MCP
    setupFiles: [],
    
    environment: 'node',
    testTimeout: 10000,
    reporter: ['verbose'],
  },
});

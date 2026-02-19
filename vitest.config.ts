import { defineConfig } from 'vitest/config';
import { resolve } from 'path';

export default defineConfig({
  resolve: {
    alias: {
      '@test': resolve(__dirname, 'tests/utils'),
    },
  },
  test: {
    include: [
      'skills/**/tests/**/*.test.ts',
      'tests/**/*.test.ts',
      'tests/skills/**/*.test.ts',
      'tests/entities/**/*.test.ts',
    ],
    exclude: [
      'skills/.needs-work/**',
      'node_modules/**',
    ],
    
    // Setup file runs in same process as tests
    setupFiles: ['./tests/setup.ts'],
    
    // Test environment
    environment: 'node',
    
    // Timeout for slow operations
    testTimeout: 30000,
    
    // Run tests sequentially (MCP connection is shared)
    pool: 'forks',
    poolOptions: {
      forks: {
        singleFork: true,  // All tests in one process to share MCP connection
      },
    },
    
    // Reporter
    reporter: ['verbose'],
  },
});

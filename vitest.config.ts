import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Look for tests in adapters and tests directories
    include: [
      'adapters/**/tests/**/*.test.ts',
      'tests/**/*.test.ts',
      'tests/adapters/**/*.test.ts',
      'tests/entities/**/*.test.ts',
    ],
    // Exclude adapters in .needs-work folder
    exclude: [
      'adapters/.needs-work/**',
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

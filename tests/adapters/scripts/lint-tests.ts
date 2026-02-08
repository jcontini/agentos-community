#!/usr/bin/env npx tsx
/**
 * Test Linter for Adapter Tests
 * 
 * Validates test files follow standards based on adapter capabilities.
 * Requirements are inferred from adapter YAML (auth, operations).
 * Adapters can declare exemptions with documented reasons.
 * 
 * Usage:
 *   npm run lint:tests              # Lint all adapters with tests
 *   npm run lint:tests -- linear    # Lint specific adapter
 *   npm run lint:tests -- --help    # Show help
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse as parseYaml } from 'yaml';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../../..');
const ADAPTERS_DIR = join(ROOT, 'adapters');

// =============================================================================
// Types
// =============================================================================

interface AdapterMeta {
  id: string;
  hasAuth: boolean;
  hasCreateOps: boolean;
  hasDeleteOps: boolean;
  firstReadAction: string | null;
  exemptions: {
    credential_handling?: string;
    cleanup?: string;
  };
}

interface Check {
  id: string;
  pattern: RegExp;
  description: string;
}

interface LintResult {
  adapter: string;
  meta: AdapterMeta;
  testFile: string | null;
  passed: boolean;
  checks: {
    required: Check[];
    passed: string[];
    failed: string[];
  };
  exemptions: string[];
}

// =============================================================================
// Check Definitions
// =============================================================================

const CHECKS: Record<string, Check> = {
  // Credential handling (for adapters with auth)
  skip_tests_variable: {
    id: 'skip_tests_variable',
    pattern: /let\s+skipTests\s*=\s*false/,
    description: 'let skipTests = false',
  },
  before_all_credential_check: {
    id: 'before_all_credential_check',
    pattern: /beforeAll[\s\S]*?Credential not found/,
    description: "beforeAll with 'Credential not found' check",
  },
  skip_check_in_tests: {
    id: 'skip_check_in_tests',
    pattern: /if\s*\(\s*skipTests\s*\)/,
    description: 'if (skipTests) in test cases',
  },
  
  // Cleanup (for adapters with create operations)
  after_all_cleanup: {
    id: 'after_all_cleanup',
    pattern: /afterAll[\s\S]*?createdItems/,
    description: 'afterAll with createdItems cleanup',
  },
  test_content_usage: {
    id: 'test_content_usage',
    pattern: /testContent\s*\(/,
    description: 'testContent() for unique test data',
  },
  
  // Always required
  fixtures_import: {
    id: 'fixtures_import',
    pattern: /from\s+['"].*fixtures['"]/,
    description: 'import from fixtures',
  },
  schema_validation: {
    id: 'schema_validation',
    pattern: /expect\s*\([^)]+\)\s*\.\s*(toBeDefined|toHaveProperty)\s*\(/,
    description: 'schema validation (toBeDefined or toHaveProperty)',
  },
};

// =============================================================================
// Adapter Parsing
// =============================================================================

function parseFrontmatter(content: string): any | null {
  if (!content.startsWith('---')) return null;
  const endIndex = content.indexOf('\n---', 3);
  if (endIndex === -1) return null;
  const yaml = content.slice(4, endIndex);
  return parseYaml(yaml);
}

function parseAdapterYaml(adapterDir: string): AdapterMeta | null {
  const readmePath = join(adapterDir, 'readme.md');
  if (!existsSync(readmePath)) return null;
  
  const content = readFileSync(readmePath, 'utf-8');
  const yaml = parseFrontmatter(content);
  if (!yaml) return null;
  
  // Extract operations from operations block
  const operationNames: string[] = [];
  let firstReadOperation: string | null = null;
  
  // Check operations block (format: "entity.operation")
  if (yaml.operations) {
    for (const operationName of Object.keys(yaml.operations)) {
      operationNames.push(operationName);
      // Check if it's a read operation (e.g., "task.get", "webpage.read")
      if (operationName.includes('.') && operationName.split('.')[1] === 'read' && !firstReadOperation) {
        firstReadOperation = operationName;
      }
    }
  }
  
  // Check if any operations are create/delete operations
  const hasCreateOps = operationNames.some(op => op.includes('.create'));
  const hasDeleteOps = operationNames.some(op => op.includes('.delete'));
  
  // Extract exemptions from testing.exempt
  const exemptions: AdapterMeta['exemptions'] = {};
  if (yaml.testing?.exempt) {
    if (typeof yaml.testing.exempt.credential_handling === 'string') {
      exemptions.credential_handling = yaml.testing.exempt.credential_handling;
    }
    if (typeof yaml.testing.exempt.cleanup === 'string') {
      exemptions.cleanup = yaml.testing.exempt.cleanup;
    }
  }
  
  return {
    id: yaml.id,
    hasAuth: yaml.auth !== null && yaml.auth !== undefined,
    hasCreateOps,
    hasDeleteOps,
    firstReadAction: firstReadOperation,
    exemptions,
  };
}

// =============================================================================
// Linting Logic
// =============================================================================

function getRequiredChecks(meta: AdapterMeta): Check[] {
  const checks: Check[] = [];
  
  // Always required
  checks.push(CHECKS.fixtures_import);
  checks.push(CHECKS.schema_validation);
  
  // Credential handling (unless exempt)
  if (meta.hasAuth && !meta.exemptions.credential_handling) {
    checks.push(CHECKS.skip_tests_variable);
    checks.push(CHECKS.before_all_credential_check);
    checks.push(CHECKS.skip_check_in_tests);
  }
  
  // Cleanup (unless exempt)
  if (meta.hasCreateOps && !meta.exemptions.cleanup) {
    checks.push(CHECKS.after_all_cleanup);
    checks.push(CHECKS.test_content_usage);
  }
  
  return checks;
}

function lintAdapter(adapterName: string): LintResult {
  const adapterDir = join(ADAPTERS_DIR, adapterName);
  const meta = parseAdapterYaml(adapterDir);
  
  if (!meta) {
    return {
      adapter: adapterName,
      meta: { id: adapterName, hasAuth: false, hasCreateOps: false, hasDeleteOps: false, firstReadAction: null, exemptions: {} },
      testFile: null,
      passed: false,
      checks: { required: [], passed: [], failed: ['adapter_yaml'] },
      exemptions: [],
    };
  }
  
  // Find test file
  const testDir = join(adapterDir, 'tests');
  const testFile = join(testDir, `${adapterName}.test.ts`);
  
  if (!existsSync(testFile)) {
    // No test file is okay - might be intentional
    return {
      adapter: adapterName,
      meta,
      testFile: null,
      passed: true,
      checks: { required: [], passed: [], failed: [] },
      exemptions: [],
    };
  }
  
  const testContent = readFileSync(testFile, 'utf-8');
  const requiredChecks = getRequiredChecks(meta);
  
  const passed: string[] = [];
  const failed: string[] = [];
  
  for (const check of requiredChecks) {
    if (check.pattern.test(testContent)) {
      passed.push(check.id);
    } else {
      failed.push(check.id);
    }
  }
  
  // Collect exemption messages
  const exemptions: string[] = [];
  if (meta.exemptions.credential_handling) {
    exemptions.push(`credential_handling: ${meta.exemptions.credential_handling}`);
  }
  if (meta.exemptions.cleanup) {
    exemptions.push(`cleanup: ${meta.exemptions.cleanup}`);
  }
  
  return {
    adapter: adapterName,
    meta,
    testFile,
    passed: failed.length === 0,
    checks: { required: requiredChecks, passed, failed },
    exemptions,
  };
}

// =============================================================================
// Output Formatting
// =============================================================================

function formatResult(result: LintResult): string {
  const lines: string[] = [];
  
  // Header with status
  const status = result.passed ? '✓' : '✗';
  lines.push(`${status} ${result.adapter}`);
  
  // Requirements summary
  const parts: string[] = [];
  parts.push(`auth: ${result.meta.hasAuth ? 'yes' : 'no'}`);
  parts.push(`create: ${result.meta.hasCreateOps ? 'yes' : 'no'}`);
  
  // What checks are needed
  const needsCredential = result.meta.hasAuth && !result.meta.exemptions.credential_handling;
  const needsCleanup = result.meta.hasCreateOps && !result.meta.exemptions.cleanup;
  
  if (needsCredential && needsCleanup) {
    parts.push('→ credential_handling + cleanup');
  } else if (needsCredential) {
    parts.push('→ credential_handling');
  } else if (needsCleanup) {
    parts.push('→ cleanup');
  } else {
    parts.push('→ minimal');
  }
  
  lines.push(`  ${parts.join(', ')}`);
  
  // Exemptions
  for (const exemption of result.exemptions) {
    lines.push(`  ⚠ exempt: ${exemption}`);
  }
  
  // No test file
  if (!result.testFile) {
    lines.push('  (no test file)');
    return lines.join('\n');
  }
  
  // Failed checks
  for (const checkId of result.checks.failed) {
    const check = CHECKS[checkId];
    if (check) {
      lines.push(`  ✗ missing: ${check.description}`);
    } else {
      lines.push(`  ✗ missing: ${checkId}`);
    }
  }
  
  return lines.join('\n');
}

// =============================================================================
// Main
// =============================================================================

function main() {
  const args = process.argv.slice(2);
  
  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
Test Linter for Adapter Tests

Usage:
  npm run lint:tests              # Lint all adapters with tests
  npm run lint:tests -- linear    # Lint specific adapter(s)

Checks are inferred from adapter YAML:
  - auth present → credential handling required
  - create operations → cleanup required

Adapters can exempt themselves in readme.md:
  testing:
    exempt:
      credential_handling: "reason"
      cleanup: "reason"
`);
    process.exit(0);
  }
  
  // Get adapters to lint
  const adapters = args.length > 0
    ? args
    : readdirSync(ADAPTERS_DIR, { withFileTypes: true })
        .filter(d => d.isDirectory())
        .map(d => d.name);
  
  console.log('Linting adapter tests...\n');
  
  const results: LintResult[] = [];
  
  for (const adapter of adapters) {
    const result = lintAdapter(adapter);
    results.push(result);
    console.log(formatResult(result));
    console.log();
  }
  
  // Summary
  const withTests = results.filter(r => r.testFile !== null);
  const passed = results.filter(r => r.passed);
  const failed = results.filter(r => !r.passed);
  
  console.log('─'.repeat(50));
  console.log(`${results.length} adapters, ${passed.length} passed, ${failed.length} failed`);
  
  if (withTests.length < results.length) {
    console.log(`(${results.length - withTests.length} adapters have no test file)`);
  }
  
  if (failed.length > 0) {
    process.exit(1);
  }
}

main();

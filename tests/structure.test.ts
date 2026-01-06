/**
 * Structure & Convention Validation Tests
 * 
 * Ensures all apps and connectors follow AgentOS standards.
 * These tests run without MCP - they just check the filesystem and YAML.
 * 
 * Run on every commit via pre-commit hook.
 * 
 * ## Testing Strategy
 * 
 * - Pre-commit: Runs structure tests + tests for changed apps/connectors only
 * - CI: Runs all tests
 * 
 * See scripts/test-changed.sh for the dynamic test runner.
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, existsSync, readFileSync } from 'fs';
import { join } from 'path';

const INTEGRATIONS_ROOT = join(__dirname, '..');
const APPS_DIR = join(INTEGRATIONS_ROOT, 'apps');

// Get all app directories
const getApps = () => readdirSync(APPS_DIR, { withFileTypes: true })
  .filter(d => d.isDirectory())
  .map(d => d.name);

// Get all connectors (nested inside apps: apps/{app}/connectors/{connector}/)
interface ConnectorInfo {
  app: string;
  connector: string;
  dir: string;
}

const getConnectors = (): ConnectorInfo[] => {
  const connectors: ConnectorInfo[] = [];
  for (const app of getApps()) {
    const connectorsDir = join(APPS_DIR, app, 'connectors');
    if (existsSync(connectorsDir)) {
      const dirs = readdirSync(connectorsDir, { withFileTypes: true })
        .filter(d => d.isDirectory())
        .map(d => d.name);
      for (const connector of dirs) {
        connectors.push({
          app,
          connector,
          dir: join(connectorsDir, connector)
        });
      }
    }
  }
  return connectors;
};

// Parse YAML-ish content (simple extraction, not full YAML parse)
const extractYamlSection = (content: string, section: string): string | null => {
  const regex = new RegExp(`^${section}:([\\s\\S]*?)(?=^\\w+:|$)`, 'm');
  const match = content.match(regex);
  return match ? match[1] : null;
};

// =============================================================================
// APP STRUCTURE TESTS
// =============================================================================

describe('App Structure', () => {
  const apps = getApps();

  it('has at least one app', () => {
    expect(apps.length).toBeGreaterThan(0);
  });

  describe.each(apps)('apps/%s', (app) => {
    const appDir = join(APPS_DIR, app);
    const readmePath = join(appDir, 'readme.md');
    const readme = existsSync(readmePath) ? readFileSync(readmePath, 'utf-8') : '';

    it('has readme.md', () => {
      expect(existsSync(readmePath)).toBe(true);
    });

    it('has icon.svg', () => {
      expect(existsSync(join(appDir, 'icon.svg'))).toBe(true);
    });

    it('readme.md has a title', () => {
      expect(readme).toMatch(/^#\s+\w+/m);
    });

    // Data apps should have schema: in readme.md
    it('data apps have schema in readme', () => {
      const readmeLower = readme.toLowerCase();
      const isDataApp = readmeLower.includes('local database') ||
                        readmeLower.includes('per-app database');
      
      if (isDataApp) {
        expect(readme).toMatch(/^schema:/m);
      }
    });
  });
});

// =============================================================================
// SCHEMA CONVENTION TESTS
// =============================================================================

describe('Schema Conventions', () => {
  const apps = getApps();

  describe.each(apps)('apps/%s schema', (app) => {
    const readmePath = join(APPS_DIR, app, 'readme.md');
    const readme = existsSync(readmePath) ? readFileSync(readmePath, 'utf-8') : '';
    const hasSchema = /^schema:/m.test(readme);
    
    // Check if app has local storage connector
    const localConnectorPath = join(APPS_DIR, app, 'connectors', 'local');
    const hasLocalStorage = existsSync(localConnectorPath);

    // Skip apps without schema
    if (!hasSchema) {
      it.skip('no schema defined', () => {});
      return;
    }

    // Apps without connectors/local/ don't store data locally
    if (!hasLocalStorage) {
      it.skip('no local storage (external connector only)', () => {});
      return;
    }

    // Apps WITH local storage need refs/metadata/timestamps for dedup and tracking
    it('has refs for external IDs', () => {
      expect(readme).toMatch(/refs.*type.*object/is);
    });

    it('has metadata field', () => {
      expect(readme).toMatch(/metadata.*type.*object/is);
    });

    it('has timestamp fields', () => {
      expect(readme).toMatch(/created_at/i);
      expect(readme).toMatch(/updated_at/i);
    });
  });
});

// =============================================================================
// ACTION CONVENTION TESTS
// =============================================================================

describe('Action Conventions', () => {
  const apps = getApps();

  describe.each(apps)('apps/%s actions', (app) => {
    const readmePath = join(APPS_DIR, app, 'readme.md');
    const readme = existsSync(readmePath) ? readFileSync(readmePath, 'utf-8') : '';
    const actionsSection = extractYamlSection(readme, 'actions');
    const hasSchema = /^schema:/m.test(readme);

    // Skip if no actions section
    if (!actionsSection) {
      it.skip('no actions defined', () => {});
      return;
    }

    // Data apps should have pull and/or push for data transfer
    if (hasSchema) {
      it('data app has pull or push action for data transfer', () => {
        const hasPull = /^\s+pull:/m.test(actionsSection);
        const hasPush = /^\s+push:/m.test(actionsSection);
        expect(hasPull || hasPush).toBe(true);
      });
    }
  });
});

// =============================================================================
// CONNECTOR STRUCTURE TESTS
// =============================================================================

describe('Connector Structure', () => {
  const connectors = getConnectors();

  it('has at least one connector', () => {
    expect(connectors.length).toBeGreaterThan(0);
  });

  describe.each(connectors)('apps/$app/connectors/$connector', ({ app, connector, dir }) => {
    it('has readme.md', () => {
      expect(existsSync(join(dir, 'readme.md'))).toBe(true);
    });

    it('has icon', () => {
      const files = readdirSync(dir);
      const hasIcon = files.some(f => f.startsWith('icon.'));
      expect(hasIcon).toBe(true);
    });

    it('has actions in readme.md frontmatter', () => {
      const readmePath = join(dir, 'readme.md');
      if (existsSync(readmePath)) {
        const readme = readFileSync(readmePath, 'utf-8');
        expect(readme).toMatch(/^actions:/m);
      }
    });
  });
});

// =============================================================================
// ICON QUALITY TESTS
// =============================================================================

describe('Icon Quality', () => {
  const apps = getApps();

  describe.each(apps)('apps/%s icon', (app) => {
    const iconPath = join(APPS_DIR, app, 'icon.svg');
    const icon = existsSync(iconPath) ? readFileSync(iconPath, 'utf-8') : '';

    it('is valid SVG', () => {
      if (icon) {
        expect(icon).toContain('<svg');
        expect(icon).toContain('</svg>');
      }
    });

    it('uses viewBox for scalability', () => {
      if (icon) {
        expect(icon).toContain('viewBox');
      }
    });

    it('uses currentColor for theming', () => {
      if (icon) {
        expect(icon.toLowerCase()).toMatch(/fill="currentcolor"|stroke="currentcolor"|fill="none"/);
      }
    });

    it('has no hardcoded colors', () => {
      if (icon) {
        const hasHardcodedColor = /#[0-9a-fA-F]{3,6}/.test(icon) ||
                                  /fill="(?!currentColor|none)[a-z]+"/i.test(icon) ||
                                  /stroke="(?!currentColor|none)[a-z]+"/i.test(icon);
        expect(hasHardcodedColor).toBe(false);
      }
    });

    it('is under 5KB', () => {
      if (icon) {
        expect(icon.length).toBeLessThan(5000);
      }
    });
  });
});

// =============================================================================
// FILE HYGIENE
// =============================================================================

describe('File Hygiene', () => {
  const apps = getApps();
  const connectors = getConnectors();

  it('no schema.sql files in apps (schema is defined in readme.md YAML)', () => {
    for (const app of apps) {
      const schemaPath = join(APPS_DIR, app, 'schema.sql');
      expect(existsSync(schemaPath)).toBe(false);
    }
  });

  it('no mapping.yaml files in connectors (actions are in readme.md)', () => {
    for (const { dir } of connectors) {
      const mappingPath = join(dir, 'mapping.yaml');
      expect(existsSync(mappingPath)).toBe(false);
    }
  });
});

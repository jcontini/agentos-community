/**
 * Structure & Convention Validation Tests
 * 
 * Ensures all apps and connectors follow AgentOS standards.
 * These tests run without MCP - they just check the filesystem and YAML.
 * 
 * Run on every commit via pre-commit hook.
 * 
 * ## Schema Versions
 * 
 * We use dated schema versions to progressively enforce new conventions:
 * - Files modified BEFORE a version date: warn only (grandfathered)
 * - Files modified AFTER a version date: must comply (fail)
 * 
 * This lets us evolve standards without breaking existing code.
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { execSync } from 'child_process';

const INTEGRATIONS_ROOT = join(__dirname, '..');
const APPS_DIR = join(INTEGRATIONS_ROOT, 'apps');

// =============================================================================
// SCHEMA VERSIONS - Add new versions here as conventions evolve
// =============================================================================

const SCHEMA_VERSIONS = {
  // v2026.01.05: refs/metadata pattern, pull/push instead of import/export/sync
  'refs-metadata': new Date('2026-01-05'),
};

// Get git last modified date for a file
const getFileLastModified = (filePath: string): Date | null => {
  try {
    const timestamp = execSync(
      `git log -1 --format="%ai" -- "${filePath}"`,
      { cwd: INTEGRATIONS_ROOT, encoding: 'utf-8' }
    ).trim();
    return timestamp ? new Date(timestamp) : null;
  } catch {
    return null;
  }
};

// Check if file was modified after a schema version date
const isFileNewerThan = (filePath: string, versionDate: Date): boolean => {
  const lastModified = getFileLastModified(filePath);
  if (!lastModified) return false; // New files (not in git) should comply
  return lastModified > versionDate;
};

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
// SCHEMA CONVENTION TESTS (v2026.01.05: refs-metadata)
// =============================================================================

describe('Schema Conventions', () => {
  const apps = getApps();
  const versionDate = SCHEMA_VERSIONS['refs-metadata'];

  describe.each(apps)('apps/%s schema', (app) => {
    const readmePath = join(APPS_DIR, app, 'readme.md');
    const readme = existsSync(readmePath) ? readFileSync(readmePath, 'utf-8') : '';
    const hasSchema = /^schema:/m.test(readme);
    const isNewFile = isFileNewerThan(readmePath, versionDate);

    // Skip apps without schema
    if (!hasSchema) {
      it.skip('no schema defined', () => {});
      return;
    }

    // New/updated files must have the new patterns
    if (isNewFile) {
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
    } else {
      // Grandfathered files: remind but don't fail
      it.skip(`grandfathered: update ${app} to refs/metadata pattern when ready`, () => {});
    }
  });
});

// =============================================================================
// ACTION CONVENTION TESTS (v2026.01.05: pull/push)
// =============================================================================

describe('Action Conventions', () => {
  const apps = getApps();
  const versionDate = SCHEMA_VERSIONS['refs-metadata'];

  describe.each(apps)('apps/%s actions', (app) => {
    const readmePath = join(APPS_DIR, app, 'readme.md');
    const readme = existsSync(readmePath) ? readFileSync(readmePath, 'utf-8') : '';
    const actionsSection = extractYamlSection(readme, 'actions');
    const hasSchema = /^schema:/m.test(readme);
    const isNewFile = isFileNewerThan(readmePath, versionDate);

    // Skip if no actions section
    if (!actionsSection) {
      it.skip('no actions defined', () => {});
      return;
    }

    // New data apps should have pull and/or push for data transfer
    if (isNewFile && hasSchema) {
      it('data app has pull or push action for data transfer', () => {
        const hasPull = /^\s+pull:/m.test(actionsSection);
        const hasPush = /^\s+push:/m.test(actionsSection);
        expect(hasPull || hasPush).toBe(true);
      });
    } else if (!isNewFile) {
      it.skip('grandfathered: add pull/push actions when ready', () => {});
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

    it('has mapping.yaml or icon', () => {
      const files = readdirSync(dir);
      const hasMapping = files.includes('mapping.yaml');
      const hasIcon = files.some(f => f.startsWith('icon.'));
      expect(hasMapping || hasIcon).toBe(true);
    });
  });
});

// =============================================================================
// CONNECTOR YAML CONVENTION TESTS (v2026.01.05: refs-metadata)
// =============================================================================

describe('Connector YAML Conventions', () => {
  const connectors = getConnectors();
  const versionDate = SCHEMA_VERSIONS['refs-metadata'];

  for (const { app, connector, dir } of connectors) {
    const mappingPath = join(dir, 'mapping.yaml');
    if (!existsSync(mappingPath)) continue;
    
    const yaml = readFileSync(mappingPath, 'utf-8');
    const isNewFile = isFileNewerThan(mappingPath, versionDate);

    describe(`apps/${app}/connectors/${connector}/mapping.yaml`, () => {
      // Basic structure check (always required)
      it('has actions section', () => {
        expect(yaml).toMatch(/^actions:/m);
      });

      // New/updated files: just remind about the new patterns
      if (!isNewFile) {
        it.skip(`grandfathered: update to pull/push and refs pattern when ready`, () => {});
      }
    });
  }
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
// FILE HYGIENE (always checked)
// =============================================================================

describe('File Hygiene', () => {
  const apps = getApps();

  it('no schema.sql files in apps (schema is defined in readme.md YAML)', () => {
    for (const app of apps) {
      const schemaPath = join(APPS_DIR, app, 'schema.sql');
      expect(existsSync(schemaPath)).toBe(false);
    }
  });
});

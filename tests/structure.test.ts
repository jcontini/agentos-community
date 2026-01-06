/**
 * Structure & Convention Validation Tests
 * 
 * Fast filesystem checks that run on every commit.
 * Validates that apps and connectors follow AgentOS standards.
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

// Get all connectors
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

// =============================================================================
// APP STRUCTURE
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

    it('readme.md has title', () => {
      expect(readme).toMatch(/^#\s+\w+/m);
    });

    it('readme.md has schema', () => {
      expect(readme).toMatch(/^schema:/m);
    });

    it('readme.md has actions', () => {
      expect(readme).toMatch(/^actions:/m);
    });
  });
});

// =============================================================================
// CONNECTOR STRUCTURE
// =============================================================================

describe('Connector Structure', () => {
  const connectors = getConnectors();

  it('has at least one connector', () => {
    expect(connectors.length).toBeGreaterThan(0);
  });

  describe.each(connectors)('apps/$app/connectors/$connector', ({ dir }) => {
    it('has readme.md', () => {
      expect(existsSync(join(dir, 'readme.md'))).toBe(true);
    });

    it('has icon', () => {
      const files = readdirSync(dir);
      expect(files.some(f => f.startsWith('icon.'))).toBe(true);
    });

    it('has actions in readme.md', () => {
      const readme = readFileSync(join(dir, 'readme.md'), 'utf-8');
      expect(readme).toMatch(/^actions:/m);
    });
  });
});

// =============================================================================
// ICON QUALITY (app icons only - connector icons can be PNGs)
// =============================================================================

describe('Icon Quality', () => {
  const apps = getApps();

  describe.each(apps)('apps/%s icon', (app) => {
    const iconPath = join(APPS_DIR, app, 'icon.svg');
    const icon = existsSync(iconPath) ? readFileSync(iconPath, 'utf-8') : '';

    it('is valid SVG', () => {
      expect(icon).toContain('<svg');
      expect(icon).toContain('</svg>');
    });

    it('uses viewBox', () => {
      expect(icon).toContain('viewBox');
    });

    it('uses currentColor for theming', () => {
      expect(icon.toLowerCase()).toMatch(/fill="currentcolor"|stroke="currentcolor"|fill="none"/);
    });

    it('has no hardcoded colors', () => {
      const hasHardcodedColor = /#[0-9a-fA-F]{3,6}/.test(icon) ||
                                /fill="(?!currentColor|none)[a-z]+"/i.test(icon) ||
                                /stroke="(?!currentColor|none)[a-z]+"/i.test(icon);
      expect(hasHardcodedColor).toBe(false);
    });

    it('is under 5KB', () => {
      expect(icon.length).toBeLessThan(5000);
    });
  });
});

// =============================================================================
// FILE HYGIENE (prevent old patterns)
// =============================================================================

describe('File Hygiene', () => {
  const apps = getApps();
  const connectors = getConnectors();

  it('no schema.sql files (schema in readme.md)', () => {
    for (const app of apps) {
      expect(existsSync(join(APPS_DIR, app, 'schema.sql'))).toBe(false);
    }
  });

  it('no mapping.yaml files (actions in readme.md)', () => {
    for (const { dir } of connectors) {
      expect(existsSync(join(dir, 'mapping.yaml'))).toBe(false);
    }
  });
});

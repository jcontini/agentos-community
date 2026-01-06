/**
 * Books App Tests
 * 
 * Minimal validation - structure tests cover the rest.
 */

import { describe, it, expect } from 'vitest';
import { existsSync, readFileSync } from 'fs';
import { join } from 'path';

const appDir = join(__dirname, '..');

describe('Books App', () => {
  it('has readme.md with frontmatter', () => {
    const readmePath = join(appDir, 'readme.md');
    expect(existsSync(readmePath)).toBe(true);
    
    const content = readFileSync(readmePath, 'utf-8');
    expect(content.startsWith('---')).toBe(true);
    expect(content).toContain('schema:');
    expect(content).toContain('actions:');
  });
});

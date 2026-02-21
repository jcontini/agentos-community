/**
 * Skill Schema Validation Tests
 * 
 * Validates:
 * - All skill readme.md files have valid YAML frontmatter conforming to skill schema
 * - Required files (icon.svg or icon.png) exist
 * - Skills have operations or utilities
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { parse as parseYaml } from 'yaml';

const INTEGRATIONS_ROOT = join(__dirname, '../..');
const SKILLS_DIR = join(INTEGRATIONS_ROOT, 'skills');
const SCHEMA_PATH = join(__dirname, 'skill.schema.json');

const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf-8'));
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);

const getSkills = (): string[] => {
  const skills: string[] = [];
  
  const scan = (dir: string, relativePath: string = '') => {
    const entries = readdirSync(dir, { withFileTypes: true });
    
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (entry.name === '.needs-work') continue;
      if (entry.name === 'node_modules') continue;
      if (entry.name === 'tests') continue;
      
      const fullPath = join(dir, entry.name);
      const entryRelativePath = relativePath ? `${relativePath}/${entry.name}` : entry.name;
      
      if (existsSync(join(fullPath, 'readme.md'))) {
        skills.push(entryRelativePath);
      } else {
        scan(fullPath, entryRelativePath);
      }
    }
  };
  
  scan(SKILLS_DIR);
  return skills;
};

// Parse YAML frontmatter from markdown
function parseFrontmatter(content: string): Record<string, unknown> | null {
  if (!content.startsWith('---')) return null;
  const endIndex = content.indexOf('\n---', 3);
  if (endIndex === -1) return null;
  const yaml = content.slice(4, endIndex);
  return parseYaml(yaml);
}

describe('Skill Schema Validation', () => {
  const skills = getSkills();

  it('schema file exists', () => {
    expect(existsSync(SCHEMA_PATH)).toBe(true);
  });

  it('has skills to validate', () => {
    expect(skills.length).toBeGreaterThan(0);
  });

  describe.each(skills)('skills/%s', (skillPath) => {
    const readmePath = join(SKILLS_DIR, skillPath, 'readme.md');

    it('has readme.md', () => {
      expect(existsSync(readmePath)).toBe(true);
    });

    it('has valid YAML frontmatter', () => {
      const content = readFileSync(readmePath, 'utf-8');
      const frontmatter = parseFrontmatter(content);
      expect(frontmatter).not.toBeNull();
    });

    it('conforms to skill schema', () => {
      const content = readFileSync(readmePath, 'utf-8');
      const frontmatter = parseFrontmatter(content);
      if (!frontmatter) {
        throw new Error('No frontmatter found');
      }

      const valid = validate(frontmatter);
      if (!valid) {
        const errors = validate.errors?.map(e => 
          `  ${e.instancePath || '/'}: ${e.message}`
        ).join('\n');
        throw new Error(`Schema validation failed:\n${errors}`);
      }
      expect(valid).toBe(true);
    });

    it('has required icon file', () => {
      const skillDir = join(SKILLS_DIR, skillPath);
      const files = readdirSync(skillDir);
      const hasIcon = files.includes('icon.svg') || files.includes('icon.png');
      expect(hasIcon).toBe(true);
    });
  });
});

describe('Schema Completeness', () => {
  it('no skills have tags (deprecated)', () => {
    for (const skillPath of getSkills()) {
      const content = readFileSync(join(SKILLS_DIR, skillPath, 'readme.md'), 'utf-8');
      const frontmatter = parseFrontmatter(content);
      expect(frontmatter?.tags, `${skillPath} should not have tags (deprecated)`).toBeUndefined();
    }
  });

  it('all skills have at least one operation, utility, action, or agent block', () => {
    for (const skillPath of getSkills()) {
      const content = readFileSync(join(SKILLS_DIR, skillPath, 'readme.md'), 'utf-8');
      const frontmatter = parseFrontmatter(content);
      const operations = frontmatter?.operations as Record<string, unknown> | undefined;
      const utilities = frontmatter?.utilities as Record<string, unknown> | undefined;
      const actions = frontmatter?.actions as Record<string, unknown> | undefined;
      const agent = frontmatter?.agent;

      const hasOperations = operations && Object.keys(operations).length > 0;
      const hasUtilities = utilities && Object.keys(utilities).length > 0;
      const hasActions = actions && Object.keys(actions).length > 0;
      const isAgentSkill = !!agent;

      expect(
        hasOperations || hasUtilities || hasActions || isAgentSkill,
        `${skillPath} must have 'operations', 'utilities', 'actions', or 'agent' block`
      ).toBe(true);
    }
  });
});

#!/usr/bin/env node
/**
 * Split readme.md YAML frontmatter into skill.yaml and markdown-only readme.
 * Only touches skills with a single opening --- and closing --- before the doc body.
 *
 * Usage: node scripts/skills/extract-skill-yaml.mjs <skill-id> [...]
 */

import { existsSync, readFileSync, writeFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../..');
const SKILLS_DIR = join(ROOT, 'skills');

/** First --- … \n---\n … rest (body may be empty) */
const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/;

const ids = process.argv.slice(2).filter((a) => !a.startsWith('-'));
if (ids.length === 0) {
  console.error('Usage: node scripts/skills/extract-skill-yaml.mjs <skill-id> [...]');
  process.exit(1);
}

let failed = 0;
for (const name of ids) {
  const dir = join(SKILLS_DIR, name);
  const readmePath = join(dir, 'readme.md');
  const yamlPath = join(dir, 'skill.yaml');

  if (existsSync(yamlPath)) {
    console.error(`skip ${name}: skill.yaml already exists`);
    continue;
  }
  if (!existsSync(readmePath)) {
    console.error(`skip ${name}: missing readme.md`);
    failed++;
    continue;
  }

  const text = readFileSync(readmePath, 'utf8');
  const m = text.match(FRONTMATTER);
  if (!m) {
    console.error(`skip ${name}: no standard YAML frontmatter (need --- … --- before markdown)`);
    failed++;
    continue;
  }

  const yamlBody = m[1].trimEnd() + '\n';
  const mdBody = m[2].replace(/^\r?\n/, '');
  writeFileSync(yamlPath, yamlBody, 'utf8');
  writeFileSync(readmePath, mdBody, 'utf8');
  console.log(`ok ${name}`);
}

if (failed > 0) process.exit(1);

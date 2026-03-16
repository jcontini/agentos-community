#!/usr/bin/env node

import { existsSync, readFileSync, readdirSync, statSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { parse as parseYaml } from 'yaml';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../..');
const SKILLS_DIR = join(ROOT, 'skills');

const INLINE_PRIMITIVE_TYPES = new Set(['string', 'number', 'integer', 'boolean', 'object', 'array', 'null', 'void']);
const REQUEST_TEMPLATE_ROOTS = new Set(['params', 'auth', 'item']);
const LEGACY_AUTH_PATTERNS = [
  /(^|[^A-Za-z0-9_])\.params\.auth(?:[.\[]|$)/,
  /(^|[^A-Za-z0-9_])\.params\.auth_key(?:[^A-Za-z0-9_]|$)/,
  /(^|[^A-Za-z0-9_])\.auth_key(?:[^A-Za-z0-9_]|$)/,
];

function parseArgs(argv) {
  const flags = new Map();
  const positionals = [];

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith('--')) {
      positionals.push(arg);
      continue;
    }

    const next = argv[i + 1];
    if (next && !next.startsWith('--')) {
      flags.set(arg, next);
      i++;
    } else {
      flags.set(arg, true);
    }
  }

  return { flags, positionals };
}

const { flags, positionals } = parseArgs(process.argv.slice(2));
const filterValue = typeof flags.get('--filter') === 'string' ? flags.get('--filter') : null;
const includeNeedsWork = !!flags.get('--include-needs-work');
const strict = !!flags.get('--strict');

function loadFrontmatter(skillDir) {
  const readmePath = join(skillDir, 'readme.md');
  const raw = readFileSync(readmePath, 'utf8');
  const match = raw.match(/^---\r?\n([\s\S]*?)\n---\r?\n?/);
  if (!match) {
    throw new Error(`Missing frontmatter in ${readmePath}`);
  }
  return parseYaml(match[1]);
}

function topLevelSkillDirs() {
  return readdirSync(SKILLS_DIR)
    .filter(name => !name.startsWith('.'))
    .map(name => join(SKILLS_DIR, name))
    .filter(path => statSync(path).isDirectory() && existsSync(join(path, 'readme.md')));
}

function needsWorkSkillDirs() {
  const needsWorkRoot = join(SKILLS_DIR, '.needs-work');
  try {
    return readdirSync(needsWorkRoot)
      .map(name => join(needsWorkRoot, name))
      .filter(path => statSync(path).isDirectory())
      .flatMap(path => collectNestedSkillDirs(path));
  } catch {
    return [];
  }
}

function collectNestedSkillDirs(root) {
  const dirs = [];
  const entries = readdirSync(root);

  if (entries.includes('readme.md')) {
    dirs.push(root);
  }

  for (const entry of entries) {
    const fullPath = join(root, entry);
    try {
      if (statSync(fullPath).isDirectory()) {
        dirs.push(...collectNestedSkillDirs(fullPath));
      }
    } catch {
      // Ignore unreadable paths.
    }
  }

  return dirs;
}

function collectSkillDirs() {
  let dirs = topLevelSkillDirs();
  if (includeNeedsWork) {
    dirs = dirs.concat(needsWorkSkillDirs());
  }

  if (positionals.length > 0) {
    const requested = new Set(positionals);
    dirs = dirs.filter(dir => requested.has(skillIdForDir(dir)));
  }

  if (filterValue) {
    dirs = dirs.filter(dir => skillIdForDir(dir).includes(filterValue));
  }

  return dirs.sort((a, b) => skillIdForDir(a).localeCompare(skillIdForDir(b)));
}

function skillIdForDir(skillDir) {
  return skillDir.replace(`${SKILLS_DIR}/`, '').replace('/readme.md', '').split('/').at(-1);
}

function looksLikeExpression(value) {
  if (typeof value !== 'string') return false;
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (trimmed.startsWith('./') || trimmed.startsWith('../')) return false;

  return trimmed.startsWith('.params')
    || trimmed.startsWith('.auth')
    || trimmed.startsWith('.item')
    || trimmed.startsWith('.[')
    || trimmed.startsWith('"')
    || trimmed.startsWith('\'')
    || trimmed.startsWith('if ')
    || trimmed.startsWith('try ')
    || trimmed.startsWith('(')
    || trimmed.startsWith('[')
    || trimmed.startsWith('{')
    || trimmed.includes(' | ')
    || trimmed.includes(' // ')
    || trimmed.includes('.params')
    || trimmed.includes('.auth')
    || trimmed.includes('.item');
}

function returnsEntityName(op) {
  if (!op || typeof op.returns !== 'string') return null;
  const entityName = op.returns.replace(/\[\]$/, '');
  return INLINE_PRIMITIVE_TYPES.has(entityName) ? null : entityName;
}

function issue(level, path, message) {
  return { level, path, message };
}

function walkStrings(value, path, visit) {
  if (typeof value === 'string') {
    visit(value, path);
    return;
  }

  if (Array.isArray(value)) {
    value.forEach((item, index) => walkStrings(item, `${path}[${index}]`, visit));
    return;
  }

  if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      const childPath = path ? `${path}.${key}` : key;
      walkStrings(child, childPath, visit);
    }
  }
}

function requestRootWarnings(value, path) {
  const warnings = [];

  walkStrings(value, path, (str, strPath) => {
    if (!looksLikeExpression(str)) return;

    const roots = [...str.matchAll(/(^|[^A-Za-z0-9_])\.([A-Za-z_][A-Za-z0-9_]*)/g)]
      .map(match => match[2])
      .filter(root => root !== ''); // ignore bare "."

    for (const root of roots) {
      if (!REQUEST_TEMPLATE_ROOTS.has(root)) {
        warnings.push(
          issue(
            'warn',
            strPath,
            `suspicious request-template root '.${root}' — prefer .params.*, .auth.*, or .item.*`
          )
        );
      }
    }
  });

  return warnings;
}

function lintSkill(frontmatter) {
  const issues = [];
  const adapters = frontmatter.adapters && typeof frontmatter.adapters === 'object'
    ? Object.keys(frontmatter.adapters)
    : [];
  const adapterSet = new Set(adapters);
  const returnedEntities = new Set();

  if (frontmatter.api?.base_url) {
    issues.push(issue('error', 'api.base_url', 'remove dead REST shortcut; use absolute rest.url values'));
  }

  if (frontmatter.api?.graphql) {
    issues.push(issue('error', 'api.graphql', 'rename to api.graphql_endpoint'));
  }

  walkStrings(frontmatter, '', (value, path) => {
    if (value.includes('{{')) {
      issues.push(issue('error', path, 'legacy mustache template found; use jaq expressions'));
    }

    if (/\{(?:token|apikey|api_key|secretapikey|secret_api_key|auth_key|access_token|refresh_token|client_id|client_secret)\}/i.test(value)) {
      issues.push(issue('error', path, 'legacy {token}-style placeholder found; use .auth.* expressions'));
    }

    if (LEGACY_AUTH_PATTERNS.some(pattern => pattern.test(value))) {
      issues.push(issue('error', path, 'legacy auth variable root found; use .auth.*'));
    }
  });

  const ops = { ...(frontmatter.operations || {}), ...(frontmatter.utilities || {}) };
  for (const [opName, op] of Object.entries(ops)) {
    if (!/^[a-z0-9_]+$/.test(opName)) {
      issues.push(issue('warn', `operations.${opName}`, 'tool name is not simple snake_case'));
    }

    const entityName = returnsEntityName(op);
    if (entityName) {
      returnedEntities.add(entityName);
      if (!adapterSet.has(entityName)) {
        issues.push(
          issue(
            'error',
            `operations.${opName}.returns`,
            `returns '${entityName}' but adapters.${entityName} is missing`
          )
        );
      }
    }

    if (op.rest) {
      if (typeof op.rest.url === 'string' && !/^https?:\/\//.test(op.rest.url) && !looksLikeExpression(op.rest.url)) {
        issues.push(issue('error', `operations.${opName}.rest.url`, 'REST url must be absolute or a jaq expression that resolves to one'));
      }
      issues.push(...requestRootWarnings(op.rest.headers, `operations.${opName}.rest.headers`));
      issues.push(...requestRootWarnings(op.rest.query, `operations.${opName}.rest.query`));
    }

    if (op.graphql) {
      issues.push(...requestRootWarnings(op.graphql.endpoint, `operations.${opName}.graphql.endpoint`));
    }

    if (op.command?.env) {
      issues.push(...requestRootWarnings(op.command.env, `operations.${opName}.command.env`));
    }
  }

  for (const adapterName of adapters) {
    if (!returnedEntities.has(adapterName)) {
      issues.push(issue('warn', `adapters.${adapterName}`, 'adapter is defined but no operation returns it'));
    }
  }

  issues.push(...requestRootWarnings(frontmatter.auth, 'auth'));

  return issues;
}

function printIssues(skillId, issues) {
  console.log(`\n${skillId}`);
  for (const item of issues) {
    const tag = item.level === 'error' ? 'ERROR' : 'WARN ';
    console.log(`  ${tag} ${item.path}: ${item.message}`);
  }
}

function main() {
  const skillDirs = collectSkillDirs();
  if (skillDirs.length === 0) {
    console.log('No skills to lint.');
    process.exit(0);
  }

  let errorCount = 0;
  let warningCount = 0;
  let affectedSkills = 0;

  for (const skillDir of skillDirs) {
    const frontmatter = loadFrontmatter(skillDir);
    const issues = lintSkill(frontmatter);
    if (issues.length === 0) continue;

    affectedSkills++;
    errorCount += issues.filter(item => item.level === 'error').length;
    warningCount += issues.filter(item => item.level === 'warn').length;
    printIssues(frontmatter.id || skillIdForDir(skillDir), issues);
  }

  console.log(`\nSemantic lint summary: ${affectedSkills}/${skillDirs.length} skills flagged, ${errorCount} errors, ${warningCount} warnings`);
  process.exit(strict && errorCount > 0 ? 1 : 0);
}

main();

#!/usr/bin/env npx tsx
/**
 * Skill Scaffold Generator
 *
 * Creates a modern AgentOS skill scaffold using the current community
 * contract.
 *
 * Usage:
 *   npm run new-skill -- my-skill
 *   npm run new-skill -- my-skill --readonly
 *   npm run new-skill -- my-skill --local
 *   npm run new-skill -- my-skill --local-control
 */

import { existsSync, mkdirSync, writeFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '../..');
const SKILLS_DIR = join(ROOT, 'skills');

const args = process.argv.slice(2);

if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
  console.log(`
Skill Scaffold Generator

Usage:
  npm run new-skill -- <name>
  npm run new-skill -- <name> --readonly
  npm run new-skill -- <name> --local
  npm run new-skill -- <name> --local-control

Modes:
  default          Entity-returning skill with adapters + operations
  --readonly       Search/read-only entity skill
  --local          Local entity skill with auth: none
  --local-control  Local-control skill with inline-schema operations
`);
  process.exit(0);
}

const skillName = args[0];
const isReadonly = args.includes('--readonly');
const isLocal = args.includes('--local');
const isLocalControl = args.includes('--local-control');

if (!/^[a-z][a-z0-9-]*$/.test(skillName)) {
  console.error(`❌ Invalid skill name: ${skillName}`);
  console.error('   Must start with lowercase letter and contain only a-z, 0-9, and -');
  process.exit(1);
}

const skillDir = join(SKILLS_DIR, skillName);
if (existsSync(skillDir)) {
  console.error(`❌ Skill already exists: ${skillDir}`);
  process.exit(1);
}

const displayName = skillName
  .split('-')
  .map(word => word.charAt(0).toUpperCase() + word.slice(1))
  .join(' ');

function entityReadme(): string {
  const authBlock = isLocal ? 'auth: none' : `auth:
  header:
    Authorization: '"Bearer " + .auth.key'
  label: API Key
  help_url: https://example.com/api-keys`;

  const writeOps = isReadonly ? '' : `
  create_item:
    description: Create an item
    returns: item
    params:
      title: { type: string, required: true }
      text: { type: string, required: false }
    rest:
      method: POST
      url: https://api.example.com/items
      body:
        title: .params.title
        text: '.params.text // ""'
      response:
        root: /

  update_item:
    description: Update an item
    returns: item
    params:
      id: { type: string, required: true }
      title: { type: string, required: false }
      text: { type: string, required: false }
    rest:
      method: PATCH
      url: '"https://api.example.com/items/" + .params.id'
      body:
        title: .params.title
        text: .params.text
      response:
        root: /`;

  const inlineActionBlock = isReadonly ? '' : `
  delete_item:
    description: Delete an item
    returns:
      ok: boolean
      id: string
    params:
      id:
        type: string
        required: true
        description: Item id to delete
    command:
      binary: python3
      args:
        - -c
        - |
          import json, sys
          params = json.loads(sys.stdin.read() or "{}")
          print(json.dumps({"ok": True, "id": params.get("id", "")}))
      stdin: .params | tojson
      timeout: 10`;

  return `---
id: ${skillName}
name: ${displayName}
description: TODO: Describe what this skill does
icon: icon.svg
color: "#4A5568"
website: https://example.com
${authBlock}

adapters:
  item:
    id: '.id // .url'
    name: '.title // .name'
    text: '.text // .summary // ""'
    url: .url
    image: .image
    author: .author
    datePublished: '.published_at // .datePublished'
    data.raw: .

operations:
  search:
    description: Search items
    returns: item[]
    params:
      query: { type: string, required: true }
      limit: { type: integer, required: false }
    rest:
      method: GET
      url: https://api.example.com/search
      query:
        q: .params.query
        limit: .params.limit // 10
      response:
        root: /results

  read_item:
    description: Read a single item
    returns: item
    params:
      id: { type: string, required: true }
    rest:
      method: GET
      url: '"https://api.example.com/items/" + .params.id'
      response:
        root: /
${writeOps}${inlineActionBlock}
---

# ${displayName}

Replace the placeholder API URLs, auth instructions, and field mappings with the
real service contract.

## Workflow

1. Update the YAML frontmatter until \`npm run validate -- ${skillName}\` is clean.
2. Use \`npm run mcp:call -- --skill ${skillName} --tool search --params '{"query":"test"}' --format json --detail full\` for live runtime proof.
3. Run \`npm run mcp:test -- ${skillName} --verbose\` once the real contract is wired up.
`;
}

function localControlReadme(): string {
  return `---
id: ${skillName}
name: ${displayName}
description: TODO: Describe the local control surface
icon: icon.svg
color: "#805AD5"
website: https://example.com
auth: none

operations:
  list_status:
    description: Inspect local runtime state
    returns:
      ok: boolean
      user: string
      cwd: string
    command:
      binary: python3
      args:
        - -c
        - |
          import getpass, json, os
          print(json.dumps({
            "ok": True,
            "user": getpass.getuser(),
            "cwd": os.getcwd(),
          }))
      timeout: 10

  echo_text:
    description: Placeholder local action that echoes text back
    returns:
      ok: boolean
      text: string
    params:
      text:
        type: string
        required: true
        description: Text to echo
    command:
      binary: python3
      args:
        - -c
        - |
          import json, sys
          params = json.loads(sys.stdin.read() or "{}")
          print(json.dumps({
            "ok": True,
            "text": params.get("text", ""),
          }))
      stdin: .params | tojson
      timeout: 10
---

# ${displayName}

This local-control scaffold is meant for command-backed skills such as terminal,
window, browser, or OS automation.

## Replace First

- Rename the placeholder tools to real local-control operations
- Replace the sample Python snippets with your real command executors
- Add setup notes in the markdown body if the skill depends on local binaries

## Runtime Proof

Use \`npm run mcp:call\` against this skill before trusting editor-side MCP output.
`;
}

function iconSvg(): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="52" fill="${isLocalControl ? '#805AD5' : '#4A5568'}"/>
  <path d="M72 80h112v96H72z" fill="#fff" opacity="0.92"/>
  <path d="M92 108h72M92 136h48M92 164h56" stroke="${isLocalControl ? '#805AD5' : '#4A5568'}" stroke-width="12" stroke-linecap="round"/>
</svg>
`;
}

mkdirSync(skillDir, { recursive: true });

writeFileSync(join(skillDir, 'readme.md'), isLocalControl ? localControlReadme() : entityReadme());
writeFileSync(join(skillDir, 'icon.svg'), iconSvg());

console.log(`✅ Created ${skillDir}`);
console.log(`   - readme.md`);
console.log(`   - icon.svg`);
console.log('');
console.log('Next steps:');
console.log(`  npm run validate -- ${skillName}`);
if (isLocalControl) {
  console.log(`  npm run mcp:call -- --skill ${skillName} --tool list_status --format json --detail full`);
} else {
  console.log(`  npm run mcp:call -- --skill ${skillName} --tool search --params '{"query":"test"}' --format json --detail full`);
}
console.log(`  npm run mcp:test -- ${skillName} --verbose`);

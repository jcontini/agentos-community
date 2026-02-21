# Contributing to AgentOS Community

Everything lives here — entities, skills, apps, and themes. Core is a generic engine; this repo is the ecosystem.

## The Guide

**Read `skills/write-skill.md`.** It's the comprehensive guide for writing skills — structure, executors, transformers, testing, entity reuse. It has live data (available models, existing adapters). Everything you need.

```bash
# Using an AI agent? Have it read the skill guide:
cat skills/write-skill.md
```

## Quick Start

```bash
# Edit directly in this repo (it's the live source)
vim skills/my-skill/readme.md

# Restart AgentOS server and test
cd ~/dev/agentos && ./restart.sh
curl http://localhost:3456/mem/tasks?skill=my-skill

# Validate and commit
npm run validate
git add -A && git commit -m "Add my-skill"
```

## Commands

```bash
npm run validate             # Schema validation + test coverage (run first!)
npm test                     # Functional tests
npm test skills/exa/tests    # Test specific skill
npm run new-skill <name>     # Create skill scaffold
```

## Schema Reference

`tests/skills/skill.schema.json` — the source of truth for skill YAML structure.

## License

MIT licensed. Contributions are MIT licensed and may be used in official releases including commercial offerings.

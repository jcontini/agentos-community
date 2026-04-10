---
id: code-review
name: Code Review
description: "Evaluate code changes against project principles, refactoring specs, and architectural direction"
color: "#DC2626"
website: https://agentos.dev

tools:
  evaluate_commit:
    async: true

test:
  evaluate_commit: { skip: true }
---

# Code Review

Evaluate code changes against project principles and architectural direction.
Reads the principles docs, active refactoring specs, and crate architecture
to score diffs and catch violations at commit time.

## Knowledge Base

The evaluator reads these documents before scoring:

| Source | What | When to apply |
|--------|------|---------------|
| `principles.md` | Engine principles — Rust is generic, templates do the work, etc. | Every Rust commit |
| `agentos-sdk/docs/principles.md` | Shape principles — no counts, edges are verbs, etc. | Shape/ontology changes |
| `agentos-sdk/skills-sdk/agentos/GUIDE.md` | Skill SDK reference — how skills are built | Any skill/Python commit |
| `docs/specs/refactoring/*.md` | Active refactoring specs — what's flagged for cleanup | Any commit touching flagged files |
| `./dev.sh arch` output | Live crate/module sizes, dependency chain, largest files | Structural awareness |

## Tools

### evaluate_commit

Score a git diff against the project's principles and refactoring specs.

**Parameters:**
- `diff` (required) — the staged git diff
- `files` — newline-separated list of changed file paths
- `threshold` — minimum passing score (default: 90)
- `model` — LLM model to use (default: sonnet)

**Returns:** `{ score, maxScore, pass, violations, summary }`

## Future Tools

- `review_pr` — evaluate all commits in a PR

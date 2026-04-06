---
id: propose
name: Propose
description: Research a problem space and generate a structured proposal ready for scored review
color: "#2563EB"
website: "https://agentos.dev"

product:
  name: agentOS
  website: https://agentos.dev
  developer: agentOS

test:
  draft:
    skip: true
  outline:
    skip: true
---

# Propose

Research a problem space and generate a structured proposal ready for scored review.

## The pipeline

```
propose.outline    →  Quick sketch (2 min read, align on scope)
propose.draft      →  Full proposal (researched, concrete, standalone)
review.start       →  Adversarial scored review (Author ↔ Reviewer ↔ Red Team)
```

Each step is independent. You can skip `outline` and go straight to `draft`.
You can write a proposal by hand and feed it directly to `review.start`.
The skills compose but don't require each other.

## What makes a good proposal

The `draft` operation produces documents with this structure:

| Section | What it answers | Why reviewers need it |
|---|---|---|
| **The Problem** | Who's affected? What's broken? Why now? | Can't evaluate a solution without understanding the problem |
| **Proposed Design** | What are we building? (with concrete artifacts) | The core of the evaluation — is this the right design? |
| **Alternatives Considered** | What else did you look at? Why not? | Proves the author explored the space, not just the first idea |
| **Trade-offs** | What are we giving up? What's risky? | Honest accounting — reviewers will find these anyway |
| **Implementation** | What ships first? What depends on what? | Is this buildable? In what order? |
| **Open Questions** | What don't we know? What needs validation? | Honesty about uncertainty is strength, not weakness |

This structure is intentionally aligned with the Review skill's evaluation
criteria. Not because it games the rubric — because the rubric measures
what makes a proposal actually good.

## The same structure, everywhere

Every rigorous field converges on the same proposal shape:

| Field | Their structure | Maps to |
|---|---|---|
| **Academic grant** | Significance → Approach → Innovation → Investigators | Problem → Design → Alternatives → Implementation |
| **Amazon PR/FAQ** | Press Release → Customer FAQ → Internal FAQ | Problem → Design → Trade-offs → Open Questions |
| **Y Combinator** | Problem → Solution → Why now → Unfair advantage | Problem → Design → Trade-offs → Implementation |
| **Architecture Decision Record** | Context → Decision → Consequences | Problem → Design → Trade-offs |
| **RFC (IETF)** | Problem → Specification → Security → IANA | Problem → Design → Trade-offs → Implementation |
| **FDA IND** | Indication → Preclinical Data → Clinical Plan → Risk | Problem → Evidence → Design → Trade-offs |

The common thread: **problem first, then solution, then honest accounting
of what you don't know.** Everyone converges on this because it's the
structure that survives adversarial review.

## Usage

```python
# Quick outline to align on scope
run({ skill: "propose", tool: "outline", params: {
    problem: "Developers can't build skills without reading 10 scattered files"
}})

# Full researched proposal
run({ skill: "propose", tool: "draft", params: {
    problem: "Developers can't build skills without reading 10 scattered files. \
              Need: scaffold, validate, context file, shape discovery CLI.",
    output: "docs/specs/dx/skill-sdk.md",
    context: "crates/core/src/shapes.rs,agentos-community/docs/skills/"
}})

# Then review it
run({ skill: "review", tool: "start", params: {
    document: "docs/specs/dx/skill-sdk.md",
    context: "crates/core/src/shapes.rs,agentos-community/skills/"
}})
```

## Domain hints

The `domain` parameter shapes the proposal's emphasis:

| Domain | Extra emphasis on |
|---|---|
| `sdk-design` | Developer experience, type safety, error messages, examples |
| `api-design` | Backwards compatibility, versioning, error codes, rate limits |
| `product-strategy` | Market, users, metrics, go-to-market, competitive landscape |
| `policy` | Enforcement, edge cases, fairness, appeals process |
| `research` | Methodology, reproducibility, limitations, related work |

If omitted, the agent infers the domain from the problem statement.

## Research

By default, `draft` searches the web for prior art and industry patterns
before writing. Set `research: false` to skip this (faster, but less
informed). The `outline` operation never does web research — it's meant
to be fast.

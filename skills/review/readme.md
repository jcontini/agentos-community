---
id: review
name: Scored Review
description: "Adversarial design review with Author, Reviewer, and Red Team agents — iterates on any document until convergence"
color: "#8B5CF6"
website: "https://agentos.dev"

product:
  name: agentOS
  website: https://agentos.dev
  developer: agentOS

test:
  start:
    skip: true
  resume:
    skip: true
---

# Scored Review

Adversarial, criteria-driven design review using three agent roles.

## How it works

```
Phase 1: Convergence
    Reviewer defines weighted criteria → scores document
    Author revises → Reviewer rescores
    Repeat until scores converge (Δ < 15 between rounds)

Phase 2: Red Team
    Fresh eyes read document + thread + actual codebase files
    Check claims against ground truth
    Identify shared blind spots from the Author↔Reviewer dialogue

Phase 3: Resolution
    Author addresses Red Team's blocking findings
    Reviewer rescores with Red Team input

Phase 4: Validation
    Red Team verifies fixes
    Writes verdict: SHIP IT / ONE MORE ROUND / NEEDS RETHINK
```

## Roles

| Role | What they do | What they don't do |
|---|---|---|
| **Reviewer** | Define criteria, score, push on weak spots | Never propose solutions |
| **Author** | Revise the document, show concrete artifacts | Never defend weak spots without evidence |
| **Red Team** | Check claims against reality, find blind spots | Not part of the iteration — independent |

## Files

Every review produces two files:

| File | Purpose | Who writes |
|---|---|---|
| `spec.md` | The document being reviewed | Author only |
| `spec-review.md` | The review thread (criteria, scores, findings) | Everyone appends |

The document is the deliverable. The thread is the process record.

## Pipeline

Review works on any document, but pairs naturally with the **Propose** skill:

```
propose.outline  →  Quick sketch (align on scope)
propose.draft    →  Full proposal (researched, concrete, standalone)
review.start     →  Scored review (Author ↔ Reviewer ↔ Red Team)
review.resume    →  Continue if verdict is ONE MORE ROUND
```

You can enter at any point. Write a doc by hand → `review.start`. Use
`propose.draft` to generate one → `review.start`. The skills compose but
don't require each other.

## Usage

```
# Review a document (hand-written or from propose.draft)
run({ skill: "review", tool: "start", params: {
    document: "docs/specs/dx/my-spec.md"
}})

# With codebase context for the Red Team
run({ skill: "review", tool: "start", params: {
    document: "docs/specs/dx/my-spec.md",
    context: "crates/core/src/shapes.rs,agentos-community/skills/"
}})

# Check status
run({ skill: "review", tool: "status", params: {
    thread: "docs/specs/dx/my-spec-review.md"
}})

# Resume after interruption or ONE MORE ROUND verdict
run({ skill: "review", tool: "resume", params: {
    thread: "docs/specs/dx/my-spec-review.md"
}})
```

## Scoring

- **Max score:** 500 (all criteria at 5/5)
- **Below 300:** Missing fundamentals — don't build yet
- **300-400:** Solid, buildable — address blocking issues
- **Above 400:** Ready to ship

## Inspiration

This process synthesizes patterns from:

- **Academic peer review** — Author submits → Referees review independently →
  Handling Editor synthesizes → Revise & Resubmit cycles. The anti-groupthink
  mechanism: independent, anonymous evaluation by multiple experts.

- **Intelligence analysis (CIA)** — Analysis of Competing Hypotheses forces
  disproof-oriented thinking. The Red Cell operates outside the normal chain
  of command with a mandate to challenge consensus.
  Ref: Richards Heuer, *Psychology of Intelligence Analysis*

- **FDA regulatory review** — Parallel discipline reviews by independent
  specialists, each with their own team leader who can formally dissent
  (non-concurrence). The advisory committee is external and independent.

- **Adversarial legal system** — Two parties with opposing interests each
  construct the strongest possible case. Amicus curiae briefs inject outside
  perspectives neither party raised.

- **Amazon six-pagers** — Read in silence at the meeting. Everyone forms
  their own opinion before discussion. Bar Raiser is an independent evaluator
  with veto authority.

The key insight across all these systems: **someone must be structurally
incentivized to disagree**. Without that, review degenerates into consensus.
The weighted criteria prevent it from degenerating into vibes.

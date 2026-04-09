---
id: project-management
name: Project Management
description: "Full project lifecycle: RFP, proposal, adversarial review, closeout"
color: "#8B5CF6"
website: "https://agentos.dev"

product:
  name: agentOS
  website: https://agentos.dev
  developer: agentOS

tools:
  write_rfp:
    async: true
  propose:
    async: true
  review:
    async: true
  closeout:
    async: true
  solve:
    async: true

test:
  write_rfp: { skip: true }
  propose: { skip: true }
  review: { skip: true }
  closeout: { skip: true }
  solve: { skip: true }
---

# Project Management

Manages the full project lifecycle: RFP, proposal, adversarial review, and closeout.

## Operations

- **write_rfp** — Agent writes `0-rfp.md` from a problem statement
- **propose** — Agent writes `1-proposal.md` responding to an RFP
- **review** — Agent scores a proposal adversarially, writes `2-review.md`
- **closeout** — Agent discovers commits, writes `3-closeout.md`
- **solve** — Orchestrates the full loop: write_rfp -> propose <-> review until 95+

## Conventions

All conventions are encoded in the system prompts inside `project_management.py`. The skill
is the single source of truth for how the project lifecycle works. No external
docs, no README templates.

## File layout

```
_projects/
  p1/                         <- priority 1
    my-project/
      0-rfp.md                <- problem definition
      1-proposal.md           <- winning proposal
      2-review.md             <- winning review (score >= 90)
      3-closeout.md           <- what actually shipped
      _drafts/                <- rejected rounds
        v1-proposal.md
        v1-review.md
  _archive/                   <- completed (must have 3-closeout.md)
now.md                        <- repo root, single line pointing to active 0-rfp.md
```

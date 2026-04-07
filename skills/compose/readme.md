---
id: compose
name: Compose
description: "Research, draft, and review documents with multi-agent iteration"
color: "#6366F1"
website: "https://agentos.dev"

product:
  name: agentOS
  website: https://agentos.dev
  developer: agentOS

operations:
  draft:
    async: true
  review:
    async: true
  resume:
    async: true

test:
  outline: { skip: true }
  draft: { skip: true }
  review: { skip: true }
  status: { skip: true }
  resume: { skip: true }
---

# Compose

Research, draft, and review documents with multi-agent iteration.

## Operations

### outline
Quick scope-alignment outline before committing to a full draft. Single LLM call, returns in seconds.

### draft (async)
Research a problem and generate a structured proposal document. Calls `llm.agent()` with web research tools. Returns a job ID — poll for completion.

### review (async)
Scored adversarial review with Author, Reviewer, and Red Team agents. 9-17 sequential LLM calls across 4 phases. Reports progress round-by-round with scores. Returns a job ID.

### status
Check the current state of a review thread without resuming.

### resume (async)
Continue an interrupted or ONE MORE ROUND review from where it left off.

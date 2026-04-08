# Problem Solver Skill — Requirements

## Overview

A multi-agent skill that takes a problem statement and produces a high-quality,
scored proposal through an adversarial process. Three roles, run sequentially
with parallelism within each phase.

**Replaces:** `propose`, `review`, `compose` — all three are consolidated here.

## Roles / Agents

### 1. RFP Writer
Takes a raw problem statement (could be rough notes, a conversation transcript,
or a structured brief) and produces a formal Request for Proposals.

**Responsibilities:**
- Identify personas / stakeholders affected by the problem
- Kick off sub-agents to research each persona's pain points (web search,
  YouTube transcripts, Reddit/HN threads, etc.)
- Prioritize pains per persona (P1/P2/P3) with evidence
- Define a weighted evaluation rubric (criteria, weights summing to 100,
  0-5 scale with concrete anchors for each level)
- Include a test case if applicable
- Output: a standalone RFP document (problems + rubric, NO solutions)

**Sub-agents the RFP Writer can spawn:**
- Persona researcher (one per persona — searches web, YouTube, Reddit, HN)
- Pain prioritizer (weights pains with evidence)

### 2. Proposal Writer
Takes the RFP as input and writes a comprehensive proposal that addresses
every problem and scores well against the rubric.

**Responsibilities:**
- Read the RFP thoroughly
- Research solutions (web search, prior art, industry patterns)
- Write a concrete proposal with artifacts (show, don't describe)
- Address every P1 problem. Address P2s where possible. Acknowledge P3s.
- Demonstrate the solution against the test case
- Output: a standalone proposal document

**Key constraint:** The proposal writer has NO access to the evaluator's
feedback template. It only sees the RFP's rubric. This prevents gaming.

**Sub-agents the Proposal Writer can spawn:**
- Research agents (web search, YouTube, Reddit/HN for prior art)
- Technical deep-dive agents (explore specific solution approaches)

### 3. Evaluator
Scores the proposal against the RFP's rubric. Identifies gaps. Does NOT
suggest solutions — only identifies where the proposal falls short.

**Responsibilities:**
- Score each criterion 0-5 with concrete justification
- Calculate weighted total (max 500)
- Classify issues as BLOCKING (must fix) or NON-BLOCKING (should fix)
- Identify what problems the proposal doesn't address
- Say WHERE it fell short, not WHAT to do about it
- Output: scored evaluation appended to a review thread

### 4. Red Team (optional, phase 3)
Fresh-eyes audit after proposal revision. Checks claims against reality.
Identifies shared blind spots between proposal writer and evaluator.

## Flow

```
Phase 1: RFP Generation
  Input: raw problem statement from user
  RFP Writer → spawns persona researchers in parallel
  Persona researchers return → RFP Writer synthesizes
  Output: rfp.md

Phase 2: Proposal Generation (parallel bids)
  Input: rfp.md + model list (e.g., ["opus", "gpt-5", "gemini-4"])
  For each model: spawn a Proposal Writer agent
  Each writer researches independently, writes proposal
  Output: proposal-{model}.md for each

Phase 3: Evaluation Loop (per proposal)
  For each proposal:
    Evaluator scores against RFP rubric
    Proposal Writer receives score + gap analysis
    Proposal Writer revises
    Evaluator rescores
    Repeat until convergence (score delta < 15) or max rounds
  Output: proposal-{model}-review.md thread for each

Phase 4: Red Team (optional)
  Red Team audits top-scoring proposal(s)
  Checks claims against codebase/reality
  Final verdict: SHIP IT / ONE MORE ROUND / NEEDS RETHINK

Phase 5: Summary
  Compare all proposals side-by-side
  Rank by final score
  Highlight where proposals diverged (different solutions to same problem)
```

## Parameters

```python
def solve(
    problem: str,          # raw problem statement or path to file
    output: str,           # output directory for all artifacts
    models: list = None,   # models for proposal bids, default ["opus"]
    bids: int = 1,         # number of bids (can use same model multiple times)
    max_rounds: int = 3,   # max evaluator↔writer rounds per bid
    context: str = "",     # comma-separated paths for codebase context
    red_team: bool = True, # whether to run red team phase
    domain: str = "",      # domain hint (sdk-design, product-strategy, etc.)
):
```

## Tools Available to All Agents

Agents should have access to agentOS skills for research:
- **Web search** — routed to Exa or Brave via agentOS handlers
- **Web read** — routed to Firecrawl for JS-heavy sites, or curl for simple
- **Reddit** — search and read Reddit threads
- **Hacker News** — search and read HN discussions
- **YouTube** — get video transcripts for research
- **Graph read/search** — query existing agentOS graph for prior work, specs, etc.
- **Sub-agent spawning** — any agent can spawn sub-agents via `llm.agent()`

Tools are made available through the SDK's `llm.agent()` which supports
tool allowlists. Research tools don't need file write access.

## Output Structure

```
{output}/
├── rfp.md                      # The RFP (problems + rubric)
├── proposal-opus.md            # Proposal from Opus
├── proposal-opus-review.md     # Evaluation thread for Opus proposal
├── proposal-gpt5.md            # Proposal from GPT-5 (if requested)
├── proposal-gpt5-review.md     # Evaluation thread
└── summary.md                  # Side-by-side comparison + rankings
```

## Implementation Notes

### Agent dispatch
All LLM calls go through `llm.agent()` — the SDK's built-in agent runner.
This handles model routing, tool allowlists, and file access. No subprocess
spawning (`shell.run("claude", ...)` is the old pattern from propose/review).

### Multi-model support
`llm.agent(model="gpt-5")` should route through OpenRouter or direct API.
The agentOS engine already has `openrouter` and `anthropic-api` skills.
The `model` parameter on `llm.agent()` needs to support non-Anthropic models.

### Progress reporting
Use `progress.progress(step, total, message)` throughout. Long-running phases
(proposal writing, evaluation) should report intermediate status.

### Skill consolidation
This skill replaces:
- `propose` (becomes the RFP Writer + Proposal Writer)
- `review` (becomes the Evaluator + Red Team)
- `compose` (was already the combination — this is the next evolution)

The old skills should be deleted once problem-solver is functional. Their
system prompts and flow logic are the starting point for the agents here.

### System prompts
Each role needs a detailed system prompt (like compose.py already has).
These should live in a `roles/` subdirectory or inline in the Python file.
Key prompts to port/evolve from compose.py:
- DRAFTER_PROMPT → Proposal Writer
- REVIEWER_PROMPT → Evaluator
- RED_TEAM_PROMPT → Red Team
- New: RFP_WRITER_PROMPT (does not exist yet — needs to be written)

## Migration from compose/propose/review

1. Build problem-solver with the full flow
2. Verify it works end-to-end on a real problem (the shape-graph-lifecycle RFP)
3. Delete `compose/`, `propose/`, `review/` skill directories
4. Update any references in docs

## First Test Case

Run the problem-solver on the shape-graph-lifecycle problem:
- Input: the raw problem statement about graph relations, inverses, lazy seeding
- Expected: it should produce an RFP similar to what we wrote manually, then
  generate and score proposals against it
- This validates the full pipeline end-to-end

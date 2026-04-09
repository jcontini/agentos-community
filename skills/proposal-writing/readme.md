---
id: proposal-writing
name: Proposal Writing
description: "Multi-agent proposal process: persona-driven RFP, bidding, scored evaluation by review committee"
color: "#8B5CF6"
website: "https://agentos.dev"

product:
  name: agentOS
  website: https://agentos.dev
  developer: agentOS

tools:
  write_proposal:
    async: true

test:
  write_proposal: { skip: true }
  status: { skip: true }
---

# Proposal Writing

Multi-agent proposal writing modeled on government contracting. A review
committee of persona agents writes the RFP, a bidder writes the proposal,
and the committee scores it iteratively until the proposal meets threshold.

## How to Use This Skill (for the calling agent)

You are the bridge between the human and this skill. Don't just fire
`run()` immediately — the best RFPs come from a conversation first.

### Step 1: Interview the human

Before writing the RFP, interview the human to understand their requirements.
Ask about:
- What problem are they trying to solve? (they may have a rough idea or a spec file)
- What does success look like? Who are the stakeholders?
- What constraints exist? (timeline, tech stack, team, budget)
- What have they already tried or ruled out?
- What's the scope of change? (can we rewrite from scratch? are there users to protect?)

Keep asking until you think you have enough, then ask: "Is there anything
else I should know before writing the RFP?" Let the human add anything
they want. Don't rush this — a weak RFP produces weak proposals.

### Step 2: Draft the RFP collaboratively

Write the RFP (or pass the problem statement + your interview notes to
this skill). But before the bidding phase begins, show the human the RFP
and ask for feedback:
- "Here's the draft RFP. Does this capture what you need?"
- "Are the evaluation criteria weighted correctly?"
- "Are there personas or concerns I'm missing?"

Iterate until the human says it's good. The human may spot gaps you missed
or reprioritize criteria. This is their project — they sign off on the RFP.

### Step 3: Run the skill and wait

Once the RFP is approved, run the skill with `execute: true`. This is a
long-running async job (15-30 min). Tell the human:
- The job ID so they can check status
- What to expect (phases, timing)
- That you'll review the output together when it's done

Don't disappear — monitor progress (see "Monitoring a Running Job" below)
and give updates at natural milestones.

### Step 4: Review the proposal together

When the job completes, read the output artifacts and present them to the
human. Walk through:
- The score breakdown per persona
- Key strengths and weaknesses
- What changed across evaluation rounds
- Whether the proposal is ready to implement or needs another pass

The human decides whether to accept, revise, or re-run with different parameters.

## Flow

```
┌─────────────────────────────────────────────────────┐
│ Phase 0: Human Interview (calling agent <-> human)  │
│   Understand requirements, constraints, scope       │
│   Draft RFP, iterate with human until approved      │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ Phase 1: Identify Personas (structured output)      │
│   llm.agent + output_schema -> 3-5 typed personas   │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ Phase 2: RFP Generation (parallel)                  │
│   asyncio.gather: all persona agents run concurrently│
│     Each: research pain points, write RFP section   │
│   RFP Manager assembles + validates full RFP        │
│   checkpoint.save() after completion                │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ Phase 3: Proposal Bid                               │
│   Bidder reads RFP, researches solutions            │
│   Writes complete proposal addressing all personas  │
│   checkpoint.save() after completion                │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ Phase 4: Evaluation Loop (repeat until >=90%)       │
│   asyncio.gather: all persona evaluators in parallel │
│     Each scores via output_schema (structured JSON) │
│   Evaluator aggregates scores (structured output)   │
│   Bidder revises proposal                           │
│   checkpoint.save() after each round                │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ Phase 5: Final Summary                              │
│   Score breakdown per persona                       │
│   checkpoint.clear() on success                     │
└─────────────────────────────────────────────────────┘
```

## Operations

### write_proposal (async)

Full pipeline: persona identification → RFP → bid → evaluation loop → summary.

**Parameters:**
- `problem` (required) — raw problem statement or path to a file containing one
- `output` (required) — output directory for all artifacts
- `model` — model for the bidder (default: opus)
- `max_rounds` — max evaluation rounds (default: 5)
- `context` — comma-separated paths for codebase context
- `domain` — domain hint (sdk-design, product-strategy, etc.)
- `threshold` — minimum score as fraction of max (default: 0.9)

### status

Check the current state of a proposal run.

## Research Tools Reference

Agents in this skill use `llm.agent()` with research tools to gather evidence.
Here's how to use each tool — discovered via `load()` and tested via `run()`.

### How tools work in llm.agent()

From MCP, you call tools like this:
```
run({ skill: "exa", tool: "search", params: { query: "..." } })
```

From `llm.agent()` in Python, tools are passed as a list of tool refs.
The engine resolves them to the right skill. Use `load({ skill: "name" })`
to discover the exact tool names.

### Web Search — Exa (primary)

Semantic/neural search. Best for research queries.

```
# From MCP:
run({ skill: "exa", tool: "search", params: { query: "multi-agent orchestration", limit: 10 } })

# Key params:
#   query (required) — search query
#   limit — max results (default 10)
#   category — optional filter: "research paper", "company", etc.
#   include_text — include full page content (default true)
```

Returns `result[]` — each has `name`, `url`, `content`, `published`.

### Web Read — Exa

Extract full content from a URL. Good for following up on search results.

```
run({ skill: "exa", tool: "read_webpage", params: { url: "https://example.com" } })
```

Returns `webpage` — has `name`, `url`, `content`, `contentType`.

### Web Read — Curl (fallback, no auth)

Simple URL fetch. No API key needed. Won't render JS.

```
run({ skill: "curl", tool: "read_webpage", params: { url: "https://example.com" } })
```

### Web Read — Firecrawl (JS-heavy sites)

Full browser rendering. Handles React/Vue/Angular. **Needs API key.**

```
run({ skill: "firecrawl", tool: "read_webpage", params: { url: "https://react.dev" } })

# Key params:
#   url (required)
#   wait_for_js — ms to wait for hydration (default 0)
#   timeout — ms timeout (default 30000)
```

### Hacker News

Search stories or get a story with comments. No auth needed.

```
# Search stories:
run({ skill: "hackernews", tool: "search_posts", params: { query: "knowledge graphs", limit: 10 } })

# Get story with comments:
run({ skill: "hackernews", tool: "get_post", params: { id: "45796897" } })

# List by feed (front, new, ask, show):
run({ skill: "hackernews", tool: "list_posts", params: { feed: "front", limit: 20 } })

# Flatten comment tree:
run({ skill: "hackernews", tool: "comments_post", params: { id: "45796897" } })
```

Returns `post[]` — each has `name`, `url`, `content`, `score`, `commentCount`, `author`.

### Reddit

Search posts and communities. No auth needed, but may get 403 bot detection.

```
# Search posts:
run({ skill: "reddit", tool: "search_posts", params: { query: "personal knowledge graph", limit: 10 } })

# List posts from a subreddit:
run({ skill: "reddit", tool: "list_posts", params: { subreddit: "programming", sort: "hot" } })

# Get a post with comments:
run({ skill: "reddit", tool: "get_post", params: { id: "abc123" } })
#   or: params: { url: "https://reddit.com/r/.../comments/..." }

# Search subreddits:
run({ skill: "reddit", tool: "search_communities", params: { query: "knowledge graph" } })
```

**Known issue:** Reddit returns 403 for bot detection. May need
http header passthrough fix. Exa + HN are more reliable alternatives.

### YouTube

Video search and transcripts. Requires `yt-dlp` installed.

```
# Search videos:
run({ skill: "youtube", tool: "search_videos", params: { query: "graph databases explained" } })

# Get transcript (plain text — great for AI summarization):
run({ skill: "youtube", tool: "transcript_video", params: { url: "https://youtube.com/watch?v=..." } })
#   lang: "en" (default), format: "text" (default) or "segments" for timestamps

# Get video metadata:
run({ skill: "youtube", tool: "get_video", params: { url: "https://youtube.com/watch?v=..." } })

# Recent videos on a topic:
run({ skill: "youtube", tool: "search_recent_video", params: { query: "agent orchestration" } })

# List channel videos:
run({ skill: "youtube", tool: "list_videos", params: { url: "https://youtube.com/@channelname" } })
```

**Known issue:** yt-dlp import chain hits sandbox (`socket` blocked).
Needs sandbox allowlist for yt-dlp's transitive imports.

### Brave Search (independent index)

```
run({ skill: "brave", tool: "search", params: { query: "...", limit: 20 } })

# Freshness filters in params: "pd" (day), "pw" (week), "pm" (month), "py" (year)
```

**Needs API key** from https://api-dashboard.search.brave.com

### Tool availability summary (tested 2026-04-08)

| Tool | Status | Auth |
|------|--------|------|
| `exa` `search` | **Works** | API key (configured) |
| `exa` `read_webpage` | **Works** | API key (configured) |
| `curl` `read_webpage` | **Works** | None needed |
| `hackernews` `search_posts` | **Works** | None needed |
| `hackernews` `get_post` | **Works** | None needed |
| `reddit` `search_posts` | **403 bot detection** | None needed |
| `youtube` `transcript_video` | **Sandbox blocks yt-dlp** | None needed |
| `brave` `search` | **Auth expired** | API key |
| `firecrawl` `read_webpage` | **Auth expired** | API key |

## Architecture Notes

### Key patterns used

- **Parallel agents via asyncio.gather()** — persona research and evaluation
  run concurrently. With 3 personas, Phase 2 takes ~3.5 min parallel vs ~9
  min sequential.
- **Structured output via output_schema** — persona identification, evaluation
  scores, and aggregation all use JSON Schema. No regex extraction.
- **Checkpoint/resume** — `checkpoint.save()` after each phase. If the skill
  crashes mid-run, it resumes from the last completed phase.
- **Prompts as external markdown** — all system prompts live in `prompts/`
  as readable markdown files, not embedded Python strings.
- **Agent nesting** — the top-level skill orchestrates sub-agents via
  `llm.agent()` calls. Each persona agent can use tools independently.
- All context is passed through files: rfp.md, proposal.md, review.md.
  Each agent reads the files it needs.
- The review thread (review.md) is append-only. Each round's evaluations,
  aggregation, and revisions are appended so later agents can read history.

## Monitoring a Running Job

This skill runs as an async job (15-30 min). Here's how to monitor it.

### 1. engine-io.jsonl (best — shows each completed dispatch)

```bash
grep 'proposal-writing' ~/.agentos/logs/engine-io.jsonl
```

Each line is a completed SDK dispatch with fields: `action`, `skill`, `ms`, `error`, `ts`.

```
progress                                              ← job starts
llm_chat    (skill: proposal-writing, ~17s)           ← Phase 1: persona identification
llm_agent   (skill: proposal-writing, ~100-220s)      ← Phase 2: persona agent #1
llm_agent   (skill: proposal-writing, ~100-220s)      ← Phase 2: persona agent #2
llm_agent   (skill: proposal-writing, ~100-220s)      ← Phase 2: persona agent #3
llm_chat    (skill: proposal-writing)                  ← Phase 2: RFP Manager assembly
llm_agent   (skill: proposal-writing, ~120-300s)       ← Phase 3: bidder writes proposal
llm_agent   (skill: proposal-writing, ~30-60s) × N    ← Phase 4: persona evaluators (per round)
llm_agent   (skill: proposal-writing, ~60-120s)        ← Phase 4: bidder revision (per round)
llm_chat    (skill: proposal-writing)                  ← Phase 5: final summary
```

`error: true` flags failures. `ms` is wall-clock time per call.
Persona agents run sequentially (~100-220s each). With 3 personas, Phase 2
takes ~9 min sequential vs ~3.5 min if parallel.

### 2. read({ id: "<job_id>" }) — minimal

Returns `status: running` or `completed/failed`. No phase, no percentage.
Useful only to confirm the job is still alive.

### 3. Output directory — artifacts appear after phase completion

```bash
ls <output_dir>/
```

Files appear as each phase completes:
- `rfp.md` — after Phase 2
- `proposal.md` — after Phase 3
- `review.md` — grows during Phase 4 (append-only)
- `summary.md` — after Phase 5

An empty dir doesn't mean stuck — it means the current phase hasn't finished.

### 4. What doesn't work for monitoring

- `engine.log` — only shows boot/startup, not job internals
- `mcp.log` — raw JSON-RPC wire protocol, too noisy
- `read({ id })` — no sub-phase progress, `updated_at` is set at creation only

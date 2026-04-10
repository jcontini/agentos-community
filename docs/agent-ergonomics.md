# Agent Ergonomics Principles

Hard-won lessons from building skills that agents use. Every skill file is a
template — other agents will copy whatever patterns they see. These principles
apply to all code that agents interact with.

## Output format

- **Never force structured JSON output on LLMs.** Let them write natural prose
  (markdown). Parse what you need from frontmatter or conventions. Structured
  output causes context overflow failures and degrades quality.
- **Never make LLMs do arithmetic.** No weighted scoring, no percentage
  calculations, no "weights must sum to 100." If you need quantitative data,
  have the LLM label things (critical/important/nice-to-have, pass/fail/partial)
  and let Python do the math.
- **Let agents write naturally.** The less rigid the output format, the better
  the content. Specify structure (sections, frontmatter keys) not format
  (JSON schemas, exact table layouts).

## Agent experience

- **Give every agent a feedback channel.** Any agent should be able to say
  what was hard, unclear, or frustrating. Use a ```feedback block or SDK API.
  Feedback is never shown to other agents on the same task — only to the team.
- **Show agents their prior work.** On revision rounds, always include the
  previous attempt AND the review. Without both, agents regress — they lose
  what was good while trying to fix what was bad.
- **Don't over-constrain.** Line limits, tool restrictions, and rigid templates
  reduce quality. Give agents room to do their best work. Iterate on ergonomics
  based on their feedback.

## Tool access

- **Give agents subagent capability.** Deep investigation (tracing call chains,
  verifying code claims) requires spawning focused subagents. Without this,
  agents make shallow claims they can't verify.
- **Never use `find`.** It crawls build artifacts and hangs. Use Glob for file
  patterns, Grep for content, tree for directory structure.
- **Let agents choose their tools.** Don't hardcode skill names — use
  capabilities (`file_read`, `web_search`). AgentOS routes to the right provider.

## Scoring and evaluation

- **Use pass/fail/partial per criterion, not 0-100 scores.** LLMs are bad at
  calibrating numeric scores. They're good at saying "this works" or "this has
  a blocker."
- **Separate critical from nice-to-have.** A single critical failure should
  block implementation regardless of how many nice-to-haves pass.
- **Let Python compute verdicts.** The reviewer labels criteria. Python applies
  the rules: any critical blocker = revise, all critical pass = implement.

## What we learned the hard way

- JSON structured output had a 33% failure rate (empty scoring tables from
  context overflow). Switching to markdown: zero failures.
- Without prior proposal context, scores regressed on revision rounds (75 → 67).
  With it: steady improvement (71 → 79 → 82 → 84).
- Agents independently surfaced the same codebase pain points (undocumented
  helpers, confusing async/sync boundary). This feedback is gold — it tells
  you what to fix in the codebase, not just the proposals.

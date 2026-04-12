---
id: problem-solving
name: Problem Solving
description: "Interview the user to a clear problem definition, then run adversarial solutioning"
color: "#8B5CF6"
website: "https://agentos.to"

product:
  name: agentOS
  website: https://agentos.to
  developer: agentOS

tools:
  evaluate_problem:
    async: true
  solution:
    async: true
  closeout:
    async: true
  give_feedback:
    async: true

test:
  evaluate_problem: { skip: true }
  solution: { skip: true }
  closeout: { skip: true }
  give_feedback: { skip: true }
---

# Problem Solving

You are talking to the user right now. **You are the interface.** Don't
spawn sub-agents to interview them — use the conversation you're already
in. This skill gives you three tools and a workflow. That's it.

## The loop

1. **Interview the user** until you think you have a clear problem definition.
2. **Write** `_projects/p<N>/<slug>/pain.md` — YAML frontmatter + markdown body.
3. Call `evaluate_problem(path="<absolute path to pain.md>")`.
4. Read the result. If `pass: false`, ask the user the clarifying questions in `feedback`, rewrite the file, call again. If `pass: true`, continue.
5. Call `solution(project="<absolute path to project dir>")`. This kicks off the adversarial propose ↔ review loop against your problem definition.
6. Once that returns `verdict: implement`, you own the implementation. Do the work.
7. When the work is shipped, call `closeout(project="<project dir>")` to write `closeout.md` from the git log.

Priority `<N>` is `1`, `2`, or `3`. Ask the user if it's unclear — don't guess.

## Execution modes

**Skill dispatch (when engine is healthy):** Use the tools above (`evaluate_problem`, `solution`, `closeout`) through normal engine dispatch.

**Sub-agent mode (always works):** When the engine dispatch is broken or unavailable, run the same loop manually with general-purpose sub-agents:
1. Write `pain.md` yourself (interview the user directly)
2. Write `proposal.md` (with web research / prior art)
3. Spawn a general-purpose sub-agent as adversarial reviewer — give it full Read/Grep/Glob access, tell it to verify every claim against source code (file:line), find blockers (wrong signatures, crate boundary violations, missing edge cases). It writes `review.md` with a verdict.
4. If fail: fix the proposal, re-run the reviewer agent. Iterate until pass.
5. If pass: implement.

The sub-agent approach is the primary fallback. It produces equivalent quality to the skill dispatch — the reviewer starts fresh with no bias from proposal writing, which is the key property.

## What makes a good problem definition

You're writing `pain.md`, not a solution. Pretend you are a skeptical
colleague hearing about the problem for the first time. A good problem
definition:

- **Names the pain in one sentence.** If you can't, you don't understand the problem yet. Go back to the user.
- **Identifies personas.** Who hurts? Skill author? End user at a GUI? Engine maintainer? A specific external API? List every party affected and how their pain differs.
- **Cites evidence.** File paths, line numbers, exact error messages, concrete scenarios that fail today. "The agent can't ask questions" is weak. "`handle_engine_dispatch_async` in `crates/core/src/skills/executor.rs:1451` has branches for `__progress__`, `__browser_*`, `__oauth_exchange__`, but no `__ask_user__` — so the interview agent at `project_management.py:568-619` runs one-shot with no way to clarify" is strong.
- **Lists forward-looking pain.** What gets worse if we don't fix this? What future work is blocked?
- **Fences the scope.** An explicit **non-problems** section: things a solution might try to bundle but shouldn't. This is the single most load-bearing section — it's what keeps the solution from overreaching.
- **Is honest about what you don't know yet.** A "What we don't know" section is fine. Pain is not solution — you don't have to have answers.
- **Stays at the scope the real fix needs.** AgentOS is pre-launch. No users, no data to protect, no backward compat. If the real fix is gutting an executor and every downstream skill, scope the problem at that level. Pre-shrinking the problem to make the solution feel smaller is the single most common failure mode.

### Required YAML frontmatter

```yaml
---
title: "<Name> — Pain"
type: pain
priority: 1  # 1, 2, or 3
labels: [engine, dispatch, ...]  # subsystems this touches
pain: |
  <the one-sentence version of the pain>
---
```

`evaluate_problem` will add `reviews:` entries to this frontmatter on
each call. Don't hand-write that field — let the tool stamp it.

### Body structure (suggested — adapt to the problem)

```markdown
# <Name> — Pain

## One sentence

<the one-sentence pain>

## Personas

| Persona | Who they are |
|---------|--------------|
| ... | ... |

## Per-persona pain, with evidence

### <persona>
**Pain:** ...
**Evidence:** <file:line citations, exact errors, concrete scenarios>

## Forward-looking pain

What gets worse if we don't fix this. Blocked work, compounding costs.

## Explicit non-problems (scope fences)

- **Not X.** <why>
- **Not Y.** <why>

## What we specifically do NOT know yet

<open questions that are solution-land, not pain-land>
```

Length target: as long as it needs to be to be **concrete**. A 40-line
pain doc with file:line evidence beats a 400-line pain doc full of
hand-waving. The example at `_projects/p1/ask-user-primitive/pain.md`
is a good reference for depth of evidence — but don't cargo-cult its
structure. Every problem is shaped differently.

## evaluate_problem — what it does

`evaluate_problem(path="...")` reads your pain file, runs it through an
adversarial evaluator, and stamps the result into the file's YAML
frontmatter under `reviews:`. Returns:

```json
{
  "pass": true | false,
  "feedback": "<markdown>",
  "path": "<path you passed in>"
}
```

- **`pass: false`**: `feedback` is a list of specific clarifying questions the evaluator wants answered. Ask the user those questions (not all at once — pick the important ones), rewrite `pain.md`, call `evaluate_problem` again.
- **`pass: true`**: You're cleared to proceed. Call `solution(project=...)`.

The evaluator is harsh on substance, kind on prose. It looks for:
concrete evidence, clear persona-level pain, tight scope fences, and
honest unknowns. It rejects vague pain, solutioneering, and
overscoped problems that bundle unrelated work.

## solution — what it does

`solution(project="<project dir>")` runs the propose ↔ review loop:

1. A proposal agent reads `pain.md` and writes `proposal.md` — a file-level design with exact files, functions, diff sketches, edge cases, and a gate test verification plan.
2. An adversarial reviewer scores it against the pain's evaluation criteria and writes `review.md` with a verdict: `implement`, `revise`, or `rethink`.
3. If `revise` or `rethink`, the loop iterates. Previous rounds move to `_drafts/v<N>-*`.
4. Once `implement`, the loop exits. Returns `{verdict, score, proposal_path, review_path, rounds}`.

Budget: up to 5 rounds. If the 5th round still isn't `implement`, the
problem is probably wrong — come back to the user and rewrite the pain.

**You do not do the implementation work inside `solution()`.** That's
your job after `solution` returns `implement`. Read `proposal.md`,
read `review.md`, and then go build it.

## closeout — what it does

`closeout(project="<project dir>")` discovers the commits that shipped
the work (scoped to files named in the proposal's Files Changed table),
writes `closeout.md` with a five-section format: Problem, What
shipped, Gate results, Deviations, Deleted. Call this after you've
actually merged the work, not before.

## File layout

```
_projects/
  p1/                           <- priority 1 (active)
    <slug>/
      pain.md                   <- problem definition (you write, tool stamps reviews)
      proposal.md               <- winning proposal (solution writes)
      review.md                 <- winning review     (solution writes)
      closeout.md               <- what actually shipped (closeout writes)
      _drafts/
        vproposal.md
        v1-review.md
  _archive/<slug>/              <- completed projects (manually moved)
```

No numeric prefixes — `pain`, `proposal`, `review`, `closeout` sort alphabetically.
Priority is the parent folder — move a project between `p1/`, `p2/`,
`p3/` to change priority. No other state lives anywhere else.

## Feedback

This skill and the SDK are under active development. When you finish a
run — especially if anything was unclear, frustrating, or could be
better — call `give_feedback(content="...")`. Even "all clear" helps.

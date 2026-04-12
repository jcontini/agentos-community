"""Problem-solving skill: evaluate a pain doc, run adversarial solutioning, write closeout.

The calling agent is the interface. This module does not interview the user,
does not spawn sub-agents to interview the user, and does not write pain docs.
The calling agent does that — inside the conversation it's already in.

Three tools:
  evaluate_problem(path)  → {pass, feedback}   (stamps frontmatter)
  solution(project)       → {verdict, ...}     (propose ↔ review loop)
  closeout(project)       → {closeout_path}    (from git log)
"""

import json
import os
import re
from datetime import date, datetime
from pathlib import Path

import yaml

from agentos import llm, progress, returns, shell, timeout


# ── Paths ────────────────────────────────────────────────────────────────────

def _find_repo_root() -> Path:
    """Find the agentos repo root. Skill runs from engine cwd, which may be
    anywhere. Prefer AGENTOS_REPO env var, else walk up from this file to find
    the sibling `agentos` repo, else fall back to ~/dev/agentos."""
    env = os.environ.get("AGENTOS_REPO")
    if env:
        return Path(env)
    # This file is at agentos-community/skills/agents/problem-solving/problem_solving.py
    # → parents: [problem-solving, agents, skills, agentos-community, dev]
    skill_dir = Path(__file__).resolve().parent
    dev_root = skill_dir.parent.parent.parent.parent  # dev/
    repo = dev_root / "agentos"
    if (repo / "_projects").exists():
        return repo
    home = Path.home() / "dev" / "agentos"
    if (home / "_projects").exists():
        return home
    return Path.cwd()


REPO_ROOT = _find_repo_root()
PROJECTS_ROOT = REPO_ROOT / "_projects"
FEEDBACK_FILE = REPO_ROOT / "_feedback" / "feedback.jsonl"


# ── System prompts ───────────────────────────────────────────────────────────

def _preamble(submit_tool: str, today: str) -> str:
    base = f"""Today is {today}.

Tool usage:
- NEVER use `find`. Use Glob for file patterns, Grep for content search, Read for specific files.

You have agentOS MCP tools:
- mcp__agentos__read — query the graph: read({{ id: "abc" }}), read({{ tags: "spec" }})
- mcp__agentos__search — full-text search: search({{ query: "filesystem" }})
- mcp__agentos__run — run skills: run({{ skill: "exa", tool: "search", params: {{ query: "..." }} }})
"""
    if submit_tool:
        base += f"""
Do your research, think it through, then submit your work with
{submit_tool}. You can think out loud, take notes, and explore — only
what you submit matters.

To submit your work:
  mcp__agentos__run({{ skill: "problem-solving", tool: "{submit_tool}", params: {{ ... }} }})
"""
    else:
        base += """
Do your research, think it through, then write your final document as
your last message. The caller will save it.
"""
    return base


# ── evaluate_problem ─────────────────────────────────────────────────────────

ROLE_EVALUATE = "You are an adversarial problem-definition evaluator."

BODY_EVALUATE = """You are evaluating a pain document — a problem definition,
not a proposal. Your job is to decide whether this is clear enough for a
solution agent to design against.

A good pain doc:
- Names the pain in **one sentence**.
- Lists **personas** (who hurts, how they differ).
- Gives **concrete evidence**: file paths, line numbers, exact errors, scenarios that fail today. "The agent can't ask questions" is weak. `file.rs:1451 has no __ask_user__ branch` is strong.
- Lists **forward-looking pain** — what gets worse if not fixed, what work is blocked.
- Has **explicit scope fences** — a "not this, not that" section. This is the single most load-bearing section. Missing scope fences is a blocker.
- Is honest about **what's not yet known** — open questions in solution-land are fine.
- **Stays at the right scope.** AgentOS is pre-launch with zero users. A pain doc that pre-shrinks the problem to make the eventual fix feel smaller is wrong. Flag timid framing as a blocker: if the real root cause needs a bigger refactor, the pain doc should say so.

What you are NOT evaluating:
- Prose quality, style, length. A 40-line doc with concrete evidence beats a 400-line doc full of hand-waving.
- Whether the solution is obvious. That's solutioneering's problem, not yours.
- Whether the author has a plan. Pain is not solution.

**Verdict rules:**
- `pass` — the doc is concrete enough, scoped, has evidence, has fences. A solution agent could design against it without having to guess what the user meant.
- `fail` — anything less. List the specific questions that need answering OR specific sections that are missing / too vague. Be blunt. Your feedback goes back to the user-facing agent, who will ask the user those questions and rewrite the doc.

When done, call submit_evaluation(verdict="pass|fail", feedback="<markdown>").
"""


# ── propose / review ─────────────────────────────────────────────────────────

ROLE_PROPOSE = "You are a proposal writer."

BODY_PROPOSE = """Read the pain doc carefully. Your proposal MUST have this exact structure:

---
title: "<Name> — Proposal"
type: proposal
pain: <project-slug>
date: {date}
---

## Methodology
What repos/files you read, what web searches you ran, what prior art you found. Cite URLs, file paths, function names. Prove you did the homework.

## Diagnosis
What's wrong, why it matters. Root causes, not symptoms.

## Design
Architecture, key decisions, trade-offs. Why this approach over alternatives. Reference prior art from your methodology.

## Implementation Plan
File-level: which files change, what changes, diff sketches for key changes. Exact files, functions, line ranges.

## Edge Cases
Table of edge cases and how the design handles them.

## Gate Test Verification
Concrete `agentos call` commands that prove the fix works.

## Files Changed
| File | Change | Est. Lines |

Requirements:
- Address every pain persona and every scope fence in the pain doc.
- Be file-level specific.
- Use web search to research prior art before designing.
- If this is a revision round, the prior review's blockers are included — you MUST address ALL of them.

**Favor audacious refactors over small patches.** AgentOS is pre-launch
with zero users and no backward-compat burden. If a band-aid fix would
leave the root cause in place, your proposal is wrong. Propose the design
that removes the root cause, even if it means gutting a pipeline and
touching every downstream skill. Blast radius is not a cost — stale
architecture is. Small safe patches that leave the inconsistency in place
should be rejected as insufficient scope in your Diagnosis section, not
defended as "pragmatic."

When done, call submit_proposal(content="your full proposal markdown").
"""


ROLE_REVIEW = "You are an adversarial proposal evaluator."

BODY_REVIEW = """Your job is to find gaps, not confirm assumptions. Harsh on
substance, kind on prose. The proposal was written by another agent — preamble
or informal language is fine. Focus on whether the DESIGN is sound.

Evaluate against the pain doc's personas, evidence, and scope fences. For each:
- Verdict: pass, partial, or fail
- Justify with specific evidence (quote proposal or cite missing content)
- Any critical miss is a blocker

**Call out timidity as a blocker.** If the proposal band-aids over a deeper
inconsistency (two shapes where one would do, sync wrapper around an async
call), flag "insufficient scope" as a blocker and point at the root cause
the proposal is avoiding. A proposal that chose the safer path without
justifying why the bigger path was wrong should fail review.

To verify claims, READ THE ACTUAL SOURCE CODE. Don't trust the proposal's
description of how things work — check the files it cites.

Write the review however you want. Include:
1. A criteria table: | # | Criterion | Priority | Verdict | Justification |
   (Priority: critical, important, nice-to-have. Verdict: pass, partial, fail.)
2. If any criteria fail or are partial, a Blockers section with specific things that must change.

Do not compute scores, percentages, or overall verdicts. The system derives
those from your criteria table.

When done, call submit_review(content="your full review markdown").
"""


# ── closeout ─────────────────────────────────────────────────────────────────

ROLE_CLOSEOUT = "You are a closeout writer."

BODY_CLOSEOUT = """Read the project's pain.md, proposal.md, review.md, and git log.
Write a closeout with YAML frontmatter and exactly five sections.

YAML frontmatter:
  title: "<Name> — Closeout"
  type: closeout
  pain: <project-slug>
  date: {date}
  verdict: shipped | partial | abandoned
  commits: [<short-hashes>]

After frontmatter: See also: [pain.md](pain.md) | [proposal.md](proposal.md) | [review.md](review.md)

Five sections only:

## Problem
1-2 sentences restating the pain from pain.md — a summary a new agent can read without opening the pain doc.

## What shipped
3-5 sentences on what actually got built. What's real now, not a copy of the proposal.

## Gate results
Each gate test from the proposal, restated with PASS/FAIL + evidence.

## Deviations
What changed from the proposal during implementation. Highest-value section — captures the gap between plan and reality.

## Deleted
Files and functions removed. Matters because we delete aggressively.

No LOC counts, no time tracking, no "lessons learned". Minimal or it won't get written.
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_system(*, role: str, submit_tool: str, body: str, today: str = "") -> str:
    if not today:
        today = str(date.today())
    return f"{role}\n\n{_preamble(submit_tool, today)}\n{body}"


def _strip_fenced_blocks(content: str) -> str:
    content = re.sub(r"```feedback\s*\n.*?```", "", content, flags=re.DOTALL)
    content = re.sub(r"```research\s*\n.*?```", "", content, flags=re.DOTALL)
    return content.rstrip() + "\n"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_without_frontmatter).

    If no frontmatter, returns ({}, text). Tolerates preamble before the first ---.
    """
    idx = text.find("---")
    if idx < 0:
        return {}, text
    rest = text[idx:]
    parts = rest.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}, text
    body = parts[2].lstrip("\n")
    return fm, body


def _dump_frontmatter(fm: dict, body: str) -> str:
    """Serialize frontmatter + body into a markdown file."""
    fm_text = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return f"---\n{fm_text}---\n\n{body}"


def _parse_criteria_table(review_text: str) -> list[dict]:
    """Parse { priority, verdict } rows from a review's criteria table."""
    rows = []
    for line in review_text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip().lower() for c in line.split("|") if c.strip()]
        if len(cells) < 4:
            continue
        if cells[0] in ("#", "---") or "criterion" in cells[1]:
            continue
        rows.append({"priority": cells[2].strip(), "verdict": cells[3].strip()})
    return rows


def _compute_score(review_text: str) -> float:
    PRIORITY_WEIGHTS = {"critical": 0.6, "important": 0.3, "nice-to-have": 0.1}
    VERDICT_SCORES = {"pass": 1.0, "partial": 0.5, "fail": 0.0}
    weighted_sum = 0.0
    weight_total = 0.0
    for row in _parse_criteria_table(review_text):
        w = PRIORITY_WEIGHTS.get(row["priority"], 0.0)
        v = VERDICT_SCORES.get(row["verdict"], 0.0)
        if w > 0:
            weighted_sum += w * v
            weight_total += w
    if weight_total == 0:
        return 0.0
    return round(weighted_sum / weight_total, 2)


def _compute_verdict(review_text: str) -> str:
    """implement | revise | rethink — derived from the criteria table."""
    rows = _parse_criteria_table(review_text)
    if not rows:
        return "revise"
    for row in rows:
        if row["priority"] == "critical" and row["verdict"] == "fail":
            return "rethink"
    for row in rows:
        if row["priority"] == "critical" and row["verdict"] == "partial":
            return "revise"
    for row in rows:
        if row["priority"] in ("critical", "important") and row["verdict"] != "pass":
            return "revise"
    return "implement"


def _parse_files_changed(proposal_text: str) -> list[str]:
    paths = []
    in_table = False
    for line in proposal_text.splitlines():
        if "| File" in line and "| Change" in line:
            in_table = True
            continue
        if in_table and line.startswith("|"):
            if "---" in line:
                continue
            cells = [c.strip().strip("`") for c in line.split("|") if c.strip()]
            if cells:
                paths.append(cells[0])
        elif in_table and not line.startswith("|"):
            break
    return paths


def _utcnow() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _append_feedback(content: str, job_id: str = "") -> dict:
    FEEDBACK_FILE.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp": _utcnow(),
        "job_id": job_id,
        "skill": "problem-solving",
        "agent_role": "",
        "content": content,
    }
    with open(FEEDBACK_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def _stamp_feedback(role: str, since: str):
    if not FEEDBACK_FILE.exists():
        return
    lines = FEEDBACK_FILE.read_text().splitlines()
    updated = False
    new_lines = []
    for line in lines:
        try:
            entry = json.loads(line)
            if entry.get("timestamp", "") >= since and not entry.get("agent_role"):
                entry["agent_role"] = role
                updated = True
            new_lines.append(json.dumps(entry))
        except json.JSONDecodeError:
            new_lines.append(line)
    if updated:
        FEEDBACK_FILE.write_text("\n".join(new_lines) + "\n")


# ── Submit tools (staging) ───────────────────────────────────────────────────

@returns({"saved": "boolean"})
async def give_feedback(content: str, **params) -> dict:
    """Submit feedback on this skill or the SDK. Call anytime.

    Args:
        content: Your feedback — anything unclear, frustrating, or improvable.
    """
    job_id = params.get("__job_id__", "")
    _append_feedback(content=content, job_id=job_id)
    return {"__result__": {"saved": True, "message": "Thanks — feedback recorded."}}


@returns({"saved": "boolean"})
async def submit_evaluation(verdict: str, feedback: str, **params) -> dict:
    """Submit the evaluator verdict. Called by the evaluator sub-agent.

    Args:
        verdict: "pass" or "fail"
        feedback: Markdown feedback — specific questions or missing sections
    """
    verdict = verdict.strip().lower()
    if verdict not in ("pass", "fail"):
        verdict = "fail"
    staging = REPO_ROOT / "_feedback" / "_staged_evaluation.json"
    staging.parent.mkdir(exist_ok=True)
    staging.write_text(json.dumps({"verdict": verdict, "feedback": feedback}))
    return {"__result__": {"saved": True}}


@returns({"saved": "boolean"})
async def submit_proposal(content: str, **params) -> dict:
    """Submit a proposal. Called by the proposal sub-agent.

    Args:
        content: The full proposal in markdown.
    """
    staging = REPO_ROOT / "_feedback" / "_staged_proposal.json"
    staging.parent.mkdir(exist_ok=True)
    staging.write_text(json.dumps({"content": content}))
    return {"__result__": {"saved": True, "message": "Proposal saved."}}


@returns({"saved": "boolean", "verdict": "string", "score": "number"})
async def submit_review(content: str, **params) -> dict:
    """Submit a review. Called by the review sub-agent.

    Args:
        content: The full review in markdown (must include criteria table)
    """
    score = _compute_score(content)
    verdict = _compute_verdict(content)
    staging = REPO_ROOT / "_feedback" / "_staged_review.json"
    staging.parent.mkdir(exist_ok=True)
    staging.write_text(json.dumps({"content": content, "score": score, "verdict": verdict}))
    return {"__result__": {"saved": True, "verdict": verdict, "score": score}}


# ── evaluate_problem ─────────────────────────────────────────────────────────

@returns({"pass": "boolean", "feedback": "string", "path": "string"})
@timeout(600)
async def evaluate_problem(path: str, **params) -> dict:
    """Evaluate a pain doc. Stamps the result into its frontmatter.

    The calling agent wrote pain.md by interviewing the user directly. This
    tool reads it, runs an adversarial evaluator, and stamps the verdict
    (pass/fail + feedback + timestamp) into the file's frontmatter under
    `reviews:`. Returns `{pass, feedback}` — if pass is false, the calling
    agent should ask the user the clarifying questions in feedback, rewrite
    the file, and call this tool again.

    Args:
        path: Absolute path to pain.md
    """
    progress.set_job_id(params.get("__job_id__", ""))

    pain_path = Path(path)
    if not pain_path.exists():
        return {"__result__": {"error": f"Pain file not found: {path}"}}

    await progress.progress(1, 3, "Evaluating problem definition...")

    pain_text = pain_path.read_text()
    today = str(date.today())
    system = _build_system(
        role=ROLE_EVALUATE,
        submit_tool="submit_evaluation",
        body=BODY_EVALUATE,
        today=today,
    )

    fb_since = _utcnow()
    result = await llm.agent(
        prompt=f"## Pain document\n\n{pain_text}",
        system=system,
        model="sonnet",
        tools=["exa.search", "exa.read_webpage"],
        timeout=540,
    )
    _stamp_feedback("evaluate_problem", fb_since)

    await progress.progress(2, 3, "Stamping frontmatter...")

    staged = REPO_ROOT / "_feedback" / "_staged_evaluation.json"
    if staged.exists():
        data = json.loads(staged.read_text())
        staged.unlink()
        verdict = data["verdict"]
        feedback = data["feedback"]
    else:
        # Fallback: agent didn't call submit_evaluation. Treat as fail.
        verdict = "fail"
        feedback = _strip_fenced_blocks(result.get("content", "")) or "Evaluator did not return a structured verdict."

    passed = verdict == "pass"

    # Stamp the pain file's frontmatter with this review.
    fm, body = _parse_frontmatter(pain_text)
    reviews = fm.get("reviews") or []
    if not isinstance(reviews, list):
        reviews = []
    reviews.append({
        "date": today,
        "verdict": verdict,
        "comments": feedback.strip()[:4000],  # cap to keep frontmatter sane
    })
    fm["reviews"] = reviews
    pain_path.write_text(_dump_frontmatter(fm, body))

    await progress.progress(3, 3, "Done")

    return {"__result__": {
        "pass": passed,
        "feedback": feedback,
        "path": str(pain_path),
    }}


# ── solution (propose ↔ review loop) ─────────────────────────────────────────

async def _propose(pain_path: Path, round_num: int, project_dir: Path, **params) -> str:
    """Run one proposal round. Returns the path to proposal.md."""
    pain_content = pain_path.read_text()
    prompt_parts = [f"## Pain\n\n{pain_content}"]

    if round_num > 1:
        drafts_dir = project_dir / "_drafts"
        prior_proposal = drafts_dir / f"v{round_num - 1}-proposal.md"
        prior_review = drafts_dir / f"v{round_num - 1}-review.md"
        if prior_proposal.exists():
            prompt_parts.append(f"\n\n## Your Previous Proposal (Round {round_num - 1})\n\n{prior_proposal.read_text()}")
        if prior_review.exists():
            prompt_parts.append(f"\n\n## Review Feedback (Round {round_num - 1})\n\n{prior_review.read_text()}")

    today = str(date.today())
    body = BODY_PROPOSE.format(date=today)
    system = _build_system(role=ROLE_PROPOSE, submit_tool="submit_proposal", body=body, today=today)

    fb_since = _utcnow()
    result = await llm.agent(
        prompt="\n".join(prompt_parts),
        system=system,
        model="sonnet",
        tools=["exa.search", "exa.read_webpage"],
        timeout=1680,
    )
    _stamp_feedback("propose", fb_since)

    proposal_path = project_dir / "proposal.md"

    # Archive prior round's proposal to _drafts
    drafts_dir = project_dir / "_drafts"
    drafts_dir.mkdir(exist_ok=True)
    if round_num > 1 and proposal_path.exists():
        prev_dest = drafts_dir / f"v{round_num - 1}-proposal.md"
        if not prev_dest.exists():
            proposal_path.rename(prev_dest)

    staged = REPO_ROOT / "_feedback" / "_staged_proposal.json"
    if staged.exists():
        data = json.loads(staged.read_text())
        staged.unlink()
        document = data["content"]
    else:
        document = _strip_fenced_blocks(result.get("content", ""))

    proposal_path.write_text(document)
    return str(proposal_path)


async def _review(pain_path: Path, proposal_path: Path, project_dir: Path, **params) -> dict:
    """Run one review round. Returns {verdict, score, review_path}."""
    pain_content = pain_path.read_text()
    proposal_content = proposal_path.read_text()
    prompt = f"## Pain\n\n{pain_content}\n\n## Proposal\n\n{proposal_content}"

    today = str(date.today())
    body = BODY_REVIEW.format(date=today)
    system = _build_system(role=ROLE_REVIEW, submit_tool="submit_review", body=body, today=today)

    fb_since = _utcnow()
    result = await llm.agent(
        prompt=prompt,
        system=system,
        model="sonnet",
        tools=["exa.search", "exa.read_webpage"],
        timeout=1680,
    )
    _stamp_feedback("review", fb_since)

    review_path = project_dir / "review.md"
    staged = REPO_ROOT / "_feedback" / "_staged_review.json"
    if staged.exists():
        data = json.loads(staged.read_text())
        staged.unlink()
        content = data["content"]
        verdict = data["verdict"]
        score = data["score"]
    else:
        content = _strip_fenced_blocks(result.get("content", ""))
        score = _compute_score(content)
        verdict = _compute_verdict(content)

    frontmatter = f"---\nverdict: {verdict}\nscore: {score}\ndate: {today}\n---\n\n"
    review_path.write_text(frontmatter + content)
    return {"verdict": verdict, "score": score, "review_path": str(review_path)}


@returns({
    "verdict": "string",
    "score": "number",
    "proposal_path": "string",
    "review_path": "string",
    "rounds": "integer",
})
@timeout(1800)
async def solution(project: str, max_rounds: int = 5, **params) -> dict:
    """Run the adversarial propose ↔ review loop against a pain doc.

    Reads `<project>/pain.md` and loops until the reviewer returns
    `implement` or max_rounds is exhausted. Writes `proposal.md` and
    `review.md` in the project dir. Rejected rounds move to `_drafts/`.

    Does NOT do the implementation. Once this returns `implement`, the
    calling agent reads the proposal and review and builds the thing.

    Args:
        project: Absolute path to the project directory (contains pain.md)
        max_rounds: Max propose↔review iterations (default 5)
    """
    progress.set_job_id(params.get("__job_id__", ""))

    project_dir = Path(project)
    pain_path = project_dir / "pain.md"
    if not pain_path.exists():
        return {"__result__": {"error": f"pain.md not found in {project_dir}"}}

    # Determine starting round from existing _drafts
    start_round = 1
    drafts_dir = project_dir / "_drafts"
    if drafts_dir.exists():
        existing = [f.name for f in drafts_dir.glob("v*-proposal.md")]
        if existing:
            start_round = max(int(f[1:].split("-")[0]) for f in existing) + 1

    proposal_path = ""
    review_result = {"verdict": "", "score": 0.0, "review_path": ""}
    round_num = start_round
    total_steps = max_rounds * 2

    for round_num in range(start_round, start_round + max_rounds):
        step = (round_num - start_round) * 2

        await progress.progress(step + 1, total_steps, f"Proposing (round {round_num})...")
        proposal_path = await _propose(pain_path, round_num, project_dir, **params)

        await progress.progress(step + 2, total_steps, f"Reviewing (round {round_num})...")
        review_result = await _review(pain_path, Path(proposal_path), project_dir, **params)

        if review_result["verdict"] == "implement":
            break

        # Move rejected review to _drafts for next round
        if round_num < start_round + max_rounds - 1:
            review_file = project_dir / "review.md"
            if review_file.exists():
                drafts_dir.mkdir(exist_ok=True)
                review_file.rename(drafts_dir / f"v{round_num}-review.md")

    await progress.progress(total_steps, total_steps, f"Done — verdict: {review_result['verdict']}")

    return {"__result__": {
        "verdict": review_result["verdict"],
        "score": review_result["score"],
        "proposal_path": proposal_path,
        "review_path": review_result["review_path"],
        "rounds": round_num,
    }}


# ── closeout ─────────────────────────────────────────────────────────────────

@returns({"closeout_path": "string", "commits": "string"})
@timeout(1800)
async def closeout(project: str, **params) -> dict:
    """Write a closeout for a completed project from the git log.

    Args:
        project: Absolute path to the project directory.
    """
    progress.set_job_id(params.get("__job_id__", ""))

    project_dir = Path(project)
    pain_content = (project_dir / "pain.md").read_text()
    proposal_content = (project_dir / "proposal.md").read_text()
    review_content = (project_dir / "review.md").read_text()

    review_fm, _ = _parse_frontmatter(review_content)
    since_date = review_fm.get("date", str(date.today()))

    file_paths = _parse_files_changed(proposal_content)

    await progress.progress(1, 4, "Discovering commits...")

    git_args = ["log", "--oneline", f"--since={since_date}"]
    if file_paths:
        git_args.append("--")
        git_args.extend(file_paths)
    git_result = await shell.run("git", git_args, timeout=15)
    git_log = git_result.get("stdout", "")

    await progress.progress(2, 4, "Writing closeout...")

    today = str(date.today())
    body = BODY_CLOSEOUT.format(date=today)
    system = _build_system(role=ROLE_CLOSEOUT, submit_tool="", body=body, today=today)
    prompt = (
        f"## Pain\n\n{pain_content}\n\n"
        f"## Proposal\n\n{proposal_content}\n\n"
        f"## Review\n\n{review_content}\n\n"
        f"## Git Log\n\n```\n{git_log}\n```"
    )

    fb_since = _utcnow()
    result = await llm.agent(
        prompt=prompt,
        system=system,
        model="sonnet",
        timeout=1680,
    )
    _stamp_feedback("closeout", fb_since)

    await progress.progress(3, 4, "Saving closeout...")

    document = _strip_fenced_blocks(result.get("content", ""))
    closeout_path = project_dir / "closeout.md"
    closeout_path.write_text(document)

    await progress.progress(4, 4, "Done")

    return {"__result__": {"closeout_path": str(closeout_path), "commits": git_log}}

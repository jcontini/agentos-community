"""Project lifecycle skill: RFP, proposal, adversarial review, closeout."""

import json
import os
import re
import yaml
from datetime import date
from pathlib import Path

from agentos import llm, progress, returns, shell, timeout

# ── Paths ────────────────────────────────────────────────────────────────────
# Resolve repo root from skill file location: skill is in agentos-community/skills/,
# which is a sibling of the agentos repo. Walk up from __file__ to find it.
# Fallback: HOME env var.

def _find_repo_root() -> Path:
    """Find the agentos repo root. The skill runs from the engine's cwd,
    which may not be the repo. Use AGENTOS_REPO env var if set, otherwise
    walk up from the skill file to find the sibling agentos repo."""
    env = os.environ.get("AGENTOS_REPO")
    if env:
        return Path(env)
    # Skill is at agentos-community/skills/project-management/project_management.py
    # agentos repo is at ../agentos (sibling of agentos-community)
    skill_dir = Path(__file__).resolve().parent
    community_root = skill_dir.parent.parent  # agentos-community/
    repo = community_root.parent / "agentos"
    if (repo / "_projects").exists():
        return repo
    # Last resort: check common dev paths
    home = Path.home() / "dev" / "agentos"
    if (home / "_projects").exists():
        return home
    return Path.cwd()

REPO_ROOT = _find_repo_root()
PROJECTS_ROOT = REPO_ROOT / "_projects"
ARCHIVE_DIR = PROJECTS_ROOT / "_archive"
NOW_FILE = REPO_ROOT / "now.md"

# ── Review output schema ─────────────────────────────────────────────────────

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "scoring_table": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "weight": {"type": "integer"},
                    "score": {"type": "integer"},
                    "justification": {"type": "string"},
                },
                "required": ["criterion", "weight", "score", "justification"],
            },
        },
        "weighted_total": {"type": "number"},
        "verdict": {"type": "string", "enum": ["implement", "revise", "rethink"]},
        "blockers": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["scoring_table", "weighted_total", "verdict", "blockers"],
}

# ── System prompts ───────────────────────────────────────────────────────────
# These ARE the conventions. When conventions change, prompts change.
# Built dynamically: shared preamble + role-specific content.


def _build_system(*, role: str, output_file: str, body: str, today: str = "") -> str:
    """Build a system prompt with shared preamble + role-specific body."""
    if not today:
        today = str(date.today())

    preamble = f"""Today is {today}.

Your ENTIRE response is the document in markdown. It will be saved directly
to {output_file} — do not use tools to write it, just output the document.
Do not summarize, describe, or talk about what you'd write — write the actual
document. No preamble, no meta-commentary. Start with the YAML frontmatter.

Tool usage:
- NEVER use `find`. It crawls build artifacts (target/, node_modules/) and hangs.
- Use Glob for file patterns (e.g. Glob("**/*.py")), Grep for content search.
- Use Read to read specific files. Read the file before referencing it.
- Keep research focused — read the files the RFP/problem names, don't crawl blindly.

You have agentOS MCP tools available:
- mcp__agentos__read — query the graph: read({{ id: "abc" }}), read({{ tags: "spec" }}),
  read({{ skill: "exa" }}), read({{ about: "skills" }})
- mcp__agentos__search — full-text search: search({{ query: "filesystem" }})
- mcp__agentos__run — run skills: run({{ skill: "exa", tool: "search", params: {{ query: "..." }} }})
Use these to look up project context, discover skills, or search the knowledge graph.
"""
    return f"{role}\n\n{preamble}\n{body}"


# ── Role-specific prompt bodies ─────────────────────────────────────────────

ROLE_WRITE_RFP = "You are an RFP writer."

BODY_WRITE_RFP = """Write a focused RFP with YAML frontmatter and these sections:
- Context (current state, key files table)
- Evaluation Criteria (1 persona, weights summing to 100)
- Gate Tests (concrete `agentos call` commands, not prose)
- Known Approaches (starting points, not solutions — require desk review/web research)
- Design Constraints

YAML frontmatter MUST include these fields:
  title: "<Name> — RFP"
  type: rfp
  priority: {priority}
  labels: [...]
  problem: |
    <problem statement>
  success_criteria: |
    - <bullet points>

Evaluation criteria table format:
| # | Criterion | Weight | What full marks looks like |
Weights MUST sum to 100. One persona only.

Gate test format — each test is an `agentos call` command with expected output:
  1. **Test name**: `agentos call run '{{...}}'` → expected result

Scoring thresholds: 95+ = implement, 70-94 = address blockers, <70 = rethink.
Keep the RFP under 300 lines.
"""

ROLE_PROPOSE = "You are a proposal writer."

BODY_PROPOSE = """Read the RFP carefully. The proposal MUST have this exact structure:

---
title: "<Name> — Proposal"
type: proposal
rfp: <project-slug>
date: {{date}}
---

## Methodology
How you researched this proposal: what repos/files you read, what web searches
you ran, what prior art you found. Show your work — cite URLs, file paths,
function names. This section proves you did the homework before designing.

## Diagnosis
What's wrong, why it matters. Root causes, not symptoms.

## Design
Architecture, key decisions, trade-offs considered. Why this approach over
alternatives. Reference prior art from your methodology.

## Implementation Plan
File-level: which files change, what changes, diff sketches for key changes.
Name exact files, functions, line ranges.

## Edge Cases
Table of edge cases and how the design handles them.

## Gate Test Verification
How each gate test from the RFP is satisfied. Concrete commands and expected output.

## Files Changed
| File | Change | Est. Lines |
Summary table of all files modified.

Requirements:
- Address EVERY evaluation criterion from the RFP
- Address EVERY gate test with concrete verification steps
- Be file-level specific: name exact files, functions, line ranges
- Use web search to research prior art and best practices before designing
- If this is a revision round, the previous review's blockers are included below.
  You MUST address ALL blockers. Do not hand-wave — show exactly what changed.

Keep the proposal under 500 lines. Concrete > comprehensive.
"""

ROLE_REVIEW = "You are an adversarial evaluator."

BODY_REVIEW = """Your job is to find gaps, not confirm assumptions. Be harsh but fair.

Score the proposal against EACH criterion from the RFP's evaluation criteria table.
For each criterion:
- Score 0-100 (where 100 = "full marks" as described in the RFP)
- Justify with specific evidence (quote the proposal or cite missing content)
- Note any blocking issues

To verify claims, READ THE ACTUAL SOURCE CODE. Don't trust the proposal's
description of how things work — check the files it references. If the proposal
says "the engine does X", verify by reading the engine code.

Output format — you MUST include:
1. Scoring table: | # | Criterion | Weight | Score | Justification |
2. Weighted total: sum(score_i * weight_i) / 100
3. Verdict: 95+ = implement, 70-94 = address blockers, <70 = rethink
4. Blockers list: specific things that MUST change (empty if score >= 95)

Scoring must be calibrated:
- 95+ means "ready to implement as-is, no significant gaps"
- 70-94 means "good design but specific things need fixing"
- <70 means "fundamental approach problems, needs rethinking"
"""

ROLE_CLOSEOUT = "You are a closeout writer."

BODY_CLOSEOUT = """Read the project's 0-rfp.md, 1-proposal.md, 2-review.md, and the git log output.
Write a closeout document with YAML frontmatter and exactly five sections.

YAML frontmatter:
  title: "<Name> — Closeout"
  type: closeout
  rfp: <project-slug>
  date: {{date}}
  verdict: shipped | partial | abandoned
  commits: [<short-hashes>]

After frontmatter, include: See also: [0-rfp.md](0-rfp.md) | [1-proposal.md](1-proposal.md) | [2-review.md](2-review.md)

Five sections only:
## Problem
1-2 sentences restating the original problem from the RFP. Not a copy — a summary
a new agent can understand without opening the RFP.

## What shipped
3-5 sentences. What actually got built. Not a copy of the proposal — what's real now.

## Gate results
Each gate test from the RFP, restated with PASS/FAIL + evidence.

## Deviations
What changed from the proposal during implementation. This is the highest-value
section — it captures the gap between plan and reality that future agents can't
reconstruct from the code alone.

## Deleted
Files and functions removed. Matters because we delete aggressively.

No LOC counts, no time tracking, no "lessons learned". Minimal or it won't get written.
"""

# ── Helpers ──────────────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text[:60].lower()).strip("-")


def _parse_frontmatter(text: str) -> dict:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return yaml.safe_load(parts[1]) or {}
    return {}


def _parse_files_changed(proposal_text: str) -> list[str]:
    """Extract file paths from the Files Changed table in a proposal."""
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


def _render_review_md(data: dict, round_num: int, today: str) -> str:
    """Render structured review data into a markdown document."""
    rows = data.get("scoring_table", [])
    total = data.get("weighted_total", 0)
    verdict = data.get("verdict", "revise")
    blockers = data.get("blockers", [])
    score_int = round(total)

    verdict_label = {
        "implement": "IMPLEMENT (95+ = ready to implement)",
        "revise": "REVISE (70-94 = address blockers)",
        "rethink": "RETHINK (<70 = fundamental problems)",
    }.get(verdict, verdict.upper())

    lines = [
        "---",
        f'title: "Evaluation — Round {round_num}"',
        "type: evaluation",
        f"score: {score_int}",
        f"verdict: {verdict}",
        f"date: {today}",
        "---",
        "",
        f"# Evaluation (Round {round_num})",
        "",
        "| # | Criterion | Weight | Score | Justification |",
        "|---|-----------|--------|-------|---------------|",
    ]

    for i, row in enumerate(rows, 1):
        c = row.get("criterion", "")
        w = row.get("weight", 0)
        s = row.get("score", 0)
        j = row.get("justification", "")
        lines.append(f"| {i} | {c} | {w} | {s} | {j} |")

    lines.extend(["", f"**Weighted total: {total:.1f}/100**", ""])
    lines.append(f"**Verdict: {verdict_label}**")

    if blockers:
        lines.extend(["", "## Blockers", ""])
        for i, b in enumerate(blockers, 1):
            lines.append(f"{i}. {b}")

    lines.append("")
    return "\n".join(lines)


def archive(project_dir: str) -> dict:
    """Move a completed project to _projects/_archive/.

    Refuses if 3-closeout.md doesn't exist in the project directory.
    """
    project = Path(project_dir)
    closeout = project / "3-closeout.md"
    if not closeout.exists():
        return {"__result__": {"error": f"Cannot archive: {closeout} does not exist. Run closeout first."}}
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    dest = ARCHIVE_DIR / project.name
    project.rename(dest)
    return {"__result__": {"archived_to": str(dest)}}


# ── Operations ───────────────────────────────────────────────────────────────


@returns({"rfp_path": "string"})
@timeout(1800)
async def write_rfp(problem: str, priority: int = 2, slug: str = "", **params) -> dict:
    """Write an RFP for an engineering problem.

    Args:
        problem: Problem statement or path to a file containing one
        priority: Priority level 1-3 (default 2)
        slug: Project slug for directory name (auto-generated if empty)
    """
    progress.set_job_id(params.get("__job_id__", ""))

    # If problem is a file path, read it
    problem_path = Path(problem)
    if problem_path.exists() and problem_path.is_file():
        problem = problem_path.read_text()

    # Deterministic slug
    if not slug:
        slug = _slugify(problem)

    # Create project directory
    project_dir = PROJECTS_ROOT / f"p{priority}" / slug
    project_dir.mkdir(parents=True, exist_ok=True)

    await progress.progress(1, 3, "Writing RFP...")

    # Agent writes the RFP content
    today = str(date.today())
    body = BODY_WRITE_RFP.format(priority=priority)
    system = _build_system(role=ROLE_WRITE_RFP, output_file="0-rfp.md", body=body, today=today)
    result = await llm.agent(
        prompt=f"Write an RFP for this problem:\n\n{problem}",
        system=system,
        model="sonnet",
        tools=["exa.search", "exa.read_webpage"],
        timeout=1680,
    )

    await progress.progress(2, 3, "Saving RFP...")

    rfp_path = project_dir / "0-rfp.md"
    rfp_path.write_text(result.get("content", ""))

    # Update now.md — always exactly one line
    NOW_FILE.write_text(str(rfp_path) + "\n")

    await progress.progress(3, 3, "Done")

    return {"__result__": {"rfp_path": str(rfp_path)}}


@returns({"proposal_path": "string"})
@timeout(1800)
async def propose(rfp: str, round: int = 1, **params) -> dict:
    """Write a proposal responding to an RFP.

    Args:
        rfp: Path to the 0-rfp.md file
        round: Revision round number (default 1, >1 reads prior review)
    """
    progress.set_job_id(params.get("__job_id__", ""))

    rfp_path = Path(rfp)
    project_dir = rfp_path.parent
    rfp_content = rfp_path.read_text()

    # Build prompt with RFP + optional prior review
    prompt_parts = [f"## RFP\n\n{rfp_content}"]

    if round > 1:
        drafts_dir = project_dir / "_drafts"
        prior_review = drafts_dir / f"v{round - 1}-review.md"
        if prior_review.exists():
            prompt_parts.append(f"\n\n## Previous Review (Round {round - 1})\n\n{prior_review.read_text()}")

    await progress.progress(1, 3, f"Writing proposal (round {round})...")

    today = str(date.today())
    system = _build_system(role=ROLE_PROPOSE, output_file="1-proposal.md", body=BODY_PROPOSE, today=today)

    result = await llm.agent(
        prompt="\n".join(prompt_parts),
        system=system,
        model="sonnet",
        tools=["exa.search", "exa.read_webpage"],
        timeout=1680,
    )

    await progress.progress(2, 3, "Saving proposal...")

    proposal_path = project_dir / "1-proposal.md"

    # On revision rounds, archive the previous proposal
    if round > 1 and proposal_path.exists():
        drafts_dir = project_dir / "_drafts"
        drafts_dir.mkdir(exist_ok=True)
        prev_dest = drafts_dir / f"v{round - 1}-proposal.md"
        if not prev_dest.exists():
            proposal_path.rename(prev_dest)

    proposal_path.write_text(result.get("content", ""))

    await progress.progress(3, 3, "Done")

    return {"__result__": {"proposal_path": str(proposal_path)}}


@returns({"score": "integer", "verdict": "string", "review_path": "string"})
@timeout(1800)
async def review(rfp: str, proposal: str, **params) -> dict:
    """Score a proposal adversarially against RFP criteria.

    Args:
        rfp: Path to 0-rfp.md
        proposal: Path to 1-proposal.md
    """
    progress.set_job_id(params.get("__job_id__", ""))

    rfp_content = Path(rfp).read_text()
    proposal_content = Path(proposal).read_text()
    project_dir = Path(rfp).parent

    prompt = f"## RFP\n\n{rfp_content}\n\n## Proposal\n\n{proposal_content}"

    await progress.progress(1, 3, "Reviewing proposal...")

    today = str(date.today())
    system = _build_system(role=ROLE_REVIEW, output_file="2-review.md", body=BODY_REVIEW, today=today)
    result = await llm.agent(
        prompt=prompt,
        system=system,
        model="sonnet",
        output_schema=REVIEW_SCHEMA,
        timeout=1680,
    )

    await progress.progress(2, 3, "Saving review...")

    data = result.get("data") or {}
    total = data.get("weighted_total", 0)
    score = round(total)
    verdict = data.get("verdict", "revise")

    # Python injects the date — agents don't determine dates
    today = str(date.today())
    review_md = _render_review_md(data, params.get("_round", 1), today)

    review_path = project_dir / "2-review.md"
    review_path.write_text(review_md)

    await progress.progress(3, 3, "Done")

    return {"__result__": {"score": score, "verdict": verdict, "review_path": str(review_path)}}


@returns({"closeout_path": "string", "commits": "string"})
@timeout(1800)
async def closeout(project: str, **params) -> dict:
    """Write a closeout for a completed project.

    Args:
        project: Path to the project directory (e.g. _projects/p1/my-project/)
    """
    progress.set_job_id(params.get("__job_id__", ""))

    project_dir = Path(project)
    rfp_content = (project_dir / "0-rfp.md").read_text()
    proposal_content = (project_dir / "1-proposal.md").read_text()
    review_content = (project_dir / "2-review.md").read_text()

    # Get review date for git log --since
    review_fm = _parse_frontmatter(review_content)
    since_date = review_fm.get("date", str(date.today()))

    # Parse file paths from proposal's Files Changed table
    file_paths = _parse_files_changed(proposal_content)

    await progress.progress(1, 4, "Discovering commits...")

    # Git log scoped to changed files
    git_args = ["log", "--oneline", f"--since={since_date}"]
    if file_paths:
        git_args.append("--")
        git_args.extend(file_paths)

    git_result = await shell.run("git", git_args, timeout=15)
    git_log = git_result.get("stdout", "")

    await progress.progress(2, 4, "Writing closeout...")

    today = str(date.today())
    system = _build_system(role=ROLE_CLOSEOUT, output_file="3-closeout.md", body=BODY_CLOSEOUT, today=today)
    prompt = (
        f"## RFP\n\n{rfp_content}\n\n"
        f"## Proposal\n\n{proposal_content}\n\n"
        f"## Review\n\n{review_content}\n\n"
        f"## Git Log\n\n```\n{git_log}\n```"
    )

    result = await llm.agent(
        prompt=prompt,
        system=system,
        model="sonnet",
        timeout=1680,
    )

    await progress.progress(3, 4, "Saving closeout...")

    closeout_path = project_dir / "3-closeout.md"
    closeout_path.write_text(result.get("content", ""))

    await progress.progress(4, 4, "Done")

    return {"__result__": {"closeout_path": str(closeout_path), "commits": git_log}}


@returns({"rfp_path": "string", "proposal_path": "string", "review_path": "string", "score": "integer", "rounds": "integer", "verdict": "string"})
@timeout(1800)
async def solve(problem: str, priority: int = 2, max_rounds: int = 3, **params) -> dict:
    """Run the full project lifecycle: RFP -> propose <-> review until 90+.

    Args:
        problem: Problem statement or path to a file
        priority: Priority level 1-3 (default 2)
        max_rounds: Max propose->review iterations (default 3)
    """
    progress.set_job_id(params.get("__job_id__", ""))
    total_steps = 2 + (max_rounds * 2)  # write_rfp + (propose + review) * rounds

    # Step 1: Write RFP
    await progress.progress(1, total_steps, "Writing RFP...")
    rfp_result = await write_rfp(problem=problem, priority=priority, **params)
    rfp_path = rfp_result["__result__"]["rfp_path"]
    project_dir = Path(rfp_path).parent
    proposal_path = str(project_dir / "1-proposal.md")
    review_path = str(project_dir / "2-review.md")

    # Step 2..N: Propose <-> Review loop
    score = 0
    verdict = "rethink"
    round_num = 0

    for round_num in range(1, max_rounds + 1):
        step = 1 + (round_num - 1) * 2 + 1

        # Propose
        await progress.progress(step, total_steps, f"Proposing (round {round_num})...")
        propose_result = await propose(rfp=rfp_path, round=round_num, **params)
        proposal_path = propose_result["__result__"]["proposal_path"]

        # Review
        await progress.progress(step + 1, total_steps, f"Reviewing (round {round_num})...")
        review_result = await review(
            rfp=rfp_path,
            proposal=proposal_path,
            _round=round_num,
            **params,
        )
        score = review_result["__result__"]["score"]
        verdict = review_result["__result__"]["verdict"]
        review_path = review_result["__result__"]["review_path"]

        if score >= 95:
            break

        # Move rejected proposal + review to _drafts
        if round_num < max_rounds:
            drafts_dir = project_dir / "_drafts"
            drafts_dir.mkdir(exist_ok=True)

            review_file = project_dir / "2-review.md"
            if review_file.exists():
                review_file.rename(drafts_dir / f"v{round_num}-review.md")

    await progress.progress(total_steps, total_steps, f"Done — score {score}, verdict: {verdict}")

    return {
        "__result__": {
            "rfp_path": rfp_path,
            "proposal_path": proposal_path,
            "review_path": review_path,
            "score": score,
            "rounds": round_num,
            "verdict": verdict,
        }
    }

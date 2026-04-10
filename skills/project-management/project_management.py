"""Project lifecycle skill: RFP, proposal, adversarial review, closeout."""

import contextvars
import json
import os
import re
import yaml
from datetime import date
from pathlib import Path

from agentos import llm, progress, returns, shell, timeout

# ── Context ─────────────────────────────────────────────────────────────────
# Flow job_id and agent role into inner agent tool calls (e.g. give_feedback)
_ctx_job_id: contextvars.ContextVar[str] = contextvars.ContextVar("_ctx_job_id", default="")
_ctx_agent_role: contextvars.ContextVar[str] = contextvars.ContextVar("_ctx_agent_role", default="")

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
FEEDBACK_FILE = REPO_ROOT / "_feedback" / "feedback.jsonl"
NOW_FILE = REPO_ROOT / "now.md"

# ── System prompts ───────────────────────────────────────────────────────────
# These ARE the conventions. When conventions change, prompts change.
# Built dynamically: shared preamble + role-specific content.


def _build_system(*, role: str, submit_tool: str, body: str, today: str = "") -> str:
    """Build a system prompt with shared preamble + role-specific body."""
    if not today:
        today = str(date.today())

    preamble = f"""Today is {today}.

Do your research, think it through, then submit your work using the submit tool
(submit_proposal or submit_review). You can think out loud, take notes, and
explore — none of that gets saved. Only what you submit matters.

Tool usage:
- NEVER use `find`. It crawls build artifacts (target/, node_modules/) and hangs.
- Use Glob for file patterns, Grep for content search, Read for specific files.

You have agentOS MCP tools:
- mcp__agentos__read — query the graph: read({{ id: "abc" }}), read({{ tags: "spec" }})
- mcp__agentos__search — full-text search: search({{ query: "filesystem" }})
- mcp__agentos__run — run skills: run({{ skill: "exa", tool: "search", params: {{ query: "..." }} }})

To submit your work:
  mcp__agentos__run({{ skill: "project-management", tool: "{submit_tool}", params: {{ ... }} }})

When you're done with your main work, please call give_feedback with a brief note:
  mcp__agentos__run({{ skill: "project-management", tool: "give_feedback", params: {{ content: "your feedback" }} }})
Even "all clear, no issues" is helpful. What was unclear? What could be better?

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
| # | Criterion | Priority | What "pass" looks like |
Priority is one of: critical, important, nice-to-have.
A single critical failure blocks implementation. Keep criteria focused — 3-6 total.

Gate test format — each test is an `agentos call` command with expected output:
  1. **Test name**: `agentos call run '{{...}}'` → expected result

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

Be concrete and specific. Don't pad — every line should earn its place.

When done, call submit_proposal(content="your full proposal markdown").
"""

ROLE_REVIEW = "You are an adversarial evaluator."

BODY_REVIEW = """Your job is to find gaps, not confirm assumptions. Be harsh on the
technical substance, but kind to the author. The proposal was written by another
agent — if it includes preamble, thinking-out-loud, or informal language, that's
fine. Focus on whether the DESIGN is sound, not the presentation.

Evaluate the proposal against EACH criterion from the RFP's evaluation criteria table.
For each criterion:
- Verdict: pass, partial, or fail
- Justify with specific evidence (quote the proposal or cite missing content)
- If partial or fail on a CRITICAL criterion, it's a blocker

To verify claims, READ THE ACTUAL SOURCE CODE. Don't trust the proposal's
description of how things work — check the files it references. If the proposal
says "the engine does X", verify by reading the engine code.

Write the review however you want. Include:
1. A criteria table: | # | Criterion | Priority | Verdict | Justification |
   (Priority comes from the RFP: critical, important, nice-to-have)
   (Verdict per criterion: pass, partial, or fail)
2. Your overall verdict — say **implement**, **revise**, or **rethink** clearly.
   Rules: any critical fail → rethink, any critical partial → revise,
   all critical+important pass → implement.
3. If not implement, a Blockers section with specific things that must change.

Do not compute scores, percentages, or weighted totals.

When done, call submit_review(content="your full review markdown", verdict="implement|revise|rethink").
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


def _strip_fenced_blocks(content: str) -> str:
    """Strip any ```feedback or ```research blocks agents may emit."""
    content = re.sub(r"```feedback\s*\n.*?```", "", content, flags=re.DOTALL)
    content = re.sub(r"```research\s*\n.*?```", "", content, flags=re.DOTALL)
    return content.rstrip() + "\n"


def _compute_score(review_text: str) -> float:
    """Compute a quantitative score from the review's criteria table.

    Parses the | # | Criterion | Priority | Verdict | ... table.
    LLM labels pass/partial/fail — Python does the math.
    Returns 0.0–1.0 weighted score (critical=0.6, important=0.3, nice-to-have=0.1).
    """
    PRIORITY_WEIGHTS = {"critical": 0.6, "important": 0.3, "nice-to-have": 0.1}
    VERDICT_SCORES = {"pass": 1.0, "partial": 0.5, "fail": 0.0}

    weighted_sum = 0.0
    weight_total = 0.0

    for line in review_text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip().lower() for c in line.split("|") if c.strip()]
        if len(cells) < 4:
            continue
        # Skip header/separator rows
        if cells[0] in ("#", "---") or "criterion" in cells[1]:
            continue

        priority = cells[2].strip()
        verdict = cells[3].strip()

        w = PRIORITY_WEIGHTS.get(priority, 0.0)
        v = VERDICT_SCORES.get(verdict, 0.0)
        if w > 0:
            weighted_sum += w * v
            weight_total += w

    if weight_total == 0:
        return 0.0
    return round(weighted_sum / weight_total, 2)


def _extract_research_from_transcript(session_id: str) -> str:
    """Extract research metadata from a Claude CLI transcript.

    Reads the .jsonl transcript for the given session_id and extracts:
    - Files read (Read tool calls)
    - Web searches (WebSearch/WebFetch)
    - Subagents spawned (Agent tool calls)
    - Grep/Glob patterns used
    """
    if not session_id:
        return ""

    # Find the transcript file — could be in any project directory
    claude_dir = Path.home() / ".claude" / "projects"
    transcript = None
    for project_dir in claude_dir.iterdir():
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            transcript = candidate
            break
        # Also check subagents/
        sub_dir = project_dir / session_id / "subagents"
        if sub_dir.exists():
            # Main transcript is in the project dir
            candidate = project_dir / f"{session_id}.jsonl"
            if candidate.exists():
                transcript = candidate
                break

    if not transcript:
        return ""

    files_read = []
    searches = []
    subagents = []
    greps = []

    with open(transcript) as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            if d.get("type") != "assistant":
                continue

            msg = d.get("message", {})
            for block in msg.get("content", []):
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name", "")
                inp = block.get("input", {})

                if name == "Read":
                    files_read.append(inp.get("file_path", ""))
                elif name == "WebSearch":
                    searches.append(inp.get("query", ""))
                elif name == "WebFetch":
                    searches.append(f"fetch: {inp.get('url', '')}")
                elif name == "Agent":
                    subagents.append(inp.get("description", inp.get("prompt", "")[:80]))
                elif name == "Grep":
                    greps.append(f"grep '{inp.get('pattern', '')}' in {inp.get('path', '.')}")
                elif name == "Glob":
                    greps.append(f"glob '{inp.get('pattern', '')}'")

    parts = []
    if files_read:
        parts.append("### Files Read\n" + "\n".join(f"- `{f}`" for f in files_read))
    if searches:
        parts.append("### Web Research\n" + "\n".join(f"- {s}" for s in searches))
    if greps:
        parts.append("### Code Search\n" + "\n".join(f"- {g}" for g in greps))
    if subagents:
        parts.append("### Subagents\n" + "\n".join(f"- {s}" for s in subagents))

    return "\n\n".join(parts)


def _append_feedback(content: str, job_id: str = "", role: str = "", skill: str = "project-management") -> dict:
    """Append one feedback entry to _feedback/feedback.jsonl."""
    from datetime import datetime
    FEEDBACK_FILE.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "job_id": job_id,
        "skill": skill,
        "agent_role": role,
        "content": content,
    }
    with open(FEEDBACK_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


@returns({"saved": "boolean"})
async def give_feedback(content: str, **params) -> dict:
    """Submit feedback to Agent Resources. Call as many times as you want.

    Args:
        content: Your feedback — anything unclear, frustrating, or improvable
    """
    job_id = params.get("__job_id__", "") or _ctx_job_id.get()
    role = params.get("_agent_role", "") or _ctx_agent_role.get()
    _append_feedback(content=content, job_id=job_id, role=role)
    return {"__result__": {"saved": True, "message": "Thanks — feedback recorded. Feel free to share more anytime."}}


@returns({"saved": "boolean", "path": "string"})
async def submit_proposal(content: str, project: str, round: int = 1, **params) -> dict:
    """Submit your proposal. Call this when you're done writing.

    Args:
        content: The full proposal in markdown
        project: Project directory path (provided in your instructions)
        round: Revision round number (provided in your instructions)
    """
    project_dir = Path(project)

    proposal_path = project_dir / "1-proposal.md"

    # Archive previous proposal on revision rounds
    if round > 1 and proposal_path.exists():
        drafts_dir = project_dir / "_drafts"
        drafts_dir.mkdir(exist_ok=True)
        prev_dest = drafts_dir / f"v{round - 1}-proposal.md"
        if not prev_dest.exists():
            proposal_path.rename(prev_dest)

    proposal_path.write_text(content)
    return {"__result__": {
        "saved": True,
        "path": str(proposal_path),
        "message": "Proposal saved.",
    }}


@returns({"saved": "boolean", "path": "string", "score": "number", "verdict": "string"})
async def submit_review(content: str, verdict: str, project: str, **params) -> dict:
    """Submit your review. Call this when you're done evaluating.

    Args:
        content: The full review in markdown
        verdict: implement, revise, or rethink
        project: Project directory path (provided in your instructions)
    """
    project_dir = Path(project)

    review_path = project_dir / "2-review.md"
    review_path.write_text(content)

    score = _compute_score(content)

    return {"__result__": {
        "saved": True,
        "path": str(review_path),
        "verdict": verdict,
        "score": score,
        "message": "Review saved.",
    }}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text[:60].lower()).strip("-")


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from text. Tolerates preamble before the first ---."""
    # Strip any preamble before the first ---
    idx = text.find("---")
    if idx < 0:
        return {}
    text = text[idx:]
    parts = text.split("---", 2)
    if len(parts) >= 3:
        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return {}
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
    _ctx_job_id.set(params.get("__job_id__", ""))
    _ctx_agent_role.set("write_rfp")

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
    system = _build_system(role=ROLE_WRITE_RFP, submit_tool="submit_proposal", body=body, today=today)
    result = await llm.agent(
        prompt=f"Write an RFP for this problem:\n\n{problem}",
        system=system,
        model="sonnet",
        tools=["exa.search", "exa.read_webpage"],
        timeout=1680,
    )

    await progress.progress(2, 3, "Saving RFP...")

    document = _strip_fenced_blocks(result.get("content", ""))
    rfp_path = project_dir / "0-rfp.md"
    rfp_path.write_text(document)

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
    _ctx_job_id.set(params.get("__job_id__", ""))
    _ctx_agent_role.set("propose")

    rfp_path = Path(rfp)
    project_dir = rfp_path.parent
    rfp_content = rfp_path.read_text()

    # Build prompt with RFP + prior proposal/review for revision rounds
    prompt_parts = [f"## RFP\n\n{rfp_content}"]

    if round > 1:
        drafts_dir = project_dir / "_drafts"
        prior_proposal = drafts_dir / f"v{round - 1}-proposal.md"
        prior_review = drafts_dir / f"v{round - 1}-review.md"
        prior_research = drafts_dir / f"v{round - 1}-research.md"
        if prior_proposal.exists():
            prompt_parts.append(f"\n\n## Your Previous Proposal (Round {round - 1})\n\n{prior_proposal.read_text()}")
        if prior_review.exists():
            prompt_parts.append(f"\n\n## Review Feedback (Round {round - 1})\n\n{prior_review.read_text()}")
        if prior_research.exists():
            prompt_parts.append(f"\n\n## Prior Research (Round {round - 1})\n\nFiles read, searches done, and findings from your previous round:\n\n{prior_research.read_text()}")

    await progress.progress(1, 3, f"Writing proposal (round {round})...")

    today = str(date.today())
    system = _build_system(role=ROLE_PROPOSE, submit_tool="submit_proposal", body=BODY_PROPOSE, today=today)

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

    document = _strip_fenced_blocks(result.get("content", ""))
    proposal_path.write_text(document)

    drafts_dir = project_dir / "_drafts"
    drafts_dir.mkdir(exist_ok=True)

    # Extract research from transcript — Python does this, not the agent
    session_id = result.get("session_id", "")
    research = _extract_research_from_transcript(session_id)
    if research:
        (drafts_dir / f"v{round}-research.md").write_text(research)

    # Save metadata — cost, turns, duration
    meta = {
        "round": round,
        "session_id": session_id,
        "cost_usd": result.get("total_cost_usd"),
        "turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
    }
    (drafts_dir / f"v{round}-propose-meta.json").write_text(json.dumps(meta, indent=2))

    await progress.progress(3, 3, "Done")

    return {"__result__": {"proposal_path": str(proposal_path)}}


@returns({"verdict": "string", "score": "number", "review_path": "string"})
@timeout(1800)
async def review(rfp: str, proposal: str, **params) -> dict:
    """Score a proposal adversarially against RFP criteria.

    Args:
        rfp: Path to 0-rfp.md
        proposal: Path to 1-proposal.md
    """
    progress.set_job_id(params.get("__job_id__", ""))
    _ctx_job_id.set(params.get("__job_id__", ""))
    _ctx_agent_role.set("review")

    rfp_content = Path(rfp).read_text()
    proposal_content = Path(proposal).read_text()
    project_dir = Path(rfp).parent

    prompt = f"## RFP\n\n{rfp_content}\n\n## Proposal\n\n{proposal_content}"

    await progress.progress(1, 3, "Reviewing proposal...")

    today = str(date.today())
    body = BODY_REVIEW.format(date=today)
    system = _build_system(role=ROLE_REVIEW, submit_tool="submit_review", body=body, today=today)
    result = await llm.agent(
        prompt=prompt,
        system=system,
        model="sonnet",
        tools=["exa.search", "exa.read_webpage"],
        timeout=1680,
    )

    await progress.progress(2, 3, "Saving review...")

    content = result.get("content", "")
    document = _strip_fenced_blocks(content)

    # Extract verdict — find "overall verdict" line, then grab the keyword
    verdict = "revise"  # safe default
    for line in document.splitlines():
        line_lower = line.lower().strip()
        if "overall" in line_lower and "verdict" in line_lower:
            for v in ["implement", "rethink", "revise"]:
                if v in line_lower:
                    verdict = v
                    break
            break
    else:
        # Fallback: scan whole doc for bold verdict keywords
        doc_lower = document.lower()
        for v in ["rethink", "revise", "implement"]:
            if f"**{v}**" in doc_lower:
                verdict = v
                break

    # Python computes the quantitative score from the criteria table
    score = _compute_score(document)

    review_path = project_dir / "2-review.md"
    review_path.write_text(document)

    await progress.progress(3, 3, "Done")

    return {"__result__": {"verdict": verdict, "score": score, "review_path": str(review_path)}}


@returns({"closeout_path": "string", "commits": "string"})
@timeout(1800)
async def closeout(project: str, **params) -> dict:
    """Write a closeout for a completed project.

    Args:
        project: Path to the project directory (e.g. _projects/p1/my-project/)
    """
    progress.set_job_id(params.get("__job_id__", ""))
    _ctx_job_id.set(params.get("__job_id__", ""))
    _ctx_agent_role.set("closeout")

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
    system = _build_system(role=ROLE_CLOSEOUT, submit_tool="submit_proposal", body=BODY_CLOSEOUT, today=today)
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

    document = _strip_fenced_blocks(result.get("content", ""))
    closeout_path = project_dir / "3-closeout.md"
    closeout_path.write_text(document)

    await progress.progress(4, 4, "Done")

    return {"__result__": {"closeout_path": str(closeout_path), "commits": git_log}}


PHASES = ["rfp", "propose", "review", "closeout"]


@returns({"rfp_path": "string", "proposal_path": "string", "review_path": "string", "rounds": "integer", "verdict": "string", "score": "number"})
@timeout(1800)
async def solve(problem: str = "", priority: int = 2, max_rounds: int = 5, start_from: str = "rfp", project: str = "", **params) -> dict:
    """Run the project lifecycle from any phase.

    Args:
        problem: Problem statement or path to a file (required if start_from="rfp")
        priority: Priority level 1-3 (default 2)
        max_rounds: Max propose->review iterations (default 3)
        start_from: Phase to start from: rfp, propose, review, closeout
        project: Path to existing project dir (required if start_from != "rfp")
    """
    progress.set_job_id(params.get("__job_id__", ""))

    start_idx = PHASES.index(start_from) if start_from in PHASES else 0

    # Resolve project dir and rfp path
    if project:
        project_dir = Path(project)
        rfp_path = str(project_dir / "0-rfp.md")
    elif start_idx == 0:
        rfp_path = ""
        project_dir = None
    else:
        return {"__result__": {"error": "project path required when start_from != 'rfp'"}}

    proposal_path = ""
    review_path = ""
    verdict = ""
    score = 0.0
    round_num = 0

    # ── RFP phase ───────────────────────────────────────────────────────
    if start_idx <= 0:
        if not problem:
            return {"__result__": {"error": "problem required for rfp phase"}}
        await progress.progress(1, 4, "Writing RFP...")
        rfp_result = await write_rfp(problem=problem, priority=priority, **params)
        rfp_path = rfp_result["__result__"]["rfp_path"]
        project_dir = Path(rfp_path).parent

    # ── Propose <-> Review loop ─────────────────────────────────────────
    if start_idx <= 2:
        # Determine starting round from existing _drafts
        start_round = 1
        if start_idx >= 1 and project_dir:
            drafts_dir = project_dir / "_drafts"
            if drafts_dir.exists():
                existing = [f.name for f in drafts_dir.glob("v*-proposal.md")]
                if existing:
                    start_round = max(int(f[1:].split("-")[0]) for f in existing) + 1

        # If starting from review, just review the existing proposal
        if start_idx == 2:
            proposal_path = str(project_dir / "1-proposal.md")
            await progress.progress(1, 2, f"Reviewing (round {start_round})...")
            review_result = await review(
                rfp=rfp_path, proposal=proposal_path, _round=start_round, **params
            )
            verdict = review_result["__result__"]["verdict"]
            review_path = review_result["__result__"]["review_path"]
            round_num = start_round
        else:
            # Propose -> review loop
            total_steps = max_rounds * 2
            for round_num in range(start_round, start_round + max_rounds):
                step = (round_num - start_round) * 2

                await progress.progress(step + 1, total_steps, f"Proposing (round {round_num})...")
                propose_result = await propose(rfp=rfp_path, round=round_num, **params)
                proposal_path = propose_result["__result__"]["proposal_path"]

                await progress.progress(step + 2, total_steps, f"Reviewing (round {round_num})...")
                review_result = await review(
                    rfp=rfp_path, proposal=proposal_path, _round=round_num, **params
                )
                verdict = review_result["__result__"]["verdict"]
                review_path = review_result["__result__"]["review_path"]
                score = review_result["__result__"].get("score", 0)

                if verdict == "implement":
                    break

                # Move rejected to _drafts for next round
                if round_num < start_round + max_rounds - 1:
                    review_file = project_dir / "2-review.md"
                    if review_file.exists():
                        review_file.rename(drafts_dir / f"v{round_num}-review.md")

    # ── Closeout phase ──────────────────────────────────────────────────
    if start_idx <= 3 and (start_idx == 3 or verdict == "implement"):
        await progress.progress(1, 1, "Writing closeout...")
        closeout_result = await closeout(project=str(project_dir), **params)

    await progress.progress(1, 1, f"Done — verdict: {verdict}")

    return {
        "__result__": {
            "rfp_path": rfp_path,
            "proposal_path": proposal_path,
            "review_path": review_path,
            "rounds": round_num,
            "verdict": verdict,
            "score": score,
        }
    }

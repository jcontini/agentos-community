"""
compose.py — Research, draft, and review documents with multi-agent iteration

Combines proposal drafting and scored adversarial review into one skill.
All LLM calls go through llm.agent() — no subprocess spawning.

Operations:
    outline  — Quick scope-alignment outline (sync, 1 LLM call)
    draft    — Full researched proposal (async, 1 LLM call)
    review   — Scored adversarial review (async, 9-17 LLM calls)
    status   — Check review state (sync, no LLM)
    resume   — Continue interrupted review (async, 3-5 LLM calls)

Review process:
    Phase 1: Reviewer defines criteria -> Author<->Reviewer iterate until convergence
    Phase 2: Red Team audits (reads document + thread + actual codebase files)
    Phase 3: Author<->Reviewer address Red Team findings
    Phase 4: Red Team validates and writes verdict
"""

import re
import textwrap
from pathlib import Path

from agentos import llm, progress, returns, timeout


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

DRAFTER_PROMPT = textwrap.dedent("""\
    You are writing a proposal document. Your job is to research the problem,
    explore the solution space, and produce a concrete, honest design document.

    ## Principles

    1. **Problem first.** Spend real effort understanding and articulating the
       problem before jumping to solutions. Who's affected? What's broken? What
       have they tried? Why hasn't it been solved yet?

    2. **Show, don't describe.** When you propose a CLI command, show its exact
       output. When you propose a file format, show a complete example. When you
       propose an API, show the call and response.

    3. **Be concrete about trade-offs.** Every design decision trades something.
       Name what you're giving up, not just what you're getting.

    4. **Separate what exists from what you're proposing.** If something already
       works, say so. If something needs building, say so.

    5. **Acknowledge what you don't know.** Open questions aren't weakness —
       they're honesty.

    6. **Write for your reviewer.** This document will be evaluated by someone
       who scores it against weighted criteria. Make their job easy: clear
       structure, concrete artifacts, honest trade-offs.

    ## Output format

    Write a complete markdown document with YAML frontmatter:

    ```
    ---
    title: "..."
    priority: N
    labels: [...]
    problem: |
      One paragraph: who's affected and what's broken.
    success_criteria: "Bullet list of measurable outcomes"
    ---

    # [Title]

    ## The Problem
    ## Proposed Design
    ## Alternatives Considered
    ## Trade-offs
    ## Implementation
    ## Open Questions
    ```

    IMPORTANT: The proposal must be a COMPLETE, STANDALONE document.
""")

OUTLINER_PROMPT = textwrap.dedent("""\
    You are creating a lightweight outline for a proposal. This is NOT the
    full document — it's a quick sketch to align on scope and approach.

    Write a concise outline (under 500 words):

    # [Title]
    ## Problem — 2-3 sentences
    ## Proposed approach — 3-5 bullet points
    ## Key sections the full proposal will cover
    ## Open questions to research
    ## Estimated scope — Small / Medium / Large

    Be direct. This is a 2-minute read, not a document.
""")

REVIEWER_PROMPT = textwrap.dedent("""\
    You are the Reviewer in a Scored Review process. Your role is adversarial
    but constructive: you define evaluation criteria, score the document against
    them, and push on weak spots.

    ## Rules

    1. **Define criteria BEFORE scoring.** On your first round, create a weighted
       scoring rubric with 5-9 criteria. Each criterion gets: name, weight (summing
       to 100), and a 0-5 scale. The criteria must be specific to the document's
       domain — not generic quality metrics.

    2. **Score with math, not vibes.** Every score must show: criterion, weight,
       score (0-5), weighted score, and a concrete justification. Total is
       sum(weight * score). Max is 500.

    3. **Never propose solutions.** Say "this is missing" or "this contradicts X"
       — never "you should do Y instead."

    4. **Push on softness.** When the document describes something vaguely, demand
       specifics. "Show me" is your most powerful phrase.

    5. **Be honest about improvements.** Raise scores when fixes are good. Don't
       anchor to your first score.

    6. **Separate blocking from non-blocking.** BLOCKING = must fix. NON-BLOCKING
       = should fix, can ship without.

    ## Output format

    ```
    ## Round N — Reviewer

    ### Score: XXX/500

    | Criterion | Weight | Score | Weighted | Notes |
    |---|---|---|---|---|

    ### Issues

    **BLOCKING:**
    1. ...

    **NON-BLOCKING:**
    1. ...

    ### Specific asks for next round
    ```

    Threshold: <300 = missing fundamentals. 300-400 = solid. >400 = ready to ship.
""")

AUTHOR_PROMPT = textwrap.dedent("""\
    You are the Author in a Scored Review process. You wrote the document being
    reviewed. Your role is to revise based on scored critique, push back when
    warranted, and show your work.

    ## Rules

    1. **Accept valid critique honestly.** If the Reviewer found a real gap, fix it.
    2. **Push back with evidence.** "I disagree because X" is valid. "I disagree" is not.
    3. **Show, don't describe.** When asked "what does it look like?" — show it.
    4. **Revise the document, not just the thread.** Actually change the document.
    5. **Don't over-fix.** Address what was asked. Don't restructure everything.

    ## Output format

    ```
    ## Round N — Author

    ### Addressing feedback

    **Issue 1: [title]**
    [What you changed and why. Or why you disagree.]

    ### What changed in the document
    - [Specific change 1]
    - [Specific change 2]
    ```
""")

RED_TEAM_PROMPT = textwrap.dedent("""\
    You are the Red Team in a Scored Review process. You have fresh eyes — you
    were not part of the Author<->Reviewer dialogue. Your role is to audit both
    the document AND the review conversation for shared blind spots.

    ## Rules

    1. **Read everything.** The document, the thread, AND the context files.
    2. **Identify shared blind spots.** Look for things they both take for
       granted that aren't actually true.
    3. **Check every factual claim.** If the document says "X exists" — verify it.
    4. **Score independently.** Use the Reviewer's criteria but apply your own scores.
    5. **Classify severity.** BLOCKING / HIGH / INFORMATIONAL.

    ## Output format

    ```
    ## Red Team Audit

    > I read: [list of files]

    ### Score: XXX/500
    | Criterion | Weight | Score | Weighted | Notes |

    ### Findings
    **BLOCKING:** ...
    **HIGH:** ...
    **INFORMATIONAL:** ...

    ### What the dialogue missed
    ### Recommendation
    ```
""")

RED_TEAM_VALIDATE_PROMPT = textwrap.dedent("""\
    You are the Red Team doing a FINAL VALIDATION. The Author has addressed your
    earlier findings. Verify:

    1. Were BLOCKING issues actually fixed?
    2. Were HIGH issues addressed?
    3. Did any new issues emerge?
    4. Is it ready to ship?

    ## Output format

    ```
    ## Final Validation — Red Team

    ### Blocking issues
    | Issue | Status | Notes |
    |---|---|---|
    | [original issue] | RESOLVED / UNRESOLVED / PARTIALLY | [evidence] |

    ### Final score: XXX/500

    ### Verdict
    [SHIP IT / ONE MORE ROUND / NEEDS RETHINK]
    [2-3 sentences rationale]
    ```
""")

PROMPTS = {
    "drafter": DRAFTER_PROMPT,
    "outliner": OUTLINER_PROMPT,
    "reviewer": REVIEWER_PROMPT,
    "author": AUTHOR_PROMPT,
    "red_team": RED_TEAM_PROMPT,
    "red_team_validate": RED_TEAM_VALIDATE_PROMPT,
}


# ---------------------------------------------------------------------------
# Agent runner — all LLM calls go through llm.agent()
# ---------------------------------------------------------------------------

def _run_agent(role, prompt, files_to_read, files_to_write=None, model="opus"):
    """Run an LLM agent with a role-specific system prompt."""
    tools = ["Read", "Glob", "Grep"]
    if files_to_write:
        tools.extend(["Edit", "Write"])

    result = llm.agent(
        prompt=prompt,
        system=PROMPTS[role],
        tools=tools,
        files=(files_to_read or []) + (files_to_write or []),
        model=model,
    )
    return result.get("content", "")


# ---------------------------------------------------------------------------
# Thread management (for review)
# ---------------------------------------------------------------------------

def _thread_path(document_path):
    p = Path(document_path)
    return str(p.parent / f"{p.stem}-review{p.suffix}")


def _init_thread(thread_path, document_path):
    header = textwrap.dedent(f"""\
        # Scored Review

        > **Document:** `{document_path}`
        > **Process:** Reviewer defines criteria -> Author<->Reviewer iterate ->
        > Red Team audits -> Author<->Reviewer address findings -> Red Team validates

        ---
    """)
    Path(thread_path).write_text(header)


def _append_to_thread(thread_path, content):
    with open(thread_path, "a") as f:
        f.write(f"\n\n{content}\n")


def _read_file(path):
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""


def _extract_score(text):
    matches = re.findall(r'(\d{2,3})\s*/\s*500', text)
    return int(matches[-1]) if matches else None


def _extract_phase(thread_text):
    if "Final Validation" in thread_text:
        return "complete"
    if "Red Team Audit" in thread_text:
        last_red = thread_text.rfind("Red Team Audit")
        last_author = thread_text.rfind("— Author")
        if last_author > last_red:
            return "phase3_revision"
        return "phase2_red_team"
    return "phase1_convergence"


def _count_rounds(thread_text):
    return len(re.findall(r'## Round \d+ — Reviewer', thread_text))


def _scores_converging(thread_text, threshold=15):
    scores = re.findall(r'### Score:\s*(\d{2,3})\s*/\s*500', thread_text)
    if len(scores) < 2:
        return False
    return abs(int(scores[-1]) - int(scores[-2])) <= threshold


def _extract_verdict(thread_text):
    if "Final Validation" not in thread_text:
        return ""
    final_section = thread_text.split("Final Validation")[-1]
    for v in ["SHIP IT", "ONE MORE ROUND", "NEEDS RETHINK"]:
        if v in final_section:
            return v
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

@returns({"outline": "string", "problem": "string", "sections": "array"})
@timeout(120)
def op_outline(problem: str, domain: str = "",
               model: str = "sonnet", **params) -> dict:
    """Generate a lightweight outline before committing to a full draft."""
    domain_hint = f"\n\nDomain: {domain}" if domain else ""
    prompt = (
        f"Create a proposal outline for:\n\n"
        f"---\n{problem}\n---\n"
        f"{domain_hint}\n\n"
        f"Keep it under 500 words. This is a sketch to align on scope."
    )
    output = _run_agent("outliner", prompt, files_to_read=[], model=model)

    sections = [line.strip()[3:] for line in output.split("\n")
                if line.strip().startswith("## ")]

    return {"__result__": {
        "outline": output,
        "problem": problem[:200],
        "sections": sections,
    }}


@returns({"document": "string", "problem": "string", "sections": "integer", "tokens": "integer"})
@timeout(600)
def op_draft(problem: str, output: str, context: str = "",
             domain: str = "", research: bool = True,
             model: str = "opus", **params) -> dict:
    """Research a problem and generate a structured proposal."""
    progress.set_job_id(params.get("__job_id__", ""))

    output = str(Path(output).resolve())
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    context_paths = []
    if context:
        for p in context.split(","):
            p = p.strip()
            if p:
                resolved = str(Path(p).resolve())
                if Path(resolved).exists():
                    context_paths.append(resolved)

    domain_hint = f"\n\nDomain: {domain}." if domain else ""
    research_hint = ("\n\nResearch the problem space using web search."
                     if research else "")

    prompt = (
        f"Write a proposal for the following problem:\n\n"
        f"---\n{problem}\n---\n"
        f"{domain_hint}{research_hint}\n\n"
        f"Write the complete proposal document to: `{output}`\n\n"
        f"The document must be standalone — someone reading it with no other "
        f"context should understand the problem, the design, and the trade-offs."
    )

    progress.progress(1, 2, "Drafting proposal...")

    agent_output = _run_agent(
        "drafter", prompt,
        files_to_read=context_paths,
        files_to_write=[output],
        model=model,
    )

    if not Path(output).exists():
        Path(output).write_text(agent_output)

    content = Path(output).read_text()
    word_count = len(content.split())

    progress.progress(2, 2, "Draft complete")

    return {"__result__": {
        "document": output,
        "problem": problem[:200],
        "sections": content.count("\n## "),
        "tokens": int(word_count * 1.3),
    }}


@returns({"thread": "string", "document": "string", "score": "integer", "verdict": "string", "rounds": "integer", "phase": "string"})
@timeout(600)
def op_review(document: str, context: str = "", domain: str = "",
              max_rounds: int = 3, model: str = "opus", **params) -> dict:
    """Start a scored review of a document."""
    progress.set_job_id(params.get("__job_id__", ""))

    document = str(Path(document).resolve())
    if not Path(document).exists():
        return {"__result__": {"error": f"Document not found: {document}"}}

    thread = _thread_path(document)
    context_paths = [str(Path(p.strip()).resolve())
                     for p in context.split(",") if p.strip()] if context else []

    _init_thread(thread, document)

    # Estimate total steps: reviewer_init(1) + rounds*2 + red_team(1) + author(1) + reviewer(1) + validate(1)
    total_steps = 1 + (max_rounds * 2) + 4
    step = 0

    doc_content = _read_file(document)
    domain_hint = f"\n\nDomain hint: {domain}" if domain else ""

    # --- Phase 1: Reviewer defines criteria and scores ---

    reviewer_prompt = (
        f"Review this document. First define weighted evaluation criteria "
        f"(5-9 criteria, weights summing to 100), then score the document "
        f"against them.{domain_hint}\n\n"
        f"Document content:\n\n{doc_content}"
    )
    reviewer_output = _run_agent("reviewer", reviewer_prompt,
                                 files_to_read=[document], model=model)
    _append_to_thread(thread, reviewer_output)
    step += 1
    score = _extract_score(_read_file(thread))
    progress.progress(step, total_steps,
                      f"Initial review: {score or '?'}/500")

    # --- Phase 1: Author <-> Reviewer iteration ---

    for round_num in range(1, max_rounds + 1):
        author_prompt = (
            "The Reviewer has scored your document and identified issues. "
            "Read the review thread, then revise the document to address "
            "the feedback. Write your response for the thread."
        )
        author_output = _run_agent("author", author_prompt,
                                   files_to_read=[document, thread],
                                   files_to_write=[document], model=model)
        _append_to_thread(thread, author_output)
        step += 1
        progress.progress(step, total_steps,
                          f"Round {round_num}: Author revised")

        reviewer_prompt = (
            "The Author has revised the document. Re-read both the document "
            "and thread, then rescore. Identify any remaining issues."
        )
        reviewer_output = _run_agent("reviewer", reviewer_prompt,
                                     files_to_read=[document, thread],
                                     model=model)
        _append_to_thread(thread, reviewer_output)
        step += 1
        score = _extract_score(_read_file(thread))
        progress.progress(step, total_steps,
                          f"Round {round_num}: Reviewer scored {score or '?'}/500")

        if _scores_converging(_read_file(thread)):
            break

    # --- Phase 2: Red Team audit ---

    red_team_files = [document, thread] + context_paths
    red_team_output = _run_agent(
        "red_team",
        "Audit this document and its review thread. You have fresh eyes. "
        "Check claims against the actual files. Identify shared blind spots.",
        files_to_read=red_team_files, model=model)
    _append_to_thread(thread, red_team_output)
    step += 1
    progress.progress(step, total_steps, "Red Team audit complete")

    # --- Phase 3: Author addresses Red Team findings ---

    author_output = _run_agent(
        "author",
        "The Red Team found issues you and the Reviewer both missed. "
        "Revise the document to address BLOCKING and HIGH issues.",
        files_to_read=[document, thread],
        files_to_write=[document], model=model)
    _append_to_thread(thread, author_output)
    step += 1
    progress.progress(step, total_steps, "Author addressed Red Team findings")

    reviewer_output = _run_agent(
        "reviewer",
        "The Author has addressed Red Team findings. Rescore incorporating "
        "both your criteria and the Red Team's findings.",
        files_to_read=[document, thread], model=model)
    _append_to_thread(thread, reviewer_output)
    step += 1
    score = _extract_score(_read_file(thread))
    progress.progress(step, total_steps,
                      f"Post-Red-Team score: {score or '?'}/500")

    # --- Phase 4: Red Team validates ---

    red_team_output = _run_agent(
        "red_team_validate",
        "Final validation — were blocking issues resolved? "
        "Read the updated document and full thread.",
        files_to_read=red_team_files, model=model)
    _append_to_thread(thread, red_team_output)
    step += 1

    final_thread = _read_file(thread)
    final_score = _extract_score(final_thread)
    verdict = _extract_verdict(final_thread)

    progress.progress(step, total_steps,
                      f"Complete: {final_score or '?'}/500 — {verdict}")

    return {"__result__": {
        "thread": thread,
        "document": document,
        "score": final_score or 0,
        "verdict": verdict,
        "rounds": _count_rounds(final_thread),
        "phase": "complete",
    }}


@returns({"phase": "string", "round": "integer", "score": "integer", "blockingIssues": "integer", "verdict": "string"})
@timeout(15)
def op_status(thread: str, **params) -> dict:
    """Check the current state of a review without resuming."""
    thread = str(Path(thread).resolve())
    if not Path(thread).exists():
        return {"__result__": {"error": f"Thread not found: {thread}"}}

    content = _read_file(thread)

    return {"__result__": {
        "phase": _extract_phase(content),
        "round": _count_rounds(content),
        "score": _extract_score(content) or 0,
        "blockingIssues": len(re.findall(r'(?i)\*\*BLOCKING\*\*', content)),
        "verdict": _extract_verdict(content),
    }}


@returns({"thread": "string", "document": "string", "score": "integer", "verdict": "string", "rounds": "integer", "phase": "string"})
@timeout(600)
def op_resume(thread: str, context: str = "", max_rounds: int = 2,
              model: str = "opus", **params) -> dict:
    """Resume an interrupted or ONE MORE ROUND review."""
    progress.set_job_id(params.get("__job_id__", ""))

    thread = str(Path(thread).resolve())
    if not Path(thread).exists():
        return {"__result__": {"error": f"Thread not found: {thread}"}}

    content = _read_file(thread)

    doc_match = re.search(r'\*\*Document:\*\*\s*`([^`]+)`', content)
    if not doc_match:
        return {"__result__": {"error": "Could not find document path in thread header"}}
    document = doc_match.group(1)

    context_paths = [str(Path(p.strip()).resolve())
                     for p in context.split(",") if p.strip()] if context else []

    phase = _extract_phase(content)
    step = 0
    total_steps = 5  # rough estimate

    if phase == "phase1_convergence":
        for _ in range(max_rounds):
            author_output = _run_agent(
                "author", "Continue addressing the Reviewer's latest feedback.",
                files_to_read=[document, thread],
                files_to_write=[document], model=model)
            _append_to_thread(thread, author_output)
            step += 1
            progress.progress(step, total_steps, "Author revised")

            reviewer_output = _run_agent(
                "reviewer", "Rescore the revised document.",
                files_to_read=[document, thread], model=model)
            _append_to_thread(thread, reviewer_output)
            step += 1
            score = _extract_score(_read_file(thread))
            progress.progress(step, total_steps, f"Reviewer scored {score or '?'}/500")

            if _scores_converging(_read_file(thread)):
                break

        red_team_files = [document, thread] + context_paths
        red_team_output = _run_agent(
            "red_team", "Audit this document and thread with fresh eyes.",
            files_to_read=red_team_files, model=model)
        _append_to_thread(thread, red_team_output)
        step += 1
        progress.progress(step, total_steps, "Red Team audit complete")

    if phase in ("phase2_red_team", "phase1_convergence"):
        author_output = _run_agent(
            "author", "Address the Red Team's BLOCKING and HIGH findings.",
            files_to_read=[document, thread],
            files_to_write=[document], model=model)
        _append_to_thread(thread, author_output)

        reviewer_output = _run_agent(
            "reviewer", "Rescore incorporating Red Team findings.",
            files_to_read=[document, thread], model=model)
        _append_to_thread(thread, reviewer_output)

    red_team_files = [document, thread] + context_paths
    red_team_output = _run_agent(
        "red_team_validate", "Final validation — were blocking issues resolved?",
        files_to_read=red_team_files, model=model)
    _append_to_thread(thread, red_team_output)

    final_thread = _read_file(thread)
    final_score = _extract_score(final_thread)
    verdict = _extract_verdict(final_thread)

    progress.progress(total_steps, total_steps,
                      f"Complete: {final_score or '?'}/500 — {verdict}")

    return {"__result__": {
        "thread": thread,
        "document": document,
        "score": final_score or 0,
        "verdict": verdict,
        "rounds": _count_rounds(final_thread),
        "phase": "complete",
    }}

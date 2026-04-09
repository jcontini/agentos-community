"""
review.py — Scored Review: adversarial design review with Author, Reviewer, and Red Team

Orchestrates three Claude agents through an iterative review process:

    Phase 1: Reviewer defines criteria → Author↔Reviewer iterate until convergence
    Phase 2: Red Team audits (reads document + thread + actual codebase files)
    Phase 3: Author↔Reviewer address Red Team findings
    Phase 4: Red Team validates and writes verdict

Each agent is a `claude -p` subprocess with a role-specific system prompt.
The thread file is the shared artifact — each agent appends their section.

Inspired by:
    - Academic peer review (referee → R&R cycles → handling editor)
    - Intelligence analysis (ACH + Red Cell adversarial audit)
    - FDA regulatory review (parallel discipline reviews + advisory committee)
    - Adversarial legal system (prosecution, defense, amicus curiae)

The key mechanism: weighted criteria defined BEFORE evaluation.
Without scores, it's just two agents trading vibes.
"""

import json
import os
import re
import textwrap
from pathlib import Path

from agentos import shell, returns, timeout

# ---------------------------------------------------------------------------
# System prompts — the soul of each role
# ---------------------------------------------------------------------------

REVIEWER_PROMPT = textwrap.dedent("""\
    You are the Reviewer in a Scored Review process. Your role is adversarial
    but constructive: you define evaluation criteria, score the document against
    them, and push on weak spots.

    ## Rules

    1. **Define criteria BEFORE scoring.** On your first round, create a weighted
       scoring rubric with 5-9 criteria. Each criterion gets: name, weight (summing
       to 100), and a 0-5 scale with concrete definitions for each level. The
       criteria must be specific to the document's domain — not generic quality
       metrics.

    2. **Score with math, not vibes.** Every score must show: criterion, weight,
       score (0-5), weighted score, and a concrete justification. Total is
       sum(weight × score). Max is 500.

    3. **Never propose solutions.** Your job is to identify problems, not fix
       them. Say "this is missing" or "this contradicts X" — never "you should
       do Y instead." The Author decides how to fix things.

    4. **Push on softness.** When the document describes something vaguely ("a
       context file with everything needed"), demand specifics ("show me the
       context file — what's in it?"). "Show me" is your most powerful phrase.

    5. **Be honest about improvements.** When the Author fixes something well,
       raise the score. Don't anchor to your first score out of stubbornness.
       But don't inflate scores to be nice either.

    6. **Separate blocking from non-blocking.** At the end of each round, list
       issues as BLOCKING (must fix before shipping) or NON-BLOCKING (should fix,
       can ship without).

    ## Output format

    Write your response as a markdown section:

    ```
    ## Round N — Reviewer

    ### Score: XXX/500

    | Criterion | Weight | Score | Weighted | Notes |
    |---|---|---|---|---|
    | ... | ... | ... | ... | ... |

    ### Issues

    **BLOCKING:**
    1. ...

    **NON-BLOCKING:**
    1. ...

    ### Specific asks for next round
    1. ...
    ```

    Threshold: below 300 = missing fundamentals. 300-400 = solid, buildable.
    Above 400 = ready to ship.
""")

AUTHOR_PROMPT = textwrap.dedent("""\
    You are the Author in a Scored Review process. You wrote the document being
    reviewed. Your role is to revise based on scored critique, push back when
    warranted, and show your work through concrete artifacts.

    ## Rules

    1. **Accept valid critique honestly.** If the Reviewer found a real gap, say
       so and fix it. Don't defend weak spots.

    2. **Push back with evidence.** If you disagree with a score, explain why
       with specific references to the document, codebase, or design constraints.
       "I disagree because X" is valid. "I disagree" is not.

    3. **Show, don't describe.** When asked "what does the scaffold output look
       like?" — show the actual files, not a description of them. When asked
       "what does the error look like?" — show the exact error message. Concreteness
       is what moves the score.

    4. **Revise the document, not just the thread.** When you accept feedback,
       actually change the document. Then describe what changed in the thread.

    5. **Don't over-fix.** Address what was asked. Don't add features, restructure
       the whole document, or "improve" things the Reviewer didn't flag. Scope
       creep in revision is as bad as scope creep in design.

    6. **Self-score honestly.** You may propose what you think the new score
       should be, but don't inflate. The Reviewer decides.

    ## Output format

    Write your response as a markdown section:

    ```
    ## Round N — Author

    ### Addressing feedback

    **Issue 1: [title]**
    [What you changed and why. Or why you disagree.]

    **Issue 2: [title]**
    [...]

    ### What changed in the document
    - [Specific change 1]
    - [Specific change 2]
    ```

    When you revise the document: read it, make the changes, then summarize
    what changed in the thread. The document should be readable standalone —
    someone shouldn't need to read the thread to understand the design.
""")

RED_TEAM_PROMPT = textwrap.dedent("""\
    You are the Red Team in a Scored Review process. You have fresh eyes — you
    were not part of the Author↔Reviewer dialogue. Your role is to audit both
    the document AND the review conversation for shared blind spots.

    ## What makes you different

    The Reviewer evaluates the design on its own terms. You check the design
    against reality. You read the actual codebase files, the actual data, the
    actual state of things. When the document says "fields are camelCase" and
    the codebase is snake_case — you catch that. When the document says "this
    tool exists" and it doesn't — you catch that.

    ## Rules

    1. **Read everything.** The document. The full review thread. AND the
       context files (codebase, docs, data). Your value comes from checking
       claims against ground truth.

    2. **Identify shared blind spots.** The Author and Reviewer have been
       talking for multiple rounds. They've developed shared assumptions that
       may be wrong. Look for things they both take for granted that aren't
       actually true.

    3. **Check every factual claim.** If the document says "X exists" — verify
       it exists. If it says "Y is the convention" — check the actual code. If
       it says "Z already works" — find the code that implements it.

    4. **Score independently.** Use the Reviewer's criteria but apply your own
       scores. If you agree with the Reviewer's scores, say so. If you
       disagree, explain why with evidence from the files you read.

    5. **Classify severity.** Every finding is either:
       - **BLOCKING** — factually wrong, contradicts codebase, or would cause
         failure if built as specified
       - **HIGH** — significant gap that should be fixed but won't cause failure
       - **INFORMATIONAL** — observation, suggestion, or meta-feedback

    ## Output format

    ```
    ## Red Team Audit

    > I read: [list of files you actually read]

    ### Score: XXX/500

    | Criterion | Weight | Score | Weighted | Notes |
    |---|---|---|---|---|

    ### Findings

    **BLOCKING:**
    1. [Finding + evidence from actual files]

    **HIGH:**
    1. [Finding + evidence]

    **INFORMATIONAL:**
    1. [Observation]

    ### What the dialogue missed
    [Shared blind spots you identified]

    ### Recommendation
    [Fix blockers + highs, then ship / needs another round / fundamental rethink]
    ```
""")

RED_TEAM_VALIDATE_PROMPT = textwrap.dedent("""\
    You are the Red Team doing a FINAL VALIDATION of a Scored Review. The Author
    has addressed your earlier findings. Your job is to verify:

    1. Were the BLOCKING issues actually fixed in the document?
    2. Were the HIGH issues addressed (fixed or acknowledged with rationale)?
    3. Did any new issues emerge from the fixes?
    4. Is the document ready to ship?

    Read the document, the thread (including your earlier audit and the Author's
    response), and the context files.

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

    [Brief rationale — 2-3 sentences max]
    ```

    Be concise. This is a final check, not a new review.
""")


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------

async def _run_agent(role: str, prompt: str, files_to_read: list[str],
               files_to_write: list[str] = None, model: str = "opus") -> str:
    """Run a Claude agent with a role-specific system prompt.

    Uses `claude -p` (print mode) with --system-prompt for the role,
    --allowed-tools for file access, and --permission-mode for autonomy.

    Returns the agent's text output.
    """
    system_prompts = {
        "reviewer": REVIEWER_PROMPT,
        "author": AUTHOR_PROMPT,
        "red_team": RED_TEAM_PROMPT,
        "red_team_validate": RED_TEAM_VALIDATE_PROMPT,
    }

    system_prompt = system_prompts[role]

    # Build the tool allowlist
    allowed_tools = ["Read", "Glob", "Grep"]
    if files_to_write:
        allowed_tools.extend(["Edit", "Write"])

    # Build add-dir list from file paths (unique parent directories)
    add_dirs = set()
    for f in (files_to_read or []) + (files_to_write or []):
        p = Path(f)
        add_dirs.add(str(p.parent if p.is_file() else p))
    # Always include cwd
    add_dirs.add(os.getcwd())

    # Construct the prompt with file reading instructions
    file_instructions = ""
    if files_to_read:
        file_list = "\n".join(f"- `{f}`" for f in files_to_read)
        file_instructions = f"\n\n**Read these files first:**\n{file_list}\n"

    write_instructions = ""
    if files_to_write:
        write_list = "\n".join(f"- `{f}`" for f in files_to_write)
        write_instructions = f"\n\n**Write your output to:**\n{write_list}\n"

    full_prompt = f"{prompt}{file_instructions}{write_instructions}"

    # Run via shell.run (which handles quoting and env)
    args = [
        "-p",
        "--dangerously-skip-permissions",
        "--model", model,
        "--system-prompt", system_prompt,
        "--allowed-tools", ",".join(allowed_tools),
        "--permission-mode", "auto",
    ]
    for d in sorted(add_dirs):
        args.extend(["--add-dir", str(d)])

    # Pass prompt via stdin — --add-dir is variadic and eats trailing positional args
    result = await shell.run("claude", args=args, input=full_prompt, timeout=300)

    return result.get("stdout", "") if isinstance(result, dict) else str(result)


# ---------------------------------------------------------------------------
# Thread management
# ---------------------------------------------------------------------------

def _thread_path(document_path: str) -> str:
    """Derive the thread file path from the document path."""
    p = Path(document_path)
    return str(p.parent / f"{p.stem}-review{p.suffix}")


def _init_thread(thread_path: str, document_path: str) -> None:
    """Create the thread file with header."""
    header = textwrap.dedent(f"""\
        # Scored Review

        > **Document:** `{document_path}`
        > **Process:** Reviewer defines criteria → Author↔Reviewer iterate →
        > Red Team audits → Author↔Reviewer address findings → Red Team validates

        ---
    """)
    Path(thread_path).write_text(header)


def _append_to_thread(thread_path: str, content: str) -> None:
    """Append a section to the thread file."""
    with open(thread_path, "a") as f:
        f.write(f"\n\n{content}\n")


def _read_file(path: str) -> str:
    """Read a file, returning empty string if it doesn't exist."""
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""


def _extract_score(text: str) -> int | None:
    """Extract the most recent score (XXX/500) from text."""
    matches = re.findall(r'(\d{2,3})\s*/\s*500', text)
    return int(matches[-1]) if matches else None


def _extract_phase(thread_text: str) -> str:
    """Determine the current phase from thread content."""
    if "Final Validation" in thread_text:
        return "complete"
    if "Red Team Audit" in thread_text:
        if thread_text.count("Red Team Audit") >= 1:
            # Check if author responded after red team
            last_red = thread_text.rfind("Red Team Audit")
            last_author = thread_text.rfind("— Author")
            if last_author > last_red:
                return "phase3_revision"
            return "phase2_red_team"
    return "phase1_convergence"


def _count_rounds(thread_text: str) -> int:
    """Count the number of Reviewer rounds in the thread."""
    return len(re.findall(r'## Round \d+ — Reviewer', thread_text))


def _scores_converging(thread_text: str, threshold: int = 15) -> bool:
    """Check if the last two Reviewer scores are within threshold."""
    scores = re.findall(r'### Score:\s*(\d{2,3})\s*/\s*500', thread_text)
    if len(scores) < 2:
        return False
    return abs(int(scores[-1]) - int(scores[-2])) <= threshold


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

@returns({"thread": "string", "document": "string", "score": "integer", "verdict": "string", "rounds": "integer", "phase": "string"})
@timeout(600)
async def op_start(document: str, context: str = "", domain: str = "",
             max_rounds: int = 3, model: str = "opus", **params) -> dict:
    """Start a scored review of a document."""
    document = str(Path(document).resolve())
    if not Path(document).exists():
        return {"__result__": {"error": f"Document not found: {document}"}}

    thread = _thread_path(document)
    context_paths = [str(Path(p.strip()).resolve())
                     for p in context.split(",") if p.strip()] if context else []

    _init_thread(thread, document)

    doc_content = _read_file(document)
    domain_hint = f"\n\nDomain hint: {domain}" if domain else ""

    # ─── Phase 1: Reviewer defines criteria and scores ──────────────────

    reviewer_prompt = (
        f"Review this document. First define weighted evaluation criteria "
        f"(5-9 criteria, weights summing to 100), then score the document "
        f"against them.{domain_hint}\n\n"
        f"Document content:\n\n{doc_content}"
    )

    reviewer_output = await _run_agent(
        "reviewer", reviewer_prompt,
        files_to_read=[document],
        model=model,
    )
    _append_to_thread(thread, reviewer_output)

    # ─── Phase 1: Author ↔ Reviewer iteration ──────────────────────────

    for round_num in range(1, max_rounds + 1):
        thread_content = _read_file(thread)

        # Author addresses feedback
        author_prompt = (
            f"The Reviewer has scored your document and identified issues. "
            f"Read the review thread, then revise the document to address "
            f"the feedback. Write your response for the thread explaining "
            f"what you changed and why."
        )
        author_output = await _run_agent(
            "author", author_prompt,
            files_to_read=[document, thread],
            files_to_write=[document],
            model=model,
        )
        _append_to_thread(thread, author_output)

        # Reviewer rescores
        reviewer_prompt = (
            f"The Author has revised the document in response to your "
            f"feedback. Re-read both the document and thread, then rescore. "
            f"Identify any remaining issues."
        )
        reviewer_output = await _run_agent(
            "reviewer", reviewer_prompt,
            files_to_read=[document, thread],
            model=model,
        )
        _append_to_thread(thread, reviewer_output)

        # Check convergence
        thread_content = _read_file(thread)
        if _scores_converging(thread_content):
            break

    # ─── Phase 2: Red Team audit ────────────────────────────────────────

    red_team_files = [document, thread] + context_paths
    red_team_prompt = (
        f"Audit this document and its review thread. You have fresh eyes — "
        f"you were not part of the Author↔Reviewer dialogue. Check claims "
        f"against the actual files. Identify shared blind spots."
    )
    red_team_output = await _run_agent(
        "red_team", red_team_prompt,
        files_to_read=red_team_files,
        model=model,
    )
    _append_to_thread(thread, red_team_output)

    # ─── Phase 3: Author addresses Red Team findings ────────────────────

    author_prompt = (
        f"The Red Team has audited the document with fresh eyes and found "
        f"issues that you and the Reviewer both missed. Read their findings, "
        f"then revise the document to address BLOCKING and HIGH issues."
    )
    author_output = await _run_agent(
        "author", author_prompt,
        files_to_read=[document, thread],
        files_to_write=[document],
        model=model,
    )
    _append_to_thread(thread, author_output)

    # Reviewer rescores with Red Team findings incorporated
    reviewer_prompt = (
        f"The Author has addressed the Red Team's findings. Re-read "
        f"everything and provide a final score incorporating both your "
        f"criteria and the Red Team's findings."
    )
    reviewer_output = await _run_agent(
        "reviewer", reviewer_prompt,
        files_to_read=[document, thread],
        model=model,
    )
    _append_to_thread(thread, reviewer_output)

    # ─── Phase 4: Red Team validates ────────────────────────────────────

    red_team_output = await _run_agent(
        "red_team_validate",
        "Validate that the BLOCKING issues from your earlier audit were "
        "resolved. Read the updated document and full thread.",
        files_to_read=red_team_files,
        model=model,
    )
    _append_to_thread(thread, red_team_output)

    # ─── Extract final state ────────────────────────────────────────────

    final_thread = _read_file(thread)
    final_score = _extract_score(final_thread)

    verdict = "UNKNOWN"
    if "SHIP IT" in final_thread.split("Final Validation")[-1]:
        verdict = "SHIP IT"
    elif "ONE MORE ROUND" in final_thread.split("Final Validation")[-1]:
        verdict = "ONE MORE ROUND"
    elif "NEEDS RETHINK" in final_thread.split("Final Validation")[-1]:
        verdict = "NEEDS RETHINK"

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
async def op_status(thread: str, **params) -> dict:
    """Read the current state of a review."""
    thread = str(Path(thread).resolve())
    if not Path(thread).exists():
        return {"__result__": {"error": f"Thread not found: {thread}"}}

    content = _read_file(thread)
    score = _extract_score(content)
    phase = _extract_phase(content)
    rounds = _count_rounds(content)

    # Count blocking issues from most recent reviewer or red team section
    blocking = len(re.findall(r'(?i)\*\*BLOCKING\*\*', content))

    verdict = ""
    if "Final Validation" in content:
        final_section = content.split("Final Validation")[-1]
        for v in ["SHIP IT", "ONE MORE ROUND", "NEEDS RETHINK"]:
            if v in final_section:
                verdict = v
                break

    return {"__result__": {
        "phase": phase,
        "round": rounds,
        "score": score or 0,
        "blockingIssues": blocking,
        "verdict": verdict,
    }}


@returns({"thread": "string", "document": "string", "score": "integer", "verdict": "string", "rounds": "integer", "phase": "string"})
@timeout(600)
async def op_resume(thread: str, context: str = "", max_rounds: int = 2,
              model: str = "opus", **params) -> dict:
    """Resume an interrupted or ONE MORE ROUND review."""
    thread = str(Path(thread).resolve())
    if not Path(thread).exists():
        return {"__result__": {"error": f"Thread not found: {thread}"}}

    content = _read_file(thread)

    # Extract document path from thread header
    doc_match = re.search(r'\*\*Document:\*\*\s*`([^`]+)`', content)
    if not doc_match:
        return {"__result__": {"error": "Could not find document path in thread header"}}
    document = doc_match.group(1)

    context_paths = [str(Path(p.strip()).resolve())
                     for p in context.split(",") if p.strip()] if context else []

    phase = _extract_phase(content)

    # Resume from wherever we left off
    if phase == "phase1_convergence":
        # Continue Author↔Reviewer rounds
        for _ in range(max_rounds):
            author_output = await _run_agent(
                "author",
                "Continue addressing the Reviewer's latest feedback.",
                files_to_read=[document, thread],
                files_to_write=[document],
                model=model,
            )
            _append_to_thread(thread, author_output)

            reviewer_output = await _run_agent(
                "reviewer",
                "Rescore the revised document.",
                files_to_read=[document, thread],
                model=model,
            )
            _append_to_thread(thread, reviewer_output)

            if _scores_converging(_read_file(thread)):
                break

        # Proceed to Red Team
        red_team_files = [document, thread] + context_paths
        red_team_output = await _run_agent(
            "red_team",
            "Audit this document and its review thread with fresh eyes.",
            files_to_read=red_team_files,
            model=model,
        )
        _append_to_thread(thread, red_team_output)

    if phase in ("phase2_red_team", "phase1_convergence"):
        # Author addresses Red Team
        author_output = await _run_agent(
            "author",
            "Address the Red Team's BLOCKING and HIGH findings.",
            files_to_read=[document, thread],
            files_to_write=[document],
            model=model,
        )
        _append_to_thread(thread, author_output)

        # Reviewer rescores
        reviewer_output = await _run_agent(
            "reviewer",
            "Rescore incorporating Red Team findings.",
            files_to_read=[document, thread],
            model=model,
        )
        _append_to_thread(thread, reviewer_output)

    # Final validation
    red_team_files = [document, thread] + context_paths
    red_team_output = await _run_agent(
        "red_team_validate",
        "Final validation — were blocking issues resolved?",
        files_to_read=red_team_files,
        model=model,
    )
    _append_to_thread(thread, red_team_output)

    final_thread = _read_file(thread)
    final_score = _extract_score(final_thread)

    verdict = "UNKNOWN"
    final_section = final_thread.split("Final Validation")[-1] if "Final Validation" in final_thread else ""
    for v in ["SHIP IT", "ONE MORE ROUND", "NEEDS RETHINK"]:
        if v in final_section:
            verdict = v
            break

    return {"__result__": {
        "thread": thread,
        "document": document,
        "score": final_score or 0,
        "verdict": verdict,
        "rounds": _count_rounds(final_thread),
        "phase": "complete",
    }}

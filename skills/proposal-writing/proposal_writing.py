"""
proposal_writing.py — Multi-agent proposal writing with persona-based review committee

Modeled on government contracting:
    Phase 1: Identify personas/stakeholders from the problem
    Phase 2: Each persona agent researches + writes their RFP section (problems + criteria)
             RFP Manager assembles the full RFP
    Phase 3: Bidder writes a proposal addressing all personas
    Phase 4: Review committee (persona agents) scores proposal on their own criteria
             Evaluator aggregates + sends feedback. Bidder revises. Repeat until ≥90%.
    Phase 5: Final summary with score breakdown

Each persona gets 100 points max. Total max = N_personas × 100.
Threshold = 90% of max. Bidder iterates until they hit it (or max_rounds).

All LLM calls via llm.agent() or llm.oneshot(). No subprocess spawning.
"""

import json
import re
import textwrap
from pathlib import Path

from agentos import llm, progress, returns, timeout


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

PERSONA_IDENTIFIER_PROMPT = textwrap.dedent("""\
    You identify the key personas/stakeholders affected by a problem.

    Return a JSON array of persona objects. Each persona has:
    - "name": short label (e.g., "Skill developer", "Runtime agent", "End user")
    - "role": one-sentence description of who they are
    - "interface": how they interact with the system

    Return 3-5 personas. Focus on distinct roles with different problems
    and different interfaces. No overlap.

    Return ONLY valid JSON. No markdown, no explanation.
""")

PERSONA_RFP_PROMPT = textwrap.dedent("""\
    You are a stakeholder writing YOUR section of a Request for Proposals (RFP).
    You represent one specific persona. You care ONLY about YOUR problems.

    ## Your job

    1. **Research your pain points.** Use web search to find real-world evidence —
       quotes, case studies, metrics, forum complaints. Don't guess.
    2. **List your problems** as a prioritized table (P1/P2/P3) with evidence.
    3. **Write detailed descriptions** of each problem with citations.
    4. **Define YOUR evaluation criteria** — 3-5 criteria, weights summing to 100.
       Each criterion gets a 0-5 scale with concrete anchors:
       - What does a 5/5 look like for YOU?
       - What does a 1/5 look like for YOU?

    ## Output format

    Write your section as markdown:

    ```
    ### [Your Persona Name] problems

    | # | Pain point | Priority | Justification |
    |---|-----------|----------|---------------|

    **1. [Pain point title].**
    [Detailed description with evidence...]

    ...

    ### [Your Persona Name] evaluation criteria

    | # | Criterion | Weight | 5/5 | 1/5 |
    |---|----------|--------|-----|-----|
    ```

    ## Rules

    - **Problems only, no solutions.** You define WHAT needs solving, not HOW.
    - **Evidence over intuition.** Every P1 must cite real-world evidence.
    - **Stay in character.** You are this persona. Your problems reflect YOUR
      daily experience, not the system architect's view.
    - **Weights sum to 100.** This is YOUR 100 points. Spend them on what
      matters most to YOU.
""")

RFP_MANAGER_PROMPT = textwrap.dedent("""\
    You are the RFP Manager. Your job is to assemble persona sections into
    a complete, coherent RFP document.

    ## Your job

    1. Read each persona's section (they've already been written).
    2. Write the RFP preamble: title, problem summary, persona overview.
    3. Assemble all persona sections into the document.
    4. Add a combined scoring summary showing all personas and total max points.
    5. Add a test case if the problem domain has one (read context files).

    ## Output format

    Write the complete RFP to the specified file. Use this structure:

    ```
    ---
    title: "... — RFP"
    type: rfp
    labels: [...]
    problem: |
      One paragraph summary.
    ---

    # [Title] — Request for Proposals

    ## Overview
    [What this RFP covers, how scoring works]

    ## Personas
    [Brief intro to each persona]

    ## Problems by Persona
    [Each persona's section as written by them]

    ## Combined Scoring
    | Persona | Max Points | Criteria Count |
    Total: N × 100 = XXX points

    ## Test Case (if applicable)

    ## Context: Current System
    ```

    ## Rules

    - **Don't rewrite persona sections.** Include them as-is. They own their words.
    - **Do add structure and context** around them.
    - **Ensure scoring math is correct.** Each persona = 100 points max.
""")

BIDDER_PROMPT = textwrap.dedent("""\
    You are a proposal writer responding to an RFP. Your job is to write a
    comprehensive proposal that addresses every persona's problems and scores
    well against ALL their criteria.

    ## Principles

    1. **Address every P1 problem from every persona.** P2s where possible.
    2. **Show, don't describe.** Concrete artifacts: code examples, data
       structures, CLI output, API calls.
    3. **Be concrete about trade-offs.** Name what you're giving up.
    4. **Demonstrate the test case** if the RFP includes one.
    5. **Structure by solution, not by persona.** The proposal should be a
       coherent design, not N separate answers glued together.
    6. **Acknowledge what you don't know.** Open questions are honesty.

    ## Output format

    Write a complete markdown document:

    ```
    ---
    title: "..."
    priority: N
    labels: [...]
    problem: |
      One paragraph.
    success_criteria: |
      Bullet list of measurable outcomes.
    ---

    # [Title]

    ## The Problem (brief — RFP has details)
    ## Proposed Design
    ## Test Case Walkthrough
    ## Persona Coverage
      ### How this addresses [Persona 1]
      ### How this addresses [Persona 2]
      ...
    ## Alternatives Considered
    ## Trade-offs
    ## Implementation Plan
    ## Open Questions
    ```
""")

PERSONA_EVALUATOR_PROMPT = textwrap.dedent("""\
    You are a stakeholder evaluating a proposal against YOUR criteria only.
    You represent one specific persona. Score ONLY your own criteria.

    ## Your job

    1. Read the proposal carefully. Read the RFP criteria carefully.
    2. Score each of YOUR criteria 0-5 with concrete justification.
       Be harsh and specific — if the RFP demands concrete code and the
       proposal is vague, that's a 2 or 3, not a 4.
    3. Calculate your weighted total (max 100).
    4. List issues as BLOCKING or NON-BLOCKING.
    5. For each issue, cite the specific criterion and what's missing.
       "Progress visibility is weak" is useless feedback.
       "Progress visibility (weight 30): no concrete event propagation
       mechanism shown — need event type, Rust→Python flow, MCP surface"
       is useful feedback.

    ## Output format

    ```
    ### [Your Persona Name] — Round N

    **Score: XX/100**

    | Criterion | Weight | Score (0-5) | Weighted | Justification |
    |---|---|---|---|---|

    **BLOCKING:**
    1. [Criterion name, weight]: [specific gap with evidence from proposal]

    **NON-BLOCKING:**
    1. [Criterion name, weight]: [specific gap]
    ```

    ## Rules

    - **Only YOUR criteria.** Don't evaluate things outside your domain.
    - **Score with math.** Weighted score = weight × score / 5.
    - **Be honest about improvements.** If the proposal fixed something, raise the score.
    - **Never suggest solutions.** Say what's missing, not what to do.
    - **Cite evidence.** Quote or reference specific sections of the proposal.
""")

EVALUATOR_PROMPT = textwrap.dedent("""\
    You are the Evaluation Coordinator. You aggregate persona scores into
    feedback for the bidder.

    You receive individual persona evaluations. Your job:

    1. Calculate the total score across all personas.
    2. List ALL blocking issues from ALL personas.
    3. Summarize the feedback clearly — what must improve to hit threshold.
    4. Be direct: which personas are satisfied, which aren't.

    ## Output format

    ```
    ## Evaluation — Round N

    ### Scores
    | Persona | Score | Max | % |
    |---|---|---|---|
    | Total | XXX | YYY | ZZ% |

    ### Blocking Issues (must fix)
    1. [Persona]: [issue]

    ### Non-blocking Issues (should fix)
    1. [Persona]: [issue]

    ### Feedback for Bidder
    [Clear summary of what needs to change]
    ```
""")

BIDDER_REVISE_PROMPT = textwrap.dedent("""\
    You are revising your proposal based on evaluation feedback from the
    review committee. Each persona scored their own criteria.

    ## Rules

    1. **Fix blocking issues first.** These are requirements.
    2. **Show your changes.** For each issue, explain what you changed.
    3. **Actually revise the proposal file.** Don't just describe changes.
    4. **Push back with evidence** if you disagree — but back it up.
    5. **Don't restructure everything.** Fix what was asked.

    ## Output format (for the review thread)

    ```
    ## Revision — Round N

    ### Addressing feedback

    **[Persona]: [Issue]**
    [What you changed and why]

    ### Changes made
    - [Specific change 1]
    - [Specific change 2]
    ```
""")


# Research tools for agents that need web access.
# Format: "skill_id.entity.operation" — entity comes from @returns(), operation is the function name.
# Verify with: load({ skill: "name" }) to see tool names, then check @returns in the .py file.
RESEARCH_TOOLS = [
    "exa.result.search",               # neural/semantic search — works
    "exa.webpage.read_webpage",         # extract content from URL — works
    "hackernews.post.search_posts",     # search HN stories — works
    # Broken/unavailable (2026-04-08):
    # "brave.result.search",            # API key expired, no refresh path
    # "firecrawl.webpage.read_webpage", # API key expired
    # "reddit.post.search_posts",       # 403 bot detection
    # "youtube.result.transcript_video",# sandbox blocks yt-dlp socket import
]

FILE_READ = ["Read", "Glob", "Grep"]
FILE_WRITE = ["Read", "Glob", "Grep", "Edit", "Write"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _agent_call(*, prompt, system, tools, files=None, model="opus", max_iterations=20):
    """Wrapper around await llm.agent() with error handling.

    Returns the agent result dict. Raises RuntimeError if the agent fails,
    so callers get a clear traceback instead of silently continuing with
    empty strings.
    """
    result = await llm.agent(
        prompt=prompt,
        system=system,
        tools=tools,
        files=files or [],
        model=model,
        max_iterations=max_iterations,
    )
    if "__error__" in result:
        raise RuntimeError(f"await llm.agent() failed: {result['__error__']}")
    return result


def _read_file(path):
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""


def _append(path, content):
    with open(path, "a") as f:
        f.write(f"\n\n{content}\n")


def _extract_persona_score(text, persona_name):
    """Extract score for a specific persona from evaluation text."""
    pattern = rf'{re.escape(persona_name)}.*?Score:\s*(\d+)\s*/\s*100'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_total_score(text):
    """Extract total score from evaluator aggregation."""
    match = re.search(r'Total\s*\|\s*(\d+)', text)
    return int(match.group(1)) if match else None


def _resolve_problem(problem):
    """If problem is a file path, read it. Otherwise return as-is."""
    p = Path(problem)
    if p.exists() and p.is_file():
        return p.read_text()
    return problem


# ---------------------------------------------------------------------------
# Phase 1: Identify personas
# ---------------------------------------------------------------------------

async def _identify_personas(problem_text, domain):
    """Use llm.oneshot to extract personas from the problem statement."""
    domain_hint = f"\nDomain: {domain}" if domain else ""
    result = await llm.oneshot(
        prompt=(
            f"Identify the key personas/stakeholders for this problem:\n\n"
            f"---\n{problem_text}\n---{domain_hint}\n\n"
            f"Return a JSON array of 3-5 persona objects."
        ),
        system=PERSONA_IDENTIFIER_PROMPT,
        model="opus",
        max_tokens=2048,
    )
    content = result.get("content", "[]")
    # Extract JSON from response (may be wrapped in markdown code block)
    json_match = re.search(r'\[.*\]', content, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(0))
    return []


# ---------------------------------------------------------------------------
# Phase 2: RFP generation (persona agents + manager)
# ---------------------------------------------------------------------------

async def _persona_write_rfp_section(persona, problem_text, context_paths, domain):
    """One persona agent researches + writes their RFP section."""
    domain_hint = f"\nDomain: {domain}" if domain else ""
    context_hint = ""
    if context_paths:
        context_hint = (
            "\n\nContext files available:\n"
            + "\n".join(f"- `{p}`" for p in context_paths)
        )

    prompt = (
        f"You are: **{persona['name']}** — {persona['role']}\n"
        f"Your interface: {persona.get('interface', 'N/A')}\n\n"
        f"The problem:\n---\n{problem_text}\n---\n"
        f"{domain_hint}{context_hint}\n\n"
        f"Research YOUR pain points and write YOUR section of the RFP.\n"
        f"Use web search to find real evidence for your problems.\n"
        f"Define YOUR evaluation criteria (3-5 criteria, weights summing to 100)."
    )

    result = await _agent_call(
        prompt=prompt,
        system=PERSONA_RFP_PROMPT,
        tools=FILE_READ + RESEARCH_TOOLS,
        files=context_paths,
        model="opus",
    )
    return result.get("content", "")


async def _assemble_rfp(personas, sections, rfp_path, problem_text, context_paths):
    """RFP Manager assembles persona sections into a complete RFP."""
    sections_text = ""
    for persona, section in zip(personas, sections):
        sections_text += f"\n---\n**{persona['name']}** section:\n\n{section}\n"

    context_hint = ""
    if context_paths:
        context_hint = (
            "\n\nContext files available to read for test case / current system:\n"
            + "\n".join(f"- `{p}`" for p in context_paths)
        )

    prompt = (
        f"Assemble this RFP from the persona sections below.\n\n"
        f"Problem statement:\n---\n{problem_text}\n---\n\n"
        f"Personas ({len(personas)}): "
        + ", ".join(p["name"] for p in personas)
        + f"\n\nTotal max score: {len(personas) * 100} points "
        f"({len(personas)} personas × 100 each)\n\n"
        f"Persona sections:{sections_text}"
        f"{context_hint}\n\n"
        f"Write the complete RFP to: `{rfp_path}`"
    )

    await _agent_call(
        prompt=prompt,
        system=RFP_MANAGER_PROMPT,
        tools=FILE_WRITE,
        files=context_paths + [rfp_path],
        model="opus",
    )


# ---------------------------------------------------------------------------
# Phase 3: Proposal bid
# ---------------------------------------------------------------------------

async def _write_proposal(rfp_path, proposal_path, context_paths, model):
    """Bidder writes a proposal responding to the RFP."""
    rfp_content = _read_file(rfp_path)
    context_hint = ""
    if context_paths:
        context_hint = (
            "\n\nContext files available:\n"
            + "\n".join(f"- `{p}`" for p in context_paths)
        )

    prompt = (
        f"Write a proposal responding to this RFP:\n\n"
        f"---\n{rfp_content}\n---\n"
        f"{context_hint}\n\n"
        f"Research solutions using web search. Find prior art and concrete "
        f"examples.\n\n"
        f"Write the complete proposal to: `{proposal_path}`"
    )

    await _agent_call(
        prompt=prompt,
        system=BIDDER_PROMPT,
        tools=FILE_WRITE + RESEARCH_TOOLS,
        files=context_paths + [rfp_path, proposal_path],
        model=model,
    )


# ---------------------------------------------------------------------------
# Phase 4: Evaluation loop
# ---------------------------------------------------------------------------

async def _persona_evaluate(persona, rfp_path, proposal_path, thread_path,
                      context_paths, round_num):
    """One persona agent scores the proposal on THEIR criteria only."""
    rfp_content = _read_file(rfp_path)

    prompt = (
        f"You are: **{persona['name']}** — {persona['role']}\n\n"
        f"This is evaluation round {round_num}.\n\n"
        f"Read the proposal at `{proposal_path}` and score it against "
        f"YOUR criteria from the RFP.\n\n"
        f"Your criteria are defined in the RFP under "
        f"'{persona['name']} evaluation criteria'.\n\n"
        f"RFP for reference:\n---\n{rfp_content}\n---"
    )

    if round_num > 1:
        prompt += (
            f"\n\nRead the review thread at `{thread_path}` to see "
            f"prior rounds and what the bidder changed."
        )

    result = await _agent_call(
        prompt=prompt,
        system=PERSONA_EVALUATOR_PROMPT,
        tools=FILE_READ,
        files=[rfp_path, proposal_path, thread_path] + context_paths,
        model="opus",
    )
    return result.get("content", "")


async def _aggregate_evaluations(persona_evals, personas, round_num):
    """Evaluator aggregates persona scores into a combined evaluation."""
    evals_text = ""
    for persona, eval_text in zip(personas, persona_evals):
        evals_text += f"\n---\n{persona['name']}:\n{eval_text}\n"

    result = await llm.oneshot(
        prompt=(
            f"Aggregate these persona evaluations for round {round_num}.\n\n"
            f"Max score per persona: 100. Total max: {len(personas) * 100}.\n"
            f"Threshold: 90% = {int(len(personas) * 100 * 0.9)}.\n\n"
            f"Persona evaluations:{evals_text}"
        ),
        system=EVALUATOR_PROMPT,
        model="opus",
        max_tokens=4096,
    )
    return result.get("content", "")


async def _revise_proposal(rfp_path, proposal_path, thread_path, context_paths,
                     round_num, model):
    """Bidder revises proposal based on evaluation feedback."""
    prompt = (
        f"This is revision round {round_num}.\n\n"
        f"Read the evaluation feedback in the review thread at "
        f"`{thread_path}`. Focus on BLOCKING issues first.\n\n"
        f"Revise the proposal at `{proposal_path}` to address the feedback.\n"
        f"The RFP is at `{rfp_path}` for reference."
    )

    result = await _agent_call(
        prompt=prompt,
        system=BIDDER_REVISE_PROMPT,
        tools=FILE_WRITE,
        files=[rfp_path, proposal_path, thread_path] + context_paths,
        model=model,
    )
    return result.get("content", "")


def _parse_total_score(aggregation_text, personas):
    """Parse total score from evaluator aggregation. Fallback: sum persona scores."""
    # Try to find total in the aggregation
    total = _extract_total_score(aggregation_text)
    if total:
        return total

    # Fallback: sum individual persona scores
    total = 0
    for persona in personas:
        score = _extract_persona_score(aggregation_text, persona["name"])
        if score:
            total += score
    return total


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

@returns({"rfp": "string", "proposal": "string", "score": "integer", "maxScore": "integer", "rounds": "integer", "personas": "integer"})
@timeout(1800)
async def write_proposal(problem: str, output: str, model: str = "opus",
                   max_rounds: int = 5, context: str = "",
                   domain: str = "", threshold: float = 0.9,
                   **params) -> dict:
    """Run the full proposal writing pipeline: personas → RFP → bid → evaluation loop → summary.

    Args:
        problem: Raw problem statement, or path to a file containing one
        output: Output directory for all artifacts
        model: Model for the bidder (default: opus)
        max_rounds: Max evaluation rounds (default: 5)
        context: Comma-separated paths for codebase context
        domain: Domain hint (sdk-design, product-strategy, etc.)
        threshold: Min score as fraction of max (default: 0.9)
    """
    await progress.set_job_id(params.get("__job_id__", ""))

    # Resolve inputs
    output_dir = str(Path(output).resolve())
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    problem_text = _resolve_problem(problem)

    context_paths = []
    if context:
        for p in context.split(","):
            p = p.strip()
            if p:
                resolved = str(Path(p).resolve())
                if Path(resolved).exists():
                    context_paths.append(resolved)

    rfp_path = f"{output_dir}/rfp.md"
    proposal_path = f"{output_dir}/proposal.md"
    thread_path = f"{output_dir}/review.md"

    # Estimate steps: identify(1) + personas*rfp(N) + assemble(1) + bid(1)
    #   + rounds*(personas*eval(N) + aggregate(1) + revise(1)) + summary(1)
    # Use rough estimate, update as we learn persona count
    step = 0

    # --- Phase 1: Identify Personas ---
    step += 1
    await progress.progress(step, 20, "Identifying personas...")

    personas = await _identify_personas(problem_text, domain)
    if not personas:
        return {"__result__": {"error": "Could not identify personas"}}

    n = len(personas)
    max_score = n * 100
    threshold_score = int(max_score * threshold)
    total_steps = 1 + n + 1 + 1 + (max_rounds * (n + 2)) + 1

    await progress.progress(step, total_steps,
                      f"Found {n} personas: "
                      + ", ".join(p["name"] for p in personas))

    # --- Phase 2: RFP Generation ---
    sections = []
    for i, persona in enumerate(personas):
        step += 1
        await progress.progress(step, total_steps,
                          f"RFP: {persona['name']} researching...")

        section = await _persona_write_rfp_section(
            persona, problem_text, context_paths, domain)
        sections.append(section)

    step += 1
    await progress.progress(step, total_steps, "RFP Manager assembling document...")
    await _assemble_rfp(personas, sections, rfp_path, problem_text, context_paths)

    if not Path(rfp_path).exists():
        return {"__result__": {"error": "RFP generation failed"}}

    await progress.progress(step, total_steps, "RFP complete")

    # --- Phase 3: Proposal Bid ---
    step += 1
    await progress.progress(step, total_steps, "Bidder writing proposal...")
    await _write_proposal(rfp_path, proposal_path, context_paths, model)

    if not Path(proposal_path).exists():
        return {"__result__": {"error": "Proposal generation failed"}}

    # Initialize review thread
    thread_header = textwrap.dedent(f"""\
        # Proposal Review

        > **RFP:** `{rfp_path}`
        > **Proposal:** `{proposal_path}`
        > **Personas:** {', '.join(p['name'] for p in personas)}
        > **Threshold:** {threshold_score}/{max_score} ({int(threshold*100)}%)

        ---
    """)
    Path(thread_path).write_text(thread_header)

    # --- Phase 4: Evaluation Loop ---
    final_score = 0
    round_num = 0

    for round_num in range(1, max_rounds + 1):
        # Each persona evaluates
        persona_evals = []
        for i, persona in enumerate(personas):
            step += 1
            await progress.progress(step, total_steps,
                              f"Round {round_num}: {persona['name']} evaluating...")

            eval_text = await _persona_evaluate(
                persona, rfp_path, proposal_path, thread_path,
                context_paths, round_num)
            persona_evals.append(eval_text)
            _append(thread_path, eval_text)

        # Evaluator aggregates
        step += 1
        await progress.progress(step, total_steps,
                          f"Round {round_num}: aggregating scores...")

        aggregation = await _aggregate_evaluations(persona_evals, personas, round_num)
        _append(thread_path, aggregation)

        final_score = _parse_total_score(aggregation, personas)
        await progress.progress(step, total_steps,
                          f"Round {round_num}: {final_score}/{max_score} "
                          f"(need {threshold_score})")

        # Check threshold
        if final_score >= threshold_score:
            await progress.progress(step, total_steps,
                              f"Threshold met! {final_score}/{max_score}")
            break

        # Bidder revises
        step += 1
        await progress.progress(step, total_steps,
                          f"Round {round_num}: bidder revising...")

        revision = await _revise_proposal(
            rfp_path, proposal_path, thread_path, context_paths,
            round_num, model)
        _append(thread_path, revision)

    # --- Phase 5: Summary ---
    summary_path = f"{output_dir}/summary.md"
    summary_content = (
        f"# Proposal Summary\n\n"
        f"**Final score:** {final_score}/{max_score} "
        f"({int(final_score/max_score*100) if max_score else 0}%)\n"
        f"**Threshold:** {threshold_score}/{max_score} "
        f"({int(threshold*100)}%)\n"
        f"**Rounds:** {round_num}\n"
        f"**Verdict:** {'ACCEPTED' if final_score >= threshold_score else 'NOT YET MET'}\n\n"
        f"## Artifacts\n"
        f"- RFP: `{rfp_path}`\n"
        f"- Proposal: `{proposal_path}`\n"
        f"- Review thread: `{thread_path}`\n"
    )
    Path(summary_path).write_text(summary_content)

    await progress.progress(total_steps, total_steps,
                      f"Complete — {final_score}/{max_score}")

    return {"__result__": {
        "rfp": rfp_path,
        "proposal": proposal_path,
        "score": final_score,
        "maxScore": max_score,
        "rounds": round_num,
        "personas": n,
    }}


@returns({"phase": "string", "score": "integer", "maxScore": "integer", "rounds": "integer", "personas": "integer"})
@timeout(15)
async def status(output: str, **params) -> dict:
    """Check the current state of a proposal writing run.

    Args:
        output: Output directory from a previous write_proposal run
    """
    output_dir = str(Path(output).resolve())
    if not Path(output_dir).exists():
        return {"__result__": {"error": f"Not found: {output_dir}"}}

    rfp_exists = Path(f"{output_dir}/rfp.md").exists()
    proposal_exists = Path(f"{output_dir}/proposal.md").exists()
    thread_exists = Path(f"{output_dir}/review.md").exists()

    if not rfp_exists:
        phase = "writing_rfp"
    elif not proposal_exists:
        phase = "writing_proposal"
    elif not thread_exists:
        phase = "pending_review"
    else:
        thread = _read_file(f"{output_dir}/review.md")
        if "ACCEPTED" in thread or Path(f"{output_dir}/summary.md").exists():
            phase = "complete"
        else:
            phase = "evaluating"

    # Try to extract score from thread
    score = 0
    rounds = 0
    if thread_exists:
        thread = _read_file(f"{output_dir}/review.md")
        total = _extract_total_score(thread)
        if total:
            score = total
        rounds = len(re.findall(r'## Evaluation — Round', thread))

    # Count personas from thread header
    personas = 0
    if thread_exists:
        thread = _read_file(f"{output_dir}/review.md")
        match = re.search(r'Personas:\*\*\s*(.+)', thread)
        if match:
            personas = len(match.group(1).split(","))

    return {"__result__": {
        "phase": phase,
        "score": score,
        "maxScore": personas * 100,
        "rounds": rounds,
        "personas": personas,
    }}

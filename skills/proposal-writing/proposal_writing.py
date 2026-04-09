"""
proposal_writing.py — Multi-agent proposal writing with persona-based review committee

Modeled on government contracting:
    Phase 1: Identify personas/stakeholders from the problem
    Phase 2: Each persona agent researches + writes their RFP section (parallel)
             RFP Manager assembles the full RFP
    Phase 3: Bidder writes a proposal addressing all personas
    Phase 4: Review committee (persona agents) scores proposal (parallel)
             Evaluator aggregates + sends feedback. Bidder revises. Repeat until >=90%.
    Phase 5: Final summary with score breakdown

Each persona gets 100 points max. Total max = N_personas x 100.
Threshold = 90% of max. Bidder iterates until they hit it (or max_rounds).

All LLM calls via llm.agent() or llm.oneshot(). Parallel via asyncio.gather().
Structured output via output_schema — no regex score extraction.
Prompts live as external markdown files in prompts/.
"""

import asyncio
from pathlib import Path

from agentos import checkpoint, llm, progress, returns, timeout


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

PROMPT_DIR = Path(__file__).parent / "prompts"


def _prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text()


# ---------------------------------------------------------------------------
# Output schemas for structured output
# ---------------------------------------------------------------------------

PERSONA_SCHEMA = {
    "type": "object",
    "properties": {
        "personas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "interface": {"type": "string"},
                },
                "required": ["name", "role", "interface"],
            },
        }
    },
    "required": ["personas"],
}

EVAL_SCHEMA = {
    "type": "object",
    "properties": {
        "personaName": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "weight": {"type": "integer"},
                    "score": {"type": "integer", "minimum": 0, "maximum": 5},
                    "weighted": {"type": "number"},
                    "justification": {"type": "string"},
                },
                "required": ["name", "weight", "score", "weighted", "justification"],
            },
        },
        "blockingIssues": {
            "type": "array",
            "items": {"type": "string"},
        },
        "nonBlockingIssues": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["personaName", "score", "criteria", "blockingIssues", "nonBlockingIssues"],
}

AGGREGATION_SCHEMA = {
    "type": "object",
    "properties": {
        "totalScore": {"type": "integer"},
        "maxScore": {"type": "integer"},
        "personaScores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "score": {"type": "integer"},
                },
                "required": ["name", "score"],
            },
        },
        "blockingIssues": {
            "type": "array",
            "items": {"type": "string"},
        },
        "feedback": {"type": "string"},
    },
    "required": ["totalScore", "maxScore", "personaScores", "blockingIssues", "feedback"],
}


# ---------------------------------------------------------------------------
# Research tools for agents that need web access
# ---------------------------------------------------------------------------

RESEARCH_TOOLS = [
    "exa.result.search",
    "exa.webpage.read_webpage",
    "hackernews.post.search_posts",
]

FILE_READ = ["Read", "Glob", "Grep"]
FILE_WRITE = ["Read", "Glob", "Grep", "Edit", "Write"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_file(path):
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""


def _append(path, content):
    with open(path, "a") as f:
        f.write(f"\n\n{content}\n")


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
    """Use llm.agent with output_schema to extract personas."""
    domain_hint = f"\nDomain: {domain}" if domain else ""
    result = await llm.agent(
        prompt=(
            f"Identify the key personas/stakeholders for this problem:\n\n"
            f"---\n{problem_text}\n---{domain_hint}\n\n"
            f"Return 3-5 personas."
        ),
        system=_prompt("persona_identifier"),
        model="opus",
        output_schema=PERSONA_SCHEMA,
    )
    data = result.get("data") or {}
    return data.get("personas", [])


# ---------------------------------------------------------------------------
# Phase 2: RFP generation (parallel persona agents + manager)
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

    result = await llm.agent(
        prompt=prompt,
        system=_prompt("persona_rfp"),
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
        f"({len(personas)} personas x 100 each)\n\n"
        f"Persona sections:{sections_text}"
        f"{context_hint}\n\n"
        f"Write the complete RFP to: `{rfp_path}`"
    )

    await llm.agent(
        prompt=prompt,
        system=_prompt("rfp_manager"),
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

    await llm.agent(
        prompt=prompt,
        system=_prompt("bidder"),
        tools=FILE_WRITE + RESEARCH_TOOLS,
        files=context_paths + [rfp_path, proposal_path],
        model=model,
    )


# ---------------------------------------------------------------------------
# Phase 4: Evaluation loop (parallel persona scoring + structured output)
# ---------------------------------------------------------------------------

async def _persona_evaluate(persona, rfp_path, proposal_path, thread_path,
                            context_paths, round_num):
    """One persona agent scores the proposal on THEIR criteria only.

    Returns structured eval data via output_schema.
    """
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

    result = await llm.agent(
        prompt=prompt,
        system=_prompt("persona_evaluator"),
        tools=FILE_READ,
        files=[rfp_path, proposal_path, thread_path] + context_paths,
        model="opus",
        output_schema=EVAL_SCHEMA,
    )
    return result


async def _aggregate_evaluations(persona_evals, personas, round_num):
    """Evaluator aggregates persona scores into a combined evaluation."""
    evals_summary = ""
    for persona, ev in zip(personas, persona_evals):
        data = ev.get("data") or {}
        score = data.get("score", "?")
        blocking = data.get("blockingIssues", [])
        evals_summary += (
            f"\n---\n{persona['name']}: {score}/100\n"
            f"Blocking: {blocking}\n"
            f"Content: {ev.get('content', '')[:2000]}\n"
        )

    result = await llm.agent(
        prompt=(
            f"Aggregate these persona evaluations for round {round_num}.\n\n"
            f"Max score per persona: 100. Total max: {len(personas) * 100}.\n"
            f"Threshold: 90% = {int(len(personas) * 100 * 0.9)}.\n\n"
            f"Persona evaluations:{evals_summary}"
        ),
        system=_prompt("evaluator"),
        model="opus",
        output_schema=AGGREGATION_SCHEMA,
    )
    return result


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

    result = await llm.agent(
        prompt=prompt,
        system=_prompt("bidder_revise"),
        tools=FILE_WRITE,
        files=[rfp_path, proposal_path, thread_path] + context_paths,
        model=model,
    )
    return result.get("content", "")


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

@returns({"rfp": "string", "proposal": "string", "score": "integer", "maxScore": "integer", "rounds": "integer", "personas": "integer"})
@timeout(1800)
async def write_proposal(problem: str, output: str, model: str = "opus",
                         max_rounds: int = 5, context: str = "",
                         domain: str = "", threshold: float = 0.9,
                         **params) -> dict:
    """Run the full proposal writing pipeline: personas -> RFP -> bid -> evaluation loop -> summary.

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

    # --- Check for checkpoint (resume from prior run) ---
    state = checkpoint.load(output_dir)

    # --- Phase 1: Identify Personas ---
    if state and state.get("phase", 0) >= 1:
        personas = state["personas"]
    else:
        await progress.progress(1, 20, "Identifying personas...")
        personas = await _identify_personas(problem_text, domain)
        if not personas:
            return {"__result__": {"error": "Could not identify personas"}}
        checkpoint.save(output_dir, {"phase": 1, "personas": personas})

    n = len(personas)
    max_score = n * 100
    threshold_score = int(max_score * threshold)
    total_steps = 1 + 1 + 1 + 1 + (max_rounds * 3) + 1  # phases, not individual agents

    await progress.progress(1, total_steps,
                            f"Found {n} personas: "
                            + ", ".join(p["name"] for p in personas))

    # --- Phase 2: RFP Generation (parallel persona agents) ---
    if state and state.get("phase", 0) >= 2:
        pass  # RFP already on disk
    else:
        await progress.progress(2, total_steps,
                                f"RFP: {n} persona agents researching in parallel...")

        sections = await asyncio.gather(*[
            _persona_write_rfp_section(persona, problem_text, context_paths, domain)
            for persona in personas
        ])

        await progress.progress(3, total_steps, "RFP Manager assembling document...")
        await _assemble_rfp(personas, sections, rfp_path, problem_text, context_paths)

        if not Path(rfp_path).exists():
            return {"__result__": {"error": "RFP generation failed"}}

        checkpoint.save(output_dir, {"phase": 2, "personas": personas})

    await progress.progress(3, total_steps, "RFP complete")

    # --- Phase 3: Proposal Bid ---
    if state and state.get("phase", 0) >= 3:
        pass  # Proposal already on disk
    else:
        await progress.progress(4, total_steps, "Bidder writing proposal...")
        await _write_proposal(rfp_path, proposal_path, context_paths, model)

        if not Path(proposal_path).exists():
            return {"__result__": {"error": "Proposal generation failed"}}

        # Initialize review thread
        thread_header = (
            f"# Proposal Review\n\n"
            f"> **RFP:** `{rfp_path}`\n"
            f"> **Proposal:** `{proposal_path}`\n"
            f"> **Personas:** {', '.join(p['name'] for p in personas)}\n"
            f"> **Threshold:** {threshold_score}/{max_score} ({int(threshold*100)}%)\n\n"
            f"---\n"
        )
        Path(thread_path).write_text(thread_header)
        checkpoint.save(output_dir, {"phase": 3, "personas": personas})

    # --- Phase 4: Evaluation Loop ---
    start_round = 1
    if state and state.get("phase", 0) >= 4:
        start_round = state.get("completedRounds", 0) + 1

    final_score = 0
    round_num = 0

    for round_num in range(start_round, max_rounds + 1):
        step_base = 4 + (round_num - 1) * 3

        # Parallel persona evaluation
        await progress.progress(step_base + 1, total_steps,
                                f"Round {round_num}: {n} persona evaluators in parallel...")

        eval_results = await asyncio.gather(*[
            _persona_evaluate(persona, rfp_path, proposal_path, thread_path,
                              context_paths, round_num)
            for persona in personas
        ])

        # Write eval content to review thread
        for persona, ev in zip(personas, eval_results):
            data = ev.get("data") or {}
            _append(thread_path,
                    f"### {persona['name']} — Round {round_num}\n\n"
                    f"**Score: {data.get('score', '?')}/100**\n\n"
                    f"{ev.get('content', '')}")

        # Aggregate evaluations (structured output)
        await progress.progress(step_base + 2, total_steps,
                                f"Round {round_num}: aggregating scores...")

        agg_result = await _aggregate_evaluations(eval_results, personas, round_num)
        agg_data = agg_result.get("data") or {}
        final_score = agg_data.get("totalScore", 0)
        feedback = agg_data.get("feedback", "")

        _append(thread_path,
                f"## Evaluation — Round {round_num}\n\n"
                f"**Total: {final_score}/{max_score}**\n\n"
                f"{feedback}\n\n{agg_result.get('content', '')}")

        await progress.progress(step_base + 2, total_steps,
                                f"Round {round_num}: {final_score}/{max_score} "
                                f"(need {threshold_score})")

        checkpoint.save(output_dir, {
            "phase": 4,
            "personas": personas,
            "completedRounds": round_num,
            "lastScore": final_score,
        })

        # Check threshold
        if final_score >= threshold_score:
            await progress.progress(step_base + 3, total_steps,
                                    f"Threshold met! {final_score}/{max_score}")
            break

        # Bidder revises
        await progress.progress(step_base + 3, total_steps,
                                f"Round {round_num}: bidder revising...")
        revision = await _revise_proposal(
            rfp_path, proposal_path, thread_path, context_paths,
            round_num, model)
        _append(thread_path, f"## Revision — Round {round_num}\n\n{revision}")

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

    # Clear checkpoint on success
    checkpoint.clear(output_dir)

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

    # Try checkpoint first — most reliable
    state = checkpoint.load(output_dir)
    if state:
        personas = state.get("personas", [])
        n = len(personas)
        phase_num = state.get("phase", 0)
        phases = {1: "identifying_personas", 2: "writing_rfp", 3: "writing_proposal", 4: "evaluating"}
        return {"__result__": {
            "phase": phases.get(phase_num, "unknown"),
            "score": state.get("lastScore", 0),
            "maxScore": n * 100,
            "rounds": state.get("completedRounds", 0),
            "personas": n,
        }}

    # No checkpoint — check artifacts
    rfp_exists = Path(f"{output_dir}/rfp.md").exists()
    proposal_exists = Path(f"{output_dir}/proposal.md").exists()
    summary_exists = Path(f"{output_dir}/summary.md").exists()

    if summary_exists:
        phase = "complete"
    elif not rfp_exists:
        phase = "writing_rfp"
    elif not proposal_exists:
        phase = "writing_proposal"
    else:
        phase = "complete"  # no checkpoint + artifacts = finished

    return {"__result__": {
        "phase": phase,
        "score": 0,
        "maxScore": 0,
        "rounds": 0,
        "personas": 0,
    }}

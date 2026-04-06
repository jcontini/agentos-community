"""
propose.py — Generate structured proposals ready for scored review

Spawns a Claude agent that:
1. Reads context files (codebase, prior specs, docs)
2. Optionally researches the problem space (web search via allowed tools)
3. Writes a proposal document in a format designed for the Review skill

The proposal format is intentionally aligned with how the Review skill's
Reviewer agent defines criteria. A well-structured proposal scores well
not because it games the rubric, but because the rubric measures what
makes a proposal actually good.

Document structure (the "proposal protocol"):

    ---
    title: ...
    priority: ...
    labels: [...]
    problem: |
      ...
    success_criteria: ...
    ---

    # Title

    ## The Problem
    [Who's affected. What's broken. Why now.]

    ## Proposed Design
    [Concrete artifacts — show, don't describe.]

    ## Alternatives Considered
    [What else you looked at and why you didn't pick it.]

    ## Trade-offs
    [What you're giving up. What's hard. What's risky.]

    ## Implementation
    [Order of work. Dependencies. What ships first.]

    ## Open Questions
    [What you don't know yet. What needs validation.]

This structure maps directly to how reviewers evaluate proposals across
every rigorous field:

    Academic:    Abstract → Methods → Results → Discussion → Limitations
    FDA:        Indication → Clinical Data → Risk-Benefit → Labeling
    Amazon:     Press Release → FAQ → Tenets → Appendix
    RFC:        Problem → Proposal → Alternatives → Unresolved
    ADR:        Context → Decision → Consequences

The common thread: problem first, then solution, then honest accounting
of what you don't know.
"""

import os
import textwrap
from pathlib import Path

from agentos import shell, returns, timeout


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
       propose an API, show the call and response. "The system will generate a
       context file" is a description. Showing the actual context file is a
       proposal.

    3. **Be concrete about trade-offs.** Every design decision trades something.
       Name what you're giving up, not just what you're getting. "We chose X
       over Y because Z" — all three parts matter.

    4. **Separate what exists from what you're proposing.** If something already
       works, say so. If something needs building, say so. Don't blur the line.

    5. **Acknowledge what you don't know.** Open questions aren't weakness —
       they're honesty. A proposal that claims to have all the answers is a
       proposal that hasn't thought hard enough.

    6. **Write for your reviewer.** This document will be evaluated by someone
       who scores it against weighted criteria. Make their job easy: clear
       structure, concrete artifacts, honest trade-offs. Don't make them hunt
       for the design.

    ## Output format

    Write a complete markdown document with YAML frontmatter. Use this structure:

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

    [2-4 paragraphs. Who's affected. What's broken. Evidence/examples.
    Why existing approaches don't work. Why now.]

    ## Proposed Design

    [The meat. Multiple subsections. Each major component gets:
    - What it does (1-2 sentences)
    - Concrete artifact (show the output, the file, the API response)
    - How it connects to the rest of the design]

    ## Alternatives Considered

    [What else you looked at. Why you didn't pick it. Be fair to the
    alternatives — a strawman comparison is worse than no comparison.]

    ## Trade-offs

    [What you're giving up. What's harder because of this design. What
    risks exist. Be honest — the reviewer will find these anyway.]

    ## Implementation

    [Ordered list of work. What ships first (highest leverage, lowest
    risk). Dependencies between pieces. What can be parallelized.]

    ## Open Questions

    [What needs validation. What you're uncertain about. What could
    change the design if answered differently.]
    ```

    IMPORTANT: The proposal must be a COMPLETE, STANDALONE document.
    Someone reading it with no other context should understand the
    problem, the design, and the trade-offs.
""")

OUTLINER_PROMPT = textwrap.dedent("""\
    You are creating a lightweight outline for a proposal. This is NOT the
    full document — it's a quick sketch to align on scope and approach before
    investing in research and detailed writing.

    ## Output format

    Write a concise outline (under 500 words):

    ```
    # [Title]

    ## Problem
    [2-3 sentences: who, what's broken, why now]

    ## Proposed approach
    [3-5 bullet points: the key design decisions]

    ## Key sections the full proposal will cover
    1. [Section name] — [one line: what it covers]
    2. ...

    ## Open questions to research
    - [Question 1]
    - [Question 2]

    ## Estimated scope
    [Small / Medium / Large — and why]
    ```

    Be direct. This is a 2-minute read, not a document.
""")


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------

def _run_agent(system_prompt: str, prompt: str, files_to_read: list[str],
               files_to_write: list[str] = None, allow_web: bool = False,
               model: str = "opus") -> str:
    """Run a Claude agent with the given system prompt."""
    allowed_tools = ["Read", "Glob", "Grep"]
    if files_to_write:
        allowed_tools.extend(["Edit", "Write"])
    if allow_web:
        allowed_tools.extend(["WebSearch", "WebFetch"])

    # Collect directories for --add-dir
    add_dirs = {os.getcwd()}
    for f in (files_to_read or []) + (files_to_write or []):
        p = Path(f)
        add_dirs.add(str(p.parent if p.is_file() else p))

    # Build file reading instructions
    file_instructions = ""
    if files_to_read:
        file_list = "\n".join(f"- `{f}`" for f in files_to_read)
        file_instructions = f"\n\n**Read these files for context:**\n{file_list}\n"

    write_instructions = ""
    if files_to_write:
        write_list = "\n".join(f"- `{f}`" for f in files_to_write)
        write_instructions = f"\n\n**Write your output to:**\n{write_list}\n"

    full_prompt = f"{prompt}{file_instructions}{write_instructions}"

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
    result = shell.run("claude", args=args, input=full_prompt, timeout=300)
    return result.get("stdout", "") if isinstance(result, dict) else str(result)


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

@returns({"document": "string", "problem": "string", "sections": "integer", "tokens": "integer"})
@timeout(600)
def op_draft(problem: str, output: str, context: str = "",
             domain: str = "", research: bool = True,
             model: str = "opus", **params) -> dict:
    """Research a problem and generate a structured proposal."""
    output = str(Path(output).resolve())

    # Ensure output directory exists
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    context_paths = []
    if context:
        for p in context.split(","):
            p = p.strip()
            if p:
                resolved = str(Path(p).resolve())
                if Path(resolved).exists():
                    context_paths.append(resolved)

    # Build the prompt
    domain_hint = f"\n\nDomain: {domain}. Tailor the proposal structure to this domain." if domain else ""
    research_hint = "\n\nResearch the problem space using web search. Look for prior art, industry patterns, and existing solutions." if research else ""

    prompt = (
        f"Write a proposal for the following problem:\n\n"
        f"---\n{problem}\n---\n"
        f"{domain_hint}"
        f"{research_hint}\n\n"
        f"Write the complete proposal document to: `{output}`\n\n"
        f"The document must be standalone — someone reading it with no other "
        f"context should understand the problem, the design, and the trade-offs. "
        f"Show concrete artifacts (exact CLI output, file contents, API "
        f"responses) — don't just describe what they'd look like."
    )

    agent_output = _run_agent(
        system_prompt=DRAFTER_PROMPT,
        prompt=prompt,
        files_to_read=context_paths,
        files_to_write=[output],
        allow_web=research,
        model=model,
    )

    # Verify the file was written
    if not Path(output).exists():
        # Agent might have output the content instead of writing the file
        # Write it ourselves
        Path(output).write_text(agent_output)

    content = Path(output).read_text()
    word_count = len(content.split())
    section_count = content.count("\n## ")

    return {"__result__": {
        "document": output,
        "problem": problem[:200],
        "sections": section_count,
        "tokens": int(word_count * 1.3),  # rough estimate
    }}


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

    output = _run_agent(
        system_prompt=OUTLINER_PROMPT,
        prompt=prompt,
        files_to_read=[],
        allow_web=False,
        model=model,
    )

    # Extract sections from the outline
    sections = []
    for line in output.split("\n"):
        if line.strip().startswith("## "):
            sections.append(line.strip()[3:])

    return {"__result__": {
        "outline": output,
        "problem": problem[:200],
        "sections": sections,
    }}

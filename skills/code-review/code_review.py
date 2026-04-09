"""
code_review.py — Evaluate code changes against project principles and architecture.

Scores every diff against engine principles, shape principles,
skill SDK patterns, and active refactoring specs. Uses llm.oneshot()
for a single evaluation pass — no tools, no agent loop.
"""

import json
from pathlib import Path

from agentos import llm, returns, shell, timeout


# ---------------------------------------------------------------------------
# Knowledge loading
# ---------------------------------------------------------------------------

# Absolute paths — skill may run from any cwd
AGENTOS_ROOT = Path.home() / "dev" / "agentos"
SDK_ROOT = Path.home() / "dev" / "agentos-sdk"


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except (FileNotFoundError, PermissionError):
        return ""


def _load_principles() -> str:
    engine = _read(AGENTOS_ROOT / "docs" / "principles.md")
    sdk = _read(SDK_ROOT / "docs" / "principles.md")
    guide = _read(SDK_ROOT / "skills-sdk" / "agentos" / "GUIDE.md")
    return engine, sdk, guide


def _load_refactoring_specs() -> str:
    specs_dir = AGENTOS_ROOT / "docs" / "specs" / "refactoring"
    if not specs_dir.exists():
        return ""
    parts = []
    for f in sorted(specs_dir.glob("*.md")):
        if f.name == "README.md":
            continue
        parts.append(f"## {f.stem}\n{f.read_text()}")
    return "\n\n".join(parts)


def _load_arch() -> str:
    try:
        result = shell.run(str(AGENTOS_ROOT / "dev.sh"), ["arch"], cwd=str(AGENTOS_ROOT))
        return result.get("stdout", "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

EVALUATOR_SYSTEM_PROMPT = """You are the CTO of agentOS — a pre-launch Rust+Python agent operating system.
You review every commit against the project's principles and architectural direction.

Score this diff 0-100. Be rigorous but fair. You are protecting the codebase from
entropy — every violation you let through makes the next fix harder.

Scoring rubric:
- Start at 100. Deduct points per violation.
- CRITICAL (-30 each): Entity-specific code in Rust, building on a module flagged
  for refactoring, hardcoded provider/service names in generic code
- MAJOR (-15 each): Rendering logic in wrong module, missing delegation pattern,
  new code in a file the refactoring specs say should shrink
- MINOR (-5 each): Naming inconsistencies, unnecessary complexity, missing
  campsite-rule improvements

If the diff touches a file that an active refactoring spec says should shrink or be
decomposed, and the diff ADDS lines to that file, that is at minimum a MAJOR violation.
The right move is to do the refactoring first, then build the feature.

Return ONLY valid JSON:
{
  "score": <0-100>,
  "violations": [
    {"severity": "critical|major|minor", "principle": "<which>", "file": "<path>", "detail": "<what's wrong>"}
  ],
  "summary": "<one sentence>"
}"""


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@returns({
    "score": "integer",
    "maxScore": "integer",
    "pass": "boolean",
    "violations": "string",
    "summary": "string",
})
@timeout(120)
async def evaluate_commit(
    diff: str,
    files: str = "",
    threshold: int = 90,
    model: str = "sonnet",
    **params,
) -> dict:
    """Evaluate a git diff against project principles and refactoring specs.

    Args:
        diff: The staged git diff to evaluate
        files: Newline-separated list of changed file paths
        threshold: Minimum passing score out of 100 (default 90)
        model: LLM model to use for evaluation (default sonnet)
    """
    engine_principles, sdk_principles, skill_guide = _load_principles()
    refactoring_specs = _load_refactoring_specs()
    arch = _load_arch()

    prompt_parts = [
        "Evaluate this git diff against the principles and specs below.",
        "",
    ]

    if engine_principles:
        prompt_parts += ["## Engine Principles", engine_principles, ""]
    if sdk_principles:
        prompt_parts += ["## Shape Principles", sdk_principles, ""]
    if skill_guide:
        prompt_parts += ["## Skill SDK Guide", skill_guide, ""]
    if refactoring_specs:
        prompt_parts += [
            "## Active Refactoring Specs (code should not build on patterns these specs plan to fix)",
            refactoring_specs,
            "",
        ]
    if arch:
        prompt_parts += ["## Architecture (crate sizes, dependency chain, largest files)", arch, ""]

    prompt_parts += [
        "## Files changed",
        files,
        "",
        "## Diff",
        diff,
    ]

    result = await llm.oneshot(
        prompt="\n".join(prompt_parts),
        system=EVALUATOR_SYSTEM_PROMPT,
        model=model,
    )

    # Parse structured JSON from response
    content = result.get("content", "")

    # Extract JSON from response (may be wrapped in markdown code fences)
    json_str = content
    if "```" in content:
        for block in content.split("```"):
            stripped = block.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{"):
                json_str = stripped
                break

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Last resort: find first { to last }
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(content[start:end + 1])
        else:
            return {"__result__": {
                "score": 0,
                "maxScore": 100,
                "pass": False,
                "violations": "Failed to parse evaluation response",
                "summary": "Evaluation error — could not parse LLM response",
            }}

    score = int(data.get("score", 0))
    violations = data.get("violations", [])
    summary = data.get("summary", "No summary")

    # Format violations as markdown
    if isinstance(violations, list):
        violation_lines = []
        for v in violations:
            if isinstance(v, dict):
                sev = v.get("severity", "?").upper()
                principle = v.get("principle", "?")
                file = v.get("file", "?")
                detail = v.get("detail", "?")
                violation_lines.append(f"- **{sev}** [{principle}] `{file}`: {detail}")
            else:
                violation_lines.append(f"- {v}")
        violations_md = "\n".join(violation_lines) if violation_lines else "None"
    else:
        violations_md = str(violations)

    return {"__result__": {
        "score": score,
        "maxScore": 100,
        "pass": score >= threshold,
        "violations": violations_md,
        "summary": summary,
    }}

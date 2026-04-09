"""Claude Code CLI as LLM provider — uses the user's existing auth, no API key needed.

    claude -p --output-format json --model sonnet "prompt"

When tools are provided, uses --mcp-config to point at a separate agentos mcp
process for native tool calling (proper tool_use blocks, no XML hacks).
When output_schema is provided, uses --json-schema for native structured output.

Routes through shell.run() so the engine logs and audits every invocation.
"""

import json

from agentos import shell, returns, timeout, connection, provides
from agentos.tools import llm

MODEL_ALIASES = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

# MCP config pointing at agentos mcp — spawns a separate process, no recursion.
MCP_CONFIG = json.dumps({
    "mcpServers": {
        "agentos": {
            "command": "agentos",
            "args": ["mcp"],
        }
    }
})

# Tools claude -p is allowed to call via MCP.
ALLOWED_TOOLS = "mcp__agentos__run,mcp__agentos__read,mcp__agentos__search"


def _format_messages(messages: list) -> str:
    """Convert chat messages to a single prompt string for claude -p.

    For multi-turn conversations, formats assistant and tool messages
    with XML tags so Claude can understand the conversation history.
    """
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            continue  # handled via --system-prompt flag
        elif role == "assistant":
            parts.append(f"<assistant>\n{content}\n</assistant>")
        elif role == "tool":
            tc_id = msg.get("tool_call_id", "")
            parts.append(f'<tool_result tool_use_id="{tc_id}">\n{content}\n</tool_result>')
        else:
            parts.append(str(content))
    return "\n\n".join(parts)


@provides(llm, models=["opus", "sonnet", "haiku", "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
          features=["tool_calling", "structured_output", "structured_output_with_tools"])
@returns({"content": "string", "tool_calls": "array", "stop_reason": "string", "usage": "object"})
@connection("cli")
@timeout(600)
async def chat(*, model: str, messages: list, tools: list = None,
         temperature: float = 0, system: str = None,
         output_schema: dict = None, **params) -> dict:
    """LLM inference via Claude Code CLI — uses existing auth, no API key.

    When tools are provided, attaches agentos as an MCP server so Claude
    handles tool calling natively (no XML-in-prompt hack). Claude runs its
    own agent loop — calling tools, processing results, iterating until done.
    The response contains the final answer after all tool calls complete.

    When output_schema is provided, uses --json-schema for native validation.
    Both can be combined — tools + structured output in the same call.
    """
    model_id = MODEL_ALIASES.get(model, model)
    prompt = _format_messages(messages)

    args = [
        "-p",
        "--output-format", "json",
        "--model", model_id,
        "--dangerously-skip-permissions",
    ]

    if system:
        args.extend(["--system-prompt", system])

    # Native MCP tool calling — point at agentos mcp for tool dispatch
    if tools:
        args.extend(["--mcp-config", MCP_CONFIG])
        args.extend(["--allowedTools", ALLOWED_TOOLS])

    # Native structured output via --json-schema
    if output_schema:
        args.extend(["--json-schema", json.dumps(output_schema)])

    result = await shell.run("claude", args=args, input=prompt, timeout=580)

    stdout = result.get("stdout", "")
    exit_code = result.get("exit_code", 1)

    if exit_code != 0:
        stderr = result.get("stderr", "")
        raise RuntimeError(f"claude -p failed (exit {exit_code}): {stderr or stdout}")

    # Parse JSON output from claude -p
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {"__result__": {
            "content": stdout,
            "tool_calls": [],
            "stop_reason": "end_turn",
            "usage": {},
        }}

    text = data.get("result", "")
    stop = data.get("stop_reason", "end_turn")
    usage = data.get("usage", {})

    # Structured output comes in structured_output field
    structured = data.get("structured_output")

    # When structured output is present, put it in content as JSON
    # so the agent loop in llm.py can extract it via _extract_json
    if structured and not text:
        text = json.dumps(structured)

    return {"__result__": {
        "content": text or None,
        "tool_calls": [],  # claude -p handles tools internally — no tool_calls to return
        "stop_reason": stop,
        "usage": usage,
        "structured_output": structured,
    }}

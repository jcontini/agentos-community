"""Claude Code CLI as LLM provider — uses the user's existing auth, no API key needed.

    claude -p --output-format json --model sonnet "prompt"

Routes through shell.run() so the engine logs and audits every invocation.
"""

import json

from agentos import shell, returns, timeout, connection
from agentos.tools import llm
from agentos.decorators import provides

MODEL_ALIASES = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}


def _format_messages(messages: list) -> str:
    """Convert chat messages to a single prompt string for claude -p."""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "tool":
            tool_id = msg.get("tool_call_id", "")
            parts.append(f"<tool_result tool_use_id=\"{tool_id}\">\n{content}\n</tool_result>")
        elif role == "assistant":
            if msg.get("tool_calls"):
                parts.append(f"<assistant>\n{content}")
                for tc in msg["tool_calls"]:
                    parts.append(
                        f'<tool_use id="{tc["id"]}" name="{tc["name"]}">\n'
                        f'{json.dumps(tc["input"])}\n</tool_use>'
                    )
                parts.append("</assistant>")
            else:
                parts.append(f"<assistant>\n{content}\n</assistant>")
        else:
            parts.append(content)
    return "\n\n".join(parts)


def _format_tools(tools: list) -> str:
    """Format tool definitions as XML for inclusion in the prompt."""
    if not tools:
        return ""
    parts = ["<tools>"]
    for tool in tools:
        name = tool.get("name", "")
        desc = tool.get("description", "")
        schema = json.dumps(tool.get("input_schema", {}), indent=2)
        parts.append(
            f'<tool name="{name}">\n'
            f'<description>{desc}</description>\n'
            f'<input_schema>{schema}</input_schema>\n'
            f'</tool>'
        )
    parts.append("</tools>")
    parts.append(
        "\nWhen you want to use a tool, respond with a tool_use block:\n"
        '<tool_use id="call_001" name="tool_name">\n'
        '{"param": "value"}\n'
        '</tool_use>\n'
        "\nYou may include text before or after tool_use blocks."
    )
    return "\n".join(parts)


def _parse_tool_calls(text: str) -> tuple[str, list]:
    """Extract tool_use blocks from response text. Returns (clean_text, tool_calls)."""
    import re
    tool_calls = []
    pattern = r'<tool_use\s+id="([^"]+)"\s+name="([^"]+)">\s*(.*?)\s*</tool_use>'
    for match in re.finditer(pattern, text, re.DOTALL):
        tc_id, name, input_str = match.groups()
        try:
            inp = json.loads(input_str.strip())
        except json.JSONDecodeError:
            inp = {"raw": input_str.strip()}
        tool_calls.append({"id": tc_id, "name": name, "input": inp})

    clean = re.sub(pattern, "", text, flags=re.DOTALL).strip()
    return clean, tool_calls


@provides(llm, models=["opus", "sonnet", "haiku", "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"])
@returns({"content": "string", "tool_calls": "array", "stop_reason": "string", "usage": "object"})
@connection("cli")
@timeout(600)
def chat(*, model: str, messages: list, tools: list = None,
         max_tokens: int = 4096, temperature: float = 0,
         system: str = None, **params) -> dict:
    """LLM inference via Claude Code CLI — uses existing auth, no API key.

    Timeout is 600s (10 min) to accommodate Opus with large context + tool
    definitions. Multi-agent workflows (proposal-writing, compose) make
    repeated calls with growing message histories. The previous 280s timeout
    caused consistent failures on agent calls with 4+ context files.
    """
    model_id = MODEL_ALIASES.get(model, model)

    prompt = _format_messages(messages)
    if tools:
        prompt = _format_tools(tools) + "\n\n" + prompt

    args = [
        "-p",
        "--output-format", "json",
        "--model", model_id,
    ]
    if system:
        args.extend(["--system-prompt", system])

    result = shell.run("claude", args=args, input=prompt, timeout=580)

    stdout = result.get("stdout", "")
    exit_code = result.get("exit_code", 1)

    if exit_code != 0:
        stderr = result.get("stderr", "")
        raise RuntimeError(f"claude -p failed (exit {exit_code}): {stderr or stdout}")

    # Parse JSON output from claude -p
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        # Plain text fallback
        return {"__result__": {
            "content": stdout,
            "tool_calls": [],
            "stop_reason": "end_turn",
            "usage": {},
        }}

    text = data.get("result", "")
    stop = data.get("stop_reason", "end_turn")
    usage = data.get("usage", {})

    # Check for tool_use blocks in the response
    clean_text, tool_calls = _parse_tool_calls(text)

    if tool_calls:
        stop = "tool_use"

    return {"__result__": {
        "content": clean_text or None,
        "tool_calls": tool_calls,
        "stop_reason": stop,
        "usage": usage,
    }}

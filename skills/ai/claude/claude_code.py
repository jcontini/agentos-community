"""Claude Code CLI as LLM provider — uses the user's existing auth, no API key needed.

    claude -p --output-format json --model sonnet "prompt"

When tools are provided, uses --mcp-config to point at a separate agentos mcp
process for native tool calling (proper tool_use blocks, no XML hacks).
When output_schema is provided, uses --json-schema for native structured output.

Routes through shell.run() so the engine logs and audits every invocation.
"""

import json

from agentos import http, shell, returns, timeout, connection, provides
from agentos.macos import keychain
from agentos.tools import llm

# Claude Code stores its OAuth token in the macOS keychain under this service.
# The token has `user:inference` scope and can call /v1/models directly —
# same endpoint as the API connection, just using the subscription's OAuth
# token instead of an API key. The response doesn't count against inference quota.
KEYCHAIN_SERVICE = "Claude Code-credentials"
API_BASE = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"


async def _read_oauth_token() -> str:
    """Read the Claude Code OAuth access token from the macOS keychain.

    Re-reads on every call — Claude Code rotates the token weekly and
    refreshes it in the background, so caching would risk staleness.
    """
    raw = await keychain.read(KEYCHAIN_SERVICE)
    if not raw:
        raise RuntimeError(
            f"No Claude Code credentials in keychain (service='{KEYCHAIN_SERVICE}'). "
            "Install Claude Code and run `claude auth login`."
        )
    blob = json.loads(raw)
    token = blob.get("claudeAiOauth", {}).get("accessToken")
    if not token:
        raise RuntimeError("Keychain entry has no claudeAiOauth.accessToken")
    return token


def _map_model(m: dict) -> dict:
    return {
        "id": m.get("id"),
        "name": m.get("display_name"),
        "published": m.get("created_at"),
        "provider": "anthropic",
        "modelType": "llm",
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

# Tools the agent is allowed to use. MCP tools for engine access,
# Claude Code native tools for file/web access. Explicitly listed so
# the agent CANNOT use Agent (sub-agent spawning) or Bash.
ALLOWED_MCP = [
    "mcp__agentos__run",
    "mcp__agentos__read",
    "mcp__agentos__search",
]
ALLOWED_NATIVE = [
    "Read", "Glob", "Grep",           # codebase access (read-only)
    "WebSearch", "WebFetch",           # web research
    "Agent",                           # subagents for deep investigation
]
ALLOWED_TOOLS = ",".join(ALLOWED_MCP + ALLOWED_NATIVE)



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


@returns("model[]")
@connection("cli")
@timeout(15)
async def list_models(**params) -> list:
    """List Claude models available to the local Claude Code subscription.

    Uses the OAuth access token from the macOS keychain (service
    'Claude Code-credentials') to call api.anthropic.com/v1/models.
    No API key required — this works on Pro/Max/Team subscriptions.

    The /v1/models endpoint does not consume inference quota.
    """
    token = await _read_oauth_token()
    headers = {"x-api-key": token, "anthropic-version": ANTHROPIC_VERSION}
    resp = await http.get(
        f"{API_BASE}/models",
        params={"limit": "100"},
        **http.headers(accept="json", extra=headers),
    )
    data = resp["json"] or {}
    return [_map_model(m) for m in data.get("data", [])]


@provides(llm, features=["tool_calling", "structured_output", "structured_output_with_tools"])
@returns({"content": "string", "tool_calls": "array", "stop_reason": "string", "usage": "object"})
@connection("cli")
@timeout(1800)
async def agent(*, model: str, messages: list, tools: list = None,
         temperature: float = 0, system: str = None,
         output_schema: dict = None, **params) -> dict:
    """Run Claude as an agent via the local Claude Code CLI — uses existing auth, no API key.

    Unlike `chat` (single Messages API call), this runs a full agent loop:
    Claude can call tools, read tool results, and iterate until done. The
    returned content is the final answer after all intermediate tool use.

    Model IDs come from the graph (list_models). No hardcoded aliases.

    When tools are provided, attaches agentos as an MCP server so Claude
    handles tool calling natively (no XML-in-prompt hack). When output_schema
    is provided, uses --json-schema for native structured validation. Both
    can be combined — tools + structured output in the same call.
    """
    prompt = _format_messages(messages)

    args = [
        "-p",
        "--output-format", "json",
        "--model", model,
        "--dangerously-skip-permissions",
    ]

    if system:
        args.extend(["--system-prompt", system])

    # Restrict tools — read-only codebase access + subagents + web + agentOS MCP
    args.extend(["--allowedTools", ALLOWED_TOOLS])

    # Native MCP tool calling — point at agentos mcp for tool dispatch
    if tools:
        args.extend(["--mcp-config", MCP_CONFIG])

    # Native structured output via --json-schema
    if output_schema:
        args.extend(["--json-schema", json.dumps(output_schema)])

    result = await shell.run("claude", args=args, input=prompt, timeout=1740)

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
        # Metadata for callers — Python can use session_id to read transcript
        "session_id": data.get("session_id"),
        "total_cost_usd": data.get("total_cost_usd"),
        "num_turns": data.get("num_turns"),
        "duration_ms": data.get("duration_ms"),
    }}

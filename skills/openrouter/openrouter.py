"""OpenRouter — unified AI gateway for models across providers."""

import json
from datetime import datetime, timezone

from agentos import http, connection, provides, returns, llm

API_BASE = "https://openrouter.ai/api/v1"


def _auth_header(params: dict) -> dict:
    key = params.get("auth", {}).get("key", "")
    return {"Authorization": f"Bearer {key}"}


def _ts_to_iso(ts) -> str | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


@returns("model[]")
@connection("api")
def list_models(**params) -> list[dict]:
    """List available AI models from all providers via OpenRouter."""
    resp = http.get(f"{API_BASE}/models", **http.headers(accept="json", extra=_auth_header(params)))
    return [
        {
            "id": m.get("id"),
            "name": m.get("name"),
            "content": m.get("description"),
            "published": _ts_to_iso(m.get("created")),
            "provider": m.get("id", "").split("/")[0] if m.get("id") else None,
            "modelType": "llm",
            "contextWindow": int(m["context_length"]) if m.get("context_length") else None,
        }
        for m in (resp["json"] or {}).get("data", [])
    ]


def _to_openai_msg(msg: dict) -> dict:
    """Convert agentOS message format to OpenAI format."""
    if msg.get("role") == "assistant" and msg.get("tool_calls"):
        return {
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc.get("input", {})),
                    },
                }
                for tc in msg["tool_calls"]
            ],
        }
    elif msg.get("role") == "tool":
        return {
            "role": "tool",
            "tool_call_id": msg.get("tool_call_id"),
            "content": msg.get("content"),
        }
    return {"role": msg.get("role"), "content": msg.get("content")}


@provides(llm, models=["opus", "sonnet", "haiku", "gpt-4o", "gpt-4o-mini", "llama3.3", "claude-opus-4-6", "claude-sonnet-4-5"])
@returns({"content": "{'type': 'string', 'description': 'Text response from the model (null if tool calls only)'}", "tool_calls": "{'type': 'array', 'description': 'Tool calls the model wants to make'}", "stop_reason": "{'type': 'string', 'enum': ['end_turn', 'tool_use', 'max_tokens']}", "usage": "{'type': 'object', 'description': 'Token usage (input_tokens, output_tokens)'}"})
@connection("api")
def chat(*, model: str, messages: list, tools: list = None, max_tokens: int = 4096, temperature: float = 0, system: str = None, **params) -> dict:
    """Send a chat completion request through OpenRouter."""
    openai_messages = []
    if system:
        openai_messages.append({"role": "system", "content": system})
    openai_messages.extend(_to_openai_msg(m) for m in messages)

    body: dict = {
        "model": model,
        "messages": openai_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    resp = http.post(f"{API_BASE}/chat/completions",
                     json=body, **http.headers(accept="json", extra=_auth_header(params)))
    data = resp["json"]
    choices = data.get("choices") or [{}]
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}
    finish_reason = choice.get("finish_reason")

    tool_calls = [
        {
            "id": tc["id"],
            "name": tc["function"]["name"],
            "input": (
                json.loads(tc["function"].get("arguments", "{}"))
                if isinstance(tc["function"].get("arguments"), str)
                else tc["function"].get("arguments") or {}
            ),
        }
        for tc in (message.get("tool_calls") or [])
    ]

    stop_reason = (
        "tool_use" if finish_reason == "tool_calls"
        else "max_tokens" if finish_reason == "length"
        else "end_turn"
    )

    usage = data.get("usage") or {}
    return {
        "content": message.get("content"),
        "tool_calls": tool_calls,
        "stop_reason": stop_reason,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }

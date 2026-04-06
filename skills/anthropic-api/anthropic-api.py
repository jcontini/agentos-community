from agentos import http, connection, provides, returns, timeout
from agentos.tools import llm

API_BASE = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"

MODEL_ALIASES = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-5",
    "haiku": "claude-haiku-4-5-20251001",
}


def _headers(params):
    key = params.get("auth", {}).get("key", "")
    return {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}


def _map_model(m: dict) -> dict:
    return {
        "id": m.get("id"),
        "name": m.get("display_name"),
        "published": m.get("created_at"),
        "provider": "anthropic",
        "modelType": "llm",
    }


def _to_anthropic_msg(msg: dict) -> dict:
    if msg.get("role") == "assistant" and msg.get("tool_calls"):
        content = []
        if msg.get("content"):
            content.append({"type": "text", "text": msg["content"]})
        for tc in msg["tool_calls"]:
            content.append({"type": "tool_use", "id": tc["id"],
                            "name": tc["name"], "input": tc["input"]})
        return {"role": "assistant", "content": content}
    if msg.get("role") == "tool":
        return {"role": "user", "content": [{
            "type": "tool_result",
            "tool_use_id": msg["tool_call_id"],
            "content": msg["content"],
        }]}
    return msg


@returns("model[]")
@connection("api")
def list_models(**params) -> list:
    """List available Claude models from Anthropic"""
    resp = http.get(f"{API_BASE}/models",
                    params={"limit": "1000"}, **http.headers(accept="json", extra=_headers(params)))
    return [_map_model(m) for m in (resp["json"] or {}).get("data", [])]


@provides(llm, models=["opus", "sonnet", "haiku", "claude-opus-4-6", "claude-sonnet-4-5", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"])
@returns({"content": "{'type': 'string', 'description': 'Text response from Claude (null if only tool calls)'}", "tool_calls": "{'type': 'array', 'description': 'Tool calls the model wants to make'}", "stop_reason": "{'type': 'string', 'enum': ['end_turn', 'tool_use', 'max_tokens']}", "usage": "{'type': 'object', 'description': 'Token usage statistics'}"})
@connection("api")
@timeout(120)
def chat(*, model: str, messages: list, tools: list = None,
         max_tokens: int = 4096, temperature: float = 0,
         system: str = None, **params) -> dict:
    """Send a chat completion request to Claude (Anthropic Messages API)

        Args:
            model: Model ID (e.g., claude-3-5-haiku-20241022, claude-4-sonnet-20250514)
            messages: Array of message objects with role and content
            tools: Optional array of tool definitions for function calling
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0 = deterministic for agents)
            system: Optional system prompt
        """
    model = MODEL_ALIASES.get(model, model)
    body = {
        "model": model,
        "messages": [_to_anthropic_msg(m) for m in messages],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        body["tools"] = tools
    if system:
        body["system"] = system
    resp = http.post(f"{API_BASE}/messages",
                     json=body, **http.headers(accept="json", extra=_headers(params)))
    data = resp["json"]
    blocks = data.get("content", [])
    return {
        "content": next((b["text"] for b in blocks if b.get("type") == "text"), None),
        "toolCalls": [{"id": b["id"], "name": b["name"], "input": b["input"]}
                      for b in blocks if b.get("type") == "tool_use"],
        "stopReason": data.get("stop_reason"),
        "usage": data.get("usage"),
    }

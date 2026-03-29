from agentos import http

API_BASE = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"


def _headers(params):
    key = params.get("auth", {}).get("key", "")
    return {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}


def _map_model(m: dict) -> dict:
    return {
        "id": m.get("id"),
        "name": m.get("display_name"),
        "datePublished": m.get("created_at"),
        "provider": "anthropic",
        "model_type": "llm",
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


def list_models(**params) -> list:
    resp = http.get(f"{API_BASE}/models",
                    params={"limit": "1000"}, headers=_headers(params),
                    profile="api")
    return [_map_model(m) for m in (resp["json"] or {}).get("data", [])]


def chat(*, model: str, messages: list, tools: list = None,
         max_tokens: int = 4096, temperature: float = 0,
         system: str = None, **params) -> dict:
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
                     json=body, headers=_headers(params),
                     profile="api")
    data = resp["json"]
    blocks = data.get("content", [])
    return {
        "content": next((b["text"] for b in blocks if b.get("type") == "text"), None),
        "tool_calls": [{"id": b["id"], "name": b["name"], "input": b["input"]}
                       for b in blocks if b.get("type") == "tool_use"],
        "stop_reason": data.get("stop_reason"),
        "usage": data.get("usage"),
    }

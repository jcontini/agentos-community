#!/usr/bin/env python3
"""Ollama skill for AgentOS — local AI model management and inference.

Connections:
  api  — Ollama REST API at http://localhost:11434
  cli  — Ollama CLI binary (default: /opt/homebrew/bin/ollama)

The api connection is the fast inference path. The cli connection is used for
server management (starting ollama serve), model pulls, and deletes. Most
inference operations prefer api but auto-start the server via cli if needed.
"""

import json
import shutil
import sys
import time
from pathlib import Path

from agentos import http, shell

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_BINARY = "/opt/homebrew/bin/ollama"


# ── Connection helpers ────────────────────────────────────────────────────────

def _base_url(connection: dict | None) -> str:
    if isinstance(connection, dict) and connection.get("base_url"):
        return str(connection["base_url"]).rstrip("/")
    return DEFAULT_BASE_URL


def _binary(connection: dict | None) -> str:
    if isinstance(connection, dict):
        b = (connection.get("vars") or {}).get("binary")
        if b:
            return str(b)
    found = shutil.which("ollama")
    if found:
        return found
    return DEFAULT_BINARY


def _connection_name(connection: dict | None) -> str:
    if not isinstance(connection, dict):
        return "api"
    name = connection.get("name") or connection.get("id") or ""
    return str(name).lower().strip() or "api"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _http_get(url: str, timeout: int = 10) -> dict:
    resp = http.get(url, **http.headers(accept="json"), timeout=timeout)
    if not resp.get("ok"):
        raise RuntimeError(f"HTTP GET {url} failed: {resp.get('status', 0)}")
    return resp.get("json") or json.loads(resp.get("body", "{}"))


def _http_post(url: str, body: dict, timeout: int = 300) -> dict:
    resp = http.post(url, json=body, **http.headers(accept="json"), timeout=timeout)
    if not resp.get("ok"):
        raise RuntimeError(f"HTTP POST {url} failed: {resp.get('status', 0)}")
    return resp.get("json") or json.loads(resp.get("body", "{}"))


def _http_delete(url: str, body: dict, timeout: int = 30) -> int:
    resp = http.delete(url, json=body, **http.headers(accept="json"), timeout=timeout)
    return resp.get("status", 0)


# ── Server management ─────────────────────────────────────────────────────────

def _api_running(base_url: str = DEFAULT_BASE_URL) -> bool:
    try:
        _http_get(f"{base_url}/api/version", timeout=3)
        return True
    except Exception:
        return False


def _start_server(binary: str) -> bool:
    """Start `ollama serve` in background. Polls up to 8s for readiness."""
    try:
        # shell.run is synchronous, so we use it to invoke `ollama serve` via
        # a background shell command. The serve process detaches itself.
        shell.run(binary, ["serve"], timeout=2)
    except Exception:
        pass  # timeout is expected — ollama serve runs forever
    for _ in range(16):
        time.sleep(0.5)
        if _api_running():
            return True
    return False


def _ensure_api_running(connection: dict | None, cli_connection: dict | None = None) -> None:
    """Ensure the Ollama REST API is reachable, starting it via CLI if not."""
    base = _base_url(connection)
    if _api_running(base):
        return
    binary = _binary(cli_connection or connection)
    started = _start_server(binary)
    if not started:
        raise RuntimeError(
            "Ollama server is not running and could not be started automatically. "
            f"Run `{binary} serve` or `brew services start ollama`."
        )


# ── Status ────────────────────────────────────────────────────────────────────

def op_status(connection: dict | None = None, **kwargs) -> dict:
    """Check if Ollama is running; start it if not. Returns running state + version."""
    binary = _binary(connection)
    base = DEFAULT_BASE_URL
    running = _api_running(base)
    started = False

    if not running:
        started = _start_server(binary)
        running = started

    version = None
    if running:
        try:
            resp = _http_get(f"{base}/api/version", timeout=5)
            version = resp.get("version")
        except Exception:
            pass

    if running and not started:
        message = f"Ollama {version} is running at {base}"
    elif started:
        message = f"Started Ollama {version} at {base}"
    else:
        message = f"Ollama is not running and could not be started (binary: {binary})"

    return {
        "running": running,
        "version": version,
        "started": started,
        "message": message,
    }


# ── Chat ──────────────────────────────────────────────────────────────────────

def _normalize_tool_calls(raw: list) -> list:
    out = []
    for tc in raw:
        fn = tc.get("function") or {}
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        out.append({
            "id": tc.get("id") or fn.get("name") or "tool_call",
            "name": fn.get("name", ""),
            "input": args,
        })
    return out


def op_chat(
    model: str,
    messages: list,
    tools: list = None,
    system: str = None,
    max_tokens: int = 4096,
    temperature: float = 0,
    thinking: bool = False,
    connection: dict | None = None,
    **kwargs,
) -> dict:
    conn_name = _connection_name(connection)

    if conn_name == "cli":
        return _chat_via_cli(model, messages, system, connection)

    # API path — auto-start if needed
    _ensure_api_running(connection)
    base = _base_url(connection)

    all_messages = []
    if system:
        all_messages.append({"role": "system", "content": system})
    all_messages.extend(messages)

    body: dict = {
        "model": model,
        "messages": all_messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    if tools:
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
                },
            }
            for t in tools
        ]

    if thinking:
        body["think"] = True

    resp = _http_post(f"{base}/api/chat", body, timeout=300)
    msg = resp.get("message") or {}
    raw_tools = msg.get("tool_calls") or []
    done_reason = resp.get("done_reason", "stop")

    return {
        "content": msg.get("content") or None,
        "thinking": msg.get("thinking") or None,
        "tool_calls": _normalize_tool_calls(raw_tools),
        "stop_reason": (
            "tool_use" if done_reason == "tool_calls"
            else "max_tokens" if done_reason == "length"
            else "end_turn"
        ),
        "usage": {
            "input_tokens": resp.get("prompt_eval_count", 0),
            "output_tokens": resp.get("eval_count", 0),
        },
    }


def _chat_via_cli(
    model: str,
    messages: list,
    system: str | None,
    connection: dict | None,
) -> dict:
    """Single-turn chat via `ollama run` subprocess (CLI connection path)."""
    binary = _binary(connection)
    parts = []
    if system:
        parts.append(f"System: {system}")
    for m in messages:
        role = m.get("role", "user").capitalize()
        content = m.get("content", "")
        parts.append(f"{role}: {content}")

    prompt = "\n\n".join(parts)
    result = shell.run(binary, ["run", model, "--nowordwrap"], input=prompt, timeout=300)
    if result["exit_code"] != 0:
        raise RuntimeError(f"ollama run failed: {result['stderr'].strip()}")

    return {
        "content": result["stdout"].strip(),
        "thinking": None,
        "tool_calls": [],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


# ── Generate ──────────────────────────────────────────────────────────────────

def op_generate(
    model: str,
    prompt: str,
    system: str = None,
    max_tokens: int = 4096,
    temperature: float = 0,
    connection: dict | None = None,
    **kwargs,
) -> dict:
    _ensure_api_running(connection)
    base = _base_url(connection)

    body: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if system:
        body["system"] = system

    resp = _http_post(f"{base}/api/generate", body, timeout=300)
    return {
        "response": resp.get("response", ""),
        "usage": {
            "input_tokens": resp.get("prompt_eval_count", 0),
            "output_tokens": resp.get("eval_count", 0),
        },
    }


# ── List models ───────────────────────────────────────────────────────────────

def op_list_models(connection: dict | None = None) -> list:
    conn_name = _connection_name(connection)
    if conn_name == "cli":
        return _list_models_via_cli(connection)

    _ensure_api_running(connection)
    base = _base_url(connection)
    resp = _http_get(f"{base}/api/tags")
    return resp.get("models", [])


def _list_models_via_cli(connection: dict | None) -> list:
    binary = _binary(connection)
    result = shell.run(binary, ["list", "--json"], timeout=15)
    if result["exit_code"] == 0 and result["stdout"].strip():
        try:
            data = json.loads(result["stdout"])
            return data.get("models", [])
        except Exception:
            pass

    # Fallback: parse text table output
    result2 = shell.run(binary, ["list"], timeout=15)
    return _parse_list_text(result2["stdout"])


def _parse_list_text(text: str) -> list:
    """Parse `ollama list` plain-text table into model dicts."""
    models = []
    lines = text.strip().splitlines()
    for line in lines[1:]:  # skip header row
        parts = line.split()
        if not parts:
            continue
        models.append({
            "name": parts[0],
            "size": parts[2] if len(parts) > 2 else None,
            "modified_at": " ".join(parts[3:]) if len(parts) > 3 else None,
        })
    return models


# ── Pull model ────────────────────────────────────────────────────────────────

def op_pull_model(model: str, connection: dict | None = None, **kwargs) -> dict:
    conn_name = _connection_name(connection)
    if conn_name == "api":
        return _pull_via_api(model, connection)
    return _pull_via_cli(model, connection)


def _pull_via_cli(model: str, connection: dict | None) -> dict:
    binary = _binary(connection)
    result = shell.run(binary, ["pull", model], timeout=600)
    if result["exit_code"] != 0:
        raise RuntimeError(f"ollama pull failed: {result['stderr'].strip()}")
    return {
        "status": "success",
        "model": model,
        "message": f"Pulled {model} successfully",
    }


def _pull_via_api(model: str, connection: dict | None) -> dict:
    _ensure_api_running(connection)
    base = _base_url(connection)
    resp = _http_post(f"{base}/api/pull", {"name": model, "stream": False}, timeout=600)
    if "error" in resp:
        raise RuntimeError(f"Pull failed: {resp['error']}")
    return {
        "status": "success",
        "model": model,
        "message": f"Pull complete — status: {resp.get('status', 'done')}",
    }


# ── Delete model ──────────────────────────────────────────────────────────────

def op_delete_model(model: str, connection: dict | None = None, **kwargs) -> dict:
    conn_name = _connection_name(connection)
    if conn_name == "cli":
        return _delete_via_cli(model, connection)

    _ensure_api_running(connection)
    base = _base_url(connection)
    status = _http_delete(f"{base}/api/delete", {"name": model}, timeout=30)
    if status == 404:
        raise RuntimeError(f"Model {model!r} not found")
    if status >= 400:
        raise RuntimeError(f"Delete failed with status {status}")
    return {"status": "success", "model": model, "message": f"Deleted {model}"}


def _delete_via_cli(model: str, connection: dict | None) -> dict:
    binary = _binary(connection)
    result = shell.run(binary, ["rm", model], timeout=30)
    if result["exit_code"] != 0:
        raise RuntimeError(f"ollama rm failed: {result['stderr'].strip()}")
    return {"status": "success", "model": model, "message": f"Deleted {model}"}


# ── Show model ────────────────────────────────────────────────────────────────

def op_show_model(model: str, connection: dict | None = None, **kwargs) -> dict:
    _ensure_api_running(connection)
    base = _base_url(connection)
    resp = _http_post(f"{base}/api/show", {"name": model}, timeout=15)

    details = resp.get("details") or {}
    model_info = resp.get("model_info") or {}

    # context_length key varies by architecture: llama.context_length, qwen2.context_length, etc.
    context_length = None
    for k, v in model_info.items():
        if k.endswith(".context_length"):
            context_length = v
            break

    return {
        "name": model,
        "format": details.get("format"),
        "family": details.get("family"),
        "parameter_size": details.get("parameter_size"),
        "quantization_level": details.get("quantization_level"),
        "context_length": context_length,
        "template": resp.get("template"),
        "system_prompt": resp.get("system"),
    }


# ── Shape-native list/ps ─────────────────────────────────────────────────────

def list_models(connection: dict | None = None, **params) -> list[dict]:
    """List downloaded models, shape-native (id=name, datePublished, size, details)."""
    raw = op_list_models(connection)
    return [
        {
            "id": m.get("name"),
            "datePublished": m.get("modified_at"),
            "size": m.get("size"),
            "digest": m.get("digest"),
            "format": (m.get("details") or {}).get("format"),
            "family": (m.get("details") or {}).get("family"),
            "parameter_size": (m.get("details") or {}).get("parameter_size"),
            "quantization_level": (m.get("details") or {}).get("quantization_level"),
        }
        for m in (raw or [])
    ]


def list_models_cli(connection: dict | None = None, **params) -> list[dict]:
    """List models via the Ollama CLI binary (for when the REST server may not be running)."""
    raw = _list_models_via_cli(connection)
    return [
        {
            "id": m.get("name"),
            "datePublished": m.get("modified_at"),
            "size": m.get("size"),
            "digest": m.get("digest"),
            "format": (m.get("details") or {}).get("format"),
            "family": (m.get("details") or {}).get("family"),
            "parameter_size": (m.get("details") or {}).get("parameter_size"),
            "quantization_level": (m.get("details") or {}).get("quantization_level"),
        }
        for m in (raw or [])
    ]


def ps(connection: dict | None = None, **params) -> list[dict]:
    """List currently loaded models (in GPU/unified RAM), shape-native."""
    _ensure_api_running(connection)
    base = _base_url(connection)
    resp = _http_get(f"{base}/api/ps")
    return [
        {
            "id": m.get("name"),
            "size": m.get("size"),
            "digest": m.get("digest"),
            "expires_at": m.get("expires_at"),
            "size_vram": m.get("size_vram"),
        }
        for m in (resp.get("models") or [])
    ]


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: ollama.py <status|list|pull|delete|show|chat|generate> [args...]"}))
        sys.exit(1)

    cmd = sys.argv[1]
    try:
        if cmd == "status":
            result = op_status()
        elif cmd == "list":
            result = op_list_models()
        elif cmd == "pull":
            if len(sys.argv) < 3:
                raise ValueError("Usage: ollama.py pull <model>")
            result = op_pull_model(sys.argv[2])
        elif cmd == "delete":
            if len(sys.argv) < 3:
                raise ValueError("Usage: ollama.py delete <model>")
            result = op_delete_model(sys.argv[2])
        elif cmd == "show":
            if len(sys.argv) < 3:
                raise ValueError("Usage: ollama.py show <model>")
            result = op_show_model(sys.argv[2])
        elif cmd == "chat":
            if len(sys.argv) < 4:
                raise ValueError("Usage: ollama.py chat <model> <message>")
            result = op_chat(
                model=sys.argv[2],
                messages=[{"role": "user", "content": sys.argv[3]}],
            )
        elif cmd == "generate":
            if len(sys.argv) < 4:
                raise ValueError("Usage: ollama.py generate <model> <prompt>")
            result = op_generate(model=sys.argv[2], prompt=sys.argv[3])
        else:
            raise ValueError(f"Unknown command: {cmd}")

        print(json.dumps(result, indent=2))
    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

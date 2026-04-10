"""Claude Code CLI as LLM provider AND local-state reader.

Two responsibilities:

1. **Inference via the local `claude` binary** — uses the user's existing
   subscription auth. `agent()` runs `claude -p` as a full agent loop.

2. **Reading Claude Code's on-disk state** under `~/.claude/` — session
   transcripts (`projects/<slug>/<sessionId>.jsonl`), sub-agent sidecars,
   tool-result overflow files, file-history snapshots. These power rapid
   prototypes (e.g. the conversation viewer in `_prototypes/claude-viewer/`)
   and future agents that need to introspect their own history.

Both responsibilities use the `cli` connection.

Routes HTTP through shell.run() / http.get() so the engine logs and audits
every invocation.
"""

import json
from pathlib import Path

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
async def list_models_cli(**params) -> list:
    """List Claude models available to the local Claude Code subscription.

    Uses the OAuth access token from the macOS keychain (service
    'Claude Code-credentials') to call api.anthropic.com/v1/models.
    No API key required — this works on Pro/Max/Team subscriptions.

    Named `list_models_cli` (not `list_models`) because `claude_api.py`
    already defines `list_models` and skill tool names share a flat
    namespace across all .py files in the skill directory.

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


# ---------------------------------------------------------------------------
# Local state reads — ~/.claude/ on-disk transcripts and metadata
# ---------------------------------------------------------------------------
#
# Claude Code stores every conversation as a JSONL file at
#   ~/.claude/projects/<slug>/<conversationId>.jsonl
# where <slug> is the cwd with '/' replaced by '-'. Sub-agent invocations
# live in the sibling directory <conversationId>/subagents/agent-*.jsonl.
# The ontology is fully documented in ai/claude/_prototype/ontology.md.
#
# Tools return shape-native dicts: `conversation` (with a `message[]` relation
# for full reads). This means `read` / `search` / the viewer all see the data
# the same way iMessage, WhatsApp, Gmail threads do — one entity type, one
# render path. Extra fields beyond the shape (slug, cwd, gitBranch, blocks,
# model, usage) are preserved for richer viewers; audit will flag them.

_CLAUDE_DIR = Path.home() / ".claude"
_PROJECTS_DIR = _CLAUDE_DIR / "projects"

# Housekeeping row types we don't expose as messages — they're folded into
# session-level properties (title) or dropped entirely.
_HOUSEKEEPING_TYPES = {
    "queue-operation", "last-prompt", "permission-mode",
    "agent-name", "file-history-snapshot",
}

# Truncation guard for individual content blocks. Full transcripts can be
# tens of MB — we cap per-block text at this size and report the dropped
# byte count so callers can fetch overflow on demand.
_MAX_BLOCK_BYTES = 200_000


def _slug_to_cwd(slug: str) -> str:
    """`-Users-joe-dev-agentos` → `/Users/joe/dev/agentos` (best-effort).

    The slug is lossy — Claude Code replaces '/' with '-', which collides
    with real dashes in path segments. Where possible, callers should prefer
    the `cwd` field inside the jsonl rows (first-class per row) over this
    reconstruction.
    """
    if not slug.startswith("-"):
        return slug
    return "/" + slug[1:].replace("-", "/")


def _truncate(s: str | None, limit: int = _MAX_BLOCK_BYTES) -> tuple[str, int]:
    """Return (possibly-truncated text, dropped_bytes)."""
    if s is None:
        return "", 0
    b = s.encode("utf-8", errors="replace")
    if len(b) <= limit:
        return s, 0
    return b[:limit].decode("utf-8", errors="replace"), len(b) - limit


def _stream_jsonl(path: Path):
    """Yield parsed JSON objects from a JSONL file, skipping bad lines."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def _flatten_content(content) -> list[dict]:
    """Normalize message.content into a list of render-ready block dicts.

    Handles all shapes observed in Claude Code's jsonl:
      - string (plain user message or local-command caveat)
      - list of blocks: text | tool_use | tool_result | thinking | image
    """
    if content is None:
        return []
    if isinstance(content, str):
        text, dropped = _truncate(content)
        return [{"kind": "text", "text": text, "dropped": dropped}]
    out: list[dict] = []
    for block in content:
        if not isinstance(block, dict):
            out.append({"kind": "raw", "data": block})
            continue
        t = block.get("type")
        if t == "text":
            text, dropped = _truncate(block.get("text", ""))
            out.append({"kind": "text", "text": text, "dropped": dropped})
        elif t == "thinking":
            text, dropped = _truncate(block.get("thinking", ""))
            out.append({"kind": "thinking", "text": text, "dropped": dropped})
        elif t == "tool_use":
            try:
                inp_str = json.dumps(block.get("input", {}), ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                inp_str = str(block.get("input", ""))
            inp_trunc, dropped = _truncate(inp_str)
            out.append({
                "kind": "tool_use",
                "id": block.get("id"),
                "name": block.get("name"),
                "input": inp_trunc,
                "dropped": dropped,
            })
        elif t == "tool_result":
            raw = block.get("content")
            if isinstance(raw, str):
                body_text = raw
            elif isinstance(raw, list):
                parts = []
                for c in raw:
                    if isinstance(c, dict):
                        if c.get("type") == "text":
                            parts.append(c.get("text", ""))
                        elif c.get("type") == "tool_reference":
                            parts.append(f"[tool_reference: {c.get('tool_name')}]")
                        elif c.get("type") == "image":
                            parts.append("[image]")
                        else:
                            parts.append(json.dumps(c, ensure_ascii=False))
                    else:
                        parts.append(str(c))
                body_text = "\n".join(parts)
            else:
                body_text = ""
            body_trunc, dropped = _truncate(body_text)
            out.append({
                "kind": "tool_result",
                "tool_use_id": block.get("tool_use_id"),
                "is_error": bool(block.get("is_error")),
                "text": body_trunc,
                "dropped": dropped,
            })
        elif t == "image":
            out.append({"kind": "image"})
        else:
            out.append({"kind": "raw", "type": t, "data": block})
    return out


def _summarize_attachment(att: dict) -> str:
    t = att.get("type", "")
    if t == "deferred_tools_delta":
        return f"deferred tools: +{len(att.get('addedNames', []))}"
    if t == "todo_list":
        return f"todo list ({len(att.get('items', []))} items)"
    if t == "selected_lines_in_ide":
        return f"IDE selection: {att.get('filePath', '?')}"
    if t == "opened_file_in_ide":
        return f"IDE opened: {att.get('filePath', '?')}"
    return t or "(attachment)"


_SYNTHETIC_PREFIXES = (
    "<local-command",
    "<command-name",
    "<system-reminder",
    "<command-message",
    "Caveat: The messages below were generated",
)


def _first_user_preview(blocks: list[dict]) -> str | None:
    for b in blocks:
        if b.get("kind") == "text":
            txt = (b.get("text") or "").strip()
            if txt and not txt.startswith(_SYNTHETIC_PREFIXES):
                return txt[:200]
    return None


def _parse_conversation_meta(path: Path) -> dict:
    """Cheap pass over a conversation file — shape-native meta, no messages.

    Returns a `conversation`-shape dict. Fields beyond the shape (slug, cwd,
    gitBranch, versions, path, sizeBytes, firstTs) are preserved for viewers
    and provenance; they'll show up as audit warnings until the shape adopts
    them or a viewer-specific extension is added.
    """
    first_ts: str | None = None
    last_ts: str | None = None
    msg_count = 0
    title: str | None = None
    cwd: str | None = None
    git_branch: str | None = None
    versions: set[str] = set()
    first_user_text: str | None = None

    for row in _stream_jsonl(path):
        rtype = row.get("type")
        ts = row.get("timestamp")
        if ts:
            if first_ts is None or ts < first_ts:
                first_ts = ts
            if last_ts is None or ts > last_ts:
                last_ts = ts
        v = row.get("version")
        if v:
            versions.add(v)
        if rtype in ("user", "assistant"):
            if not cwd and row.get("cwd"):
                cwd = row.get("cwd")
            if not git_branch and row.get("gitBranch"):
                git_branch = row.get("gitBranch")
            msg_count += 1
            if rtype == "user" and first_user_text is None and not row.get("isMeta"):
                msg = row.get("message") or {}
                blocks = _flatten_content(msg.get("content"))
                first_user_text = _first_user_preview(blocks)
        elif rtype == "ai-title":
            title = row.get("aiTitle")

    if not title and first_user_text:
        title = first_user_text[:80]

    return {
        # Shape-native fields
        "platform": "claude-code",
        "id": path.stem,
        "name": title,
        "text": first_user_text[:200] if first_user_text else None,
        "published": last_ts,  # temporal anchor = last activity
        "messageCount": msg_count,
        # Viewer / provenance extras (audit will flag these — by design)
        "slug": path.parent.name,
        "cwd": cwd or _slug_to_cwd(path.parent.name),
        "gitBranch": git_branch,
        "firstTs": first_ts,
        "versions": sorted(versions),
        "path": str(path),
        "sizeBytes": path.stat().st_size if path.exists() else 0,
    }


def _blocks_to_text(blocks: list[dict]) -> str:
    """Collapse a list of render-ready blocks into a single text string.

    Used to populate `message.content` (the FTS-indexed long-body field).
    Tool calls are rendered as a pseudo-xml tag so FTS can find them by
    tool name; tool results become their body text.
    """
    parts: list[str] = []
    for b in blocks:
        kind = b.get("kind")
        if kind == "text":
            parts.append(b.get("text") or "")
        elif kind == "thinking":
            parts.append(b.get("text") or "")
        elif kind == "tool_use":
            parts.append(f"<tool_use name=\"{b.get('name','')}\">\n{b.get('input','')}\n</tool_use>")
        elif kind == "tool_result":
            parts.append(b.get("text") or "")
    return "\n\n".join(p for p in parts if p)


def _parse_conversation_full(path: Path) -> dict:
    """Full parse — conversation shape with nested `message[]` relation.

    Returns a single `conversation` dict. Each item in `message` is a
    `message`-shape dict with shape-native fields (id, author, content,
    published, conversationId, isOutgoing) plus viewer extras (blocks,
    model, usage, kind, parent, isSidechain, isMeta).
    """
    first_ts: str | None = None
    last_ts: str | None = None
    title: str | None = None
    cwd: str | None = None
    git_branch: str | None = None
    versions: set[str] = set()
    first_user_text: str | None = None
    messages: list[dict] = []
    conversation_id = path.stem

    for row in _stream_jsonl(path):
        rtype = row.get("type")
        ts = row.get("timestamp")
        if ts:
            if first_ts is None or ts < first_ts:
                first_ts = ts
            if last_ts is None or ts > last_ts:
                last_ts = ts
        v = row.get("version")
        if v:
            versions.add(v)
        if rtype in ("user", "assistant"):
            if not cwd and row.get("cwd"):
                cwd = row.get("cwd")
            if not git_branch and row.get("gitBranch"):
                git_branch = row.get("gitBranch")

        if rtype == "ai-title":
            title = row.get("aiTitle")
            continue
        if rtype in _HOUSEKEEPING_TYPES:
            continue
        if rtype == "progress":
            messages.append({
                "platform": "claude-code",
                "id": row.get("uuid"),
                "conversationId": conversation_id,
                "author": "progress",
                "content": str(row.get("content", ""))[:500],
                "published": ts,
                "kind": "progress",
            })
            continue
        if rtype == "system":
            content = row.get("content", "")
            text_str = content if isinstance(content, str) else json.dumps(content)
            text, _ = _truncate(text_str)
            messages.append({
                "platform": "claude-code",
                "id": row.get("uuid"),
                "conversationId": conversation_id,
                "author": "system",
                "content": text,
                "published": ts,
                "kind": "system",
                "subtype": row.get("subtype"),
                "level": row.get("level"),
            })
            continue
        if rtype == "attachment":
            att = row.get("attachment", {})
            summary = _summarize_attachment(att)
            messages.append({
                "platform": "claude-code",
                "id": row.get("uuid"),
                "conversationId": conversation_id,
                "author": "attachment",
                "content": summary,
                "published": ts,
                "kind": "attachment",
                "attType": att.get("type"),
            })
            continue
        if rtype in ("user", "assistant"):
            msg = row.get("message") or {}
            blocks = _flatten_content(msg.get("content"))
            if rtype == "user" and first_user_text is None and not row.get("isMeta"):
                first_user_text = _first_user_preview(blocks)
            messages.append({
                "platform": "claude-code",
                "id": row.get("uuid"),
                "conversationId": conversation_id,
                "author": rtype,
                "content": _blocks_to_text(blocks),
                "published": ts,
                "isOutgoing": (rtype == "user"),
                # Viewer extras
                "kind": rtype,
                "parent": row.get("parentUuid"),
                "isSidechain": bool(row.get("isSidechain")),
                "isMeta": bool(row.get("isMeta")),
                "model": (msg.get("model") if rtype == "assistant" else None),
                "usage": (msg.get("usage") if rtype == "assistant" else None),
                "blocks": blocks,
            })
            continue
        messages.append({
            "platform": "claude-code",
            "id": row.get("uuid"),
            "conversationId": conversation_id,
            "author": rtype or "unknown",
            "content": None,
            "published": ts,
            "kind": "unknown",
        })

    if not title and first_user_text:
        title = first_user_text[:80]

    # Count real user/assistant turns, not every row
    msg_count = sum(1 for m in messages if m.get("kind") in ("user", "assistant"))

    return {
        # Shape-native fields
        "platform": "claude-code",
        "id": conversation_id,
        "name": title,
        "text": first_user_text[:200] if first_user_text else None,
        "published": last_ts,
        "messageCount": msg_count,
        # Relations
        "message": messages,
        # Viewer / provenance extras
        "slug": path.parent.name,
        "cwd": cwd or _slug_to_cwd(path.parent.name),
        "gitBranch": git_branch,
        "firstTs": first_ts,
        "versions": sorted(versions),
        "path": str(path),
        "sizeBytes": path.stat().st_size if path.exists() else 0,
    }


@returns({"projects": "array"})
@connection("cli")
@timeout(10)
async def list_projects(**params) -> dict:
    """List every Claude Code project directory under ~/.claude/projects/.

    A "project" is a directory whose slug is the cwd with '/' replaced by '-'.
    Returns one entry per project with a conversation count and the most-recent
    activity timestamp. Useful as the top level of a project → conversation
    browser.
    """
    if not _PROJECTS_DIR.is_dir():
        return {"projects": []}
    out = []
    for pdir in sorted(_PROJECTS_DIR.iterdir()):
        if not pdir.is_dir():
            continue
        jsonls = sorted(pdir.glob("*.jsonl"))
        last_ts: str | None = None
        for jp in jsonls:
            mtime = jp.stat().st_mtime
            # Use mtime as a cheap proxy — avoids reading every file. Callers
            # can ask for real timestamps via list_conversations.
            iso = _mtime_iso(mtime)
            if last_ts is None or iso > last_ts:
                last_ts = iso
        out.append({
            "slug": pdir.name,
            "cwd": _slug_to_cwd(pdir.name),
            "conversationCount": len(jsonls),
            "lastActivity": last_ts,
        })
    out.sort(key=lambda p: p.get("lastActivity") or "", reverse=True)
    return {"projects": out}


def _mtime_iso(epoch: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


@returns("conversation[]")
@connection("cli")
@timeout(60)
async def list_conversations_cli(*, project: str | None = None, limit: int = 0, **params) -> list:
    """List Claude Code conversations (local transcripts under ~/.claude/projects/).

    Named `list_conversations_cli` because `claude_web.py` owns `list_conversations`
    (for claude.ai web chats) and skill tool names share a flat namespace.

    Each conversation is one JSONL transcript file. Returns a flat list of
    `conversation`-shape dicts — id (the transcript UUID), name (ai-title or
    first meaningful user message), platform ('claude-code'), published (last
    activity), messageCount, plus viewer extras (slug, cwd, gitBranch, versions,
    path, sizeBytes, firstTs).

    Args:
        project: Optional project slug (e.g. '-Users-joe-dev-agentos') to
                 scope the listing. If omitted, returns conversations from
                 every project under ~/.claude/projects/.
        limit:   Optional cap (0 = all). Conversations are sorted newest-first
                 by `published`, so `limit: 20` returns the 20 most recent.

    Does NOT read message bodies — cheap enough to call at page load.
    """
    if not _PROJECTS_DIR.is_dir():
        return []

    if project:
        proj_dirs = [_PROJECTS_DIR / project]
    else:
        proj_dirs = [p for p in _PROJECTS_DIR.iterdir() if p.is_dir()]

    conversations: list[dict] = []
    for pdir in proj_dirs:
        if not pdir.is_dir():
            continue
        for jp in pdir.glob("*.jsonl"):
            try:
                conversations.append(_parse_conversation_meta(jp))
            except Exception as e:  # noqa: BLE001 — corrupt files shouldn't kill the listing
                conversations.append({
                    "platform": "claude-code",
                    "id": jp.stem,
                    "name": None,
                    "slug": pdir.name,
                    "path": str(jp),
                    "error": f"{type(e).__name__}: {e}",
                })

    conversations.sort(key=lambda c: c.get("published") or "", reverse=True)
    if limit and limit > 0:
        conversations = conversations[:limit]
    return conversations


@returns("conversation")
@connection("cli")
@timeout(60)
async def read_conversation_cli(*, id: str, project: str | None = None, **params) -> dict:
    """Read a full Claude Code conversation transcript.

    Named `read_conversation_cli` because `claude_web.py` owns `get_conversation`
    (for claude.ai web chats) and skill tool names share a flat namespace.

    Returns one `conversation`-shape dict with a nested `message[]` relation.
    Each message has the shape-native fields (id, author, content, published,
    conversationId, isOutgoing) plus viewer extras (blocks, model, usage,
    kind, parent, isSidechain, isMeta) for rich rendering.

    Args:
        id:      The conversation id (the jsonl stem — a UUID).
        project: Optional project slug. If omitted, the conversation is
                 located by scanning every project directory — fine for
                 single-user machines with a few thousand conversations,
                 slow on huge filesystems. Pass `project` when known.

    The `blocks` field on each message is a list of render-ready blocks
    (text, thinking, tool_use, tool_result, image). Tool calls and their
    results are kept as separate blocks — callers that want them paired
    can walk the list and match by `tool_use_id`. The `content` field
    is the flattened text version of the same blocks, suitable for FTS.

    Large content blocks are capped at 200KB; the cap byte count is reported
    on each block as `dropped` so viewers can indicate truncation.
    """
    if not _PROJECTS_DIR.is_dir():
        raise FileNotFoundError(f"{_PROJECTS_DIR} does not exist")

    target: Path | None = None
    if project:
        cand = _PROJECTS_DIR / project / f"{id}.jsonl"
        if cand.is_file():
            target = cand
    else:
        for pdir in _PROJECTS_DIR.iterdir():
            if not pdir.is_dir():
                continue
            cand = pdir / f"{id}.jsonl"
            if cand.is_file():
                target = cand
                break

    if target is None:
        raise FileNotFoundError(f"conversation {id!r} not found under {_PROJECTS_DIR}")

    return _parse_conversation_full(target)

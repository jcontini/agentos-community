"""Cursor AI editor — sessions, research extraction, and MCP configuration."""

import glob
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from agentos import shell, sql


# ── Paths ─────────────────────────────────────────────────────────────────────

CURSOR_PROJECTS = os.path.expanduser("~/.cursor/projects")
WORKSPACE_STORAGE = os.path.expanduser(
    "~/Library/Application Support/Cursor/User/workspaceStorage"
)
GLOBAL_STATE_DB = os.path.expanduser(
    "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
)
AGENTOS_HOME = os.path.expanduser("~/.agentos")

MCP_CONFIG_PATHS = {
    "cursor": os.path.expanduser("~/.cursor/mcp.json"),
    # Future: "claude-code": os.path.expanduser("~/.claude.json"),
}
MCP_SERVER_NAME = "agentOS"
MCP_SERVER_ARGS = ["mcp"]

# Thresholds for qualifying a Cursor sub-agent result as "research"
_MIN_SEARCHES = 3
_MIN_CHARS = 3000
_MIN_STEPS = 5


# ── Sessions — JSONL transcript source ────────────────────────────────────────


def _find_transcripts():
    pattern = os.path.join(CURSOR_PROJECTS, "*", "agent-transcripts", "*", "*.jsonl")
    results = []
    for path in glob.glob(pattern):
        if "subagents" in path:
            continue
        mtime = os.path.getmtime(path)
        results.append((mtime, path))
    results.sort(key=lambda x: x[0], reverse=True)
    return results


def _extract_user_query(text):
    match = re.search(r"<user_query>\s*(.*?)\s*</user_query>", text, re.DOTALL)
    return match.group(1).strip() if match else None


def _derive_name(first_query, max_len=80):
    if not first_query:
        return "Untitled conversation"
    text = " ".join(first_query.split())
    text = re.sub(r"@\S+", "", text).strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut + "…" if cut else text[:max_len] + "…"


def _build_conversation(uuid, workspace, messages, path=None):
    first_user = next((t for r, t in messages if r == "user"), None)
    last_user = next((t for r, t in reversed(messages) if r == "user"), None)
    user_count = sum(1 for r, _ in messages if r == "user")

    transcript = "\n".join(f"## {r}\n\n{t}\n" for r, t in messages)

    if path:
        mtime = os.path.getmtime(path)
        last_message_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    else:
        last_message_at = datetime.now(tz=timezone.utc).isoformat()

    return {
        "id": uuid,
        "name": _derive_name(first_user),
        "last_message": (" ".join((last_user or "").split()))[:200],
        "last_message_at": last_message_at,
        "message_count": user_count,
        "workspace": workspace,
        "transcript": transcript,
    }


def _parse_jsonl_conversation(path):
    uuid = Path(path).stem
    workspace = (
        path.split("/projects/")[1].split("/agent-transcripts/")[0]
        if "/projects/" in path
        else "unknown"
    )

    messages = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = d.get("role")
            if role not in ("user", "assistant"):
                continue

            text_parts = [
                b["text"]
                for b in d.get("message", {}).get("content", [])
                if b.get("type") == "text"
            ]
            full_text = "\n".join(text_parts)

            if role == "user":
                query = _extract_user_query(full_text)
                if query:
                    messages.append(("user", query))
            elif role == "assistant":
                cleaned = re.sub(r"<[^>]+>", "", full_text).strip()
                if cleaned:
                    messages.append(("assistant", cleaned))

    if not messages:
        return None
    return _build_conversation(uuid, workspace, messages, path=path)


# ── Sessions — SQLite backfill source ─────────────────────────────────────────


def _workspace_path_to_slug(path):
    return path.lstrip("/").replace("/", "-")


def _read_composer_metadata(db_path):
    try:
        rows = sql.query(
            "SELECT value FROM ItemTable WHERE key = 'composer.composerData'",
            db=db_path,
        )
        if not rows:
            return []
        return json.loads(rows[0]["value"]).get("allComposers", [])
    except (json.JSONDecodeError, Exception):
        return []


def _discover_workspaces():
    workspaces = {}
    if not os.path.isdir(WORKSPACE_STORAGE):
        return workspaces

    for entry in os.listdir(WORKSPACE_STORAGE):
        ws_dir = os.path.join(WORKSPACE_STORAGE, entry)
        ws_json = os.path.join(ws_dir, "workspace.json")
        state_db = os.path.join(ws_dir, "state.vscdb")

        if not os.path.isfile(ws_json) or not os.path.isfile(state_db):
            continue

        try:
            with open(ws_json) as f:
                folder = json.load(f).get("folder", "")
            if not folder:
                continue
            workspace_path = folder.replace("file://", "")
        except (json.JSONDecodeError, IOError):
            continue

        composers = _read_composer_metadata(state_db)
        if composers:
            workspaces[workspace_path] = {"db": state_db, "composers": composers}

    return workspaces


def _get_jsonl_conversations():
    conversations = {}
    for _, path in _find_transcripts():
        conv = _parse_jsonl_conversation(path)
        if conv:
            conversations[conv["id"]] = conv
    return conversations


def _get_backfill_conversations(workspace_filter=None, exclude_ids=None):
    workspaces = _discover_workspaces()
    exclude_ids = exclude_ids or set()
    conversations = {}

    to_process = []
    for ws_path, ws_data in workspaces.items():
        if workspace_filter and not ws_path.startswith(workspace_filter):
            continue
        ws_slug = _workspace_path_to_slug(ws_path)
        for composer in ws_data["composers"]:
            cid = composer.get("composerId", "")
            if not cid or cid in exclude_ids or cid.startswith("task-"):
                continue
            if composer.get("isArchived") or composer.get("isDraft"):
                continue
            to_process.append((cid, ws_slug, composer))

    if not to_process or not os.path.isfile(GLOBAL_STATE_DB):
        return conversations

    for cid, ws_slug, composer in to_process:
        try:
            prefix = f"bubbleId:{cid}:"
            end_prefix = prefix[:-1] + chr(ord(":") + 1)
            rows = sql.query(
                "SELECT value FROM cursorDiskKV WHERE key >= :start AND key < :end",
                db=GLOBAL_STATE_DB,
                params={"start": prefix, "end": end_prefix},
            )
        except Exception:
            continue

        if not rows:
            continue

        raw_messages = []
        for row in rows:
            blob_json = row.get("value")
            if not isinstance(blob_json, str):
                continue
            try:
                blob = json.loads(blob_json)
            except (json.JSONDecodeError, TypeError):
                continue
            typ = blob.get("type", 0)
            text = (blob.get("text", "") or "").strip()
            created = blob.get("createdAt", "")
            if text and typ in (1, 2):
                raw_messages.append((created, "user" if typ == 1 else "assistant", text))

        if not raw_messages:
            continue

        raw_messages.sort(key=lambda x: x[0])
        messages = [(role, text) for _, role, text in raw_messages]
        conv = _build_conversation(cid, ws_slug, messages)

        created_ms = composer.get("createdAt", 0)
        if created_ms:
            conv["created_at"] = datetime.fromtimestamp(
                created_ms / 1000, tz=timezone.utc
            ).isoformat()

        updated_ms = composer.get("lastUpdatedAt", 0)
        if updated_ms:
            conv["last_message_at"] = datetime.fromtimestamp(
                updated_ms / 1000, tz=timezone.utc
            ).isoformat()

        if composer.get("name"):
            conv["name"] = composer["name"]

        conversations[cid] = conv

    return conversations


def _get_session_by_id(conv_id):
    pattern = os.path.join(
        CURSOR_PROJECTS, "*", "agent-transcripts", conv_id, f"{conv_id}.jsonl"
    )
    matches = glob.glob(pattern)
    if matches:
        return _parse_jsonl_conversation(matches[0])

    workspaces = _discover_workspaces()
    for ws_path, ws_data in workspaces.items():
        for composer in ws_data["composers"]:
            if composer.get("composerId") == conv_id:
                ws_slug = _workspace_path_to_slug(ws_path)
                # Reconstruct from global blob store
                if not os.path.isfile(GLOBAL_STATE_DB):
                    return None
                try:
                    prefix = f"bubbleId:{conv_id}:"
                    end_prefix = prefix[:-1] + chr(ord(":") + 1)
                    rows = sql.query(
                        "SELECT value FROM cursorDiskKV WHERE key >= :start AND key < :end",
                        db=GLOBAL_STATE_DB,
                        params={"start": prefix, "end": end_prefix},
                    )
                except Exception:
                    return None

                raw_messages = []
                for row in rows:
                    blob_json = row.get("value")
                    if not isinstance(blob_json, str):
                        continue
                    try:
                        blob = json.loads(blob_json)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    typ = blob.get("type", 0)
                    text = (blob.get("text", "") or "").strip()
                    created = blob.get("createdAt", "")
                    if text and typ in (1, 2):
                        raw_messages.append(
                            (created, "user" if typ == 1 else "assistant", text)
                        )

                if not raw_messages:
                    return None
                raw_messages.sort(key=lambda x: x[0])
                return _build_conversation(
                    conv_id, ws_slug, [(r, t) for _, r, t in raw_messages]
                )

    return None


# ── Research extraction ────────────────────────────────────────────────────────


def _sql_query(query_str, db_path, params=None):
    """Wrapper around sql.query for cursor DBs."""
    return sql.query(query_str, db=db_path, params=params or {})


def _parse_task_blob(blob_value):
    if isinstance(blob_value, bytes):
        try:
            blob_value = blob_value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    try:
        data = json.loads(blob_value)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None

    if data.get("role") != "tool":
        return None
    content = data.get("content", [])
    if not content or content[0].get("toolName") != "Task":
        return None

    item = content[0]
    result_text = item.get("result", "")

    po = (
        data.get("providerOptions", {})
        .get("cursor", {})
        .get("highLevelToolCallResult", {})
        .get("output", {})
        .get("success", {})
    )

    steps = po.get("conversationSteps", [])
    searches, urls_fetched, final_text = [], [], ""

    for step in steps:
        tc = step.get("toolCall", {})
        if "webSearchToolCall" in tc:
            term = tc["webSearchToolCall"].get("args", {}).get("searchTerm", "")
            if term:
                searches.append(term)
        elif "webFetchToolCall" in tc:
            url = tc["webFetchToolCall"].get("args", {}).get("url", "")
            if url:
                urls_fetched.append(url)

    for step in reversed(steps):
        if "assistantMessage" in step:
            final_text = step["assistantMessage"].get("text", "")
            break

    clean_result = result_text
    if clean_result.startswith("This is the last output of the subagent:"):
        clean_result = clean_result[len("This is the last output of the subagent:"):].lstrip()

    return {
        "result_text": clean_result,
        "final_text": final_text,
        "agent_id": po.get("agentId"),
        "tool_call_id": item.get("toolCallId", ""),
        "duration_ms": po.get("durationMs"),
        "steps": len(steps),
        "searches": searches,
        "urls_fetched": urls_fetched,
    }


def _build_workspace_map():
    ws_map = {}
    if not os.path.isdir(WORKSPACE_STORAGE):
        return ws_map
    for d in os.listdir(WORKSPACE_STORAGE):
        wj = os.path.join(WORKSPACE_STORAGE, d, "workspace.json")
        if os.path.exists(wj):
            try:
                with open(wj) as f:
                    data = json.load(f)
                folder = data.get("folder", data.get("workspace", ""))
                if folder.startswith("file:///"):
                    from urllib.parse import unquote
                    folder = unquote(folder[7:])
                ws_map[d] = folder
            except (json.JSONDecodeError, IOError):
                pass
    return ws_map


def _build_conversation_index():
    ws_map = _build_workspace_map()
    convos = {}
    for ws_hash, folder in ws_map.items():
        db_path = os.path.join(WORKSPACE_STORAGE, ws_hash, "state.vscdb")
        if not os.path.exists(db_path):
            continue
        try:
            rows = _sql_query(
                "SELECT value FROM ItemTable WHERE key = 'composer.composerData'",
                db_path,
            )
            if not rows:
                continue
            for c in json.loads(rows[0]["value"]).get("allComposers", []):
                cid = c.get("composerId", "")
                convos[cid] = {
                    "name": c.get("name", ""),
                    "workspace": folder,
                    "created_at": c.get("createdAt", 0),
                }
        except (json.JSONDecodeError, Exception):
            pass
    return convos


def _generate_title(parsed, blob_key=""):
    text = parsed["final_text"] or parsed["result_text"]
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line.startswith("## ") and len(line) > 20:
            return line[3:].strip()
    for line in text.split("\n"):
        line = line.strip()
        if len(line) > 30 and not line.startswith("#") and not line.startswith("|"):
            return line[:80]
    return f"Research {blob_key[:16]}"


# ── MCP configuration ──────────────────────────────────────────────────────────


def _find_agentos_binary():
    """Discover the agentos binary via: running engine PID → existing mcp.json → PATH."""
    # 1. Engine PID → lsof
    pid_file = os.path.join(AGENTOS_HOME, "engine.pid")
    if os.path.isfile(pid_file):
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
            result = shell.run("lsof", ["-p", str(pid), "-a", "-d", "txt", "-F", "n"], timeout=5)
            for line in result["stdout"].splitlines():
                if line.startswith("n") and "agentos" in line.lower():
                    path = line[1:]
                    if os.path.isfile(path) and os.access(path, os.X_OK):
                        return path
        except (ValueError, OSError):
            pass

    # 2. Existing Cursor mcp.json
    cursor_mcp = MCP_CONFIG_PATHS.get("cursor", "")
    if os.path.isfile(cursor_mcp):
        try:
            with open(cursor_mcp) as f:
                config = json.load(f)
            cmd = config.get("mcpServers", {}).get(MCP_SERVER_NAME, {}).get("command", "")
            if cmd and os.path.isfile(cmd) and os.access(cmd, os.X_OK):
                return cmd
        except (json.JSONDecodeError, IOError):
            pass

    # 3. PATH
    result = shell.run("which", ["agentos"])
    if result["exit_code"] == 0:
        path = result["stdout"].strip()
        if os.path.isfile(path):
            return path

    return None


def _write_json_atomic(path, data):
    """Write JSON atomically using a temp file + rename."""
    dir_path = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def install_mcp(binary_path=None, client="cursor"):
    """Install agentOS MCP server into a client's config file."""
    config_path = MCP_CONFIG_PATHS.get(client)
    if not config_path:
        raise ValueError(
            f"Unknown client '{client}'. Supported: {list(MCP_CONFIG_PATHS.keys())}"
        )

    if not binary_path:
        binary_path = _find_agentos_binary()
        if not binary_path:
            raise RuntimeError(
                "Could not auto-detect the agentos binary. "
                "Pass binary_path explicitly, e.g. /Users/you/dev/agentos/target/release/agentos"
            )

    if not os.path.isfile(binary_path):
        raise FileNotFoundError(f"Binary not found: {binary_path}")
    if not os.access(binary_path, os.X_OK):
        raise PermissionError(f"Binary not executable: {binary_path}")

    config = {}
    if os.path.isfile(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass  # Start fresh if corrupted

    already_installed = MCP_SERVER_NAME in config.get("mcpServers", {})
    config.setdefault("mcpServers", {})[MCP_SERVER_NAME] = {
        "command": binary_path,
        "args": MCP_SERVER_ARGS,
    }

    _write_json_atomic(config_path, config)

    verb = "Updated" if already_installed else "Installed"
    return {
        "status": "ok",
        "path": binary_path,
        "config": config_path,
        "message": f"{verb} agentOS MCP in {config_path}",
    }


def uninstall_mcp(client="cursor"):
    """Remove agentOS MCP server from a client's config file."""
    config_path = MCP_CONFIG_PATHS.get(client)
    if not config_path:
        raise ValueError(
            f"Unknown client '{client}'. Supported: {list(MCP_CONFIG_PATHS.keys())}"
        )

    if not os.path.isfile(config_path):
        return {
            "status": "ok",
            "message": f"Config not found at {config_path} — nothing to do",
        }

    try:
        with open(config_path) as f:
            config = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise RuntimeError(f"Could not read {config_path}: {e}")

    if MCP_SERVER_NAME not in config.get("mcpServers", {}):
        return {
            "status": "ok",
            "message": f"agentOS not found in {config_path} — nothing to do",
        }

    del config["mcpServers"][MCP_SERVER_NAME]
    _write_json_atomic(config_path, config)

    return {
        "status": "ok",
        "config": config_path,
        "message": f"Removed agentOS MCP from {config_path}",
    }


# ── Operation entry points ─────────────────────────────────────────────────────


def op_list_sessions():
    """List sessions from JSONL transcripts (fast, sub-second)."""
    conversations = _get_jsonl_conversations()
    return sorted(
        conversations.values(),
        key=lambda c: c.get("last_message_at", ""),
        reverse=True,
    )


def op_backfill_session(workspace=None):
    """List sessions including full SQLite history."""
    conversations = _get_jsonl_conversations()
    backfill = _get_backfill_conversations(
        workspace_filter=workspace,
        exclude_ids=set(conversations.keys()),
    )
    conversations.update(backfill)
    return sorted(
        conversations.values(),
        key=lambda c: c.get("last_message_at", ""),
        reverse=True,
    )


def op_get_session(id):
    """Get a session by UUID (checks JSONL then SQLite)."""
    conv = _get_session_by_id(id)
    if not conv:
        raise ValueError(f"No transcript found for {id}")
    return conv


def op_pull_document():
    """Pull sub-agent research blobs from Cursor's global SQLite store."""
    if not os.path.isfile(GLOBAL_STATE_DB):
        return []

    blobs = _sql_query(
        "SELECT key, value FROM cursorDiskKV "
        "WHERE key LIKE 'agentKv:blob:%' "
        "AND CAST(value AS TEXT) LIKE '%\"toolName\":\"Task\"%'",
        GLOBAL_STATE_DB,
    )

    convos = _build_conversation_index()

    items = []
    for row in blobs:
        blob_key = row["key"]
        parsed = _parse_task_blob(row["value"])
        if not parsed:
            continue

        text = parsed["final_text"] or parsed["result_text"]
        if (
            len(parsed["searches"]) < _MIN_SEARCHES
            or len(text) < _MIN_CHARS
            or parsed["steps"] < _MIN_STEPS
        ):
            continue

        blob_hash = blob_key.split(":")[-1]
        date = None
        workspace = ""
        conversation = None

        composer_key = f"task-{parsed['tool_call_id']}" if parsed["tool_call_id"] else ""
        if composer_key and composer_key in convos:
            conversation = convos[composer_key]

        if conversation:
            ts = conversation.get("created_at", 0)
            if ts:
                date = datetime.fromtimestamp(ts / 1000).date().isoformat()
            workspace = conversation.get("workspace", "")

        if not date:
            date = datetime.now().date().isoformat()

        items.append(
            {
                "id": blob_hash,
                "title": _generate_title(parsed, blob_key),
                "content": text,
                "source": "cursor-subagent",
                "date": date,
                "searches": parsed["searches"],
                "urls_fetched": parsed["urls_fetched"],
                "conversation_steps": parsed["steps"],
                "duration_ms": parsed["duration_ms"],
                "agent_id": parsed["agent_id"],
                "workspace": workspace,
                "blob_key": blob_key,
            }
        )

    return items

#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import time
from glob import glob
from pathlib import Path


KITTY_BINARY = "/Applications/kitty.app/Contents/MacOS/kitty"
SOCKET_GLOB = "/tmp/kitty-socket*"


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def read_params() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON params: {exc}")
    if not isinstance(value, dict):
        fail("Expected params object")
    return value


def normalize_socket(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("unix:") or value.startswith("tcp:"):
        return value
    if value.startswith("/"):
        return f"unix:{value}"
    return value


def discover_socket() -> str | None:
    env_socket = normalize_socket(os.environ.get("KITTY_LISTEN_ON"))
    if env_socket:
        return env_socket

    candidates: list[Path] = []
    exact = Path("/tmp/kitty-socket")
    if exact.exists():
        candidates.append(exact)
    for path in glob(SOCKET_GLOB):
        socket_path = Path(path)
        if socket_path.exists():
            candidates.append(socket_path)

    if not candidates:
        return None

    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    return f"unix:{latest}"


def ensure_socket(start_if_missing: bool = False, wait_secs: float = 8.0) -> str | None:
    socket = discover_socket()
    if socket:
        return socket
    if not start_if_missing:
        return None

    if not Path(KITTY_BINARY).exists():
        fail(f"Kitty not found at {KITTY_BINARY}")

    launch_attempts = [
        ["open", "-a", "kitty"],
        [KITTY_BINARY],
    ]
    for command in launch_attempts:
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            break
        except OSError:
            continue
    else:
        fail("Failed to start Kitty")

    deadline = time.time() + wait_secs
    while time.time() < deadline:
        socket = discover_socket()
        if socket:
            return socket
        time.sleep(0.25)

    fail(
        "Kitty did not expose a remote-control socket. "
        "Ensure kitty is installed and configured with allow_remote_control yes."
    )


def kitty_command(socket: str, *args: str) -> str:
    command = [KITTY_BINARY, "@", "--to", socket, *args]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip() or "Kitty command failed"
        fail(message)
    return result.stdout.strip()


def kitty_ls(socket: str) -> list[dict]:
    output = kitty_command(socket, "ls")
    if not output:
        return []
    try:
        value = json.loads(output)
    except json.JSONDecodeError as exc:
        fail(f"Kitty ls returned invalid JSON: {exc}")
    if not isinstance(value, list):
        fail("Kitty ls did not return a list")
    return value


def find_tab(ls_data: list[dict], tab_id: int) -> dict | None:
    for os_window in ls_data:
        for tab in os_window.get("tabs", []):
            if tab.get("id") == tab_id:
                return tab
    return None


def find_window(ls_data: list[dict], window_id: int) -> dict | None:
    for os_window in ls_data:
        for tab in os_window.get("tabs", []):
            for window in tab.get("windows", []):
                if window.get("id") == window_id:
                    return window
    return None


def find_tab_and_os_window_for_window(ls_data: list[dict], window_id: int) -> tuple[dict | None, dict | None]:
    for os_window in ls_data:
        for tab in os_window.get("tabs", []):
            for window in tab.get("windows", []):
                if window.get("id") == window_id:
                    return tab, os_window
    return None, None


def find_os_window(ls_data: list[dict], os_window_id: int) -> dict | None:
    for os_window in ls_data:
        if os_window.get("id") == os_window_id:
            return os_window
    return None


def active_window(tab: dict) -> dict | None:
    windows = tab.get("windows", [])
    for window in windows:
        if window.get("is_active"):
            return window
    return windows[0] if windows else None


def normalize_os_window(os_window: dict) -> dict:
    tabs = os_window.get("tabs", [])
    focused_tab = next((tab for tab in tabs if tab.get("is_focused")), None)
    active_tab = next((tab for tab in tabs if tab.get("is_active")), None)
    title_tab = focused_tab or active_tab or (tabs[0] if tabs else None)
    return {
        "os_window_id": os_window.get("id"),
        "platform_window_id": os_window.get("platform_window_id"),
        "title": title_tab.get("title") if title_tab else None,
        "is_active": bool(os_window.get("is_active")),
        "is_focused": bool(os_window.get("is_focused")),
        "tab_count": len(tabs),
        "tabs": [tab.get("id") for tab in tabs],
        "active_tab_id": active_tab.get("id") if active_tab else None,
        "focused_tab_id": focused_tab.get("id") if focused_tab else None,
    }


def normalize_tab(os_window: dict, tab: dict) -> dict:
    windows = tab.get("windows", [])
    active = active_window(tab)
    return {
        "tab_id": tab.get("id"),
        "os_window_id": os_window.get("id"),
        "title": tab.get("title"),
        "layout": tab.get("layout"),
        "is_active": bool(tab.get("is_active")),
        "is_focused": bool(tab.get("is_focused")),
        "window_count": len(windows),
        "window_ids": [window.get("id") for window in windows],
        "active_window_id": active.get("id") if active else None,
    }


def normalize_window(os_window: dict, tab: dict, window: dict) -> dict:
    foreground = window.get("foreground_processes") or []
    process = foreground[-1] if foreground else {}
    cmdline = process.get("cmdline") or window.get("cmdline") or []
    cwd = process.get("cwd") or window.get("cwd")
    return {
        "window_id": window.get("id"),
        "tab_id": tab.get("id"),
        "os_window_id": os_window.get("id"),
        "title": window.get("title"),
        "cwd": cwd,
        "pid": window.get("pid"),
        "is_active": bool(window.get("is_active")),
        "is_focused": bool(window.get("is_focused")),
        "at_prompt": bool(window.get("at_prompt")),
        "lines": window.get("lines"),
        "columns": window.get("columns"),
        "last_cmd_exit_status": window.get("last_cmd_exit_status"),
        "command": " ".join(cmdline) if isinstance(cmdline, list) else str(cmdline),
        "cmdline": cmdline,
    }


def require_int(params: dict, name: str) -> int:
    value = params.get(name)
    if value is None:
        fail(f"Missing required param: {name}")
    if isinstance(value, bool):
        fail(f"Param {name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    fail(f"Param {name} must be an integer")


def command_list_os_windows(params: dict) -> list[dict]:
    socket = normalize_socket(params.get("socket")) or ensure_socket(False)
    if not socket:
        return []
    return [normalize_os_window(os_window) for os_window in kitty_ls(socket)]


def command_list_tabs(params: dict) -> list[dict]:
    socket = normalize_socket(params.get("socket")) or ensure_socket(False)
    if not socket:
        return []
    os_window_filter = params.get("os_window_id")
    results: list[dict] = []
    for os_window in kitty_ls(socket):
        if os_window_filter is not None and os_window.get("id") != os_window_filter:
            continue
        for tab in os_window.get("tabs", []):
            results.append(normalize_tab(os_window, tab))
    return results


def command_list_panes(params: dict) -> list[dict]:
    socket = normalize_socket(params.get("socket")) or ensure_socket(False)
    if not socket:
        return []
    os_window_filter = params.get("os_window_id")
    tab_filter = params.get("tab_id")
    results: list[dict] = []
    for os_window in kitty_ls(socket):
        if os_window_filter is not None and os_window.get("id") != os_window_filter:
            continue
        for tab in os_window.get("tabs", []):
            if tab_filter is not None and tab.get("id") != tab_filter:
                continue
            for window in tab.get("windows", []):
                results.append(normalize_window(os_window, tab, window))
    return results


def command_launch_tab(params: dict) -> dict:
    socket = normalize_socket(params.get("socket")) or ensure_socket(True)
    args = ["launch", "--type=tab"]
    title = params.get("title")
    cwd = params.get("cwd")
    keep_focus = bool(params.get("keep_focus"))
    command = params.get("command")

    if title:
        args.extend(["--tab-title", str(title)])
    if cwd:
        args.extend(["--cwd", str(cwd)])
    if keep_focus:
        args.append("--keep-focus")
    if command:
        args.extend(["/bin/zsh", "-lc", str(command)])

    output = kitty_command(socket, *args)
    try:
        window_id = int(output)
    except ValueError:
        fail(f"Unexpected kitty launch response: {output}")

    ls_data = kitty_ls(socket)
    tab, os_window = find_tab_and_os_window_for_window(ls_data, window_id)
    if not tab or not os_window:
        fail("Launched Kitty tab but could not resolve its tab/window metadata")

    return {
        "socket": socket,
        "os_window_id": os_window.get("id"),
        "tab_id": tab.get("id"),
        "window_id": window_id,
        "title": tab.get("title"),
    }


def command_focus_tab(params: dict) -> dict:
    socket = normalize_socket(params.get("socket")) or ensure_socket(False)
    if not socket:
        fail("Kitty is not running")

    tab_id = require_int(params, "tab_id")
    ls_data = kitty_ls(socket)
    tab = find_tab(ls_data, tab_id)
    if not tab:
        fail(f"No Kitty tab found with id {tab_id}")

    kitty_command(socket, "focus-tab", "--match", f"id:{tab_id}")
    return {"ok": True, "socket": socket, "tab_id": tab_id}


def command_focus_os_window(params: dict) -> dict:
    socket = normalize_socket(params.get("socket")) or ensure_socket(False)
    if not socket:
        fail("Kitty is not running")

    os_window_id = require_int(params, "os_window_id")
    ls_data = kitty_ls(socket)
    os_window = find_os_window(ls_data, os_window_id)
    if not os_window:
        fail(f"No Kitty OS window found with id {os_window_id}")

    target_tab = next((tab for tab in os_window.get("tabs", []) if tab.get("is_active")), None)
    target_tab = target_tab or (os_window.get("tabs", [None])[0])
    if not target_tab:
        fail(f"Kitty OS window {os_window_id} has no tabs")

    target_window = active_window(target_tab)
    if not target_window:
        fail(f"Kitty OS window {os_window_id} has no windows")

    window_id = target_window.get("id")
    kitty_command(socket, "focus-window", "--match", f"id:{window_id}")
    return {
        "ok": True,
        "socket": socket,
        "os_window_id": os_window_id,
        "window_id": window_id,
        "tab_id": target_tab.get("id"),
    }


def command_send_text(params: dict) -> dict:
    socket = normalize_socket(params.get("socket")) or ensure_socket(False)
    if not socket:
        fail("Kitty is not running")

    text = params.get("text")
    if text is None:
        fail("Missing required param: text")
    text = str(text)
    if params.get("press_enter"):
        text += "\r"

    args = ["send-text"]
    tab_id = params.get("tab_id")
    window_id = params.get("window_id")

    if tab_id is not None and window_id is not None:
        fail("Provide either tab_id or window_id, not both")

    ls_data = kitty_ls(socket)
    if window_id is not None:
        window_id = require_int(params, "window_id")
        if not find_window(ls_data, window_id):
            fail(f"No Kitty window found with id {window_id}")
        args.extend(["--match", f"id:{window_id}"])
    elif tab_id is not None:
        tab_id = require_int(params, "tab_id")
        if not find_tab(ls_data, tab_id):
            fail(f"No Kitty tab found with id {tab_id}")
        args.extend(["--match-tab", f"id:{tab_id}"])

    args.append(text)
    kitty_command(socket, *args)
    return {
        "ok": True,
        "socket": socket,
        "tab_id": tab_id,
        "window_id": window_id,
    }


def command_get_text(params: dict) -> dict:
    socket = normalize_socket(params.get("socket")) or ensure_socket(False)
    if not socket:
        fail("Kitty is not running")

    args = ["get-text"]
    extent = str(params.get("extent") or "screen")
    args.extend(["--extent", extent])
    if params.get("ansi"):
        args.append("--ansi")

    window_id = params.get("window_id")
    if window_id is not None:
        window_id = require_int(params, "window_id")
        if not find_window(kitty_ls(socket), window_id):
            fail(f"No Kitty window found with id {window_id}")
        args.extend(["--match", f"id:{window_id}"])

    text = kitty_command(socket, *args)
    return {
        "socket": socket,
        "window_id": window_id,
        "extent": extent,
        "text": text,
    }


def command_close_tab(params: dict) -> dict:
    socket = normalize_socket(params.get("socket")) or ensure_socket(False)
    if not socket:
        fail("Kitty is not running")

    tab_id = require_int(params, "tab_id")
    if not find_tab(kitty_ls(socket), tab_id):
        fail(f"No Kitty tab found with id {tab_id}")

    kitty_command(socket, "close-tab", "--match", f"id:{tab_id}", "--ignore-no-match")
    return {"ok": True, "socket": socket, "tab_id": tab_id}


COMMANDS = {
    "list_os_windows": command_list_os_windows,
    "list_tabs": command_list_tabs,
    "list_panes": command_list_panes,
    "launch_tab": command_launch_tab,
    "focus_tab": command_focus_tab,
    "focus_os_window": command_focus_os_window,
    "send_text": command_send_text,
    "get_text": command_get_text,
    "close_tab": command_close_tab,
}


def main() -> None:
    if len(sys.argv) < 2:
        fail("Usage: kitty-control.py <operation>")

    operation = sys.argv[1]
    handler = COMMANDS.get(operation)
    if not handler:
        fail(f"Unknown operation: {operation}")

    params = read_params()
    result = handler(params)
    print(json.dumps(result))


if __name__ == "__main__":
    main()

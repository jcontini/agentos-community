#!/usr/bin/env python3

import base64
import grp
import json
import math
import mimetypes
import os
import pwd
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from agentos import shell, provides, returns, timeout, file_info, file_list, file_read


APP_SYSTEM_PROFILER_SWIFT = r"""
import Foundation
import AppKit

func rectDict(_ rect: NSRect) -> [String: Double] {
    [
        "x": Double(rect.origin.x),
        "y": Double(rect.origin.y),
        "width": Double(rect.size.width),
        "height": Double(rect.size.height)
    ]
}

let screens = NSScreen.screens
let mainId = CGMainDisplayID()
let result = screens.enumerated().map { (index, screen) -> [String: Any] in
    let number = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber
    let displayId = UInt32(number?.uint32Value ?? 0)
    return [
        "displayId": String(displayId),
        "displayIndex": index + 1,
        "isPrimary": displayId == mainId,
        "scale": Double(screen.backingScaleFactor),
        "frame": rectDict(screen.frame),
        "visibleFrame": rectDict(screen.visibleFrame)
    ]
}

let data = try JSONSerialization.data(withJSONObject: result, options: [])
FileHandle.standardOutput.write(data)
"""


CG_WINDOWS_SWIFT = r"""
import Foundation
import CoreGraphics

let list = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]] ?? []
let result = list.map { info -> [String: Any] in
    [
        "windowId": info[kCGWindowNumber as String] ?? 0,
        "ownerName": info[kCGWindowOwnerName as String] ?? "",
        "ownerPid": info[kCGWindowOwnerPID as String] ?? 0,
        "title": info[kCGWindowName as String] ?? "",
        "layer": info[kCGWindowLayer as String] ?? 0,
        "alpha": info[kCGWindowAlpha as String] ?? 0,
        "bounds": info[kCGWindowBounds as String] ?? [:],
        "memoryBytes": info[kCGWindowMemoryUsage as String] ?? 0,
        "sharingState": info[kCGWindowSharingState as String] ?? 0,
        "isOnscreen": info[kCGWindowIsOnscreen as String] ?? false
    ]
}

let data = try JSONSerialization.data(withJSONObject: result, options: [])
FileHandle.standardOutput.write(data)
"""


JXA_WINDOWS_SCRIPT = r"""
function safe(fn) {
  try { return fn(); } catch (error) { return null; }
}

function attr(windowRef, name) {
  try {
    return windowRef.attributes.byName(name).value();
  } catch (error) {
    return null;
  }
}

const systemEvents = Application("System Events");
systemEvents.includeStandardAdditions = true;

const result = systemEvents.applicationProcesses
  .whose({ backgroundOnly: false })()
  .map((app) => ({
    app_name: safe(() => app.name()),
    pid: safe(() => app.unixId()),
    frontmost: safe(() => app.frontmost()),
    hidden: (() => {
      const visible = safe(() => app.visible());
      return visible === null ? null : !visible;
    })(),
    windows: app.windows().map((windowRef, index) => ({
      window_index: index,
      title: safe(() => windowRef.name()),
      position: safe(() => windowRef.position()),
      size: safe(() => windowRef.size()),
      minimized: attr(windowRef, "AXMinimized"),
      fullscreen: attr(windowRef, "AXFullScreen"),
      is_main: attr(windowRef, "AXMain"),
      is_focused: attr(windowRef, "AXFocused"),
      role_description: safe(() => windowRef.roleDescription()),
      subrole: safe(() => windowRef.subrole())
    }))
  }));

JSON.stringify(result);
"""


def _read_params() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    value = json.loads(raw)
    return value if isinstance(value, dict) else {}


def _run_json_command(args, input_text=None):
    result = shell.run(args[0], args[1:], input=input_text)
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"].strip() or f"Command failed: {args[0]}")
    stdout = result["stdout"].strip()
    return json.loads(stdout) if stdout else None


def _run_text_command(args):
    result = shell.run(args[0], args[1:])
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"].strip() or f"Command failed: {args[0]}")
    return result["stdout"]


def _run_swift_json(script: str):
    return _run_json_command(["swift", "-e", script])


def _run_jxa_json(script: str):
    return _run_json_command(["osascript", "-l", "JavaScript", "-e", script])


def _load_display_names():
    data = _run_json_command(["system_profiler", "SPDisplaysDataType", "-json"])
    names = {}
    for gpu in data.get("SPDisplaysDataType", []):
        for display in gpu.get("spdisplays_ndrvs", []):
            display_id = display.get("_spdisplays_displayID")
            if display_id is None:
                continue
            names[str(display_id)] = {
                "name": display.get("_name"),
                "resolution": display.get("spdisplays_resolution"),
                "pixels": display.get("_spdisplays_pixels"),
                "isPrimary": display.get("spdisplays_main") == "spdisplays_yes",
                "refreshRate": display.get("_spdisplays_resolution"),
            }
    return names


def _load_displays():
    displays = _run_swift_json(APP_SYSTEM_PROFILER_SWIFT)
    metadata = _load_display_names()
    primary = next((display for display in displays if display.get("is_primary")), None)
    primary_center_x = _frame_center_x(primary["frame"]) if primary else None
    primary_center_y = _frame_center_y(primary["frame"]) if primary else None

    normalized = []
    for display in displays:
        display_id = str(display["display_id"])
        extra = metadata.get(display_id, {})
        frame = _normalize_frame(display["frame"])
        visible_frame = _normalize_frame(display["visible_frame"])
        is_primary = bool(display.get("is_primary") or extra.get("is_primary"))
        result = {
            "displayId": display_id,
            "displayIndex": int(display["display_index"]),
            "name": extra.get("name") or f"Display {display_id}",
            "isPrimary": is_primary,
            "scale": float(display.get("scale", 1.0)),
            "frame": frame,
            "visibleFrame": visible_frame,
            "width": frame["width"],
            "height": frame["height"],
            "originX": frame["x"],
            "originY": frame["y"],
            "resolution": extra.get("resolution"),
            "pixels": extra.get("pixels"),
        }
        result["position_relative_to_primary"] = _relative_position(
            result,
            primary_center_x,
            primary_center_y,
            is_primary,
        )
        normalized.append(result)

    normalized.sort(key=lambda display: display["display_index"])
    return normalized


@returns({"displays": "{'type': 'array', 'description': 'Connected displays'}", "count": "integer"})
@timeout(15)
def list_displays(**params):
    """List connected displays with geometry for left/right monitor reasoning"""
    displays = _load_displays()
    return {
        "displays": displays,
        "count": len(displays),
    }


@returns({"apps": "{'type': 'array', 'description': 'Installed applications'}", "count": "integer"})
@timeout(60)
def list_apps(*, limit=None, **params):
    """List installed macOS applications using system_profiler

        Args:
            limit: Optional maximum number of apps to return
        """
    data = _run_json_command(["system_profiler", "SPApplicationsDataType", "-json"])
    apps = []
    for item in data.get("SPApplicationsDataType", []):
        path = item.get("path")
        name = item.get("_name") or (Path(path).stem if path else None)
        apps.append(
            {
                "name": name,
                "path": path,
                "version": item.get("version"),
                "obtainedFrom": item.get("obtained_from"),
                "lastModified": item.get("lastModified"),
                "arch": item.get("arch_kind"),
                "signedBy": item.get("signed_by") or [],
            }
        )

    apps.sort(key=lambda app: ((app.get("name") or "").lower(), app.get("path") or ""))
    normalized_limit = _normalize_limit(limit)
    if normalized_limit is not None:
        apps = apps[:normalized_limit]
    return {
        "apps": apps,
        "count": len(apps),
    }


@returns({"processes": "{'type': 'array', 'description': 'Running processes'}", "count": "integer"})
@timeout(15)
def list_processes(*, limit=None, **params):
    """List running macOS processes with stable fields from ps

        Args:
            limit: Optional maximum number of processes to return
        """
    output = _run_text_command(
        [
            "ps",
            "-axo",
            "pid=,ppid=,user=,%cpu=,%mem=,rss=,state=,lstart=,comm=",
        ]
    )
    processes = []
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        parts = line.split(None, 12)
        if len(parts) < 13:
            continue
        pid, ppid, user, cpu, mem, rss, state = parts[:7]
        started_at = " ".join(parts[7:12])
        command = parts[12]
        processes.append(
            {
                "pid": int(pid),
                "ppid": int(ppid),
                "user": user,
                "cpuPercent": float(cpu),
                "memoryPercent": float(mem),
                "rssKb": int(rss),
                "rssBytes": int(rss) * 1024,
                "state": state,
                "startedAt": started_at,
                "command": command,
                "name": os.path.basename(command),
            }
        )

    processes.sort(key=lambda process: process["pid"])
    normalized_limit = _normalize_limit(limit)
    if normalized_limit is not None:
        processes = processes[:normalized_limit]
    return {
        "processes": processes,
        "count": len(processes),
    }


@returns({"windows": "{'type': 'array', 'description': 'User-facing application windows'}", "count": "integer"})
def list_windows(*, limit=None, **params):
    """List useful user-facing application windows with capture eligibility

        Args:
            limit: Optional maximum number of windows to return
        """
    displays = _load_displays()
    cg_windows = _run_swift_json(CG_WINDOWS_SWIFT)
    jxa_apps = _run_jxa_json(JXA_WINDOWS_SCRIPT)

    normalized = []
    for app in jxa_apps:
        app_name = app.get("app_name")
        pid = app.get("pid")
        frontmost = bool(app.get("frontmost"))
        hidden = bool(app.get("hidden"))
        for window in app.get("windows", []):
            position = window.get("position")
            size = window.get("size")
            if not _is_useful_window(app_name, position, size):
                continue

            frame = {
                "x": int(position[0]),
                "y": int(position[1]),
                "width": int(size[0]),
                "height": int(size[1]),
            }
            matched = _match_cg_window(
                app_name=app_name,
                pid=pid,
                title=window.get("title") or "",
                frame=frame,
                cg_windows=cg_windows,
            )
            display_id = _display_for_frame(frame, displays)
            normalized.append(
                {
                    "windowId": matched.get("window_id") if matched else None,
                    "appName": app_name,
                    "pid": pid,
                    "title": window.get("title") or "",
                    "frame": frame,
                    "displayId": display_id,
                    "isMinimized": bool(window.get("minimized")),
                    "isFullscreen": bool(window.get("fullscreen")),
                    "isMain": bool(window.get("is_main")),
                    "isFocused": bool(window.get("is_focused")),
                    "isHidden": hidden,
                    "isFrontmostApp": frontmost,
                    "roleDescription": window.get("role_description"),
                    "subrole": window.get("subrole"),
                    "captureEligible": bool(
                        matched
                        and matched.get("is_onscreen")
                        and matched.get("sharing_state", 0) != 0
                        and not hidden
                        and not window.get("minimized")
                    ),
                    "cgWindowName": matched.get("title") if matched else None,
                }
            )

    normalized.sort(
        key=lambda window: (
            not window["is_frontmost_app"],
            not window["is_main"],
            not window["is_focused"],
            (window["app_name"] or "").lower(),
            (window["title"] or "").lower(),
            window["pid"] or 0,
        )
    )
    normalized_limit = _normalize_limit(limit)
    if normalized_limit is not None:
        normalized = normalized[:normalized_limit]
    return {
        "windows": normalized,
        "count": len(normalized),
    }


@returns("image")
@timeout(20)
def screenshot_display(*, display_id=None, display_index=None, path=None, **params):
    """Capture a screenshot of a display by display_id or display_index

        Args:
            display_id: Display ID from list_displays
            display_index: 1-based display index from list_displays
            path: Optional output path for the PNG file
        """
    displays = _load_displays()
    target = None

    if display_index is not None:
        target = next(
            (display for display in displays if display["display_index"] == int(display_index)),
            None,
        )
    elif display_id is not None:
        target = next(
            (display for display in displays if display["display_id"] == str(display_id)),
            None,
        )
    else:
        target = next((display for display in displays if display["is_primary"]), None)

    if not target:
        raise ValueError("Display not found")

    resolved_path = _resolve_output_path(path, f"display-{target['display_id']}")
    result = shell.run("screencapture", ["-x", "-D", str(target["display_index"]), resolved_path])
    if result["exit_code"] != 0:
        raise RuntimeError(f"screencapture failed: {result['stderr'].strip()}")
    return {
        "name": f"Display {target['display_id']} screenshot",
        "filename": resolved_path.rsplit("/", 1)[-1],
        "path": resolved_path,
        "format": "PNG",
        "mimeType": "image/png",
        "width": target.get("width"),
        "height": target.get("height"),
        "displayId": target["display_id"],
        "displayIndex": target["display_index"],
        "published": _iso_now(),
    }


@returns("image")
@timeout(20)
def screenshot_window(*, window_id, path=None, **params):
    """Capture a screenshot of a specific application window by window_id

        Args:
            window_id: Window ID from list_windows
            path: Optional output path for the PNG file
        """
    target_window_id = int(window_id)
    windows = list_windows().get("windows", [])
    target = next((window for window in windows if window.get("window_id") == target_window_id), None)
    if not target:
        raise ValueError("Window not found")
    if not target.get("capture_eligible"):
        raise ValueError("Window is not capture_eligible")

    resolved_path = _resolve_output_path(path, f"window-{target_window_id}")
    result = shell.run("screencapture", ["-x", "-l", str(target_window_id), resolved_path])
    if result["exit_code"] != 0:
        raise RuntimeError(f"screencapture failed: {result['stderr'].strip()}")
    frame = target.get("frame", {})
    return {
        "name": f"{target.get('app_name', 'Window')} — {target.get('title', '')}",
        "filename": resolved_path.rsplit("/", 1)[-1],
        "path": resolved_path,
        "format": "PNG",
        "mimeType": "image/png",
        "width": frame.get("width"),
        "height": frame.get("height"),
        "windowId": target_window_id,
        "appName": target.get("app_name"),
        "published": _iso_now(),
    }


def _normalize_limit(value):
    if value is None:
        return None
    limit = int(value)
    return max(limit, 0)


def _normalize_frame(frame):
    return {
        "x": int(round(float(frame["x"]))),
        "y": int(round(float(frame["y"]))),
        "width": int(round(float(frame["width"]))),
        "height": int(round(float(frame["height"]))),
    }


def _frame_center_x(frame):
    return frame["x"] + (frame["width"] / 2.0)


def _frame_center_y(frame):
    return frame["y"] + (frame["height"] / 2.0)


def _relative_position(display, primary_center_x, primary_center_y, is_primary):
    if is_primary or primary_center_x is None or primary_center_y is None:
        return "primary" if is_primary else None

    dx = _frame_center_x(display["frame"]) - primary_center_x
    dy = _frame_center_y(display["frame"]) - primary_center_y
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "above" if dy > 0 else "below"


def _is_useful_window(app_name, position, size):
    if not isinstance(position, list) or not isinstance(size, list):
        return False
    if len(position) != 2 or len(size) != 2:
        return False
    width = int(size[0])
    height = int(size[1])
    if width < 80 or height < 60:
        return False
    if app_name in {"Control Center", "Dock", "Window Server", "Notification Center"}:
        return False
    return True


def _match_cg_window(app_name, pid, title, frame, cg_windows):
    title_normalized = _normalize_title(title)
    candidates = [
        window
        for window in cg_windows
        if int(window.get("owner_pid", -1)) == int(pid)
        and int(window.get("layer", 0)) == 0
    ]
    best = None
    best_score = -math.inf
    for candidate in candidates:
        score = 0.0
        candidate_title = _normalize_title(candidate.get("title") or "")
        bounds = _normalize_cg_bounds(candidate.get("bounds") or {})
        if candidate.get("owner_name") == app_name:
            score += 20
        if title_normalized and candidate_title == title_normalized:
            score += 50
        elif title_normalized and candidate_title and _titles_related(title_normalized, candidate_title):
            score += 35
        elif title_normalized and candidate_title:
            score -= 20
        score -= _bounds_distance(frame, bounds) / 10.0
        if candidate.get("is_onscreen"):
            score += 5
        if score > best_score:
            best_score = score
            best = {
                "windowId": int(candidate["window_id"]),
                "title": candidate.get("title") or "",
                "isOnscreen": bool(candidate.get("is_onscreen")),
                "sharingState": int(candidate.get("sharing_state", 0)),
            }

    if best_score < 10:
        return None
    return best


def _normalize_cg_bounds(bounds):
    return {
        "x": int(round(float(bounds.get("X", 0)))),
        "y": int(round(float(bounds.get("Y", 0)))),
        "width": int(round(float(bounds.get("Width", 0)))),
        "height": int(round(float(bounds.get("Height", 0)))),
    }


def _bounds_distance(left, right):
    return (
        abs(left["x"] - right["x"])
        + abs(left["y"] - right["y"])
        + abs(left["width"] - right["width"])
        + abs(left["height"] - right["height"])
    )


def _normalize_title(value):
    return " ".join((value or "").split())


def _titles_related(left, right):
    return left in right or right in left


def _display_for_frame(frame, displays):
    best_display_id = None
    best_overlap = -1
    for display in displays:
        overlap = _intersection_area(frame, display["frame"])
        if overlap > best_overlap:
            best_overlap = overlap
            best_display_id = display["display_id"]
    return best_display_id


def _intersection_area(a, b):
    x1 = max(a["x"], b["x"])
    y1 = max(a["y"], b["y"])
    x2 = min(a["x"] + a["width"], b["x"] + b["width"])
    y2 = min(a["y"] + a["height"], b["y"] + b["height"])
    if x2 <= x1 or y2 <= y1:
        return 0
    return (x2 - x1) * (y2 - y1)


def _resolve_output_path(value, label):
    if value:
        return os.path.abspath(os.path.expanduser(str(value)))
    timestamp = int(time.time())
    return f"/tmp/macos-control-{label}-{timestamp}.png"


@returns({"text": "string"})
@timeout(5)
def clipboard_read(**_kwargs):
    """Read the current macOS clipboard contents."""
    result = shell.run("pbpaste", [])
    return {"content": result["stdout"]}


@returns({"status": "string", "length": "integer"})
@timeout(5)
def clipboard_write(*, text, **_kwargs):
    """Write text to the macOS clipboard."""
    result = shell.run("pbcopy", [], input=text)
    if result["exit_code"] != 0:
        raise RuntimeError(f"pbcopy failed: {result['stderr'].strip()}")
    return {"status": "ok", "length": len(text)}


def _iso_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Filesystem operations
# ---------------------------------------------------------------------------

TEXT_EXTENSIONS = {
    ".md", ".mdx", ".txt", ".csv", ".log", ".json", ".yaml", ".yml", ".toml",
    ".py", ".rs", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".htm",
    ".sh", ".bash", ".zsh", ".sql", ".xml", ".ini", ".cfg", ".conf",
    ".env", ".gitignore", ".dockerignore", ".editorconfig",
}

MAX_TEXT_BYTES = 1024 * 1024       # 1 MB
MAX_BINARY_BYTES = 10 * 1024 * 1024  # 10 MB


def _stat_to_iso(ts):
    """Convert a stat timestamp to ISO 8601."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _mime_for_path(path):
    """Guess MIME type from file extension."""
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def _is_text_file(path):
    """Check if a file is likely text based on extension."""
    return Path(path).suffix.lower() in TEXT_EXTENSIONS


def _format_size(size_bytes):
    """Human-readable file size."""
    if size_bytes is None:
        return None
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def _entry_from_direntry(entry):
    """Build a shape-compatible dict from an os.DirEntry."""
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return None

    is_dir = entry.is_dir(follow_symlinks=True)
    is_symlink = entry.is_symlink()

    result = {
        "name": entry.name,
        "tags": "folder" if is_dir else "file",
        "kind": "dir" if is_dir else ("symlink" if is_symlink else "file"),
        "path": entry.path,
        "size": st.st_size if not is_dir else None,
        "modified": _stat_to_iso(st.st_mtime),
    }

    if not is_dir:
        result["mime_type"] = _mime_for_path(entry.name)
        ext = Path(entry.name).suffix.lower()
        if ext:
            result["format"] = ext.lstrip(".").upper()

    return result


SORT_KEYS = {
    "name": lambda e: (e["kind"] != "dir", e["name"].lower()),
    "size": lambda e: (e["kind"] != "dir", -(e["size"] or 0), e["name"].lower()),
    "modified": lambda e: (e["kind"] != "dir", e["modified"] or "", e["name"].lower()),
    "kind": lambda e: (e["kind"], e["name"].lower()),
}


@returns({"path": "string", "entries": "{'type': 'array', 'description': 'File and folder entries with shape-compatible fields'}", "count": "integer"})
@provides(file_list)
@timeout(10)
def list_directory(*, path=None, show_hidden=False, sort=None, **_kwargs):
    """List contents of a directory. Returns file and folder shapes."""
    resolved = os.path.expanduser(path or "~")
    resolved = os.path.abspath(resolved)

    if not os.path.isdir(resolved):
        raise ValueError(f"Not a directory: {resolved}")

    entries = []
    with os.scandir(resolved) as scanner:
        for entry in scanner:
            if not show_hidden and entry.name.startswith("."):
                continue
            item = _entry_from_direntry(entry)
            if item:
                entries.append(item)

    sort_fn = SORT_KEYS.get(sort or "name", SORT_KEYS["name"])
    entries.sort(key=sort_fn)

    return {
        "path": resolved,
        "entries": entries,
        "count": len(entries),
    }


@returns({"name": "string", "path": "string", "content": "string", "encoding": "string", "mimeType": "string", "size": "integer"})
@provides(file_read)
@timeout(10)
def read_file(*, path, **_kwargs):
    """Read file contents. Text as UTF-8 string, binary as base64."""
    resolved = os.path.expanduser(path)
    resolved = os.path.abspath(resolved)

    if not os.path.isfile(resolved):
        raise ValueError(f"Not a file: {resolved}")

    file_size = os.path.getsize(resolved)
    is_text = _is_text_file(resolved)

    if is_text and file_size > MAX_TEXT_BYTES:
        raise ValueError(f"File too large for text read: {_format_size(file_size)} (max {_format_size(MAX_TEXT_BYTES)})")
    if not is_text and file_size > MAX_BINARY_BYTES:
        raise ValueError(f"File too large for binary read: {_format_size(file_size)} (max {_format_size(MAX_BINARY_BYTES)})")

    if is_text:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        encoding = "utf-8"
    else:
        with open(resolved, "rb") as f:
            content = base64.b64encode(f.read()).decode("ascii")
        encoding = "base64"

    return {
        "name": os.path.basename(resolved),
        "path": resolved,
        "content": content,
        "encoding": encoding,
        "mimeType": _mime_for_path(resolved),
        "size": file_size,
    }


def _get_volumes():
    """Get mounted volumes via diskutil."""
    try:
        result = shell.run("diskutil", ["list", "-plist"])
        if result["exit_code"] != 0:
            return _get_volumes_fallback()

        import plistlib
        data = plistlib.loads(result["stdout"].encode("utf-8"))
        disk_ids = data.get("AllDisksAndPartitions", [])

        volumes = []
        for disk in disk_ids:
            # Check partitions within each disk
            for part in disk.get("Partitions", []) + disk.get("APFSVolumes", []):
                mount_point = part.get("MountPoint")
                if not mount_point:
                    continue
                vol_name = part.get("VolumeName") or os.path.basename(mount_point) or "Untitled"
                size = part.get("Size", 0)

                # Get free space from statvfs
                try:
                    sv = os.statvfs(mount_point)
                    free_bytes = sv.f_bavail * sv.f_frsize
                    total_bytes = sv.f_blocks * sv.f_frsize
                except OSError:
                    free_bytes = 0
                    total_bytes = size

                fs_type = part.get("FilesystemType") or part.get("Content", "")

                volumes.append({
                    "name": vol_name,
                    "tags": "volume",
                    "path": mount_point,
                    "totalBytes": total_bytes,
                    "freeBytes": free_bytes,
                    "usedBytes": total_bytes - free_bytes,
                    "filesystem": fs_type.lower() if fs_type else None,
                    "volumeType": "internal" if not mount_point.startswith("/Volumes/") else "external",
                    "removable": mount_point.startswith("/Volumes/"),
                    "readOnly": False,
                })

        # Filter out macOS system volumes that users never interact with
        SYSTEM_VOLUME_PREFIXES = ("/System/Volumes/",)
        SYSTEM_VOLUME_NAMES = {"Preboot", "Update", "VM", "Data", "xART", "Hardware", "iSCPreboot"}
        user_volumes = []
        for v in volumes:
            path = v["path"]
            name = v["name"]
            # Keep root and /Volumes/* mounts, skip system internals
            if any(path.startswith(p) for p in SYSTEM_VOLUME_PREFIXES):
                continue
            if name in SYSTEM_VOLUME_NAMES:
                continue
            user_volumes.append(v)

        # Deduplicate by mount point (keep first)
        seen = set()
        unique = []
        for v in user_volumes:
            if v["path"] not in seen:
                seen.add(v["path"])
                unique.append(v)

        return unique if unique else _get_volumes_fallback()
    except Exception:
        return _get_volumes_fallback()


def _get_volumes_fallback():
    """Fallback volume detection using statvfs."""
    volumes = []
    # Always include root
    try:
        sv = os.statvfs("/")
        volumes.append({
            "name": "Macintosh HD",
            "tags": "volume",
            "path": "/",
            "totalBytes": sv.f_blocks * sv.f_frsize,
            "freeBytes": sv.f_bavail * sv.f_frsize,
            "usedBytes": (sv.f_blocks - sv.f_bavail) * sv.f_frsize,
            "filesystem": "apfs",
            "volumeType": "internal",
            "removable": False,
            "readOnly": False,
        })
    except OSError:
        pass

    # Check /Volumes/ for external drives
    volumes_dir = "/Volumes"
    if os.path.isdir(volumes_dir):
        for name in os.listdir(volumes_dir):
            mount = os.path.join(volumes_dir, name)
            if not os.path.ismount(mount):
                continue
            try:
                sv = os.statvfs(mount)
                volumes.append({
                    "name": name,
                    "tags": "volume",
                    "path": mount,
                    "totalBytes": sv.f_blocks * sv.f_frsize,
                    "freeBytes": sv.f_bavail * sv.f_frsize,
                    "usedBytes": (sv.f_blocks - sv.f_bavail) * sv.f_frsize,
                    "filesystem": None,
                    "volumeType": "external",
                    "removable": True,
                    "readOnly": False,
                })
            except OSError:
                pass

    return volumes


def _get_finder_favorites():
    """Read Finder sidebar favorites from macOS shared file list."""
    import plistlib as _plistlib

    sfl_path = os.path.expanduser(
        "~/Library/Application Support/com.apple.sharedfilelist/"
        "com.apple.LSSharedFileList.FavoriteItems.sfl4"
    )
    if not os.path.exists(sfl_path):
        return []

    try:
        with open(sfl_path, "rb") as f:
            data = _plistlib.load(f)
    except Exception:
        return []

    objects = data.get("$objects", [])
    favorites = []

    for obj in objects:
        if not isinstance(obj, bytes) or len(obj) < 48:
            continue

        # Parse bookmark binary: extract null-terminated path segments
        segments = []
        current = b""
        for byte_val in obj:
            if byte_val == 0:
                if len(current) > 1:
                    try:
                        s = current.decode("utf-8")
                        if s.isascii() and not any(c < " " for c in s):
                            segments.append(s)
                    except (UnicodeDecodeError, ValueError):
                        pass
                current = b""
            else:
                current += bytes([byte_val])

        # Reconstruct path: find 'Users' anchor, build forward
        path_parts = []
        found_anchor = False
        for s in segments:
            if s in ("Users", "Volumes"):
                found_anchor = True
                path_parts = [s]
            elif found_anchor and len(s) < 100:
                path_parts.append(s)
                test = "/" + "/".join(path_parts)
                if not os.path.exists(test):
                    path_parts.pop()
                    break

        if path_parts:
            resolved = "/" + "/".join(path_parts)
            if os.path.exists(resolved):
                favorites.append({
                    "name": os.path.basename(resolved),
                    "path": resolved,
                    "tags": "folder",
                })

    return favorites


@returns({"provider": "string", "providerName": "string", "home": "string", "specialFolders": "{'type': 'object', 'description': 'Well-known folders: desktop, documents, downloads'}", "volumes": "{'type': 'array', 'description': 'Mounted volumes with capacity and filesystem info'}"})
@provides(file_info)
@timeout(15)
def get_info(**_kwargs):
    """Get filesystem info — home dir, special folders, volumes, Finder favorites."""
    home = os.path.expanduser("~")
    username = os.path.basename(home)

    special_folders = {}
    for name in ("Desktop", "Documents", "Downloads"):
        folder = os.path.join(home, name)
        if os.path.isdir(folder):
            special_folders[name.lower()] = folder

    volumes = _get_volumes()
    favorites = _get_finder_favorites()

    return {
        "provider": "macos-control",
        "providerName": "This Computer",
        "home": home,
        "username": username,
        "specialFolders": special_folders,
        "volumes": volumes,
        "favorites": favorites,
    }


@returns({"name": "string", "path": "string", "kind": "string", "size": "integer", "sizeOnDisk": "integer", "created": "string", "modified": "string", "accessed": "string", "mimeType": "string", "permissions": "string", "owner": "string", "group": "string", "hidden": "boolean", "readOnly": "boolean"})
@timeout(10)
def get_file_info(*, path, **_kwargs):
    """Get detailed file/folder properties — like XP Properties dialog."""
    resolved = os.path.expanduser(path)
    resolved = os.path.abspath(resolved)

    if not os.path.exists(resolved):
        raise ValueError(f"Path not found: {resolved}")

    st = os.stat(resolved)
    is_dir = stat.S_ISDIR(st.st_mode)
    is_symlink = os.path.islink(resolved)

    # Owner/group
    try:
        owner = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        owner = str(st.st_uid)
    try:
        group = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        group = str(st.st_gid)

    # Permissions as rwx string
    mode = st.st_mode
    perms = stat.filemode(mode)

    # Size on disk (blocks * 512)
    size_on_disk = st.st_blocks * 512 if hasattr(st, "st_blocks") else st.st_size

    # Directory size: count immediate children, don't recurse (fast)
    dir_item_count = None
    if is_dir:
        try:
            dir_item_count = len(os.listdir(resolved))
        except OSError:
            dir_item_count = None

    result = {
        "name": os.path.basename(resolved),
        "path": resolved,
        "kind": "dir" if is_dir else ("symlink" if is_symlink else "file"),
        "tags": "folder" if is_dir else "file",
        "size": st.st_size,
        "sizeFormatted": _format_size(st.st_size),
        "sizeOnDisk": size_on_disk,
        "sizeOnDiskFormatted": _format_size(size_on_disk),
        "created": _stat_to_iso(st.st_birthtime) if hasattr(st, "st_birthtime") else _stat_to_iso(st.st_ctime),
        "modified": _stat_to_iso(st.st_mtime),
        "accessed": _stat_to_iso(st.st_atime),
        "permissions": perms,
        "owner": owner,
        "group": group,
        "hidden": os.path.basename(resolved).startswith("."),
        "readOnly": not os.access(resolved, os.W_OK),
    }

    if is_dir:
        result["contains_count"] = dir_item_count
        result["location"] = os.path.dirname(resolved)
    else:
        result["mime_type"] = _mime_for_path(resolved)
        ext = Path(resolved).suffix.lower()
        if ext:
            result["format"] = ext.lstrip(".").upper()
        result["location"] = os.path.dirname(resolved)

    # Symlink target
    if is_symlink:
        try:
            result["symlink_target"] = os.readlink(resolved)
        except OSError:
            pass

    return result


def _main():
    if len(sys.argv) < 2:
        raise ValueError("operation is required")

    params = _read_params()
    operation = sys.argv[1]
    handlers = {
        "listApps": list_apps,
        "listProcesses": list_processes,
        "listDisplays": list_displays,
        "listWindows": list_windows,
        "screenshotDisplay": screenshot_display,
        "screenshotWindow": screenshot_window,
        "clipboardRead": clipboard_read,
        "clipboardWrite": clipboard_write,
        "listDirectory": list_directory,
        "readFile": read_file,
        "getInfo": get_info,
        "getFileInfo": get_file_info,
    }
    if operation not in handlers:
        raise ValueError(f"unknown operation: {operation}")

    result = handlers[operation](**params)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        _main()
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() if error.stderr else str(error)
        sys.stderr.write(message + "\n")
        sys.exit(error.returncode or 1)
    except Exception as error:
        sys.stderr.write(str(error) + "\n")
        sys.exit(1)

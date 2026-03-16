#!/usr/bin/env python3

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path


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
        "display_id": String(displayId),
        "display_index": index + 1,
        "is_primary": displayId == mainId,
        "scale": Double(screen.backingScaleFactor),
        "frame": rectDict(screen.frame),
        "visible_frame": rectDict(screen.visibleFrame)
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
        "window_id": info[kCGWindowNumber as String] ?? 0,
        "owner_name": info[kCGWindowOwnerName as String] ?? "",
        "owner_pid": info[kCGWindowOwnerPID as String] ?? 0,
        "title": info[kCGWindowName as String] ?? "",
        "layer": info[kCGWindowLayer as String] ?? 0,
        "alpha": info[kCGWindowAlpha as String] ?? 0,
        "bounds": info[kCGWindowBounds as String] ?? [:],
        "memory_bytes": info[kCGWindowMemoryUsage as String] ?? 0,
        "sharing_state": info[kCGWindowSharingState as String] ?? 0,
        "is_onscreen": info[kCGWindowIsOnscreen as String] ?? false
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


def read_params() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    value = json.loads(raw)
    return value if isinstance(value, dict) else {}


def run_json_command(args, input_text=None):
    completed = subprocess.run(
        args,
        input=input_text,
        capture_output=True,
        text=True,
        check=True,
    )
    stdout = completed.stdout.strip()
    return json.loads(stdout) if stdout else None


def run_text_command(args):
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def run_swift_json(script: str):
    return run_json_command(["swift", "-e", script])


def run_jxa_json(script: str):
    return run_json_command(["osascript", "-l", "JavaScript", "-e", script])


def load_display_names():
    data = run_json_command(["system_profiler", "SPDisplaysDataType", "-json"])
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
                "is_primary": display.get("spdisplays_main") == "spdisplays_yes",
                "refresh_rate": display.get("_spdisplays_resolution"),
            }
    return names


def load_displays():
    displays = run_swift_json(APP_SYSTEM_PROFILER_SWIFT)
    metadata = load_display_names()
    primary = next((display for display in displays if display.get("is_primary")), None)
    primary_center_x = frame_center_x(primary["frame"]) if primary else None
    primary_center_y = frame_center_y(primary["frame"]) if primary else None

    normalized = []
    for display in displays:
        display_id = str(display["display_id"])
        extra = metadata.get(display_id, {})
        frame = normalize_frame(display["frame"])
        visible_frame = normalize_frame(display["visible_frame"])
        is_primary = bool(display.get("is_primary") or extra.get("is_primary"))
        result = {
            "display_id": display_id,
            "display_index": int(display["display_index"]),
            "name": extra.get("name") or f"Display {display_id}",
            "is_primary": is_primary,
            "scale": float(display.get("scale", 1.0)),
            "frame": frame,
            "visible_frame": visible_frame,
            "width": frame["width"],
            "height": frame["height"],
            "origin_x": frame["x"],
            "origin_y": frame["y"],
            "resolution": extra.get("resolution"),
            "pixels": extra.get("pixels"),
        }
        result["position_relative_to_primary"] = relative_position(
            result,
            primary_center_x,
            primary_center_y,
            is_primary,
        )
        normalized.append(result)

    normalized.sort(key=lambda display: display["display_index"])
    return normalized


def list_displays(params):
    displays = load_displays()
    return {
        "displays": displays,
        "count": len(displays),
    }


def list_apps(params):
    data = run_json_command(["system_profiler", "SPApplicationsDataType", "-json"])
    apps = []
    for item in data.get("SPApplicationsDataType", []):
        path = item.get("path")
        name = item.get("_name") or (Path(path).stem if path else None)
        apps.append(
            {
                "name": name,
                "path": path,
                "version": item.get("version"),
                "obtained_from": item.get("obtained_from"),
                "last_modified": item.get("lastModified"),
                "arch": item.get("arch_kind"),
                "signed_by": item.get("signed_by") or [],
            }
        )

    apps.sort(key=lambda app: ((app.get("name") or "").lower(), app.get("path") or ""))
    limit = normalize_limit(params.get("limit"))
    if limit is not None:
        apps = apps[:limit]
    return {
        "apps": apps,
        "count": len(apps),
    }


def list_processes(params):
    output = run_text_command(
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
                "cpu_percent": float(cpu),
                "memory_percent": float(mem),
                "rss_kb": int(rss),
                "rss_bytes": int(rss) * 1024,
                "state": state,
                "started_at": started_at,
                "command": command,
                "name": os.path.basename(command),
            }
        )

    processes.sort(key=lambda process: process["pid"])
    limit = normalize_limit(params.get("limit"))
    if limit is not None:
        processes = processes[:limit]
    return {
        "processes": processes,
        "count": len(processes),
    }


def list_windows(params):
    displays = load_displays()
    cg_windows = run_swift_json(CG_WINDOWS_SWIFT)
    jxa_apps = run_jxa_json(JXA_WINDOWS_SCRIPT)

    normalized = []
    for app in jxa_apps:
        app_name = app.get("app_name")
        pid = app.get("pid")
        frontmost = bool(app.get("frontmost"))
        hidden = bool(app.get("hidden"))
        for window in app.get("windows", []):
            position = window.get("position")
            size = window.get("size")
            if not is_useful_window(app_name, position, size):
                continue

            frame = {
                "x": int(position[0]),
                "y": int(position[1]),
                "width": int(size[0]),
                "height": int(size[1]),
            }
            matched = match_cg_window(
                app_name=app_name,
                pid=pid,
                title=window.get("title") or "",
                frame=frame,
                cg_windows=cg_windows,
            )
            display_id = display_for_frame(frame, displays)
            normalized.append(
                {
                    "window_id": matched.get("window_id") if matched else None,
                    "app_name": app_name,
                    "pid": pid,
                    "title": window.get("title") or "",
                    "frame": frame,
                    "display_id": display_id,
                    "is_minimized": bool(window.get("minimized")),
                    "is_fullscreen": bool(window.get("fullscreen")),
                    "is_main": bool(window.get("is_main")),
                    "is_focused": bool(window.get("is_focused")),
                    "is_hidden": hidden,
                    "is_frontmost_app": frontmost,
                    "role_description": window.get("role_description"),
                    "subrole": window.get("subrole"),
                    "capture_eligible": bool(
                        matched
                        and matched.get("is_onscreen")
                        and matched.get("sharing_state", 0) != 0
                        and not hidden
                        and not window.get("minimized")
                    ),
                    "cg_window_name": matched.get("title") if matched else None,
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
    limit = normalize_limit(params.get("limit"))
    if limit is not None:
        normalized = normalized[:limit]
    return {
        "windows": normalized,
        "count": len(normalized),
    }


def screenshot_display(params):
    displays = load_displays()
    target = None
    display_index = params.get("display_index")
    display_id = params.get("display_id")

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

    path = resolve_output_path(params.get("path"), f"display-{target['display_id']}")
    subprocess.run(
        ["screencapture", "-x", "-D", str(target["display_index"]), path],
        check=True,
    )
    return {
        "display_id": target["display_id"],
        "display_index": target["display_index"],
        "path": path,
        "captured_at": iso_now(),
    }


def screenshot_window(params):
    if params.get("window_id") is None:
        raise ValueError("window_id is required")

    target_window_id = int(params["window_id"])
    windows = list_windows({}).get("windows", [])
    target = next((window for window in windows if window.get("window_id") == target_window_id), None)
    if not target:
        raise ValueError("Window not found")
    if not target.get("capture_eligible"):
        raise ValueError("Window is not capture_eligible")

    path = resolve_output_path(params.get("path"), f"window-{target_window_id}")
    subprocess.run(
        ["screencapture", "-x", "-l", str(target_window_id), path],
        check=True,
    )
    return {
        "window_id": target_window_id,
        "app_name": target.get("app_name"),
        "title": target.get("title"),
        "path": path,
        "captured_at": iso_now(),
    }


def normalize_limit(value):
    if value is None:
        return None
    limit = int(value)
    return max(limit, 0)


def normalize_frame(frame):
    return {
        "x": int(round(float(frame["x"]))),
        "y": int(round(float(frame["y"]))),
        "width": int(round(float(frame["width"]))),
        "height": int(round(float(frame["height"]))),
    }


def frame_center_x(frame):
    return frame["x"] + (frame["width"] / 2.0)


def frame_center_y(frame):
    return frame["y"] + (frame["height"] / 2.0)


def relative_position(display, primary_center_x, primary_center_y, is_primary):
    if is_primary or primary_center_x is None or primary_center_y is None:
        return "primary" if is_primary else None

    dx = frame_center_x(display["frame"]) - primary_center_x
    dy = frame_center_y(display["frame"]) - primary_center_y
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "above" if dy > 0 else "below"


def is_useful_window(app_name, position, size):
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


def match_cg_window(app_name, pid, title, frame, cg_windows):
    title_normalized = normalize_title(title)
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
        candidate_title = normalize_title(candidate.get("title") or "")
        bounds = normalize_cg_bounds(candidate.get("bounds") or {})
        if candidate.get("owner_name") == app_name:
            score += 20
        if title_normalized and candidate_title == title_normalized:
            score += 50
        elif title_normalized and candidate_title and titles_related(title_normalized, candidate_title):
            score += 35
        elif title_normalized and candidate_title:
            score -= 20
        score -= bounds_distance(frame, bounds) / 10.0
        if candidate.get("is_onscreen"):
            score += 5
        if score > best_score:
            best_score = score
            best = {
                "window_id": int(candidate["window_id"]),
                "title": candidate.get("title") or "",
                "is_onscreen": bool(candidate.get("is_onscreen")),
                "sharing_state": int(candidate.get("sharing_state", 0)),
            }

    if best_score < 10:
        return None
    return best


def normalize_cg_bounds(bounds):
    return {
        "x": int(round(float(bounds.get("X", 0)))),
        "y": int(round(float(bounds.get("Y", 0)))),
        "width": int(round(float(bounds.get("Width", 0)))),
        "height": int(round(float(bounds.get("Height", 0)))),
    }


def bounds_distance(left, right):
    return (
        abs(left["x"] - right["x"])
        + abs(left["y"] - right["y"])
        + abs(left["width"] - right["width"])
        + abs(left["height"] - right["height"])
    )


def normalize_title(value):
    return " ".join((value or "").split())


def titles_related(left, right):
    return left in right or right in left


def display_for_frame(frame, displays):
    best_display_id = None
    best_overlap = -1
    for display in displays:
        overlap = intersection_area(frame, display["frame"])
        if overlap > best_overlap:
            best_overlap = overlap
            best_display_id = display["display_id"]
    return best_display_id


def intersection_area(a, b):
    x1 = max(a["x"], b["x"])
    y1 = max(a["y"], b["y"])
    x2 = min(a["x"] + a["width"], b["x"] + b["width"])
    y2 = min(a["y"] + a["height"], b["y"] + b["height"])
    if x2 <= x1 or y2 <= y1:
        return 0
    return (x2 - x1) * (y2 - y1)


def resolve_output_path(value, label):
    if value:
        return os.path.abspath(os.path.expanduser(str(value)))
    timestamp = int(time.time())
    return f"/tmp/macos-control-{label}-{timestamp}.png"


def iso_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main():
    if len(sys.argv) < 2:
        raise ValueError("operation is required")

    params = read_params()
    operation = sys.argv[1]
    handlers = {
        "list_apps": list_apps,
        "list_processes": list_processes,
        "list_displays": list_displays,
        "list_windows": list_windows,
        "screenshot_display": screenshot_display,
        "screenshot_window": screenshot_window,
    }
    if operation not in handlers:
        raise ValueError(f"unknown operation: {operation}")

    result = handlers[operation](params)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() if error.stderr else str(error)
        sys.stderr.write(message + "\n")
        sys.exit(error.returncode or 1)
    except Exception as error:
        sys.stderr.write(str(error) + "\n")
        sys.exit(1)

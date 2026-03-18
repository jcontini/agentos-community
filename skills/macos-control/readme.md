---
id: macos-control
name: macOS Control
description: Inspect macOS apps, processes, displays, windows, and screenshots with built-in system tools
icon: icon.svg
color: "#111827"
website: https://www.apple.com/macos/
connections: {}
operations:
  list_apps:
    description: List installed macOS applications using system_profiler
    params:
      limit:
        type: integer
        description: Optional maximum number of apps to return
    returns:
      apps:
        type: array
        description: Installed applications
      count: integer
    python:
      module: ./macos_control.py
      function: list_apps
      params: true
      timeout: 60

  list_processes:
    description: List running macOS processes with stable fields from ps
    params:
      limit:
        type: integer
        description: Optional maximum number of processes to return
    returns:
      processes:
        type: array
        description: Running processes
      count: integer
    python:
      module: ./macos_control.py
      function: list_processes
      params: true
      timeout: 15

  list_displays:
    description: List connected displays with geometry for left/right monitor reasoning
    returns:
      displays:
        type: array
        description: Connected displays
      count: integer
    python:
      module: ./macos_control.py
      function: list_displays
      params: true
      timeout: 15

  list_windows:
    description: List useful user-facing application windows with capture eligibility
    params:
      limit:
        type: integer
        description: Optional maximum number of windows to return
    returns:
      windows:
        type: array
        description: User-facing application windows
      count: integer
    python:
      module: ./macos_control.py
      function: list_windows
      params: true
      timeout: 30

  screenshot_window:
    description: Capture a screenshot of a specific application window by window_id
    params:
      window_id:
        type: integer
        required: true
        description: Window ID from list_windows
      path:
        type: string
        description: Optional output path for the PNG file
    returns:
      window_id: integer
      app_name: string
      title: string
      path: string
      captured_at: string
    python:
      module: ./macos_control.py
      function: screenshot_window
      params: true
      timeout: 20

  screenshot_display:
    description: Capture a screenshot of a display by display_id or display_index
    params:
      display_id:
        type: string
        description: Display ID from list_displays
      display_index:
        type: integer
        description: 1-based display index from list_displays
      path:
        type: string
        description: Optional output path for the PNG file
    returns:
      display_id: string
      display_index: integer
      path: string
      captured_at: string
    python:
      module: ./macos_control.py
      function: screenshot_display
      params: true
      timeout: 20
---

# macOS Control

Read-only macOS inspection skill for local computer awareness. This first pass is intentionally limited to discovery and screenshots only.

## What It Uses

- `system_profiler` for installed apps and display metadata
- `ps` for running processes
- Swift with `AppKit` and `CoreGraphics` for display and window geometry
- JXA via `System Events` for window state like minimized, fullscreen, hidden, and focused
- `screencapture` for window and display PNG captures

## Permissions

For best results, grant:

- **Accessibility** access to the host process so `System Events` can inspect windows
- **Screen Recording** access so `screencapture` can capture window and display images

Without those permissions, `list_windows` and screenshot tools may return incomplete data or fail.

## Tool Notes

### `list_apps`

Returns installed applications from `system_profiler SPApplicationsDataType -json`.

```javascript
use({ skill: "macos-control", tool: "list_apps", params: { limit: 10 } })
```

### `list_processes`

Returns stable process fields from `ps`, including `pid`, `ppid`, `cpu_percent`, `memory_percent`, and `command`.

```javascript
use({ skill: "macos-control", tool: "list_processes", params: { limit: 25 } })
```

### `list_displays`

Returns display IDs, 1-based display indices for screenshot capture, geometry, scale, and relative position to the primary display.

```javascript
use({ skill: "macos-control", tool: "list_displays" })
```

### `list_windows`

Returns useful user-facing windows only. Each result includes `window_id` when it could be matched to a CoreGraphics window and a `capture_eligible` flag for screenshot safety.

```javascript
use({ skill: "macos-control", tool: "list_windows", params: { limit: 20 } })
```

### `screenshot_window`

Captures a PNG for a `window_id` returned by `list_windows`.

```javascript
use({ skill: "macos-control", tool: "screenshot_window", params: { window_id: 12345 } })
```

### `screenshot_display`

Captures a PNG for a display. You can pass `display_id`, `display_index`, or neither to default to the primary display.

```javascript
use({ skill: "macos-control", tool: "screenshot_display", params: { display_index: 1 } })
```

## Scope

This skill currently does not mutate app or window state. It does not open, focus, move, resize, quit, or force-quit anything in this first pass.

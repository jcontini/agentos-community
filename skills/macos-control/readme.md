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
run({ skill: "macos-control", tool: "list_apps", params: { limit: 10 } })
```

### `list_processes`

Returns stable process fields from `ps`, including `pid`, `ppid`, `cpu_percent`, `memory_percent`, and `command`.

```javascript
run({ skill: "macos-control", tool: "list_processes", params: { limit: 25 } })
```

### `list_displays`

Returns display IDs, 1-based display indices for screenshot capture, geometry, scale, and relative position to the primary display.

```javascript
run({ skill: "macos-control", tool: "list_displays" })
```

### `list_windows`

Returns useful user-facing windows only. Each result includes `window_id` when it could be matched to a CoreGraphics window and a `capture_eligible` flag for screenshot safety.

```javascript
run({ skill: "macos-control", tool: "list_windows", params: { limit: 20 } })
```

### `screenshot_window`

Captures a PNG for a `window_id` returned by `list_windows`.

```javascript
run({ skill: "macos-control", tool: "screenshot_window", params: { window_id: 12345 } })
```

### `screenshot_display`

Captures a PNG for a display. You can pass `display_id`, `display_index`, or neither to default to the primary display.

```javascript
run({ skill: "macos-control", tool: "screenshot_display", params: { display_index: 1 } })
```

## Scope

This skill currently does not mutate app or window state. It does not open, focus, move, resize, quit, or force-quit anything in this first pass.

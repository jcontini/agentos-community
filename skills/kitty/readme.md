# Kitty

Kitty remote control for AgentOS. This skill is for terminal orchestration: inspect windows, focus tabs, send input, and launch or close tabs without relying on the old CLI glue.

## Setup

Kitty must allow remote control. A typical config looks like this:

```conf
allow_remote_control yes
listen_on unix:/tmp/kitty-socket
```

The helper auto-discovers `/tmp/kitty-socket*` and also respects `KITTY_LISTEN_ON`. If you want to target a specific instance, pass `socket`.

## What It Covers

- `list_os_windows`
- `list_tabs`
- `list_panes`
- `focus_os_window`
- `focus_tab`
- `send_text`
- `get_text`
- `launch_tab`
- `close_tab`

## Example

```js
run({ skill: "kitty", tool: "launch_tab", params: { title: "watch", cwd: "/Users/joe/dev/agentos", command: "python3 bin/mcp-watch" } })

run({ skill: "kitty", tool: "list_tabs", params: {} })

run({ skill: "kitty", tool: "send_text", params: { window_id: 12, text: "cargo test", press_enter: true } })
```

---
id: kitty
name: Kitty
description: Control Kitty windows, tabs, and panes through Kitty remote control
icon: icon.svg
color: "#C34C89"
website: https://sw.kovidgoyal.net/kitty/
auth: none
operations:
  list_os_windows:
    description: List Kitty OS windows with their focused tab state
    returns: array
    params:
      socket:
        type: string
        required: false
        description: Optional Kitty remote-control socket (for example unix:/tmp/kitty-socket-12345)
    python:
      module: ./kitty-control.py
      function: command_list_os_windows
      params: true
      timeout: 15

  list_tabs:
    description: List Kitty tabs across all OS windows
    returns: array
    params:
      socket:
        type: string
        required: false
        description: Optional Kitty remote-control socket
      os_window_id:
        type: integer
        required: false
        description: Filter results to a single Kitty OS window id
    python:
      module: ./kitty-control.py
      function: command_list_tabs
      params: true
      timeout: 15

  list_panes:
    description: List Kitty panes with cwd, process, and focus state
    returns: array
    params:
      socket:
        type: string
        required: false
        description: Optional Kitty remote-control socket
      os_window_id:
        type: integer
        required: false
        description: Filter results to a single Kitty OS window id
      tab_id:
        type: integer
        required: false
        description: Filter results to a single Kitty tab id
    python:
      module: ./kitty-control.py
      function: command_list_panes
      params: true
      timeout: 15

  launch_tab:
    description: Launch a new Kitty tab, starting Kitty first if needed
    returns:
      socket: string
      os_window_id: integer
      tab_id: integer
      window_id: integer
      title: string
    params:
      socket:
        type: string
        required: false
        description: Optional Kitty remote-control socket
      title:
        type: string
        required: false
        description: Optional tab title
      cwd:
        type: string
        required: false
        description: Working directory for the new tab
      command:
        type: string
        required: false
        description: Optional shell command to run with /bin/zsh -lc
      keep_focus:
        type: boolean
        required: false
        default: false
        description: Keep focus on the current tab after launching the new one
    python:
      module: ./kitty-control.py
      function: command_launch_tab
      params: true
      timeout: 20

  focus_tab:
    description: Focus an existing Kitty tab by id
    returns:
      ok: boolean
      socket: string
      tab_id: integer
    params:
      socket:
        type: string
        required: false
        description: Optional Kitty remote-control socket
      tab_id:
        type: integer
        required: true
        description: Kitty tab id to focus
    python:
      module: ./kitty-control.py
      function: command_focus_tab
      params: true
      timeout: 15

  focus_os_window:
    description: Focus a Kitty OS window by targeting its active pane
    returns:
      ok: boolean
      socket: string
      os_window_id: integer
      tab_id: integer
      window_id: integer
    params:
      socket:
        type: string
        required: false
        description: Optional Kitty remote-control socket
      os_window_id:
        type: integer
        required: true
        description: Kitty OS window id to focus
    python:
      module: ./kitty-control.py
      function: command_focus_os_window
      params: true
      timeout: 15

  send_text:
    description: Send text to the active Kitty pane, a specific pane, or a whole tab
    returns:
      ok: boolean
      socket: string
      tab_id: integer
      window_id: integer
    params:
      socket:
        type: string
        required: false
        description: Optional Kitty remote-control socket
      text:
        type: string
        required: true
        description: Text to send
      window_id:
        type: integer
        required: false
        description: Target Kitty pane id
      tab_id:
        type: integer
        required: false
        description: Target Kitty tab id
      press_enter:
        type: boolean
        required: false
        default: false
        description: Append carriage return after sending the text
    python:
      module: ./kitty-control.py
      function: command_send_text
      params: true
      timeout: 15

  get_text:
    description: Read text currently visible in a Kitty pane
    returns:
      socket: string
      window_id: integer
      extent: string
      text: string
    params:
      socket:
        type: string
        required: false
        description: Optional Kitty remote-control socket
      window_id:
        type: integer
        required: false
        description: Target Kitty pane id; defaults to the active pane
      extent:
        type: string
        required: false
        default: screen
        description: Kitty get-text extent such as screen, all, or selection
      ansi:
        type: boolean
        required: false
        default: false
        description: Include ANSI escape sequences in the returned text
    python:
      module: ./kitty-control.py
      function: command_get_text
      params: true
      timeout: 15

  close_tab:
    description: Close a Kitty tab by id
    returns:
      ok: boolean
      socket: string
      tab_id: integer
    params:
      socket:
        type: string
        required: false
        description: Optional Kitty remote-control socket
      tab_id:
        type: integer
        required: true
        description: Kitty tab id to close
    python:
      module: ./kitty-control.py
      function: command_close_tab
      params: true
      timeout: 15
---

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
use({ skill: "kitty", tool: "launch_tab", params: { title: "watch", cwd: "/Users/joe/dev/agentos", command: "python3 bin/mcp-watch" } })

use({ skill: "kitty", tool: "list_tabs", params: {} })

use({ skill: "kitty", tool: "send_text", params: { window_id: 12, text: "cargo test", press_enter: true } })
```

---
id: github
name: GitHub
description: GitHub CLI wrapper for repos, issues, PRs, and more
icon: icon.svg
color: "#24292f"
tags: [code, git, github, developer]

website: https://cli.github.com
platform: [macos, linux, windows]

auth:
  type: none
  # gh handles its own auth via `gh auth login`

instructions: |
  GitHub CLI wrapper. Enables repos, issues, PRs, releases, gists, and more.
  
  **First time setup:** User must run `gh auth login` in terminal once.
  
  **Usage:** Run `github.help` to see available commands, then use `github.run`
  with the appropriate arguments.
  
  **Examples:**
  - List repos: `gh repo list`
  - Create issue: `gh issue create --title "Bug" --body "Description"`
  - Create PR: `gh pr create --title "Feature" --body "Details"`
  - Check PR status: `gh pr status`
  - Clone repo: `gh repo clone owner/repo`
  
  The `gh` CLI is the source of truth. Run help commands to learn more:
  - `gh help` - General help
  - `gh repo --help` - Repo commands
  - `gh issue --help` - Issue commands
  - `gh pr --help` - PR commands

actions:
  help:
    operation: read
    label: "Show help"
    description: Show gh CLI help. Pass topic for specific help (e.g., "repo", "issue", "pr")
    command:
      binary: gh
      args:
        - "{{params.topic | default: 'help'}}"
        - "--help"
      timeout: 10
    response:
      raw: true

  run:
    operation: update
    label: "Run gh command"
    description: Run any gh CLI command. Pass the full command after 'gh' (e.g., "repo list" or "pr create --title 'My PR'")
    command:
      binary: gh
      args_string: "{{params.command}}"
      timeout: 120
    response:
      raw: true

  status:
    operation: read
    label: "Check status"
    description: Show status of relevant PRs, issues, and notifications
    command:
      binary: gh
      args:
        - "status"
      timeout: 30
    response:
      raw: true
---

# GitHub

GitHub CLI wrapper for AgentOS. Provides access to repos, issues, PRs, releases, gists, actions, and more through the official `gh` CLI.

## Setup

1. Install gh CLI: `brew install gh`
2. Authenticate once: `gh auth login`

That's it. No API keys to configure in AgentOS — `gh` handles its own authentication.

## Usage

The plugin exposes three actions:

| Action | Purpose |
|--------|---------|
| `help` | Learn available commands |
| `run` | Execute any gh command |
| `status` | Quick status check |

## Examples

```
# Learn what's available
github.help topic="repo"

# List your repos  
github.run command="repo list"

# Create a PR
github.run command="pr create --title 'Add feature' --body 'Description here'"

# Check CI status
github.run command="pr checks"

# Create a release
github.run command="release create v1.0.0 --title 'Version 1.0' --notes 'Initial release'"
```

## Why a wrapper?

The `gh` CLI is excellent and handles auth, pagination, and formatting well. Rather than reimplementing every GitHub API endpoint, this plugin provides a secure gateway through AgentOS's firewall while letting `gh` do what it does best.

Users who don't grant terminal access can still use GitHub through this plugin, with the firewall controlling what's allowed.

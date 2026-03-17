---
id: github
name: GitHub
description: Work with GitHub issues, pull requests, and repository files through the local gh CLI. Use when working with GitHub repos, issues, PRs, or reading files from a repo.
icon: icon.svg
color: "#24292F"
website: https://github.com
auth: none

adapters:
  task:
    id: '.number | tostring'
    name: .title
    description: '.body // null'
    content: '.body // null'
    url: .url
    created_at: .created_at
    updated_at: .updated_at
    completed_at: '.closed_at // null'
    data.state: .state
    data.repository: '.repository // null'
    data.author: '.author // null'
    data.labels: '.labels // []'

  document:
    id: '.sha // .path'
    name: .name
    text: '.content // null'
    url: '.url // null'
    content: '.content // null'
    data.path: .path
    data.kind: '.kind // null'
    data.sha: '.sha // null'
    data.size: '.size // null'
    data.repository: '.repository // null'

operations:
  list_tasks:
    description: List issues for a repository
    returns: task[]
    params:
      repo:
        type: string
        required: true
        description: Repository in owner/name format
      state:
        type: string
        description: open, closed, or all
      limit:
        type: integer
        description: Maximum number of issues to return
    command:
      binary: python3
      args:
        - ./github-cli.py
        - list_tasks
      stdin: '{params: .params} | tojson'
      timeout: 30

  get_task:
    description: Get a single issue by number
    returns: task
    params:
      repo:
        type: string
        required: true
        description: Repository in owner/name format
      number:
        type: integer
        required: true
        description: Issue number
    command:
      binary: python3
      args:
        - ./github-cli.py
        - get_task
      stdin: '{params: .params} | tojson'
      timeout: 30

  create_task:
    description: Create a new GitHub issue
    returns:
      url: string
      number: integer
      title: string
    params:
      repo:
        type: string
        required: true
        description: Repository in owner/name format
      title:
        type: string
        required: true
        description: Issue title
      body:
        type: string
        description: Issue body
    command:
      binary: python3
      args:
        - ./github-cli.py
        - create_task
      stdin: '{params: .params} | tojson'
      timeout: 30

  close_task:
    description: Close an issue
    returns:
      ok: boolean
      url: string
    params:
      repo:
        type: string
        required: true
      number:
        type: integer
        required: true
        description: Issue number
    command:
      binary: python3
      args:
        - ./github-cli.py
        - close_task
      stdin: '{params: .params} | tojson'
      timeout: 30

  reopen_task:
    description: Reopen a closed issue
    returns:
      ok: boolean
      url: string
    params:
      repo:
        type: string
        required: true
      number:
        type: integer
        required: true
        description: Issue number
    command:
      binary: python3
      args:
        - ./github-cli.py
        - reopen_task
      stdin: '{params: .params} | tojson'
      timeout: 30

  list_pull_requests:
    description: List pull requests for a repository
    returns: array
    params:
      repo:
        type: string
        required: true
        description: Repository in owner/name format
      state:
        type: string
        description: open, closed, or all
      limit:
        type: integer
        description: Maximum number of pull requests to return
    command:
      binary: python3
      args:
        - ./github-cli.py
        - list_pull_requests
      stdin: '{params: .params} | tojson'
      timeout: 30

  create_pull_request:
    description: Create a pull request
    returns:
      url: string
    params:
      repo:
        type: string
        required: true
        description: Repository in owner/name format
      title:
        type: string
        required: true
        description: Pull request title
      body:
        type: string
        description: Pull request body
      head:
        type: string
        required: true
        description: Source branch
      base:
        type: string
        description: Target branch
    command:
      binary: python3
      args:
        - ./github-cli.py
        - create_pull_request
      stdin: '{params: .params} | tojson'
      timeout: 30

  list_documents:
    description: List files and folders at a repository path
    returns: document[]
    params:
      repo:
        type: string
        required: true
        description: Repository in owner/name format
      path:
        type: string
        description: Path within the repository
      ref:
        type: string
        description: Branch, tag, or commit
    command:
      binary: python3
      args:
        - ./github-cli.py
        - list_documents
      stdin: '{params: .params} | tojson'
      timeout: 30

  read_document:
    description: Read a text file from a repository
    returns: document
    params:
      repo:
        type: string
        required: true
        description: Repository in owner/name format
      path:
        type: string
        required: true
        description: File path within the repository
      ref:
        type: string
        description: Branch, tag, or commit
    command:
      binary: python3
      args:
        - ./github-cli.py
        - read_document
      stdin: '{params: .params} | tojson'
      timeout: 30

  status:
    description: Show GitHub CLI status for the current machine
    returns:
      output: string
    command:
      binary: python3
      args:
        - ./github-cli.py
        - status
      stdin: '{params: .params} | tojson'
      timeout: 30
---

# GitHub

GitHub via the local `gh` CLI. This skill is intentionally scoped to high-signal workflows that are useful from AgentOS today: issues as `task` entities, pull request utilities, and repository file reads as `document` entities.

## Requirements

- Install the GitHub CLI: `brew install gh`
- Authenticate once with `gh auth login`
- Public repository reads often work without login, but issue and PR mutations generally require auth

## What Maps Cleanly

- GitHub issues map to `task`
- Repository files map to `document`
- Pull requests stay inline utility results for now

## Recommended Workflow

1. Use `list_tasks` or `get_task` when you want GitHub issues to flow through the normal task shape.
2. Use `list_documents` and `read_document` for lightweight repo browsing or to inspect a single file without cloning.
3. Use `list_pull_requests` and `create_pull_request` when you need PR metadata or creation, but do not need a first-class PR entity yet.

## Notes

- `read_document` is best for text files tracked in the GitHub contents API.
- Large binaries, LFS-backed objects, and directories that require tree traversal are out of scope for this first pass.
- This skill relies on whatever account and host configuration your local `gh` installation already uses.

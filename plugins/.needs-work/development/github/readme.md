---
id: github
name: GitHub
description: GitHub issues, gists, and repo file access via existing entities
icon: icon.svg

website: https://cli.github.com
platform: [macos, linux, windows]

auth:
  type: none
  # gh handles its own auth via `gh auth login`

instructions: |
  GitHub integration via the `gh` CLI. Maps to existing entities:
  
  - **Issues → Tasks** - Show up in Tasks app alongside Todoist, Linear
  - **Gists → Posts** - Show up in Posts app alongside Reddit, HN  
  - **Repo contents → Files** - Browse repos in Files app
  
  **Setup:** Run `gh auth login` in terminal once.
  
  **Examples:**
  - List issues as tasks: `task.list (plugin: github, repo: "owner/repo")`
  - List gists as posts: `post.list (plugin: github)`
  - Browse repo files: `file.list (plugin: github, path: "owner/repo")`

# =============================================================================
# Entity Adapters - Map GitHub to existing entities
# =============================================================================

adapters:
  task:
    list: issue.list
    get: issue.get
    create: issue.create
    complete: issue.close
    reopen: issue.reopen
  post:
    list: gist.list
    get: gist.get
    create: gist.create
  file:
    list: contents.list
    read: contents.read
    write: contents.write

actions:
  # -------------------------------------------------------------------------
  # Issues → task entity
  # -------------------------------------------------------------------------
  issue.list:
    operation: read
    label: "List issues"
    description: List issues for a repository (maps to task entity)
    params:
      repo:
        type: string
        required: true
        description: "Repository in owner/name format"
      state:
        type: string
        default: open
        description: "Filter by state: open, closed, all"
      limit:
        type: number
        default: 30
    command:
      binary: gh
      args:
        - issue
        - list
        - --repo
        - "{{params.repo}}"
        - --state
        - "{{params.state}}"
        - --limit
        - "{{params.limit}}"
        - --json
        - number,title,body,state,url,createdAt,updatedAt,closedAt
      timeout: 30
    response:
      format: json
      adapter:
        items: .
        mapping:
          id: '(.number | tostring)'
          title: .title
          description: .body
          completed: '(.state == "closed")'
          url: .url
          created_at: .createdAt
          updated_at: .updatedAt
          completed_at: .closedAt

  issue.get:
    operation: read
    label: "Get issue"
    description: Get a specific issue (maps to task entity)
    params:
      repo:
        type: string
        required: true
      id:
        type: string
        required: true
        description: "Issue number"
    command:
      binary: gh
      args:
        - issue
        - view
        - "{{params.id}}"
        - --repo
        - "{{params.repo}}"
        - --json
        - number,title,body,state,url,createdAt,updatedAt,closedAt,comments
      timeout: 30
    response:
      format: json
      adapter:
        mapping:
          id: '(.number | tostring)'
          title: .title
          description: .body
          completed: '(.state == "closed")'
          url: .url
          created_at: .createdAt
          updated_at: .updatedAt
          completed_at: .closedAt

  issue.create:
    operation: create
    label: "Create issue"
    description: Create a new issue (maps to task.create)
    params:
      repo:
        type: string
        required: true
      title:
        type: string
        required: true
      description:
        type: string
        description: "Issue body"
    command:
      binary: gh
      args:
        - issue
        - create
        - --repo
        - "{{params.repo}}"
        - --title
        - "{{params.title}}"
        - --body
        - "{{params.description | default: ''}}"
      timeout: 30
    response:
      raw: true

  issue.close:
    operation: update
    label: "Close issue"
    description: Close an issue (maps to task.complete)
    params:
      repo:
        type: string
        required: true
      id:
        type: string
        required: true
    command:
      binary: gh
      args:
        - issue
        - close
        - "{{params.id}}"
        - --repo
        - "{{params.repo}}"
      timeout: 30
    response:
      raw: true

  issue.reopen:
    operation: update
    label: "Reopen issue"
    description: Reopen a closed issue (maps to task.reopen)
    params:
      repo:
        type: string
        required: true
      id:
        type: string
        required: true
    command:
      binary: gh
      args:
        - issue
        - reopen
        - "{{params.id}}"
        - --repo
        - "{{params.repo}}"
      timeout: 30
    response:
      raw: true

  # -------------------------------------------------------------------------
  # Gists → post entity
  # -------------------------------------------------------------------------
  gist.list:
    operation: read
    label: "List gists"
    description: List your gists (maps to post entity)
    params:
      limit:
        type: number
        default: 30
    command:
      binary: gh
      args:
        - gist
        - list
        - --limit
        - "{{params.limit}}"
      timeout: 30
    response:
      raw: true
      # Note: gh gist list doesn't support --json, need to parse text output
      # or use API directly. For now, raw output.

  gist.get:
    operation: read
    label: "Get gist"
    description: Get a specific gist (maps to post entity)
    params:
      id:
        type: string
        required: true
    command:
      binary: gh
      args:
        - gist
        - view
        - "{{params.id}}"
        - --raw
      timeout: 30
    response:
      raw: true

  gist.create:
    operation: create
    label: "Create gist"
    description: Create a new gist (maps to post.create)
    params:
      content:
        type: string
        required: true
        description: "Gist content"
      title:
        type: string
        description: "Description for the gist"
      filename:
        type: string
        default: "gist.md"
      public:
        type: boolean
        default: false
    command:
      binary: gh
      args:
        - gist
        - create
        - --desc
        - "{{params.title | default: ''}}"
        - --filename
        - "{{params.filename}}"
        - "{{params.public | if . then '--public' else '' end}}"
        - "-"
      stdin: "{{params.content}}"
      timeout: 30
    response:
      raw: true

  # -------------------------------------------------------------------------
  # Repo contents → file entity
  # -------------------------------------------------------------------------
  contents.list:
    operation: read
    label: "List repo contents"
    description: List files in a repository (maps to file entity)
    params:
      path:
        type: string
        required: true
        description: "Path: owner/repo or owner/repo/subdir"
      ref:
        type: string
        description: "Branch, tag, or commit"
    command:
      binary: gh
      args:
        - api
        - "repos/{{params.path | split:'/' | .[0:2] | join:'/'}}/contents/{{params.path | split:'/' | .[2:] | join:'/'}}{{params.ref | if . then '?ref=' + . else '' end}}"
      timeout: 30
    response:
      format: json
      adapter:
        items: .
        mapping:
          name: .name
          path: '("{{params.path | split:''/'' | .[0:2] | join:''/''}}/" + .path)'
          type: 'if .type == "dir" then "directory" else "file" end'
          size: .size

  contents.read:
    operation: read
    label: "Read file"
    description: Read a file from a repository (maps to file entity)
    params:
      path:
        type: string
        required: true
        description: "Path: owner/repo/path/to/file"
      ref:
        type: string
        description: "Branch, tag, or commit"
    command:
      binary: gh
      args:
        - api
        - "repos/{{params.path | split:'/' | .[0:2] | join:'/'}}/contents/{{params.path | split:'/' | .[2:] | join:'/'}}{{params.ref | if . then '?ref=' + . else '' end}}"
        - --jq
        - ".content | @base64d"
      timeout: 30
    response:
      format: text
      adapter:
        mapping:
          path: '"{{params.path}}"'
          name: '"{{params.path | split:''/'' | .[-1]}}"'
          content: .

  contents.write:
    operation: create
    label: "Write file"
    description: Create or update a file in a repository
    params:
      path:
        type: string
        required: true
      content:
        type: string
        required: true
      message:
        type: string
        required: true
        description: "Commit message"
      branch:
        type: string
      sha:
        type: string
        description: "SHA of existing file (required for updates)"
    command:
      binary: gh
      args:
        - api
        - --method
        - PUT
        - "repos/{{params.path | split:'/' | .[0:2] | join:'/'}}/contents/{{params.path | split:'/' | .[2:] | join:'/'}}"
        - -f
        - "message={{params.message}}"
        - -f
        - "content={{params.content | @base64}}"
      timeout: 30
    response:
      format: json
      adapter:
        mapping:
          success: true
          path: .content.path
          url: .content.html_url

  # -------------------------------------------------------------------------
  # Utilities (no entity mapping)
  # -------------------------------------------------------------------------
  pr.list:
    operation: read
    label: "List PRs"
    description: List pull requests (utility - no entity mapping)
    params:
      repo:
        type: string
        required: true
      state:
        type: string
        default: open
      limit:
        type: number
        default: 30
    command:
      binary: gh
      args:
        - pr
        - list
        - --repo
        - "{{params.repo}}"
        - --state
        - "{{params.state}}"
        - --limit
        - "{{params.limit}}"
      timeout: 30
    response:
      raw: true

  pr.create:
    operation: create
    label: "Create PR"
    description: Create a pull request
    params:
      repo:
        type: string
        required: true
      title:
        type: string
        required: true
      body:
        type: string
      head:
        type: string
        required: true
        description: "Source branch"
      base:
        type: string
        description: "Target branch"
    command:
      binary: gh
      args:
        - pr
        - create
        - --repo
        - "{{params.repo}}"
        - --title
        - "{{params.title}}"
        - --body
        - "{{params.body | default: ''}}"
        - --head
        - "{{params.head}}"
        - --base
        - "{{params.base | default: ''}}"
      timeout: 30
    response:
      raw: true

  status:
    operation: read
    label: "Check status"
    description: Show status of PRs, issues, and notifications
    command:
      binary: gh
      args:
        - status
      timeout: 30
    response:
      raw: true

  run:
    operation: update
    label: "Run command"
    description: Run any gh CLI command
    params:
      command:
        type: string
        required: true
    command:
      binary: gh
      args_string: "{{params.command}}"
      timeout: 120
    response:
      raw: true
---

# GitHub

GitHub integration that maps to existing AgentOS entities.

## Setup

```bash
brew install gh
gh auth login
```

## Entity Mappings

| GitHub | AgentOS Entity | Shows Up In |
|--------|----------------|-------------|
| Issues | `task` | Tasks app (alongside Todoist, Linear) |
| Gists | `post` | Posts app (alongside Reddit, HN) |
| Repo contents | `file` | Files app (as G: drive) |

## Usage

### Issues as Tasks

```bash
# List issues from a repo
task.list (plugin: github, repo: "owner/repo")

# Create an issue
task.create (plugin: github, repo: "owner/repo", title: "Fix bug", description: "Details...")

# Close an issue
task.complete (plugin: github, repo: "owner/repo", id: "123")
```

### Gists as Posts

```bash
# List your gists
post.list (plugin: github)

# Create a gist
post.create (plugin: github, content: "# My Gist", title: "Description")
```

### Repo Files

```bash
# Browse repo root
file.list (plugin: github, path: "owner/repo")

# Read a file
file.read (plugin: github, path: "owner/repo/README.md")

# Read from branch
file.read (plugin: github, path: "owner/repo/config.json", ref: "develop")
```

### Utilities (Raw Output)

```bash
# List PRs
github.pr.list (repo: "owner/repo")

# Create PR
github.pr.create (repo: "owner/repo", title: "Feature", head: "feature-branch")

# Check status
github.status

# Run any gh command
github.run (command: "release list")
```

## Why Entity Mapping?

When GitHub issues map to `task`, they appear in the unified Tasks app:

```
┌─────────────────────────────────────────────────┐
│  ✓ Tasks                               ─ □ ×   │
├─────────────────────────────────────────────────┤
│  All │ Todoist │ Linear │ GitHub               │
├─────────────────────────────────────────────────┤
│  □ Fix login bug              [github]         │
│  □ Update dependencies        [todoist]        │
│  □ API refactor               [linear]         │
└─────────────────────────────────────────────────┘
```

Same UI, same experience, different sources.

---
id: code-editing
name: Code Editing
description: Read, write, and surgically edit files on disk
icon: icon.svg
color: "#10B981"

website: https://github.com/jcontini/agentos-community

connections: {}

---

# Code Editing

Filesystem operations for agents. Covers the full file CRUD cycle needed to scaffold
projects, edit configs, and write code — without a terminal.

## Inspiration: Cursor's Tool Set

Cursor (the AI code editor) exposes exactly the right primitive set. This skill's
operations mirror them:

| This skill | Cursor tool | What it does |
|------------|-------------|--------------|
| `file.read` | `Read` | Read file contents, optionally with line offset/limit |
| `file.write` | `Write` | Create or overwrite a file completely |
| `file.edit` | `StrReplace` | Replace an exact string in a file (surgical edit) |
| `file.delete` | `Delete` | Delete a file |
| `file.list` | `Glob` | List files matching a glob pattern |
| `file.search` | `Grep` | Search file contents with regex |
| `file.find` | `Glob` | Find files by name pattern |

Cursor's tool definitions live in:
```
/Applications/Cursor.app/Contents/Resources/app/extensions/cursor-agent-exec/dist/main.js
```

## Operations

> **Status:** Spec — not yet implemented. Executor TBD (likely `command` wrapping shell
> primitives, or a dedicated `files` executor in the AgentOS core).

### `file.read`
```yaml
params:
  path: { type: string, required: true }
  offset: { type: integer }   # line number to start from
  limit: { type: integer }    # number of lines to read
```

### `file.write`
```yaml
params:
  path: { type: string, required: true }
  contents: { type: string, required: true }
```

### `file.edit`
```yaml
params:
  path: { type: string, required: true }
  old_string: { type: string, required: true }  # must be unique in file
  new_string: { type: string, required: true }
  replace_all: { type: boolean }               # default false
```

### `file.delete`
```yaml
params:
  path: { type: string, required: true }
```

### `file.list`
```yaml
params:
  path: { type: string, required: true }
  glob: { type: string }      # pattern like "**/*.yaml"
```

### `file.search`
```yaml
params:
  path: { type: string, required: true }
  pattern: { type: string, required: true }   # regex
  glob: { type: string }                      # file filter
  case_insensitive: { type: boolean }
```

## Who needs this

Skills that build or modify files need `file.write` and `file.edit` capabilities:

```yaml
# In a skill's readme.md credits section:
```

The install engine resolves this at install time: "this skill needs file editing
— is code-editing (or equivalent) installed?"

## Implementation path

Phase 1 — `command` executor wrapping shell primitives:
- `file.read` → `cat -n {path}` with awk for offset/limit
- `file.write` → write to temp file, `mv` into place
- `file.edit` → Python one-liner with `str.replace()`
- `file.delete` → `rm {path}`
- `file.list` → `find {path} -name "{glob}"`
- `file.search` → `grep -rn {pattern} {path}`

Phase 2 — native `files` executor in AgentOS core (Rust):
- Safer (no shell injection risk)
- Cross-platform
- Better error messages
- Atomic writes (temp file + rename)

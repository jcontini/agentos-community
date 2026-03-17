# Handoff: Build a `python:` Executor for agentOS

## Goal

Build a first-class `python:` executor in the agentOS Rust engine, on par with `rest:` and `graphql:`. Then migrate the Goodreads skill to use it as a proof of concept. Then update `CONTRIBUTING.md`.

## Why

Python is the most-used command executor — 50 operations across 10 skills all use `command:` with `binary: python3`. Every one of them repeats the same boilerplate: `binary: python3`, `working_dir: .`, `timeout: 30`, positional args with `| tostring`, and a Python `main()` that parses `sys.argv` and `print(json.dumps(...))`. A first-class executor eliminates all of this.

## Design

### YAML shape

```yaml
operations:
  list_similar_books:
    description: List similar books
    returns: book[]
    params:
      book_id: { type: string, required: true }
      limit: { type: integer, default: 20 }
    python:
      module: ./public_graph.py
      function: list_similar_books
      args:
        book_id: .params.book_id
        limit: '.params.limit // 20'
      timeout: 30                  # optional, sensible default
      response:                    # optional, same as rest/graphql
        root: /results
```

### What the runtime handles

| Boilerplate today (command:) | python: executor handles it |
|---|---|
| `binary: python3` | Implicit |
| `working_dir: .` | Module path resolved relative to skill folder |
| `\| tostring` on every arg | Args passed as typed JSON (int stays int) |
| `sys.argv` parsing in Python | Runtime calls function directly with kwargs |
| `print(json.dumps(result))` | Runtime captures the return value |
| `timeout: 30` everywhere | Sensible default, overridable |

### How it works under the hood

The Rust executor generates a thin Python loader script and shells out:

```python
import json, sys, importlib.util
spec = importlib.util.spec_from_file_location("mod", "<resolved_module_path>")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
result = mod.<function>(**json.loads(sys.stdin.read()))
print(json.dumps(result))
```

The args dict (already resolved by jaq in Rust) is serialized as JSON to stdin.
The function's return value is captured from stdout as JSON.

### Python module convention

Functions accept keyword arguments and return JSON-serializable data:

```python
def list_similar_books(book_id: str, limit: int = 20) -> list[dict]:
    ...
    return books
```

No more `if __name__ == "__main__"` dispatch boilerplate.

### Auth passthrough

For skills that need auth (cookies, API keys), the `python:` executor should support passing auth context the same way `rest:` does. The args dict can include auth values:

```yaml
python:
  module: ./claude-api.py
  function: list_conversations
  args:
    session_key: .auth.sessionKey
    limit: .params.limit
```

## Rust Implementation Plan

### Where to add code

All paths relative to `/Users/joe/dev/agentos`.

#### 1. `crates/core/src/skills/types.rs` — Add the struct

Add `PythonExecutor` alongside the existing executor structs:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonExecutor {
    pub module: String,
    pub function: String,
    #[serde(default)]
    pub args: Option<IndexMap<String, serde_yaml::Value>>,
    #[serde(default)]
    pub timeout: Option<u64>,
    #[serde(default)]
    pub response: Option<ResponseMapping>,
}
```

Add the field to `Operation` (and `Utility` and `Step` if desired):

```rust
pub struct Operation {
    // ... existing fields ...
    #[serde(default)]
    pub python: Option<PythonExecutor>,
}
```

#### 2. `crates/core/src/executors/python.rs` — New file

Create the execution function. It should:
- Resolve the module path relative to the skill folder
- Generate the thin Python loader (import + call + json dump)
- Serialize the resolved args as JSON to stdin
- Shell out via `std::process::Command` (reuse patterns from `command.rs`)
- Parse stdout as JSON
- Apply `response.root` mapping if present

#### 3. `crates/core/src/skills/executor.rs` — Wire into dispatch

Add `extract_python` and `execute_python_action` functions.

Add them to both dispatch chains:

```rust
// In extract_operation_inner:
if let Some(ref python) = operation.python {
    return extract_python(skill, python, &params, account, auth_override);
}

// In execute_operation_inner:
if let Some(ref python) = operation.python {
    return execute_python_action(skill, python, &params, account, auth_override);
}
```

#### 4. No loader changes needed

Serde will deserialize `python:` blocks automatically once the struct fields exist.

### Key implementation details

**Arg resolution:** The `args` map values are jaq expressions (just like `rest.body` or `graphql.variables`). The Rust executor should resolve them against the params context using the existing `resolve_jaq_value` or equivalent, producing a `serde_json::Value` dict to serialize to stdin.

**Module path resolution:** Use the same path resolution as `command:` working_dir — resolve relative to the skill folder. The skill folder path is available on the `Skill` struct.

**Timeout default:** Use 30 seconds if not specified (matching current convention).

**Error handling:** If the Python process exits non-zero, capture stderr and return it as a structured error. If stdout isn't valid JSON, return a parse error with the raw output.

## Existing Executor Patterns for Reference

**REST** (`rest:`): `method`, `url`, `body`/`query`, `response.root` — see `skills/exa/readme.md`, `skills/todoist/readme.md`

**GraphQL** (`graphql:`): `query`, `variables`, `response.root`, top-level `api.graphql_endpoint` — see `skills/linear/readme.md`

**Command** (`command:`): `binary`, `args`, `stdin`, `working_dir`, `timeout`, `response` — see any Python skill

## Migration Test: Goodreads

After building the executor, migrate `skills/goodreads/readme.md` to use `python:` instead of `command:`. The current pattern across all 8 operations:

```yaml
# BEFORE (current)
command:
  binary: python3
  args:
    - "./public_graph.py"
    - "list_similar_books"
    - ".params.book_id"
    - '.params.limit // 20 | tostring'
  working_dir: .
  timeout: 30

# AFTER (new)
python:
  module: ./public_graph.py
  function: list_similar_books
  args:
    book_id: .params.book_id
    limit: '.params.limit // 20'
```

The Python module (`public_graph.py`) will need to be refactored:
- Remove the `main()` / `sys.argv` dispatch boilerplate
- Ensure each function accepts keyword args and returns JSON-serializable data
- The functions already do most of this; just remove the CLI wrapper layer

Verify with:
```bash
npm run validate -- goodreads
npm run mcp:test -- goodreads --verbose
```

## Full Scope of Python Command Usage (for future migration)

50 operations across 10 skills — all candidates for eventual migration:

| Skill | Ops | Module(s) | Dispatch pattern |
|---|---|---|---|
| goodreads | 8 | `public_graph.py` | subcommand + positional args |
| github | 10 | `github-cli.py` | subcommand + JSON stdin |
| kitty | 9 | `kitty-control.py` | subcommand + JSON stdin |
| claude | 6 | `claude-api.py`, `claude-login.py` | `--op` flag + named flags |
| macos-control | 6 | `macos_control.py` | subcommand + JSON stdin |
| austin-boulder-project | 5 | `abp.py` | subcommand + JSON stdin |
| copilot-money | 3 | `copilot-accounts.py`, `copilot-transactions.py` | JSON in args |
| chase | 2 | `chase-api.py` | subcommand + named flags |
| brave-browser | 1 | `get-cookie.py` | named flags |

The JSON-stdin skills (github, kitty, macos-control, abp) are the cleanest migration path after goodreads since they already pass structured data.

## CONTRIBUTING.md Update

After the executor is built and Goodreads is migrated, update `CONTRIBUTING.md` at `/Users/joe/dev/agentos-community/CONTRIBUTING.md`:

1. Add a `## Python Executor Shape` section (peer to Entity Skill Shape and Local Control Shape)
2. Add `python:` to the executor list in the Advanced Stuff section
3. Update the Helper Files section to reference the new pattern
4. Add a migration note: existing `command:` + `binary: python3` skills can adopt `python:` for cleaner YAML

## Repos

- Engine (Rust): `/Users/joe/dev/agentos`
- Skills (YAML + Python): `/Users/joe/dev/agentos-community`

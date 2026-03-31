# Python Skills

Use the `python:` executor when a skill needs Python logic (parsing, API glue, multi-step flows). It calls a function directly in a Python module — no `binary: python3` boilerplate, no `sys.argv` dispatch, no `| tostring` on every arg.

## Basic shape

```yaml
operations:
  get_schedule:
    description: Get today's class schedule
    returns: class[]
    params:
      date: { type: string, required: false }
      location_id: { type: integer, default: 6 }
    python:
      module: ./my_script.py
      function: get_schedule
      args:
        date: .params.date
        location_id: .params.location_id
      timeout: 30
```

The Python function receives keyword arguments and returns shape-native data — dicts whose keys match the declared shape:

```python
def get_schedule(date: str = None, location_id: int = 6) -> list[dict]:
    # ... fetch from API ...
    return [
        {
            "id": cls["id"],
            "name": cls["title"],
            "datePublished": cls["start_time"],
            "text": cls["description"],
            # shape-specific fields
            "instructor": cls.get("coach_name"),
            "capacity": cls.get("max_capacity"),
        }
        for cls in raw_classes
    ]
```

The function does the field mapping — it transforms raw API/service data into dicts matching the shape declared in `returns:`. No separate mapping layer is needed.

Rules:

- `module` is resolved relative to the skill folder (use `./my_script.py`)
- `function` is the function name in the module
- `args` values are jaq expressions resolved against the params context (same as `rest.body`)
- **Shorthand:** When the Python function expects a single `params` dict, use `params: true` instead of `args: { params: .params }`
- Args are passed as typed JSON — integers stay integers, no `| tostring` needed
- `timeout` defaults to 30 seconds
- `response` mapping (root, transform) works the same as `rest:` and `graphql:`
- Auth values are available via `.auth.*` in args expressions
- The runtime handles I/O — just return a value from your function

Examples: `gmail`, `claude`, `goodreads`, `granola`, `cursor`, `here-now`.

## Returning shape-native data

When an operation declares `returns: email[]`, the Python function must return a list of dicts matching the `email` shape. Use well-known fields (`id`, `name`, `text`, `url`, `image`, `author`, `datePublished`, `content`) plus any shape-specific fields.

```python
# gmail.py — returns email-shaped dicts directly
def get_email(id: str, url: str = None, _call=None) -> dict:
    # ... Gmail API logic ...
    return {
        "id": msg_id,
        "name": subject,                    # well-known: primary label
        "text": snippet,                     # well-known: preview text
        "url": f"https://mail.google.com/...",
        "datePublished": internal_date,      # well-known: temporal anchor
        "content": body_text,                # well-known: long body (FTS)
        # email-specific fields from shape
        "from_email": sender,
        "to": recipients,
        "labels": label_ids,
    }
```

For typed references (relations to other entities), return nested dicts keyed by entity type:

```python
def get_email(id: str, _call=None) -> dict:
    return {
        "id": msg_id,
        "name": subject,
        # typed reference — creates a linked account entity
        "from": {
            "account": {
                "handle": sender_email,
                "platform": "email",
                "display_name": sender_name,
            }
        },
    }
```

## Connection dispatch

When a skill has multiple connections that serve the same operations via different transports (SDK vs CLI, live API vs cache), the Python helper receives the active connection and dispatches accordingly:

```yaml
operations:
  list_items:
    description: List items from the service
    returns: item[]
    connection: [sdk, cli]
    python:
      module: ./my_skill.py
      function: list_items
      args:
        vault: .params.vault
        connection: '.connection'
      timeout: 60
```

```python
def list_items(vault, connection=None):
    if connection and connection.get("id") == "sdk":
        return _list_via_sdk(vault, connection["vars"])
    else:
        return _list_via_cli(vault, connection.get("vars", {}))
```

Both code paths return the same shape-native dicts. This pattern is useful when a primary path (SDK with batch ops) needs a stable fallback (CLI with subprocess calls). See `skills/granola/` for the `api` + `cache` variant of this pattern.

## `_call` dispatch

When a Python operation needs to compose multiple API calls (e.g. list returns stubs, get returns full data), use `_call` to invoke sibling operations. The engine injects `_call` automatically when the function signature accepts it.

```python
def list_emails(query="", limit=20, _call=None):
    stubs = _call("list_email_stubs", {"query": query, "limit": limit})
    return [_call("get_email", {"id": s["id"]}) for s in stubs]
```

The YAML wires the Python function as usual:

```yaml
operations:
  list_emails:
    description: List emails with full content
    returns: email[]
    python:
      module: ./gmail.py
      function: list_emails
      args:
        query: '.params.query // ""'
        limit: '.params.limit // 20'
      timeout: 120

  list_email_stubs:
    description: "Internal: list email IDs only"
    returns: email[]
    rest:
      url: "/messages"
      method: GET
      query:
        maxResults: ".params.limit // 20"
        q: ".params.query"
      response:
        transform: ".messages // []"
```

Rules:

- `_call` can only call operations in the **same skill** — no cross-skill calls
- The engine executes each dispatched call with full credential injection (OAuth, cookies, API keys)
- Python never sees raw credentials — the engine is the only process that touches tokens
- `_call` is synchronous and blocking — each call completes before the next starts
- The same `account` context from the parent call is used for dispatched operations
- If a function's signature does not include `_call` (or `**kwargs`), it is not injected — existing functions work unchanged

Leading by example: `skills/gmail/gmail.py` (list + hydrate pattern with `_call`).

# Data & Storage

## Sandbox storage

Skills can persist state across runs using two reserved keys on their graph node:

- **`cache`** — regeneratable state (discovered endpoints, scraped tokens). Can be cleared at any time; the skill re-discovers on next run.
- **`data`** — persistent state (settings, preferences, sync timestamps). Survives cache clears.

If losing it requires user action to recover (re-entering a setting), it's data. If the skill can regenerate it, it's cache.

### Reading

The execution context always includes `.data` and `.cache`:

```json
{ "params": { ... }, "auth": { ... }, "data": { ... }, "cache": { ... } }
```

In YAML expressions:

```yaml
rest:
  url: '(.cache.graphql_endpoint // "https://fallback.example.com/graphql")'
```

In Python, pass `cache` and/or `data` via `args:`:

```yaml
python:
  module: ./my_script.py
  function: search
  args:
    query: .params.query
    cache: .cache
```

### Writing back

Python and command executors write back using reserved keys in their return value:

- `__cache__` — merged into the skill node's cache
- `__data__` — merged into the skill node's data
- `__result__` — the actual result callers see

```python
def discover_endpoint(cache=None, **kwargs):
    if cache and cache.get("graphql_endpoint"):
        return {"endpoint": cache["graphql_endpoint"]}

    endpoint = _discover()
    return {
        "__cache__": {"graphql_endpoint": endpoint},
        "__result__": {"endpoint": endpoint},
    }
```

If neither `__cache__` nor `__data__` is present, the result passes through unchanged. Fully backward compatible.

### `__secrets__` — secret store writes

A third reserved key, `__secrets__`, handles importing secrets from external sources (password managers, payment info, identity documents, etc.) into the credential store. The `__secrets__` handler is pure credential store CRUD — it writes credential rows and strips the key. It does **not** create graph entities or edges; entity creation happens through the normal adapter pipeline processing `__result__`. The two systems are joined by `(issuer, identifier)`.

```python
def import_items(vault, dry_run=False):
    items = fetch_from_source(vault)
    if dry_run:
        return [{"issuer": i["issuer"], "label": i["label"]} for i in items]

    return {
        # Secrets → credential store (engine writes rows, strips key)
        "__secrets__": [
            {
                "item_type": "password",
                "issuer": "github.com",
                "identifier": "joe",
                "label": "GitHub",
                "source": "mymanager",
                "value": {"password": "..."},
                "metadata": {"masked": {"password": "••••••••"}}
            },
            {
                "item_type": "credit_card",
                "issuer": "chase",
                "identifier": "visa-4242",
                "label": "Personal Visa",
                "source": "mymanager",
                "value": {"card_number": "4111111111114242", "cvv": "123"},
                "metadata": {"masked": {"card_number": "••••4242", "cvv": "•••"}}
            }
        ],
        # Entities → shaped by adapters into graph nodes
        "__result__": [
            {"issuer": "github.com", "identifier": "joe", "title": "GitHub",
             "category": "LOGIN", "url": "https://github.com", "username": "joe"},
            {"issuer": "chase", "identifier": "visa-4242", "title": "Personal Visa",
             "category": "CREDIT_CARD", "cardholder": "Joe", "card_type": "Visa",
             "expiry": "12/2027", "masked": {"card_number": "••••4242", "cvv": "•••"}}
        ]
    }
```

The trust model: Python sees secrets (it reads them from the source), the engine intercepts and encrypts them, the agent never sees them — only `metadata` (including `masked` representations). Graph entities carry masked previews ("Visa ending in 4242") so the agent can reason about which card to use without seeing the full number.

See `spec/credential-system.md` and `spec/1password-integration.md` in the engine repo for full design.

**Status:** Implemented (Phase A). The engine intercepts `__secrets__` in `process_storage_writeback()`, writes credential rows to `credentials.sqlite`, creates account entities and `claims` edges on the graph, then strips the key before the MCP response.

Leading by example: `skills/goodreads/public_graph.py` (GraphQL endpoint discovery cached via `__cache__`).

## Expressions

Use one expression style everywhere:

- `rest:`, `graphql:`, `command:`, `python:`, and connection auth fields all use jq/jaq-style expressions
- Resolved credentials are available under `.auth.*` such as `.auth.key` or `.auth.access_token`

Common jq/jaq patterns:

```yaml
url: '"/items/" + .params.id'
query:
  q: .params.query
  limit: .params.limit // 10
body:
  title: .params.title
```

Common command patterns:

```yaml
command:
  binary: python3
  args:
    - ./my_script.py
    - run
  stdin: '.params | tojson'
```

When a `command:` argument or `working_dir:` looks like a relative file path, it is resolved relative to the skill folder. Prefer `./my_script.py` over machine-specific absolute paths.

If you need advanced command, steps, or crypto behavior, copy from an existing skill.

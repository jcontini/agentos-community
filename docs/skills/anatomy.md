# Skill Anatomy

## The short version

The current skill style is:

- Use `connections:` for external service dependencies (auth, base URLs)
- Use `returns:` on operations to declare the shape (entity type) the operation produces
- Python modules return dicts matching the shape schema directly — no mapping layer
- Use simple `snake_case` tool names like `search`, `read_webpage`, or `send_text`
- Use `operations:` for both entity-returning tools and local-control/action tools
- Use inline `returns:` schemas for non-entity or action-style tools
- Validate live behavior through the direct MCP path, not just by reading YAML

## Folder shape

Every skill is a folder like:

```text
skills/
  my-skill/
    skill.yaml           # required — executable manifest (connections, operations, …)
    readme.md            # recommended before ship — markdown instructions for agents (no YAML front matter)
    requirements.md      # recommended — scope out the API, auth model, and entities before writing YAML
    my_helper.py         # optional — Python helper when inline command logic gets complex
```

The runtime loads **only** `skill.yaml` for structure; `readme.md` is merged in as the instruction body (markdown only, no YAML front matter).

Start with `requirements.md` before writing skill YAML. Use it to scope out what endpoints or data surfaces exist, what auth model the service uses, which entities map to what, and any decisions or trade-offs. This is useful for any skill — not just reverse-engineered ones. For web skills without public APIs, it also becomes the place to log endpoint discoveries, header mysteries, and auth boundary mappings. See the [Reverse Engineering](../reverse-engineering/overview.md) section for that playbook.

## Entity skill shape

Use this pattern for normal data-fetching or CRUD-ish skills.

```yaml
id: my-skill
name: My Skill
description: One-line description
website: https://example.com

connections:
  api:
    base_url: "https://api.example.com"
    auth:
      type: api_key
      header:
        Authorization: '"Bearer " + .auth.key'
    label: API Key
    help_url: https://example.com/api-keys

operations:
  search:
    description: Search the service
    returns: result[]
    params:
      query: { type: string, required: true }
      limit: { type: integer, required: false }
    python:
      module: ./search.py
      function: search
      timeout: 30
```

The `returns: result[]` declaration points to a shape defined in `shapes/result.yaml`. The Python function returns a list of dicts whose keys match that shape's fields:

```python
def search(query: str, limit: int = 10, _call=None) -> list[dict]:
    # ... API logic ...
    return [
        {
            "id": item["url"],
            "name": item["title"],
            "text": item.get("summary"),
            "url": item["url"],
            "image": item.get("image"),
            "author": item.get("author"),
            "datePublished": item.get("published_at"),
        }
        for item in results
    ]
```

The Python code is where field mapping happens — it transforms raw API data into shape-native dicts. No separate mapping layer needed.

## Local control shape

Use this pattern for command-backed skills such as terminal, browser, OS, or app control. Local skills have no `connections:` block — they don't need external auth.

```yaml
id: my-local-skill
name: My Local Skill
description: Control a local surface
website: https://example.com

operations:
  list_status:
    description: Inspect local state
    returns:
      ok: boolean
      cwd: string
    command:
      binary: python3
      args:
        - -c
        - |
          import json, os
          print(json.dumps({"ok": True, "cwd": os.getcwd()}))
      timeout: 10
```

If you are starting a new skill from scratch, use `npm run new-skill -- my-skill` for an entity scaffold or `npm run new-skill -- my-skill --local-control` for a local-control scaffold.

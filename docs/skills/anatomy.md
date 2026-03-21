# Skill Anatomy

## The short version

The current skill style is:

- Use `connections:` for external service dependencies (auth, base URLs)
- Use `adapters:` for entity mappings
- Use simple `snake_case` tool names like `search`, `read_webpage`, or `send_text`
- Put canonical fields directly in the adapter body
- Treat the adapter body itself as the default mapping
- Use `operations:` for both entity-returning tools and local-control/action tools
- Use inline `returns:` schemas for non-entity or action-style tools
- Validate live behavior through the direct MCP path, not just by reading YAML

## Folder shape

Every skill is a folder like:

```text
skills/
  my-skill/
    skill.yaml           # required — executable manifest (connections, adapters, operations, …)
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
    header:
      Authorization: '"Bearer " + .auth.key'
    label: API Key
    help_url: https://example.com/api-keys

adapters:
  result:
    id: .url
    name: .title
    text: .summary
    url: .url
    image: .image
    author: .author
    datePublished: .published_at
    data.score: .score

operations:
  search:
    description: Search the service
    returns: result[]
    params:
      query: { type: string, required: true }
      limit: { type: integer, required: false }
    rest:
      method: POST
      url: /search
      body:
        query: .params.query
        limit: '.params.limit // 10'
      response:
        root: /results
```

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

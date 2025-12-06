# Contributing Skills

Thanks for contributing! Here's how to add a new skill.

## Quick Start

1. Fork this repo
2. Create `skills/{service-name}.md`
3. Add entry to `index.yaml`
4. Submit a PR

## Skill File Structure

```markdown
---
id: service-name
name: Service Name
description: One-line description
category: productivity  # productivity, communication, search, code, finance

icon: https://cdn.simpleicons.org/servicename
color: "#hexcolor"

auth:
  type: api_key          # api_key, oauth, local, cli
  header: Authorization  # Header name for API key
  prefix: "Bearer "      # Prefix before key (optional)
  help_url: https://...  # Where to get API key

api:
  type: rest             # rest, graphql, sqlite, local
  base_url: https://api.service.com
---

# Service Name

**Use for:** Brief description of use cases

## Quick Start

Show a simple curl example using the Passport proxy:

\```bash
curl -s http://localhost:1111/cloud/service-name/endpoint | jq .
\```

## API Reference

Document the key endpoints and operations...
```

## Auth Types

### api_key
Most common. User pastes an API key.

```yaml
auth:
  type: api_key
  header: Authorization    # or X-Api-Key, etc.
  prefix: "Bearer "        # prefix before key (use "" for none)
  help_url: https://...    # where to get the key
```

### oauth
For services using OAuth 2.0.

```yaml
auth:
  type: oauth
  auth_url: https://service.com/oauth/authorize
  token_url: https://service.com/oauth/token
  scopes:
    - read
    - write
```

### local
For local-only services (no API key needed).

```yaml
auth:
  type: local
local: true
```

## API Types

Permissions are enforced automatically based on API type:

```yaml
api:
  type: rest     # GET = See, POST/PUT/DELETE = Do
  # or
  type: graphql  # query = See, mutation = Do
  # or  
  type: sqlite   # SELECT = See, INSERT/UPDATE/DELETE = Do
  # or
  type: local    # Local execution (may require full access)
```

Users control "See" (read) and "Do" (write) permissions per account.

## Categories

- `productivity` — Task management, notes, bookmarks
- `communication` — Email, messaging, notifications
- `search` — Web search, content extraction
- `code` — GitHub, GitLab, code hosting
- `finance` — Banking, payments, accounting

## Index Entry

Add your skill to `index.yaml`:

```yaml
  - id: service-name
    name: Service Name
    description: One-line description
    category: productivity
    icon: https://cdn.simpleicons.org/servicename
    color: "#hexcolor"
    updated_at: "2025-01-15"
```

## Tips

1. **Test with curl first** — Make sure the API works before documenting
2. **Keep it concise** — AI reads this, so less is often more
3. **Show real examples** — Actual curl commands that work
4. **Note quirks** — API gotchas, rate limits, pagination

## Questions?

Open an issue or discussion!


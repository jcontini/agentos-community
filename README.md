# agentOS Skills

Open-source skill definitions for [agentOS](https://github.com/jcontini/agentos).

Skills teach AI agents how to use your connected apps — they're markdown files with API documentation and configuration.

## What's a Skill?

A skill is a markdown file with:
- **YAML frontmatter** — metadata (protocol, auth config, actions/API settings)
- **Instructions** — API docs the AI reads to make requests

### Two Protocol Types

**1. Shell Protocol** — Executes local commands (e.g., YouTube, Exa)

```yaml
---
id: youtube
name: YouTube
description: Get video transcripts and download videos
category: media
icon: https://cdn.simpleicons.org/youtube
color: "#FF0000"
protocol: shell

requires:
  - yt-dlp

actions:
  transcribe:
    description: Get transcript text from a YouTube video
    params:
      url:
        type: string
        required: true
        description: YouTube video URL
      lang:
        type: string
        default: en
        description: Subtitle language code
    run: |
      yt-dlp --skip-download --write-auto-sub \
        --sub-lang "$PARAM_LANG" "$PARAM_URL"
---

# YouTube

Instructions for using YouTube...
```

**2. REST/GraphQL Protocol** — Cloud APIs (e.g., Todoist, Linear)

```yaml
---
id: todoist
name: Todoist
description: Personal task management
category: productivity
icon: https://cdn.simpleicons.org/todoist
color: "#E44332"
protocol: rest  # or graphql

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  help_url: https://todoist.com/app/settings/integrations

api:
  type: rest
  base_url: https://api.todoist.com
---

# Todoist

API documentation here...
```

## Skill Schema

Skills have a YAML frontmatter section with metadata and a markdown body with instructions.

**Required fields:** `id`, `name`, `description`, `category`, `protocol`  
**Optional fields:** `icon`, `color`, `requires` (for shell), `actions` (for shell), `api` (for rest/graphql), `auth`

For complete schema documentation, examples, and all authentication types, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Available Skills

| Skill | Category | Protocol | Description |
|-------|----------|----------|-------------|
| [Todoist](skills/todoist/skill.md) | Productivity | Shell | Personal task management |
| [Linear](skills/linear/skill.md) | Productivity | Shell | Issue tracking and project management |
| [Exa](skills/exa/skill.md) | Search | Shell | Semantic web search |
| [Raindrop](skills/raindrop/skill.md) | Productivity | Shell | Bookmark management |
| [YouTube](skills/youtube/skill.md) | Media | Shell | Video transcripts and downloads |
| [Firecrawl](skills/firecrawl/skill.md) | Search | Shell | Web content extraction |
| [Computer](skills/computer/skill.md) | Productivity | Shell | macOS system control |

## Using Skills

Skills are fetched by the agentOS app when you browse and install them.

1. Open agentOS → Apps tab
2. Browse available skills
3. Click "Install" on any skill
4. Connect your account (API key)
5. Your AI agents can now use that service

**Updating Skills:** Click "Update Skill Definition" in the app detail view to re-download the latest version from this repo.

## Contributing

Want to add a skill for a new service? See [CONTRIBUTING.md](CONTRIBUTING.md).

### Validating Skills

Before submitting a PR, validate your skills:

```bash
npm install
npm run validate
```

This checks all skills against the schema and reports any errors or warnings.

## License

MIT

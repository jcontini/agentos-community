# AgentOS Community

Open-source plugins, components, apps, and agent configs for [AgentOS](https://github.com/jcontini/agentos).

## What's Here

```
plugins/           Service integrations (Linear, Todoist, Exa, etc.)
components/        Reusable UI building blocks
apps/              Capability renderers (Browser, Tasks, etc.)
agents/            Setup instructions for AI clients (Cursor, Claude, etc.)
```

## Plugins

Connect AgentOS to external services. Each plugin is YAML config + docs.

```
plugins/
  linear/
    readme.md       # YAML config + markdown docs
    icon.png        # Square icon
    tests/          # Integration tests
  todoist/
  exa/
  ...
```

| Category | Plugins |
|----------|---------|
| Tasks | todoist, linear |
| Messages | imessage, whatsapp |
| Databases | postgres, sqlite, mysql |
| Calendar | apple-calendar |
| Contacts | apple-contacts |
| Web | exa, firecrawl, reddit |
| Books | hardcover, goodreads |

## Components

Reusable UI pieces that compose atoms (text, image, icon, container).

```
components/
  url-bar/          # Location bar for browser views
  search-result/    # Search result card
  ...
```

## Apps

Render capabilities with components. Define how data is displayed.

```
apps/
  browser/          # Renders web_search, web_read
  ...
```

## Agents

Setup instructions for AI clients that use AgentOS via MCP.

```
agents/
  cursor/           # Cursor IDE setup
  claude/           # Claude Desktop setup
  raycast/          # Raycast setup
  ...
```

## Development

```bash
git clone https://github.com/jcontini/agentos-community
cd agentos-community
npm install    # Sets up pre-commit hooks
```

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for plugin development, testing, and contribution terms.

## License

**MIT** — see [LICENSE](LICENSE)

By contributing, you grant AgentOS the right to use your contributions in official releases, including commercial offerings. Your code stays open forever. See [CONTRIBUTING.md](CONTRIBUTING.md) for full terms.

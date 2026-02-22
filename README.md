# AgentOS Community

Skills, entities, apps, and themes for [AgentOS](https://github.com/jcontini/agentos).

---

## What is AgentOS?

**AgentOS is the semantic layer between AI assistants and your digital life.**

Your tasks are in Todoist. Your calendar is in Google. Your messages are split across iMessage, WhatsApp, Slack. Your files are everywhere. Each service is a walled garden—they don't talk to each other, and switching is painful.

**AgentOS fixes this.** It gives AI assistants a unified way to access all your services through a universal language. Your AI can manage tasks, read your calendar, send messages, and search the web—all through one interface, regardless of which service you use.

### The Vision

**You should own your digital life.** Not rent it. Not have it held hostage. Own it.

AgentOS creates a universal entity model—tasks, events, contacts, messages, files—that works across all services. A Todoist skill maps Todoist's API to the universal `task` entity. A Linear skill does the same. From your AI's perspective, they're identical: `task.list()`, `task.create()`, `task.complete()`.

This means:
- **Migration is trivial** — Switch from Todoist to Linear? Same entity, different backend
- **Cross-service queries work** — "Show tasks due today from all sources"
- **AI understands everything** — One schema, not 50 proprietary formats
- **You're in control** — Your data, your computer, your rules

### How It Works

```
┌──────────────────────────────────────────────────────────────┐
│                         YOUR SERVICES                        │
│    Todoist · Linear · Reddit · YouTube · Calendar · iMessage │
└──────────────────────────────┬───────────────────────────────┘
                               │ APIs
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                           SKILLS                             │
│  YAML configs: API endpoints, auth, field mappings (jaq)     │
│  One line routes content to body table: _body: .content      │
└──────────────────────────────┬───────────────────────────────┘
                               │ extract
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                     ENTITY GRAPH (SQLite)                     │
│  tasks · people · messages · videos · webpages · documents   │
│  + FTS5 full-text search across all content (BM25 ranking)   │
└──────────────────────────────┬───────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
         ┌─────────┐   ┌───────────┐   ┌─────────────┐
         │ Desktop  │   │  HTTP API │   │  MCP (AI)   │
         │  (apps)  │   │  (REST)   │   │  (agents)   │
         └─────────┘   └───────────┘   └─────────────┘
```

### What You Can Do

- **Let AI manage your tasks** — "Create a task to review the PR" → Done
- **Cross-service queries** — "What did I discuss with Sarah last week?" → Searches messages, emails, calendar
- **Full-text search across everything** — Search finds content inside YouTube transcripts, web scrapes, research reports, task descriptions — with highlighted excerpts and relevance ranking
- **Smart workflows** — "Every morning, summarize unread emails and add tasks for action items"
- **Easy migration** — Switch from Todoist to Linear without losing data or relationships

### For Everyone

**You don't need to be technical to use AgentOS.** Enable skills, connect your services, and your AI assistants can use them. The community builds the skills—you just use them.

**You don't need to code to contribute.** Found a bug? Want a new skill? Have an idea? Open an issue. The community is here to help.

---

## What's Here

```
entities/          Entity type definitions (the Memex model)
  _primitives/     Abstract base types (document, media, collection)
  _relationships/  Relationship types (contains, references, posts)
  task.yaml        Concrete entity types
  person.yaml
  video.yaml
  ...

skills/            Skills — service connections + agent context
  todoist/         Maps Todoist API → task, project, tag entities
  reddit/          Maps Reddit JSON → post, forum entities
  youtube/         Maps yt-dlp → video, channel, post entities
  curl/            Fetches URLs → webpage entities
  write-skill.md   Guide skills (AI context, no API binding)
  ...

apps/              Visual apps (UI experiences)
  videos/          Video player with channel info and embed
  memex/           Universal entity viewer and editor
  settings/        System preferences
  ...

themes/            Visual styling (CSS)
  os/
    macos9/        Mac OS 9 theme
    win98/         Windows 98 theme
```

### Entity Schemas

Entity types are defined in YAML. They declare properties, validation rules, operations, and display hints. The Rust engine reads these schemas — no hardcoded types.

### Skills

Skills connect to services — Todoist, Linear, YouTube, Reddit, iMessage. They're YAML configurations: API endpoints, auth, and field mappings expressed as jaq expressions. The Rust backend is a generic engine that evaluates expressions and creates entities.

| Skill | Entity | What it provides |
|-------|--------|------------------|
| todoist | task, project, tag | Task management with priorities and projects |
| linear | task, project | Engineering project management |
| reddit | post, forum | Posts and comments from Reddit |
| youtube | video, channel, post | Video metadata, transcripts, and comments |
| exa | webpage | Semantic web search and content extraction |
| firecrawl | webpage | Browser-rendered page scraping |
| curl | webpage | Simple URL fetching (no API key) |
| hackernews | post | Stories, comments, and discussions |
| apple-calendar | meeting, calendar | macOS Calendar events |
| apple-contacts | person | macOS Contacts |
| imessage | message, conversation, person | iMessage history |
| whatsapp | message, conversation, person | WhatsApp history |
| brave | webpage | Web search |
| cursor | document | Research reports from Cursor sub-agents |

### Body Content + Full-Text Search

Skills that produce rich content — transcripts, articles, self-posts, task descriptions — route it to a dedicated body table with one YAML line:

```yaml
transformers:
  video:
    mapping:
      title: .title
      description: .description
      _body: .transcript           # → stored in entity_bodies
      _body_role: '"transcript"'   # → keyed by role (default: "body")
```

FTS5 indexes bodies alongside entity names and data. Search returns BM25-ranked results with highlighted excerpts showing exactly where terms matched. Any skill that produces content becomes searchable automatically.

### Themes

Visual styling for the AgentOS desktop. Mac OS 9, Windows 98, and more.

---

## Contributing

**Anyone can contribute.** Found a bug? Want a new skill? Have an idea? [Open an issue](https://github.com/jcontini/agentos-community/issues) or see [CONTRIBUTING.md](CONTRIBUTING.md) for how to build skills.

**The community builds everything.** Skills, entities, apps, themes—all open source, all MIT licensed, all yours forever.

---

## License

**MIT** — see [LICENSE](LICENSE)

By contributing, you grant AgentOS the right to use your contributions in official releases, including commercial offerings. Your code stays open forever. See [CONTRIBUTING.md](CONTRIBUTING.md) for full terms.

---

## App Store

**The AgentOS App Store fetches items directly from this repository.** No backend servers, no infrastructure costs—GitHub IS the backend.

When you add or modify skills/entities/apps/themes, a GitHub Action automatically:
1. Scans the repository structure
2. Reads metadata from YAML front matter
3. Generates an updated `manifest.json`
4. Commits it back to the repo

**You never touch `manifest.json` manually!** Just add your files and the manifest updates automatically.

---

## For Developers

```bash
git clone https://github.com/jcontini/agentos-community
cd agentos-community
npm install    # Sets up pre-commit hooks
```

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for skill development, testing, and contribution guidelines.

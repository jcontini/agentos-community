# Contributing to the AgentOS Community

Declarative YAML for entities, plugins, components, apps, and themes.

**Schema reference:** `tests/plugins/plugin.schema.json` — the source of truth for plugin structure.

**Using an AI agent?** Have it read `AGENTS.md` for operational guidance and workflow patterns.

---

## Development Workflow

**Recommended:** Develop in `~/.agentos/installed/`, then copy here when ready.

```bash
# 1. Edit directly in installed folder (fast iteration)
vim ~/.agentos/installed/plugins/reddit/readme.md

# 2. Restart server and test
cd ~/dev/agentos && ./restart.sh
curl -X POST http://localhost:3456/api/plugins/reddit/post.list \
  -d '{"subreddit": "programming", "limit": 1}'

# 3. When working, copy to community repo
cp -r ~/.agentos/installed/plugins/reddit ~/dev/agentos-community/plugins/

# 4. Validate and commit
cd ~/dev/agentos-community
npm run validate
git add -A && git commit -m "Update Reddit plugin"
```

**Why this workflow:**
- Changes in `~/.agentos/installed/` take effect on server restart
- No copy step between edits — fast feedback
- Community repo stays clean — only tested code gets committed

---

## 🎉 Important: Manifest Auto-Generates!

**Never edit `manifest.json` manually!** 

When you add or modify plugins, apps, themes, or components, a GitHub Action automatically:
1. Scans the repository on push to `main`
2. Reads metadata from YAML front matter
3. Generates an updated `manifest.json`
4. Commits it back to the repo

The manifest is what powers the AgentOS App Store. Just add your files with proper metadata and it updates automatically.

### Setup: Auto-Resolve Manifest Conflicts

To avoid merge conflicts when GitHub Actions updates `manifest.json`, configure a merge driver that automatically regenerates it:

```bash
git config merge.regenerate-manifest.driver "scripts/merge-manifest.sh %O %A %B"
```

This ensures that when `manifest.json` conflicts occur (e.g., when GitHub Actions commits while you're working), Git will automatically regenerate the manifest instead of showing a conflict.

### How to Test Locally

```bash
# Regenerate manifest
node scripts/generate-manifest.js

# Validate without writing
node scripts/generate-manifest.js --check
```

---

## Architecture Overview

**Key insight: Apps contain models.** Apps are self-contained packages that include models (data schema), views, and components. When you install a plugin that provides `task` operations, you get a "Tasks" app on your desktop.

```
apps/              Self-contained app packages
  tasks/           Example: Tasks app
    models.yaml    Data models (task, project, label)
    icon.png       Desktop icon
    components/    UI components for this app
  posts/           Example: Posts app
    models.yaml    Data models (post)
    icon.png       Desktop icon
    components/
      post-item.tsx
      post-header.tsx
  operations.yaml  Shared operation definitions
  .needs-work/     Apps that need completion

plugins/           Adapters (how services map to app models)
  reddit/          Maps Reddit API → post model
  todoist/         Maps Todoist API → task model
  youtube/         Maps YouTube API → video model
  .needs-work/     Plugins that need completion

themes/            Visual styling (CSS)
```

**The flow:** 
1. Plugins declare which models they provide (via `adapters:` section)
2. Apps define models + views + components
3. Apps with `show_as_app: true` appear on the desktop when plugins support them
4. The viewer shell renders app views using app components + framework components

---

## Apps

Apps are self-contained packages that define models (data schemas), how to display them, and the components to render them.

**Structure:** `apps/{app}/models.yaml` + `icon.png` + `components/`

```
apps/
  posts/                    # App folder
    models.yaml             # Data models + views
    icon.png                # Desktop icon (PNG preferred, SVG fallback)
    components/
      post-item.tsx         # List item component
      post-header.tsx       # Detail view header
      comment-thread.tsx    # Nested comments
```

### Models Definition

A `models.yaml` file can contain multiple related models (e.g., task + project + label).

```yaml
# apps/posts/models.yaml

id: post
plural: posts
name: Post
description: A social media post, comment, or reply

references:
  schema_org: https://schema.org/SocialMediaPosting
  wikidata: Q7246757

properties:
  id: { type: string, required: true }
  title: { type: string }
  content: { type: string }
  author:
    type: object
    properties:
      name: { type: string, required: true }
      url: { type: string, format: url }
  # ... more properties

operations: [list, search, get]

display:
  primary: title
  secondary: author.name
  icon: message-square
  show_as_app: true         # Shows on desktop (default: false)

# Views define how to render each operation
views:
  list:
    title: "Posts"
    layout:
      - component: list
        data:
          source: activity
        item_component: post-item    # Resolves to app's components/
        item_props:
          title: "{{title}}"
          author: "{{author.name}}"
          # ...

  get:
    title: "{{activity.response.title}}"
    layout:
      - component: layout/scroll-area
        children:
          - component: post-header     # App component
          - component: text            # Framework component
          - component: comment-thread  # App component
```

### show_as_app

Controls whether a model appears as an app on the desktop:
- `show_as_app: true` — Main models (task, message, event, post, video, group)
- `show_as_app: false` (default) — Supporting models (project, label, calendar, conversation)

### Component Resolution

When a view references a component:
1. **App components** — Check `apps/{app}/components/`
2. **Framework components** — Check bundled `components/` (list, text, layout/*)

App components can override framework components for that app's views.

### Icon Loading

Desktop icons resolve in order:
1. `apps/{app}/icon.png` — PNG (preferred)
2. `apps/{app}/icon.svg` — SVG fallback
3. Lucide icon from `display.icon` field
4. First letter fallback

**Important:** If PNG exists, SVG is not loaded.

### Relationships

Defined in `apps/graph.yaml`:

```yaml
relationships:
  task_project:
    from: task
    to: project
    description: The project a task belongs to
```

When creating a plugin, check `apps/{app}/models.yaml` to see what properties to map.

---

## Plugins

Plugins are adapters that transform service-specific API responses into universal entities.

### Structure

```
plugins/{name}/
  readme.md     # Plugin definition (YAML front matter + markdown docs)
  icon.svg      # Required — vector icon (or icon.png)
  tests/        # Functional tests
```

**Common plugins** live at root: `plugins/todoist/`, `plugins/linear/`, `plugins/reddit/`

**Category folders** for organization when needed:
- `.needs-work/` — Plugins that need completion
- `government/us/national/` — Use ISO 3166 codes for government plugins

```yaml
# readme.md YAML front matter
id: todoist
name: Todoist
description: Personal task management
icon: icon.png
color: "#DE483A"            # Brand color for UI
tags: [tasks, todos]
display: browser            # Optional: how to display (browser, etc.)

website: https://todoist.com
privacy_url: https://...
terms_url: https://...

auth: { ... }               # Authentication config
adapters: { ... }           # How API data maps to entity schemas
operations: { ... }         # Entity CRUD (returns: entity, entity[], or void)
utilities: { ... }          # Helpers with custom return shapes (optional)
instructions: |             # AI notes — tips for using this plugin
  Plugin-specific notes for AI...

# Optional
requires: [...]             # System dependencies
handles: { urls: [...] }    # URL patterns this plugin routes
sources: { images: [...] }  # External resources for CSP
```

**Examples:** `plugins/todoist/` (REST API), `plugins/apple-calendar/` (Swift/native)

### Optional: Dependencies, URL Handlers, External Sources

**Dependencies** — system requirements:
```yaml
requires:
  - name: yt-dlp
    install: { macos: "brew install yt-dlp" }
```

**URL handlers** — route URLs to plugins:
```yaml
handles:
  urls: ["youtube.com/*", "youtu.be/*"]
```

### External Sources

Plugins can declare external resources they need:

```yaml
sources:
  images:
    - "i.ytimg.com"               # Video thumbnails
    - "yt3.ggpht.com"             # Channel avatars
  api:
    - "https://api.example.com/*" # API endpoints
```

| Category | Purpose |
|----------|---------|
| `images` | External images — proxied by server to bypass hotlink protection |
| `api` | REST/GraphQL endpoints (CSP) |

**Image Proxy:**

External images often fail due to hotlink protection (403 errors). When you declare `sources.images`, the server will proxy requests through `/api/proxy/image`. Entity components use `getProxiedSrc()` to rewrite URLs automatically.

```typescript
// In entity components
function getProxiedSrc(src: string | undefined): string | undefined {
  if (!src) return undefined;
  if (src.startsWith('/') || src.startsWith('data:') || src.startsWith('blob:')) return src;
  if (src.startsWith('http://') || src.startsWith('https://')) {
    return `/api/proxy/image?url=${encodeURIComponent(src)}`;
  }
  return src;
}

// Usage
<img src={getProxiedSrc(thumbnail_url)} alt={title} />
```

**Important:** Only domains declared in `sources.images` will be proxied. Undeclared domains return 403.

### Adapters

Map API fields to entity properties. Defined once, applied to all operations.

```yaml
adapters:
  task:
    terminology: Task           # What the service calls it
    relationships:              # Which graph relationships this plugin supports
      task_project: full        # full | read_only | write_only | none
      task_labels: full
    mapping:
      id: .id
      title: .content
      completed: .checked
      priority: 5 - .priority   # Invert: Todoist 4=urgent → AgentOS 1=highest
      due_date: .due.date?      # Optional field
      _project_id: .project_id  # Relationship data (underscore prefix)
```

**Relationship fields** use underscore prefix (`_project_id`) — these connect to `graph.yaml` relationships.

**Dot syntax** for nested objects: `author.name: .data.author` creates `{ author: { name: ... } }`

**See real examples:** `plugins/reddit/readme.md`, `plugins/todoist/readme.md`

### Operations

Entity CRUD. **Naming:** `entity.operation` — `task.list`, `webpage.search`, `event.create`

**Return types:** `entity` (single), `entity[]` (array), `void` (no data)

### Executors

| Executor | Use case | Example plugin |
|----------|----------|----------------|
| `rest` | HTTP APIs | `plugins/todoist/` |
| `graphql` | GraphQL APIs | `plugins/linear/` |
| `swift` | macOS native APIs | `plugins/apple-calendar/` |
| `command` | Shell commands | `plugins/reddit/` (group.get) |
| `sql` | Database queries | — |

**REST example:**
```yaml
operations:
  task.list:
    description: List actionable tasks
    returns: task[]
    web_url: https://app.todoist.com/app/today
    rest:
      method: GET
      url: https://api.todoist.com/api/v1/tasks/filter
      query:
        query: .params.query
      response:
        root: /results
```

**Dynamic URLs:** `url: '"https://api.example.com/tasks/" + .params.id'`

**`web_url`:** Links to web interface (jaq expression)

### Expression Syntax (jaq)

All values use jaq expressions (Rust jq). Access `.params.*`, do math, conditionals:

| Pattern | Example |
|---------|---------|
| Dynamic URL | `'"https://api.example.com/tasks/" + .params.id'` |
| Query param | `.params.limit \| tostring` |
| URL encode | `.params.query \| @uri` |
| Math | `5 - .params.priority` |
| Conditional | `'if .params.feed == "new" then "story" else "front_page" end'` |
| Unix → ISO | `.created_utc \| todate` |
| Static string | `'"Bearer "'` |
| Optional | `.due.date?` |

**See examples:** `plugins/todoist/readme.md`, `plugins/hackernews/readme.md`

### Utilities

Helpers returning custom shapes (not entities). **Naming:** `verb_noun` — `move_task`, `get_teams`

**See examples:** `plugins/todoist/readme.md` (move_task), `plugins/linear/readme.md` (get_teams, setup)

### Advanced

**Mutation handlers** — when API can't update a field normally:
```yaml
adapters:
  task:
    relationships:
      task_project:
        support: full
        mutation: move_task  # Routes changes through utility
```

**Operation-level mapping** — when API returns different shapes:
```yaml
response:
  mapping:           # Override adapter mapping for this operation
    url: .url
    title: .title
```

### Response Transforms

For complex API responses, use `response.transform` with jaq/jq:

```yaml
response:
  transform: |
    def map_comment: { id: .id, content: .text, replies: [.children[]? | map_comment] };
    { objectID: (.id | tostring), replies: [.children[]? | map_comment] }
  root: /data
```

**Pipeline:** API Response → `transform` → `root` → Adapter mapping

**See examples:** `plugins/reddit/readme.md` (post.get), `plugins/hackernews/readme.md` (post.get)

---

## Components

App components live in `apps/{app}/components/`. They compose framework primitives — never custom CSS.

**Key rules:**
- Use `data-*` attributes for styling: `data-component="text" data-variant="title"`
- Proxy external images with `getProxiedSrc()` (see `apps/posts/components/post-item.tsx`)
- Export default: `export default MyComponent`

**See examples:** `apps/posts/components/`, `apps/groups/components/`

---

## Testing

```bash
npm run validate              # Schema + test coverage (run first!)
npm test                      # Functional tests
npm test plugins/exa/tests    # Single plugin
```

**Validation** checks: schema structure, test coverage, required files (icon).

**`.needs-work/`** — Plugins that fail validation are auto-moved here. Fix issues, run `npm run validate`, then move back.

**Writing tests:** See `plugins/todoist/tests/todoist.test.ts` for examples. Every operation needs at least one test.

---

## Commands

```bash
npm run new-plugin <name>    # Create plugin scaffold
npm run validate             # Schema validation (run first!)
npm test                     # Functional tests (excludes .needs-work)
npm run test:needs-work      # Test plugins in .needs-work
```

---

## License

MIT licensed. Contributions are MIT licensed and may be used in official releases including commercial offerings.

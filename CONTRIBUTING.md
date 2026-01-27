# Contributing to the AgentOS Community

Declarative YAML for entities, plugins, components, apps, and themes.

**Schema reference:** `tests/plugins/plugin.schema.json` — the source of truth for plugin structure.

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

```
entities/          Universal schemas (what a task/message/webpage IS)
  graph.yaml       Relationships between entities
  task.yaml        Task schema
  webpage.yaml     Webpage schema
  ...

plugins/           Adapters (how services map to universal entities)
  tasks/           Category folder
    todoist/       Maps Todoist API → task entity
    linear/        Maps Linear API → task entity
  search/          Category folder
    exa/           Maps Exa API → webpage entity
  calendar/
    apple-calendar/
  .needs-work/     Plugins that need completion
    communication/
    government/
      us/
        national/  Federal agencies (USPTO, etc.)
        us-tx/     State agencies (TxDOT, etc.)

components/        UI building blocks (TSX)
apps/              Activity → component wiring (YAML)
themes/            Visual styling (CSS)
```

**The flow:** Entities define universal schemas → Plugins adapt service APIs to those schemas → Components render the data.

---

## Entities

Entities are universal schemas that define what something IS, regardless of which service provides it.

**Location:** `entities/{entity}.yaml`

```yaml
id: task
name: Task
description: A unit of work to be done

properties:
  id: { type: string, required: true }
  title: { type: string, required: true }
  completed: { type: boolean, default: false }
  priority: { type: integer, min: 1, max: 4 }
  due_date: { type: date }
  # ...

operations: [list, get, create, update, delete, complete]
```

**Relationships** are defined in `entities/graph.yaml`:

```yaml
relationships:
  task_project:
    from: task
    to: project
    description: The project a task belongs to

  task_labels:
    from: task
    to: label
    description: Labels applied to the task
```

When creating a plugin, check `entities/{entity}.yaml` to see what properties to map.

---

## Plugins

Plugins are adapters that transform service-specific API responses into universal entities.

### Structure

Plugins are organized into category folders based on entity type or domain:

```
plugins/{category}/{name}/
  readme.md     # Plugin definition (YAML front matter + markdown docs)
  icon.svg      # Required — vector icon
  tests/        # Functional tests
```

**Category types:**
- **Entity-type categories:** `calendar/`, `contacts/`, `tasks/`, `search/`, `messages/`
- **Domain categories:** `communication/`, `development/`, `social/`, `databases/`, `domains/`, `storage/`, `media/books/`
- **Government plugins:** Use ISO 3166 codes — `government/us/national/`, `government/us/us-tx/`

```yaml
# readme.md YAML front matter
requires:     # System dependencies (optional)
handles:      # URL patterns this plugin routes (optional)
sources:      # External resources for CSP (optional)
adapters:     # How API data maps to entity schemas
operations:   # Entity CRUD (returns: entity, entity[], or void)
utilities:    # Helpers with custom return shapes (optional)
```

**Examples:** `plugins/tasks/todoist/` (REST API), `plugins/calendar/apple-calendar/` (Swift/native)

### Dependencies

Plugins can declare system dependencies that must be installed:

```yaml
requires:
  - name: yt-dlp
    install:
      macos: brew install yt-dlp
      linux: sudo apt install -y yt-dlp
      windows: choco install yt-dlp -y
```

| Field | Description |
|-------|-------------|
| `name` | Dependency name (shown to user) |
| `install.macos` | macOS install command |
| `install.linux` | Linux install command |
| `install.windows` | Windows install command |

The system checks if dependencies are available and shows install instructions if missing.

### URL Handlers

Plugins can register for URL patterns. When AI calls `url.read(url)`, the system routes to the appropriate plugin:

```yaml
handles:
  urls:
    - "youtube.com/*"
    - "youtu.be/*"
    - "music.youtube.com/*"
```

**Pattern syntax:**
- `*` matches any characters within a path segment
- Patterns match against the URL's host + path (without protocol)
- First matching plugin wins (order defined in Settings)

**Example flow:**
1. AI calls `url.read("https://youtube.com/watch?v=abc123")`
2. System matches `youtube.com/*` → routes to YouTube plugin
3. YouTube plugin returns a `video` entity
4. Browser displays video view (entity routing)

### External Sources

Plugins can declare external resources they need. The server uses these to build Content Security Policy (CSP) headers dynamically:

```yaml
sources:
  images:
    - "https://i.ytimg.com/*"      # Video thumbnails
    - "https://yt3.ggpht.com/*"    # Channel avatars
  api:
    - "https://api.example.com/*"  # API endpoints
  scripts:
    - "https://cdn.example.com/*"  # External scripts (use sparingly)
  styles:
    - "https://fonts.googleapis.com/*"
  fonts:
    - "https://fonts.gstatic.com/*"
```

| Category | CSP Directive | Use for |
|----------|---------------|---------|
| `images` | `img-src` | Thumbnails, avatars, covers |
| `api` | `connect-src` | REST/GraphQL endpoints |
| `scripts` | `script-src` | External JavaScript |
| `styles` | `style-src` | External CSS |
| `fonts` | `font-src` | Web fonts |

**How it works:**
- Server collects sources from all enabled plugins at startup
- CSP header is built dynamically based on enabled plugins
- Disabling a plugin removes its sources from the allowlist
- Resources from undeclared sources are blocked by the browser

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
      title: .content           # API field → entity property
      completed: .is_completed
      priority: ".priority | invert:5"  # Transform if needed
      _project_id: .project_id  # Relationship data (underscore prefix)
```

**Relationship fields** use underscore prefix (`_project_id`) — these connect to `graph.yaml` relationships.

### Operations

Entity CRUD. Return type determines which adapter mapping applies.

**Naming:** `entity.operation` — `task.list`, `webpage.search`, `event.create`

**Return types:** `entity` (single), `entity[]` (array), `void` (no data returned)

```yaml
operations:
  task.list:
    description: List all tasks
    returns: task[]
    rest:
      method: GET
      url: https://api.example.com/tasks
      response:
        root: "/data"           # JSON Pointer — must start with /
```

### Executors

Each operation uses exactly one executor. Available types:

| Executor | Use case | Required fields |
|----------|----------|-----------------|
| `rest` | HTTP APIs | `url`, optional `method`, `query`, `body` |
| `graphql` | GraphQL APIs | `query`, optional `variables` |
| `sql` | Database queries | `query` |
| `swift` | macOS native APIs | `script` |
| `command` | Shell commands | `binary` |
| `csv` | CSV file parsing | `path` |

#### REST Executor

```yaml
operations:
  task.list:
    returns: task[]
    rest:
      method: GET
      url: https://api.example.com/tasks
      query:
        filter: "{{params.filter}}"
      response:
        root: "/data"
```

#### SQL Executor

```yaml
operations:
  message.list:
    returns: message[]
    sql:
      query: |
        SELECT id, text, date FROM messages
        WHERE conversation_id = '{{params.conversation_id}}'
        ORDER BY date DESC
        LIMIT {{params.limit | default: 50}}
```

#### Swift Executor (macOS only)

For native macOS APIs (EventKit, Contacts, etc.):

```yaml
operations:
  event.list:
    returns: event[]
    swift:
      script: |
        import EventKit
        import Foundation
        
        // Swift code that prints JSON to stdout
        let args = CommandLine.arguments
        let days = args.count > 1 ? Int(args[1]) ?? 7 : 7
        // ... implementation ...
        print(jsonString)
      args:
        - "{{params.days}}"
        - "{{params.calendar_id}}"
```

#### Command Executor

```yaml
operations:
  file.list:
    returns: file[]
    command:
      binary: /usr/bin/find
      args:
        - "{{params.path}}"
        - "-type"
        - "f"
```

### Template Syntax

Parameters are substituted using `{{params.name}}` syntax:

```yaml
params:
  limit: { type: integer, default: 50 }
  query: { type: string }

rest:
  url: https://api.example.com/search
  query:
    q: "{{params.query}}"
    limit: "{{params.limit}}"
```

**Filters:** `{{params.limit | default: 50}}` — provides fallback value

### Utilities

Helpers returning custom shapes (not entities).

```yaml
utilities:
  move_task:
    description: Move task to different project
    params:
      id: { type: string, required: true }
      project_id: { type: string, required: true }
    returns:
      success: boolean
    rest: ...
```

**Naming:** `verb_noun` — `move_task`, `get_teams`

### Key Rules

| Rule | Details |
|------|---------|
| JSON Pointer for `response.root` | Must start with `/` (e.g., `/data`, `/results/0`) |
| Single source of truth | Mapping in adapters, not duplicated per operation |
| Relationship fields use `_` prefix | `_project_id`, `_parent_id` |
| Handle API quirks internally | Use mutation handlers, not instructions |

### Mutation Handlers

When an API can't update a field through the normal endpoint:

```yaml
adapters:
  task:
    relationships:
      task_project:
        support: full
        mutation: move_task  # Routes project_id changes through utility
```

### Operation-Level Mapping Override

When API returns different shapes per operation:

```yaml
operations:
  webpage.search:
    returns: webpage[]
    rest:
      response:
        mapping:           # Override adapter mapping
          url: .url
          title: .title    # Search results lack full content
```

### Checklist

- [ ] `icon.svg` exists (vector icon required)
- [ ] Plugin is in the correct category folder
- [ ] `npm run validate` passes (schema validation)
- [ ] Parameters verified against API docs
- [ ] Mapping covers entity properties (`entities/{entity}.yaml`)
- [ ] Relationship fields use `_` prefix
- [ ] API quirks handled internally
- [ ] Functional tests pass (`npm test`)

---

## Components

TSX files dynamically loaded and transpiled by the server.

**Location:** `components/{name}.tsx` or `components/{category}/{name}.tsx`

```
components/
  list.tsx           # Core primitives
  text.tsx
  markdown.tsx
  layout/
    stack.tsx        # Layout components
    scroll-area.tsx
  items/
    search-result.tsx   # Item renderers for lists
    history-item.tsx
```

### Rules

1. **Import React explicitly** — `import React from 'react'`
2. **Export default** — `export default MyComponent`
3. **TypeScript interfaces for props** — document your component's API
4. **No heavy deps** — avoid Zod, lodash, etc. (breaks ESM bundling)
5. **Accept both `children` and `content`** — YAML templates use `content` prop

### Example Component

```tsx
import React from 'react';

interface MyItemProps {
  title: string;
  description?: string;
  // For YAML templates, accept content as alternative to children
  content?: string;
  children?: React.ReactNode;
}

export function MyItem({ title, description, content, children }: MyItemProps) {
  return (
    <div className="my-item">
      <span className="my-item-title">{title}</span>
      {description && <span className="my-item-desc">{description}</span>}
      {children ?? content}
    </div>
  );
}

export default MyItem;
```

### Styling

Components use class names that themes style. Add your component's CSS to the theme:

```css
/* In themes/os/macos9/theme.css */
.my-item {
  padding: 8px;
  border-bottom: 1px solid var(--border-color);
}
.my-item-title {
  font-weight: bold;
}
```

---

## Apps

Apps wire activities to components. They define what shows up when AI uses a capability.

**Location:** `apps/{name}/app.yaml` with `icon.svg`

```
apps/
  browser/
    app.yaml      # App definition
    icon.svg      # App icon (shows on desktop)
  settings/
    app.yaml
    icon.svg
```

### Basic Structure

```yaml
id: browser
name: Browser
icon: icon.svg
description: Watch AI search the web and read pages

# Entity types this app displays
entities:
  - webpage

# Menu bar (when app is focused)
menus:
  - name: Browser
    items:
      - label: About Browser
        action: open_view
        view: about
  - name: History
    action: open_view    # Direct click (no dropdown)
    view: history

# Views define what to show for different activities
views:
  search:
    entity: webpage
    operation: search
    title: Browser
    toolbar: [...]
    layout: [...]

  read:
    entity: webpage
    operation: read
    title: "{{activity.response.title}}"
    layout: [...]

default_view: search
```

### Menus

Apps can define menus that appear in the menu bar when focused.

**Dropdown menus** have `items`:

```yaml
menus:
  - name: File
    items:
      - label: New Window
        action: new_window
        shortcut: "⌘N"
      - separator: true
      - label: Close
        action: close
```

**Direct-action menus** have `action` (clickable, no dropdown):

```yaml
menus:
  - name: History
    action: open_view
    view: history
```

**Actions:**
- `open_view` — Opens a new window with the specified view
- `about` — Opens the app's about view
- `close` — Closes the focused window

### Views

Views define how to display activities. There are two types:

**Activity-driven views** — triggered by AI activity:

```yaml
views:
  search:
    entity: webpage        # Which entity type
    operation: search      # Which operation
    title: Browser
    layout:
      - component: list
        data:
          source: activity   # Use the triggering activity's response
        item_component: items/search-result
        item_props:
          title: "{{title}}"
          url: "{{url}}"
```

**Static views** — not tied to activities (About, Settings, etc.):

```yaml
views:
  about:
    title: About Browser
    layout:
      - component: layout/stack
        props:
          gap: 16
          align: center
        children:
          - component: text
            props:
              content: "Browser"
              variant: title
          - component: text
            props:
              content: "Watch AI search the web"
              variant: body
```

### Data Sources

**`source: activity`** — Uses the current activity's response:

```yaml
layout:
  - component: list
    data:
      source: activity    # Response from the triggering activity
    item_component: items/search-result
    item_props:
      title: "{{title}}"  # Each item in response array
```

**`source: activities`** — Queries activity history:

```yaml
layout:
  - component: list
    data:
      source: activities   # Query all matching activities
      entity: webpage      # Filter by entity
      limit: 100
    item_component: items/history-item
    item_props:
      operation: "{{operation}}"
      title: "{{response.title}}"
      query: "{{request.params.query}}"
      timestamp: "{{created_at}}"
```

### Template Syntax

Props support template expressions with `{{...}}`:

```yaml
# Access activity data
title: "{{activity.response.title}}"
query: "{{activity.request.params.query}}"
source: "{{activity.connector}}"

# In list items, access item data directly
title: "{{title}}"
url: "{{url}}"

# Fallback with ||
title: "{{response.title || request.params.query}}"
```

### Layout Components

Compose layouts with container components:

```yaml
layout:
  - component: layout/stack
    props:
      gap: 16
      direction: vertical    # or horizontal
      align: center          # start, center, end
      padding: 24
    children:
      - component: text
        props:
          content: "Hello"
      - component: text
        props:
          content: "World"
```

**Available layout components:**
- `layout/stack` — Vertical or horizontal stack with gap
- `layout/scroll-area` — Scrollable container
- `layout/split-view` — Side-by-side panels

### Toolbar

Views can have a toolbar above the main layout:

```yaml
views:
  search:
    toolbar:
      - component: url-bar
        props:
          mode: search
          value: "{{activity.request.params.query}}"
    layout:
      - component: list
        # ...
```

### Example: Complete App

```yaml
id: tasks
name: Tasks
icon: icon.svg
description: View and manage tasks

entities:
  - task

menus:
  - name: Tasks
    items:
      - label: About Tasks
        action: open_view
        view: about
  - name: History
    action: open_view
    view: history

views:
  list:
    entity: task
    operation: list
    title: Tasks
    layout:
      - component: list
        data:
          source: activity
        item_component: items/task-item
        item_props:
          title: "{{title}}"
          completed: "{{completed}}"
          due_date: "{{due_date}}"

  about:
    title: About Tasks
    layout:
      - component: layout/stack
        props:
          gap: 16
          align: center
          padding: 24
        children:
          - component: text
            props:
              content: "Tasks"
              variant: title
          - component: text
            props:
              content: "View and manage your tasks"
              variant: body

  history:
    title: Task History
    layout:
      - component: layout/scroll-area
        children:
          - component: list
            data:
              source: activities
              entity: task
              limit: 100
            item_component: items/history-item
            item_props:
              operation: "{{operation}}"
              title: "{{response.title || request.params.title}}"
              timestamp: "{{created_at}}"

default_view: list
```

---

## Themes

CSS and assets in `themes/{family}/{theme-id}/`.

**Example:** `themes/os/macos9/`

---

## Testing

### Test Types

| Type | Command | What it checks |
|------|---------|----------------|
| **Validation** | `npm run validate` | Schema + test coverage — run this first |
| **Functional tests** | `npm test` | Actually calls APIs, verifies behavior |

### Validation

`npm run validate` checks three things:

1. **Schema validation** — YAML structure matches `tests/plugins/plugin.schema.json`
2. **Test coverage** — every operation and utility has a test
3. **Required files** — `icon.svg` exists

```bash
npm run validate                    # All plugins
npm run validate -- --filter exa    # Single plugin
npm run validate -- --no-move       # Validate without auto-moving failures
```

**Auto-move behavior:** By default, plugins that fail validation are automatically moved to `plugins/.needs-work/`. This keeps the main plugins directory clean. Use `--no-move` to disable this (useful for pre-commit hooks).

A plugin fails validation if any operation/utility lacks a test. The validator looks for `tool: 'operation.name'` in your test files.

**Test structure:** Tests are organized by domain:
- `tests/plugins/` — Plugin schema and operations tests
- `tests/entities/` — Entity schema and graph validation

### Functional Tests

Verify real API behavior:

```bash
npm test                                              # All tests (excludes .needs-work)
npm run test:needs-work                               # Only plugins in .needs-work
npm test plugins/search/exa/tests                     # Single plugin
npm test plugins/.needs-work/communication/whatsapp   # Specific .needs-work plugin
```

**Note:** Tests automatically exclude plugins in `plugins/.needs-work/` to focus on working plugins. You can still test specific plugins in `.needs-work` by specifying their path directly.

### The `.needs-work` Folder

Plugins that need completion live in `plugins/.needs-work/`, organized by category:

```
plugins/.needs-work/
  communication/
    whatsapp/
  government/
    us/
      national/
        uspto/
      us-tx/
        tx-dot/
```

**What goes in `.needs-work`:**
- Missing `icon.svg`
- Schema validation errors
- Missing tests for operations/utilities
- Work-in-progress plugin specs

To fix a plugin in `.needs-work`:
1. Fix the issues (add icon, fix schema, add tests)
2. Run `npm run validate` to verify
3. Move it to the working category: `mv plugins/.needs-work/tasks/my-plugin plugins/tasks/my-plugin`

### Writing Tests

Tests live in `plugins/{category}/{name}/tests/{name}.test.ts`. Every operation needs at least one test.

```typescript
import { aos, TEST_PREFIX } from '../../../../tests/utils/fixtures';

describe('My Plugin', () => {
  it('operation.list returns array', async () => {
    const result = await aos().call('UsePlugin', {
      plugin: 'my-plugin',
      tool: 'entity.list',  // This tool is now marked as tested
      params: {},
    });
    expect(Array.isArray(result)).toBe(true);
  });
});
```

See `plugins/tasks/todoist/tests/` or `plugins/calendar/apple-calendar/tests/` for comprehensive examples.

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

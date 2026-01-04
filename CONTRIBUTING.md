# Contributing to AgentOS Integrations

## Mental Model

```
┌─────────────────────────────────────────────────────────────────────┐
│  INTERFACES: MCP Server • HTTP API • CarPlay • Widgets • ...       │
│  (All call into the same AgentOS Core)                              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  APPS: Tasks • Books • Messages • Calendar • Finance • Databases   │
│  Location: apps/{app}/                                              │
│    - readme.md: schema, actions, params, returns                    │
│    - schema.sql: database tables (optional, for data apps)          │
│    - icon.svg: app icon                                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CONNECTORS: todoist • linear • goodreads • hardcover • postgres   │
│  Location: connectors/{connector}/                                  │
│    - readme.md: auth config                                         │
│    - {app}.yaml: action→executor mappings with transforms          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  EXECUTORS: rest: • graphql: • sql: • csv: • command: • app:       │
│  Location: AgentOS Core (Rust)                                      │
└─────────────────────────────────────────────────────────────────────┘
```

| Layer | What | Location |
|-------|------|----------|
| **App** | Capability with unified schema | `apps/{app}/` |
| **Connector** | Service implementation + transforms | `connectors/{connector}/` |
| **Executor** | Protocol handler (Rust) | AgentOS Core |

---

## Two Types of Apps

### 1. Pass-through Apps (e.g., Tasks, Calendar)
Data lives in external services. AgentOS queries them directly.

```
User → AgentOS → Linear API → Response
```

### 2. Data Apps (e.g., Books, Movies, Music)
Data is pulled into a local SQLite database for unified access.

```
User → AgentOS → Local SQLite → Response
                     ↑
         Pull from Goodreads CSV
         Push to Hardcover API
```

**Data apps have:**
- `schema:` in readme.md — defines database tables (auto-generated from YAML)
- Per-app database at `~/.agentos/data/{app}.db`
- Auto-generated CRUD actions (list, get, create, update, delete)
- Custom pull/push actions via connectors

---

## App Structure

### Pass-through App
```
apps/tasks/
  readme.md     # Schema + actions
  icon.svg
```

### Data App
```
apps/books/
  readme.md     # Schema + actions (schema: section triggers DB creation)
  icon.svg
```

When `schema:` exists in readme.md, AgentOS automatically:
1. Creates `~/.agentos/data/{app}.db`
2. Generates tables from YAML schema
3. Exposes CRUD actions (list, get, create, update, delete)

---

## Adding a Data App

### 1. Create the App

**`apps/books/readme.md`** — Schema in YAML auto-generates database tables
```yaml
schema:
  book:
    id: { type: string, required: true }
    title: { type: string, required: true }
    authors: { type: array }
    isbn: { type: string }
    status: { type: enum, values: [want_to_read, reading, read, dnf] }
    rating: { type: number, min: 1, max: 5 }
    review: { type: string }
    date_added: { type: datetime }
    date_finished: { type: datetime }
    tags: { type: array }
    refs: { type: object }        # IDs in external systems
    metadata: { type: object }    # Connector-specific extras

actions:
  list:
    description: List books with filters
  get:
    description: Get a single book
  create:
    description: Add a book
  update:
    description: Update a book
  delete:
    description: Remove a book
  pull:
    description: Pull from a connector (Goodreads CSV, Hardcover API)
  push:
    description: Push to a connector (Hardcover API)
```

### 2. Create Connectors

**`connectors/goodreads/books.yaml`** — Pull from CSV
```yaml
actions:
  pull:
    # Chained executor: csv reads file, app upserts to database
    - csv:
        path: "{{params.path}}"
        response:
          mapping:
            # Core metadata
            title: "[].'Title'"
            authors: "[].'Author' | to_array"
            
            # Personal data
            status: |
              [].'Exclusive Shelf' == 'to-read' ? 'want_to_read' :
              [].'Exclusive Shelf' == 'currently-reading' ? 'reading' :
              [].'Exclusive Shelf' == 'read' ? 'read' : 'none'
            rating: "[].'My Rating' | to_int"
            review: "[].'My Review'"
            tags: "[].'Bookshelves' | split:,"
            
            # Dates (convert / to - for ISO format)
            date_added: "[].'Date Added' | replace:/:-"
            date_finished: "[].'Date Read' | replace:/:-"
            
            # Refs (IDs in external systems)
            refs:
              goodreads: "[].'Book Id'"
              isbn: "[].'ISBN' | strip_quotes"
              isbn13: "[].'ISBN13' | strip_quotes"
      as: records
    
    - app:
        action: upsert
        table: books
        on_conflict: refs.goodreads
        data: "{{records}}"
```

**`connectors/hardcover/books.yaml`** — Push to API
```yaml
actions:
  push:
    # Step 1: Get books from local DB that haven't been pushed
    - app:
        action: list
        table: books
        where:
          refs.hardcover: null
      as: local_books
    
    # Step 2: For each book, search Hardcover and push
    - foreach: "{{local_books}}"
      graphql:
        query: |
          mutation($book_id: Int!, $status_id: Int!) {
            insert_user_book(object: {book_id: $book_id, status_id: $status_id}) {
              id
            }
          }
        variables:
          book_id: "{{item.refs.hardcover}}"
          status_id: |
            {{item.status}} == 'read' ? 3 :
            {{item.status}} == 'reading' ? 2 : 1
```

---

## Connector Structure

```
connectors/goodreads/
  readme.md       # Auth config (if any)
  icon.svg
  books.yaml      # Implements Books app
```

**One YAML per app.** If `connectors/hardcover/books.yaml` exists, Hardcover implements Books.

---

## Executors

### `rest:` — REST APIs
```yaml
rest:
  method: GET
  url: https://api.example.com/{{params.id}}
  body: { field: "{{params.value}}" }
  response:
    mapping:
      id: ".id"
      title: ".name"
```

### `graphql:` — GraphQL APIs
```yaml
graphql:
  query: "query { items { id name } }"
  variables: { limit: "{{params.limit}}" }
  response:
    root: "data.items"
    mapping:
      id: "[].id"
      title: "[].name"
```

### `sql:` — Database queries
```yaml
sql:
  query: "SELECT * FROM table WHERE id = {{params.id}}"
```

### `csv:` — CSV file reading
```yaml
csv:
  path: "{{params.path}}"
  response:
    mapping:
      title: "[].Column Name"
      value: "[].Other Column | transform"
```

### `app:` — Per-app database operations
```yaml
# List with filters
app:
  action: list
  table: books
  where:
    status: "{{params.status}}"
  limit: "{{params.limit}}"

# Upsert (insert or update)
app:
  action: upsert
  table: books
  on_conflict: [source_connector, source_id]
```

### `command:` — CLI tools (firewall-controlled)
```yaml
command:
  binary: tree
  args: ["-L", "2", "{{params.path}}"]
  timeout: 30
```

### Chained Executors

Chain multiple executors to build complex workflows. Each step can name its output with `as:`, and subsequent steps can reference it with `{{name.field}}`.

```yaml
actions:
  complete:
    # Step 1: Look up the "completed" state for this issue's team
    - graphql:
        query: |
          query($id: String!) {
            issue(id: $id) {
              team { states(filter: { type: { eq: "completed" } }) { nodes { id } } }
            }
          }
        variables:
          id: "{{params.id}}"
      as: lookup
    
    # Step 2: Use the lookup result to update the issue
    - graphql:
        query: |
          mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) { success }
          }
        variables:
          id: "{{params.id}}"
          input:
            stateId: "{{lookup.data.issue.team.states.nodes[0].id}}"
```

**Data flow pattern for pull:**
```yaml
actions:
  pull:
    # Step 1: Read and transform CSV
    - csv:
        path: "{{params.path}}"
        response:
          mapping:
            title: "[].'Title'"
            authors: "[].'Author' | to_array"
            refs:
              isbn: "[].'ISBN' | strip_quotes"
              goodreads: "[].'Book Id'"
      as: records
    
    # Step 2: Upsert to database (references step 1's output)
    - app:
        action: upsert
        table: books
        on_conflict: refs.goodreads
        data: "{{records}}"
```

---

## Response Mapping

All executors support `response.mapping` to transform data to the app schema.

### Syntax
```yaml
mapping:
  # Direct field mapping
  id: ".id"
  title: ".name"
  
  # Array mapping (use [] prefix)
  items: "[].id"
  
  # Transforms (pipe syntax)
  authors: "[].author | to_array"
  isbn: "[].isbn | strip_quotes"
  
  # Conditionals
  status: ".completed ? 'done' : 'open'"
  
  # Complex conditionals
  priority: |
    .priority == 'urgent' ? 1 :
    .priority == 'high' ? 2 :
    .priority == 'medium' ? 3 : 4
  
  # Static values
  connector: "'goodreads'"
```

### Built-in Transforms
| Transform | Description |
|-----------|-------------|
| `to_array` | Wrap single value in array |
| `to_int` | Convert to integer |
| `strip_quotes` | Remove `="..."` wrapper (common in CSV exports) |
| `trim` | Remove whitespace |
| `split:delimiter` | Split string into array (e.g., `split:,`) |
| `nullif:value` | Return null if equals value (e.g., `nullif:0`) |
| `default:value` | Use value if null/empty |
| `replace:from:to` | Replace text (e.g., `replace:/:- ` for date conversion) |

For arithmetic and conditionals, use mapping expressions directly:
```yaml
mapping:
  priority: "4 - .priority"           # Invert priority
  status: ".done ? 'done' : 'open'"   # Conditional
```

---

## Security: No Shell Scripts

**`run:` blocks are not supported.** Connectors use declarative executor blocks only.

| Executor | Use Case |
|----------|----------|
| `rest:` | REST APIs |
| `graphql:` | GraphQL APIs |
| `sql:` | Database queries |
| `csv:` | CSV file reading |
| `app:` | Local database operations |
| `command:` | CLI tools (user-approved via firewall) |

This ensures:
- Credentials never leave Rust core
- All operations go through the firewall
- No arbitrary code execution

---

## Schema Conventions

### Field Naming
- **snake_case** — `created_at`, `parent_id`
- **Flat structure** — avoid deep nesting in core fields

### Universal Fields (every table should have)
| Field | Type | Purpose |
|-------|------|---------|
| `id` | TEXT PRIMARY KEY | AgentOS internal UUID |
| `refs` | JSON | IDs in external systems (goodreads, hardcover, isbn, etc.) |
| `metadata` | JSON | Connector-specific extras |
| `created_at` | TEXT | When created in AgentOS |
| `updated_at` | TEXT | Last modified |

### The Refs + Metadata Pattern

Apps support **multiple connectors** with different fields. Use this pattern:

```yaml
schema:
  item:
    # Core fields: universal, queryable, powers the UI
    id: { type: string, required: true }
    title: { type: string, required: true }
    status: { type: string }
    rating: { type: number }
    
    # User organization
    tags: { type: array }     # ["tag1", "tag2"] - simple array
    
    # External references (for linking/dedup)
    refs: { type: object }    # { goodreads: "123", isbn: "978..." }
    
    # Connector-specific extras
    metadata: { type: object } # Connector dumps its extras here
```

**Core fields** = Universal across all connectors, queryable, shown in UI  
**tags** = User organization (shelves, categories, labels)  
**refs** = IDs in external systems for dedup and linking  
**metadata** = Connector-specific data preserved but not in core schema

### Metadata Examples

```json
// Books from Goodreads
{"bookshelves": ["sci-fi", "favorites"], "average_rating": 4.2}

// Books from StoryGraph  
{"pace": "slow", "moods": ["dark", "emotional"], "content_warnings": ["violence"]}

// Books from Hardcover
{"edition_id": "abc123", "progress": 150, "owned": true}

// Tasks from Linear
{"cycle": {"id": "...", "name": "Sprint 5"}, "estimate": 3}

// Tasks from Todoist
{"todoist_priority": 4, "parent_id": "..."}
```

### Why This Works

1. **Schema stays clean** — Core fields cover 90% of use cases
2. **No data loss** — Connector-specific fields preserved in metadata
3. **No schema changes** — New connectors add fields to metadata, not schema
4. **Queryable** — Core fields are indexed and fast
5. **Portable** — When pushing between connectors, core fields transfer, metadata is connector-specific

### Connectors Map to Core Fields

Transforms happen in connector YAML, not the app schema:

```yaml
# connectors/goodreads/books.yaml
response:
  mapping:
    title: "[].Title"
    status: |
      [].Exclusive Shelf == 'read' ? 'read' :
      [].Exclusive Shelf == 'to-read' ? 'want_to_read' : 'none'
    tags: "[].Bookshelves | split:, "
    refs:
      goodreads: "[].Book Id"
      isbn: "[].ISBN | strip_quotes"
    metadata:                                    # Extras go here
      average_rating: "[].Average Rating"
```

---

## Icon Requirements

Every app must have an `icon.svg` file. Icons are validated by structure tests.

### Requirements

| Requirement | Why |
|-------------|-----|
| Use `viewBox` attribute | Scales properly at any size |
| Use `currentColor` for fills/strokes | Adapts to light/dark themes |
| Under 5KB | Fast loading |
| No hardcoded colors | Theme compatibility |

### Example Icon

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" 
     fill="none" stroke="currentColor" stroke-width="2">
  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
</svg>
```

### Where to Find Icons

Good sources for SVG icons (copy the SVG, don't use Iconify runtime):
- [Lucide](https://lucide.dev/) — Clean, consistent line icons
- [Heroicons](https://heroicons.com/) — Tailwind's icon set
- [Tabler Icons](https://tabler.io/icons) — 4000+ free icons
- [Material Symbols](https://fonts.google.com/icons) — Google's icons

Copy the SVG source directly into your `icon.svg` file.

---

## Credentials

Connectors never see credential values. Auth config in `readme.md` specifies WHERE credentials go:

```yaml
auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
```

AgentOS injects the actual value at runtime.

---

## Example: Building a Movies App

### 1. Define the app schema

**`apps/movies/readme.md`** — Schema auto-generates database
```yaml
schema:
  movie:
    id: { type: string, required: true }
    title: { type: string, required: true }
    year: { type: number }
    directors: { type: array }
    status: { type: enum, values: [watchlist, watching, watched] }
    rating: { type: number }
    review: { type: string }
    tags: { type: array }
    refs: { type: object }
    metadata: { type: object }
```

### 2. Add Letterboxd connector

**`connectors/letterboxd/movies.yaml`**
```yaml
actions:
  pull:
    # Chained: csv reads file, app writes to database
    - csv:
        path: "{{params.path}}"
        response:
          mapping:
            title: "[].Name"
            year: "[].Year | to_int"
            rating: "[].Rating | to_int"
            status: "'watched'"
            refs:
              letterboxd: "[].Letterboxd URI"
      as: records
    
    - app:
        action: upsert
        table: movies
        on_conflict: refs.letterboxd
        data: "{{records}}"
```

### 3. Done!

Users can now:
```
Pull my Letterboxd data from ~/Downloads/letterboxd.csv
List all movies I've watched
```

No Rust code needed. The connector defines all the Letterboxd-specific logic.

---

## Testing

### Philosophy

**All tests are end-to-end.** We test the real AgentOS binary with real data. No mocking, no unit tests. If E2E passes, the whole stack works.

**Tests live with the code they test.** Each app and connector includes its own tests. This scales to thousands of apps without bloating the core repo.

### What Contributors Need

| You need | You don't need |
|----------|----------------|
| Node.js + npm | Rust |
| Vitest (test runner) | Playwright |
| MCP client (provided) | Svelte |
| AgentOS binary (built) | Core repo access |

Contributors write **YAML configs + tests**. That's it. The MCP client talks to the real AgentOS binary - no browser automation needed.

### Test Ownership

| What | Where | Tests |
|------|-------|-------|
| AgentOS Core | `agentos/` repo | Executors, MCP protocol, UI (Playwright) |
| Apps | `integrations/apps/{app}/` | Schema validation, CRUD operations |
| Connectors | `integrations/connectors/{connector}/` | Pull/push, field mapping |

### Directory Structure

```
integrations/
  apps/
    books/
      schema.sql
      readme.md
      icon.svg
      tests/                          ← App tests
        books.test.ts
        fixtures/
          sample-books.json
          
  connectors/
    goodreads/
      books.yaml
      readme.md
      tests/                          ← Connector tests
        pull.test.ts
        fixtures/
          goodreads-export.csv        ← Sample data for tests
          
    hardcover/
      books.yaml
      tests/
        push.test.ts
        
  tests/                              ← Shared test infrastructure
    utils/
      mcp-client.ts                   ← MCP test client
      fixtures.ts                     ← Common helpers
    setup.ts                          ← Global test setup
    tsconfig.json
    
  package.json                        ← Test dependencies (vitest, etc.)
```

### Running Tests

```bash
# Run all tests
npm test

# Run tests for a specific app
npm test -- apps/books

# Run tests for a specific connector
npm test -- connectors/goodreads

# Run with verbose output
npm test -- --reporter=verbose

# Watch mode during development
npm test -- --watch
```

### What to Test

#### App Tests (`apps/{app}/tests/`)

Test that the app's schema and CRUD work correctly:

```typescript
// apps/books/tests/books.test.ts
import { describe, it, expect, afterAll } from 'vitest';
import { aos, cleanupTestData, TEST_PREFIX } from '../../../tests/utils/fixtures';

describe('Books App', () => {
  // MCP connection is handled globally by tests/setup.ts
  // Just use the aos() helper to make calls
  
  afterAll(async () => {
    // Clean up any test data we created
    await cleanupTestData('Books');
  });

  describe('List', () => {
    it('can list all books', async () => {
      const books = await aos().books.list();
      expect(Array.isArray(books)).toBe(true);
    });

    it('can filter by status', async () => {
      const books = await aos().books.list({ status: 'read' });
      books.forEach(book => {
        expect(book.status).toBe('read');
      });
    });
  });

  describe('Data Integrity', () => {
    it('books have required fields', async () => {
      const books = await aos().books.list({ limit: 10 });
      for (const book of books) {
        expect(book.id).toBeDefined();
        expect(book.title).toBeDefined();
        expect(book.status).toBeDefined();
        expect(['want_to_read', 'reading', 'read', 'dnf']).toContain(book.status);
      }
    });
  });
});
```

#### Connector Tests (`connectors/{connector}/tests/`)

Test that the connector correctly pulls/pushes data:

```typescript
// connectors/goodreads/tests/pull.test.ts
import { describe, it, expect, afterAll } from 'vitest';
import { aos, cleanupTestData } from '../../../tests/utils/fixtures';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixturesDir = join(__dirname, 'fixtures');

describe('Goodreads Connector', () => {
  afterAll(async () => {
    // Clean up pulled test books
    await cleanupTestData('Books', 
      (book) => book.refs?.goodreads && book.title?.startsWith('[TEST]')
    );
  });

  describe('CSV Pull', () => {
    it('pulls books from Goodreads CSV (dry run)', async () => {
      const csvPath = join(fixturesDir, 'sample-export.csv');
      const result = await aos().books.pull('goodreads', { path: csvPath, dry_run: true });

      expect(result.pulled).toBeGreaterThan(0);
      expect(result.errors).toEqual([]);
    });
  });

  describe('Field Mapping', () => {
    it('maps title correctly', async () => {
      const csvPath = join(fixturesDir, 'sample-export.csv');
      await aos().books.pull('goodreads', { path: csvPath });

      const books = await aos().books.list();
      const book = books.find(b => b.refs?.goodreads === '12345');

      expect(book?.title).toBe('[TEST] The Great Gatsby');
    });

    it('strips ISBN quotes wrapper', async () => {
      const books = await aos().books.list();
      const book = books.find(b => b.refs?.goodreads === '12345');

      // Goodreads CSVs have ISBNs like ="0743273567"
      expect(book?.refs?.isbn).toBe('0743273567');
    });

    it('maps shelf to status', async () => {
      const books = await aos().books.list();
      
      expect(books.find(b => b.refs?.goodreads === '12345')?.status).toBe('read');
      expect(books.find(b => b.refs?.goodreads === '12346')?.status).toBe('reading');
      expect(books.find(b => b.refs?.goodreads === '12347')?.status).toBe('want_to_read');
    });
  });
});
```

### Test Fixtures

Place sample data in `tests/fixtures/` within each connector:

```
connectors/goodreads/tests/fixtures/
  goodreads-export.csv          # Full sample export
  goodreads-isbn-quotes.csv     # Edge case: ISBN formatting
  goodreads-shelves.csv         # Edge case: shelf mapping
  goodreads-empty.csv           # Edge case: empty file
```

**Fixture Best Practices:**
- Use small, focused fixtures (5-10 records max)
- Include edge cases (empty values, special characters)
- Use `[TEST]` prefix in titles for easy cleanup
- Don't commit real user data

### Shared Test Utilities

The `tests/utils/` directory provides common helpers:

```typescript
// tests/utils/fixtures.ts - The main import for tests
import { aos, cleanupTestData, testContent, TEST_PREFIX } from '../../../tests/utils/fixtures';

// aos() - Get the global AgentOS instance (connected via setup.ts)
const books = await aos().books.list();
const result = await aos().books.pull('goodreads', { path, dry_run: true });
await aos().call('Books', { action: 'list', params: { status: 'read' } });

// cleanupTestData() - Remove test records after tests
await cleanupTestData('Books');  // Removes items with [TEST] prefix
await cleanupTestData('Books', (b) => b.source_connector === 'goodreads');

// testContent() - Generate unique test content
const title = testContent('My Book');  // "[TEST] My Book 1704312000000_abc123"

// TEST_PREFIX - The prefix for test data
expect(book.title.startsWith(TEST_PREFIX)).toBe(true);
```

**The MCP connection is managed globally** - you don't need `beforeAll`/`afterAll` to connect. Just use `aos()` and it works.

### Test Environment

Tests run against a separate test database:
- Location: `~/.agentos/data/test/{app}.db`
- Set via: `AGENTOS_ENV=test`

This ensures tests don't affect your real data.

### Writing Good Tests

1. **Test behavior, not implementation** — Test what the connector does, not how
2. **Use fixtures** — Don't rely on external APIs in tests
3. **Clean up after** — Delete test data created during tests
4. **Test edge cases** — Empty files, missing fields, special characters
5. **Keep tests fast** — Use small fixtures, mock external calls

### CI Integration

Tests run automatically on PR:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm install
      - run: npm test
```

### Structure Validation Tests

The `tests/structure.test.ts` file automatically validates all apps and connectors:

```bash
npm test -- tests/structure.test.ts
```

**What it checks:**

| For Apps | For Connectors | For Icons |
|----------|----------------|-----------|
| Has `readme.md` | Has `readme.md` | Uses `viewBox` |
| Has `icon.svg` | Has yaml or icon | Uses `currentColor` |
| Valid SVG icon | Yaml references valid app | Under 5KB |
| Data apps have `schema.sql` | | No hardcoded colors |

These tests run automatically with `npm test` - you don't need to write them.

### Adding Tests to Your Contribution

When contributing an app or connector:

1. Create `tests/` directory in your app/connector folder
2. Add at least one test file (`*.test.ts`)
3. Include fixture files if needed
4. Run `npm test -- {your-path}` to verify
5. Structure tests validate your files automatically
6. All tests must pass before merge

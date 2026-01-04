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
Data is imported into a local SQLite database for unified access.

```
User → AgentOS → Local SQLite → Response
                     ↑
         Import from Goodreads CSV
         Sync with Hardcover API
```

**Data apps have:**
- `schema.sql` — defines database tables
- Per-app database at `~/.agentos/data/{app}.db`
- Auto-generated CRUD actions (list, get, create, update, delete)
- Custom import/sync actions via connectors

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
  readme.md     # Schema + actions
  schema.sql    # Database tables ← triggers per-app DB creation
  icon.svg
```

When `schema.sql` exists, AgentOS automatically:
1. Creates `~/.agentos/data/{app}.db`
2. Runs the schema SQL
3. Exposes CRUD actions (list, get, create, update, delete)

---

## Adding a Data App

### 1. Create the App

**`apps/books/schema.sql`**
```sql
CREATE TABLE IF NOT EXISTS books (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  authors JSON,
  isbn TEXT,
  status TEXT NOT NULL,  -- want_to_read, reading, read, dnf
  rating INTEGER,
  review TEXT,
  date_added TEXT,
  date_finished TEXT,
  source_connector TEXT NOT NULL,
  source_id TEXT NOT NULL,
  UNIQUE(source_connector, source_id)
);
```

**`apps/books/readme.md`**
```markdown
# Books

Track your reading library across services.

## Schema
| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier |
| title | string | Book title |
| authors | array | List of author names |
| status | enum | want_to_read, reading, read, dnf |
| rating | integer | 1-5 stars |
| ... | ... | ... |

## Actions
- **list** — List books with filters
- **get** — Get a single book
- **create** — Add a book
- **update** — Update a book
- **delete** — Remove a book
- **import** — Import from a connector (Goodreads CSV, etc.)
- **sync** — Sync with a connector (Hardcover API, etc.)
```

### 2. Create Connectors

**`connectors/goodreads/books.yaml`** — Import from CSV
```yaml
actions:
  import:
    csv:
      path: "{{params.path}}"
      response:
        mapping:
          goodreads_id: "[].Book Id"
          title: "[].Title"
          authors: "[].Author | to_array"
          isbn: "[].ISBN | strip_quotes"
          isbn13: "[].ISBN13 | strip_quotes"
          rating: "[].My Rating | to_int"
          status: |
            [].Exclusive Shelf == 'read' ? 'read' :
            [].Exclusive Shelf == 'currently-reading' ? 'reading' : 'want_to_read'
          date_added: "[].Date Added"
          date_finished: "[].Date Read"
          review: "[].My Review"
          source_connector: "'goodreads'"
          source_id: "[].Book Id"
    app:
      action: upsert
      table: books
      on_conflict: [source_connector, source_id]
```

**`connectors/hardcover/books.yaml`** — Sync with API
```yaml
actions:
  sync:
    # Step 1: Get books from local DB that need syncing
    - app:
        action: list
        table: books
        where:
          hardcover_id: null
      as: local_books
    
    # Step 2: For each book, search Hardcover and link
    - foreach: "{{local_books}}"
      graphql:
        query: |
          query($title: String!) {
            search(query: $title, query_type: "books", per_page: 1) {
              results
            }
          }
        variables:
          title: "{{item.title}}"
      as: search_result
    
    # Step 3: Push to Hardcover
    - graphql:
        query: |
          mutation($book_id: Int!, $status_id: Int!) {
            insert_user_book(object: {book_id: $book_id, status_id: $status_id}) {
              id
            }
          }
        variables:
          book_id: "{{search_result.results[0].id}}"
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

### `csv:` — CSV file import
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
```yaml
action:
  - graphql: { query: "..." }
    as: step1
  - rest:
      url: "https://api.example.com/{{step1.data.id}}"
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
| `csv:` | File imports |
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
| `source_connector` | TEXT | Which connector imported this |
| `source_id` | TEXT | ID in the source system |
| `created_at` | TEXT | When created in AgentOS |
| `updated_at` | TEXT | Last modified |

### The Metadata Pattern

Apps support **multiple connectors** with different fields. Use this pattern:

```sql
CREATE TABLE items (
  -- Core fields: universal, queryable, powers the UI
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT,
  rating INTEGER,
  
  -- User organization
  tags JSON,                -- ["tag1", "tag2"] - simple array
  
  -- Source tracking
  source_connector TEXT NOT NULL,
  source_id TEXT NOT NULL,
  
  -- Connector-specific extras
  metadata JSON,            -- Connector dumps its extras here
  
  UNIQUE(source_connector, source_id)
);
```

**Core fields** = Universal across all connectors, queryable, shown in UI  
**tags JSON** = User organization (shelves, categories, labels)  
**metadata JSON** = Connector-specific data preserved but not in core schema

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
5. **Portable** — When syncing between connectors, core fields transfer, metadata is connector-specific

### Connectors Map to Core Fields

Transforms happen in connector YAML, not the app schema:

```yaml
# connectors/goodreads/books.yaml
response:
  mapping:
    title: "[].Title"
    status: "[].Exclusive Shelf | map_status"  # Transform to core status
    tags: "[].Bookshelves | split:, "          # Custom shelves → tags
    metadata:                                    # Extras go here
      average_rating: "[].Average Rating"
      bookshelves: "[].Bookshelves | split:, "
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

**`apps/movies/schema.sql`**
```sql
CREATE TABLE IF NOT EXISTS movies (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  year INTEGER,
  directors JSON,
  status TEXT NOT NULL,  -- watchlist, watching, watched
  rating INTEGER,
  review TEXT,
  source_connector TEXT NOT NULL,
  source_id TEXT NOT NULL,
  UNIQUE(source_connector, source_id)
);
```

### 2. Add Letterboxd connector

**`connectors/letterboxd/movies.yaml`**
```yaml
actions:
  import:
    csv:
      path: "{{params.path}}"
      response:
        mapping:
          title: "[].Name"
          year: "[].Year | to_int"
          rating: "[].Rating | to_int"
          status: "'watched'"
          source_connector: "'letterboxd'"
          source_id: "[].Letterboxd URI"
    app:
      action: upsert
      table: movies
      on_conflict: [source_connector, source_id]
```

### 3. Done!

Users can now:
```
Import my Letterboxd data from ~/Downloads/letterboxd.csv
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
| Connectors | `integrations/connectors/{connector}/` | Import/sync, field mapping |

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
        import.test.ts
        fixtures/
          goodreads-export.csv        ← Sample data for tests
          
    hardcover/
      books.yaml
      tests/
        sync.test.ts
        
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

Test that the connector correctly imports/syncs data:

```typescript
// connectors/goodreads/tests/import.test.ts
import { describe, it, expect, afterAll } from 'vitest';
import { aos, cleanupTestData } from '../../../tests/utils/fixtures';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixturesDir = join(__dirname, 'fixtures');

describe('Goodreads Connector', () => {
  afterAll(async () => {
    // Clean up imported test books
    await cleanupTestData('Books', 
      (book) => book.source_connector === 'goodreads' && book.title?.startsWith('[TEST]')
    );
  });

  describe('CSV Import', () => {
    it('imports books from Goodreads CSV (dry run)', async () => {
      const csvPath = join(fixturesDir, 'sample-export.csv');
      const result = await aos().books.import('goodreads', csvPath, true);

      expect(result.imported).toBeGreaterThan(0);
      expect(result.errors).toEqual([]);
    });
  });

  describe('Field Mapping', () => {
    it('maps title correctly', async () => {
      const csvPath = join(fixturesDir, 'sample-export.csv');
      await aos().books.import('goodreads', csvPath, false);

      const books = await aos().books.list();
      const book = books.find(b => b.source_id === '12345');

      expect(book?.title).toBe('[TEST] The Great Gatsby');
    });

    it('strips ISBN quotes wrapper', async () => {
      const books = await aos().books.list();
      const book = books.find(b => b.source_id === '12345');

      // Goodreads CSVs have ISBNs like ="0743273567"
      expect(book?.isbn).toBe('0743273567');
    });

    it('maps shelf to status', async () => {
      const books = await aos().books.list();
      
      expect(books.find(b => b.source_id === '12345')?.status).toBe('read');
      expect(books.find(b => b.source_id === '12346')?.status).toBe('reading');
      expect(books.find(b => b.source_id === '12347')?.status).toBe('want_to_read');
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
const result = await aos().books.import('goodreads', path, true);
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

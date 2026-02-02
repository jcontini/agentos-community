# Database App

Browse and query SQLite databases. See what AI has been doing, explore activity logs, run SQL queries.

## Vision

The Database app is a SQLite browser built into AgentOS. It provides transparency — users can see exactly what's in the activity database, what AI has been doing, and explore the data directly.

**Primary use case:** Browse `~/.agentos/data/agentos.db` — the activity log, settings, and system data.

**Future:** Could connect to any SQLite database via a SQLite plugin.

---

## Features

### Table Browser
- List all tables in a database
- View table schema (columns, types)
- Browse rows with pagination
- Sort and filter

### SQL Query
- Write and execute SQL queries
- Results displayed as table
- Query history
- Save favorite queries

### Activity Log View
- Pre-built view for `activity_log` table
- Filter by plugin, entity, operation
- Timeline view of AI actions
- Error highlighting

---

## Capabilities

| Capability | Description |
|------------|-------------|
| `database_list` | List available databases |
| `table_list` | List tables in a database |
| `table_schema` | Get schema for a table |
| `table_browse` | Browse rows with pagination |
| `query_execute` | Run SQL query |

---

## Schemas

### `database_list`

```typescript
// Input
{}

// Output
{
  databases: {
    id: string           // e.g., "agentos"
    name: string         // Display name
    path: string         // File path
    size: number         // Bytes
    tables: number       // Table count
  }[]
}
```

### `table_list`

```typescript
// Input
{ database: string }

// Output
{
  tables: {
    name: string
    row_count: number
    columns: number
  }[]
}
```

### `table_schema`

```typescript
// Input
{ database: string, table: string }

// Output
{
  table: string
  columns: {
    name: string
    type: string         // TEXT, INTEGER, REAL, BLOB, etc.
    nullable: boolean
    primary_key: boolean
    default: any
  }[]
  indexes: {
    name: string
    columns: string[]
    unique: boolean
  }[]
}
```

### `table_browse`

```typescript
// Input
{
  database: string
  table: string
  limit?: number        // default 50
  offset?: number       // default 0
  order_by?: string     // column name
  order_dir?: "asc" | "desc"
  filter?: {
    column: string
    op: "=" | "!=" | ">" | "<" | "like" | "is_null"
    value: any
  }[]
}

// Output
{
  rows: Record<string, any>[]
  total: number
  limit: number
  offset: number
}
```

### `query_execute`

```typescript
// Input
{
  database: string
  query: string         // SQL query (SELECT only for safety)
}

// Output
{
  columns: string[]
  rows: any[][]
  row_count: number
  execution_time_ms: number
}
```

---

## UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ ≣  Database                                               ─ □ × │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Database: [agentos          ▼]                                │
│                                                                 │
│  ┌──────────────┬───────────────────────────────────────────┐  │
│  │ Tables       │  activity_log                              │  │
│  │              │                                            │  │
│  │ activity_log │  timestamp  | plugin_id | entity | op     │  │
│  │ settings     │  ─────────────────────────────────────────│  │
│  │ credentials  │  2026-01-22 | exa       | webpage| search │  │
│  │              │  2026-01-22 | firecrawl | webpage| read   │  │
│  │              │  2026-01-22 | settings  | setting| get    │  │
│  │              │  ...                                       │  │
│  │              │                                            │  │
│  └──────────────┴───────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ SQL Query ──────────────────────────────────────────────┐  │
│  │ SELECT * FROM activity_log WHERE plugin_id = 'exa'       │  │
│  │                                                 [Run ▶]  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security

- **Read-only by default** — Only SELECT queries allowed
- **Scoped to AgentOS databases** — Cannot access arbitrary SQLite files
- **Activity logged** — All queries logged to activity_log (meta!)

**Future:** Could allow write access for specific databases with user confirmation.

---

## Implementation Notes

### SQLite Plugin

The Database app would use a **SQLite plugin** that provides the capabilities above. This keeps the pattern consistent — apps are UI, plugins provide data access.

```yaml
# plugins/database/sqlite/readme.md
id: sqlite
name: SQLite
description: Query SQLite databases
category: database

operations:
  - database.list
  - table.list
  - table.schema
  - table.browse
  - query.execute
```

### Pre-configured Databases

AgentOS ships with knowledge of its own databases:

```yaml
databases:
  agentos:
    path: ~/.agentos/data/agentos.db
    name: AgentOS
    description: Activity log, settings, system data
```

Users could add their own SQLite databases in the future.

---

## Transparency Value

This app embodies the AgentOS vision of **transparency**:

> "When AI searches the web, you see results appear. When it creates a task, you see it in the task list."

With the Database app, users can:
- See every action AI has taken (activity_log)
- Understand what data AgentOS stores
- Debug issues by querying directly
- Feel confident about what's happening

---

## Related

- **Files app** — Browse Data/ folder containing databases
- **Settings app** — Activity log view in About panel (simpler version)
- **personal-archive** — Future databases for imported data

---
id: sqlite
name: SQLite
description: Connect to SQLite database files
icon: icon.png
color: "#003B57"
tags: [database, sql]

website: https://www.sqlite.org
docs_url: https://www.sqlite.org/docs.html

auth:
  type: local_path
  label: Database Path
  description: Path to SQLite database file
  placeholder: "/path/to/database.sqlite"
  file_extensions: [".sqlite", ".sqlite3", ".db"]
  examples:
    - "/Users/joe/data/app.sqlite"
    - "./local.db"

instructions: |
  SQLite-specific notes:
  - File must exist and be readable
  - No network connection needed
  - Uses sqlite_master for metadata queries
  - Supports both .sqlite and .db extensions

# Action implementations (merged from mapping.yaml)
actions:
  query:
    operation: read
    label: "Execute SQL query"
    sql:
      # Use |raw modifier to skip SQL escaping - the AI provides complete SQL queries
      query: "{{params.sql | raw}}"
      format: json
    response:
      mapping:
        rows: "."
        row_count: "length(.)"

  tables:
    operation: read
    label: "List tables"
    sql:
      query: |
        SELECT name
        FROM sqlite_master 
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
      format: json
    response:
      mapping: "[].name"

  describe:
    operation: read
    label: "Describe table"
    sql:
      # SQLite uses PRAGMA instead of information_schema
      query: "PRAGMA table_info('{{params.table}}')"
      format: json
    response:
      mapping:
        name: "'{{params.table}}'"
        schema: "null"
        columns: |
          [.[] | {
            name: .name,
            type: .type,
            nullable: (.notnull == 0),
            default: .dflt_value,
            primary_key: (.pk == 1)
          }]
---

# SQLite

Connect to local SQLite database files.

## Setup

1. Get the path to your SQLite database file
2. Add it in AgentOS Settings → Connectors → SQLite

## Path Format

SQLite uses file paths instead of connection strings:

```bash
# Absolute path
/Users/joe/projects/myapp/data.sqlite

# Relative path (from AgentOS working directory)
./data/local.db

# Home directory expansion
~/Documents/app.sqlite3
```

## Common Locations

```bash
# macOS app data
~/Library/Application Support/[AppName]/database.sqlite

# Development databases
./prisma/dev.db
./db/development.sqlite3

# Browser data (careful - locked while browser is running)
~/Library/Application Support/Google/Chrome/Default/History
```

## Limitations

- File must be readable by AgentOS
- Database is locked while another process has it open
- In-memory databases (`:memory:`) are not supported
- WAL mode databases require both .sqlite and .sqlite-wal files

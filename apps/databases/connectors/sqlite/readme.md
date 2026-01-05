---
id: sqlite
name: SQLite
description: Connect to SQLite database files
icon: icon.svg
color: "#003B57"

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

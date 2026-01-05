---
id: postgres
name: PostgreSQL
description: Connect to PostgreSQL databases
icon: icon.svg
color: "#336791"

website: https://www.postgresql.org
docs_url: https://www.postgresql.org/docs/current/

auth:
  type: connection_string
  label: Connection String
  description: PostgreSQL connection string
  placeholder: "postgresql://user:password@host:5432/database"
  examples:
    - "postgresql://joe:secret@localhost:5432/myapp"
    - "postgres://user:pass@db.example.com:5432/prod?sslmode=require"

instructions: |
  PostgreSQL-specific notes:
  - Default schema is "public"
  - Use information_schema for metadata queries
  - SSL mode can be configured via connection string params
  - For cloud providers (Supabase, Neon), use their provided connection string
---

# PostgreSQL

Connect to PostgreSQL databases.

## Setup

1. Get your connection string (or construct one):
   ```
   postgresql://username:password@host:port/database
   ```

2. Add credential in AgentOS Settings → Connectors → PostgreSQL

## Connection String Format

```
postgresql://[user]:[password]@[host]:[port]/[database]?[params]
```

### Examples

```bash
# Local development
postgresql://postgres:postgres@localhost:5432/myapp

# Cloud database with SSL
postgresql://user:pass@db.example.com:5432/prod?sslmode=require

# Supabase
postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:5432/postgres

# Neon
postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
```

## SSH Tunnels

For databases behind a firewall:

1. Create tunnel in Settings → Terminal
2. Point connection string to `localhost` with forwarded port

## Limitations

- Large result sets may be truncated
- Binary columns return base64-encoded data
- Transactions are not supported (each query is auto-committed)

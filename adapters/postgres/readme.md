---
id: postgres
name: PostgreSQL
description: Connect to PostgreSQL databases
icon: icon.svg
color: "#336791"

website: https://www.postgresql.org

auth:
  type: connection_string
  label: Connection String
  description: PostgreSQL connection string
  placeholder: "postgresql://user:password@host:5432/database"
  examples:
    - "postgresql://joe:secret@localhost:5432/myapp"
    - "postgres://user:pass@db.example.com:5432/prod?sslmode=require"

instructions: |
  PostgreSQL database access for AI agents.
  - Use table.list to discover available tables
  - Use table.get to understand table structure before querying
  - Use the query utility for custom SQL queries
  - For databases behind firewalls, set up an SSH tunnel in AgentOS Terminal

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  table:
    terminology: Table
    mapping:
      id: .name
      name: .name
      schema: .schema
      row_count: .row_count
      size: .size
      description: .description

  column:
    terminology: Column
    mapping:
      id: .name
      name: .name
      type: .type
      nullable: .nullable
      default: .default
      is_primary_key: .primary_key

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  table.list:
    description: List all tables in the database
    returns: table[]
    params:
      schema: { type: string, default: "public", description: "Schema to list tables from" }
    sql:
      query: |
        SELECT 
          t.table_name as name,
          t.table_schema as schema,
          pg_stat_user_tables.n_live_tup as row_count,
          pg_size_pretty(pg_total_relation_size(quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))) as size,
          obj_description((quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass) as description
        FROM information_schema.tables t
        LEFT JOIN pg_stat_user_tables ON pg_stat_user_tables.relname = t.table_name
          AND pg_stat_user_tables.schemaname = t.table_schema
        WHERE t.table_schema = '{{params.schema | default: public}}'
          AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name
      response:
        root: "/"

  table.get:
    description: Get table schema with columns and constraints
    returns: table
    params:
      name: { type: string, required: true, description: "Table name" }
      schema: { type: string, default: "public", description: "Schema name" }
    sql:
      query: |
        SELECT 
          c.column_name as name,
          c.data_type as type,
          c.is_nullable = 'YES' as nullable,
          c.column_default as default,
          CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as primary_key,
          c.character_maximum_length as max_length
        FROM information_schema.columns c
        LEFT JOIN (
          SELECT ku.column_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage ku
            ON tc.constraint_name = ku.constraint_name
            AND tc.table_schema = ku.table_schema
          WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_name = '{{params.name}}'
            AND tc.table_schema = '{{params.schema | default: public}}'
        ) pk ON c.column_name = pk.column_name
        WHERE c.table_name = '{{params.name}}'
          AND c.table_schema = '{{params.schema | default: public}}'
        ORDER BY c.ordinal_position
      response:
        root: "/"
        # Wrap columns into a table object
        transform: |
          {
            "name": "{{params.name}}",
            "schema": "{{params.schema | default: public}}",
            "columns": .
          }

  table.search:
    description: Search for tables by name pattern
    returns: table[]
    params:
      query: { type: string, required: true, description: "Table name pattern (supports % wildcard)" }
      schema: { type: string, default: "public", description: "Schema to search in" }
    sql:
      query: |
        SELECT 
          t.table_name as name,
          t.table_schema as schema,
          pg_stat_user_tables.n_live_tup as row_count,
          pg_size_pretty(pg_total_relation_size(quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))) as size
        FROM information_schema.tables t
        LEFT JOIN pg_stat_user_tables ON pg_stat_user_tables.relname = t.table_name
          AND pg_stat_user_tables.schemaname = t.table_schema
        WHERE t.table_schema = '{{params.schema | default: public}}'
          AND t.table_type = 'BASE TABLE'
          AND t.table_name ILIKE '%{{params.query}}%'
        ORDER BY t.table_name
      response:
        root: "/"

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

utilities:
  query:
    description: Execute a custom SQL query (read-only)
    params:
      sql: { type: string, required: true, description: "SQL query to execute" }
    returns:
      rows: array
      row_count: integer
    sql:
      query: "{{params.sql | raw}}"
      response:
        root: "/"
        transform: |
          {
            "rows": .,
            "row_count": (. | length)
          }

  get_schemas:
    description: List all schemas in the database
    returns:
      name: string
      owner: string
    sql:
      query: |
        SELECT 
          schema_name as name,
          schema_owner as owner
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schema_name
      response:
        root: "/"

  get_indexes:
    description: List indexes on a table
    params:
      table: { type: string, required: true, description: "Table name" }
      schema: { type: string, default: "public", description: "Schema name" }
    returns:
      name: string
      columns: string
      is_unique: boolean
      is_primary: boolean
    sql:
      query: |
        SELECT 
          i.relname as name,
          array_to_string(array_agg(a.attname ORDER BY x.ordinality), ', ') as columns,
          ix.indisunique as is_unique,
          ix.indisprimary as is_primary
        FROM pg_index ix
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        CROSS JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS x(attnum, ordinality)
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
        WHERE t.relname = '{{params.table}}'
          AND n.nspname = '{{params.schema | default: public}}'
        GROUP BY i.relname, ix.indisunique, ix.indisprimary
        ORDER BY i.relname
      response:
        root: "/"

  get_foreign_keys:
    description: List foreign key relationships for a table
    params:
      table: { type: string, required: true, description: "Table name" }
      schema: { type: string, default: "public", description: "Schema name" }
    returns:
      constraint_name: string
      column: string
      references_table: string
      references_column: string
    sql:
      query: |
        SELECT
          tc.constraint_name,
          kcu.column_name as column,
          ccu.table_name as references_table,
          ccu.column_name as references_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
          AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = '{{params.table}}'
          AND tc.table_schema = '{{params.schema | default: public}}'
      response:
        root: "/"
---

# PostgreSQL

Connect to PostgreSQL databases for schema exploration and querying.

## Setup

1. Get your connection string:
   ```
   postgresql://username:password@host:port/database
   ```

2. Add credential in AgentOS Settings → Accounts → PostgreSQL

## SSH Tunnels

For databases behind a firewall:

1. Configure tunnel in AgentOS Terminal:
   - Name: `my-db-tunnel`
   - Connection: `user@bastion-host -L 5433:db-host:5432`

2. Start tunnel: `tunnel_start my-db-tunnel`

3. Use local connection string:
   ```
   postgresql://user:pass@localhost:5433/database
   ```

## Operations

### table.list
List all tables with row counts and sizes.

### table.get
Get full schema for a table including columns, types, and constraints.

### table.search
Find tables by name pattern.

## Utilities

### query
Execute custom SQL queries. Use for data exploration.

### get_schemas
List all schemas in the database.

### get_indexes
Show indexes on a specific table.

### get_foreign_keys
Show foreign key relationships.

## Examples

```
# List all tables
table.list

# Describe a specific table
table.get name="users"

# Find tables related to orders
table.search query="order"

# Custom query
query sql="SELECT * FROM users WHERE created_at > '2024-01-01' LIMIT 10"
```

## Limitations

- Read-only queries recommended (no transaction support)
- Large result sets may be truncated
- Binary columns return base64-encoded data

---
id: mysql
name: MySQL
description: Connect to MySQL and MariaDB databases
icon: icon.svg
color: "#4479A1"

website: https://www.mysql.com
docs_url: https://dev.mysql.com/doc/

auth:
  type: connection_string
  label: Connection String
  description: MySQL connection string
  placeholder: "mysql://user:password@host:3306/database"
  examples:
    - "mysql://joe:secret@localhost:3306/myapp"
    - "mysql://user:pass@db.example.com:3306/prod"

instructions: |
  MySQL-specific notes:
  - Works with both MySQL and MariaDB
  - Default port is 3306
  - Use information_schema for metadata queries
  - For PlanetScale, use their provided connection string
---

# MySQL

Connect to MySQL and MariaDB databases.

## Setup

1. Get your connection string (or construct one):
   ```
   mysql://username:password@host:port/database
   ```

2. Add credential in AgentOS Settings → Connectors → MySQL

## Connection String Format

```
mysql://[user]:[password]@[host]:[port]/[database]
```

### Examples

```bash
# Local development
mysql://root:password@localhost:3306/myapp

# Remote server
mysql://user:pass@db.example.com:3306/prod

# MariaDB (same format)
mysql://user:pass@localhost:3306/myapp

# PlanetScale
mysql://user:pass@aws.connect.psdb.cloud/mydb?ssl={"rejectUnauthorized":true}
```

## SSH Tunnels

For databases behind a firewall:

1. Create tunnel in Settings → Terminal
2. Point connection string to `localhost` with forwarded port

## Limitations

- Large result sets may be truncated
- Transactions are not supported (each query is auto-committed)
- Some MariaDB-specific features may not work

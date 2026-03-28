"""Database queries through the engine.

Replaces direct sqlite3 usage. All queries routed through the engine
for logging, path validation, and future permission controls.

    from agentos import sql

    rows = sql.query("SELECT id, name FROM users LIMIT :n", db="~/data.db", params={"n": 10})
    sql.execute("INSERT INTO items (name) VALUES (:name)", db="~/data.db", params={"name": "test"})
"""

from agentos._bridge import dispatch


def query(sql_str, db, params=None):
    """Execute a read-only SQL query.

    Args:
        sql_str: SQL query with :param bind syntax.
        db: Path to SQLite database (tilde-expanded by engine).
        params: Optional bind parameters dict.

    Returns:
        List of row dicts, one per result row.
    """
    return dispatch("__sql_query__", {"sql": sql_str, "db": db, "params": params or {}})


def execute(sql_str, db, params=None):
    """Execute a write SQL statement.

    Args:
        sql_str: SQL statement with :param bind syntax.
        db: Path to SQLite database (tilde-expanded by engine).
        params: Optional bind parameters dict.

    Returns:
        Dict with execution result.
    """
    return dispatch("__sql_execute__", {"sql": sql_str, "db": db, "params": params or {}})

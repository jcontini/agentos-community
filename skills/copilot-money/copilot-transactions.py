#!/usr/bin/env python3
"""
Copilot Money — transaction list with category enrichment
Reads from CopilotDB.sqlite and the categories widget JSON.
Accepts optional CLI args: --account_id, --limit, --query
No auth needed — local files only.
"""

import json
import os
import sqlite3
import sys
import argparse

WIDGET_DIR = os.path.expanduser(
    "~/Library/Group Containers/group.com.copilot.production/widget-data"
)
DB_PATH = os.path.expanduser(
    "~/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
)


def load_categories():
    """Load categories from widget JSON, return dict keyed by category id."""
    path = os.path.join(WIDGET_DIR, "widgets-category-default_categories.json")
    try:
        with open(path) as f:
            cats = json.load(f)
        return {c["id"]: c for c in cats}
    except Exception:
        return {}


def fetch_transactions(account_id=None, limit=100, query=None):
    categories = load_categories()

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    base_sql = """
        SELECT
            t.id,
            t.name AS merchant_name,
            t.amount,
            date(t.date, 'localtime') AS date,
            t.account_id,
            t.category_id,
            t.type,
            t.recurring,
            t.pending,
            t.user_note AS notes
        FROM Transactions t
        WHERE t.user_deleted = 0
    """

    params = {}

    if account_id:
        base_sql += " AND t.account_id = :account_id"
        params["account_id"] = account_id

    if query:
        base_sql += """
          AND (
            t.name LIKE '%' || :query || '%'
            OR t.original_name LIKE '%' || :query || '%'
            OR t.user_note LIKE '%' || :query || '%'
          )
        """
        params["query"] = query

    base_sql += " ORDER BY t.date DESC LIMIT :limit"
    params["limit"] = limit

    rows = conn.execute(base_sql, params).fetchall()
    conn.close()

    results = []
    for row in rows:
        r = dict(row)

        # Enrich with category info from widget JSON
        cat_id = r.get("category_id")
        cat = categories.get(cat_id) if cat_id else None
        r["category_name"] = cat["name"] if cat else None
        r["category_emoji"] = cat.get("emoji") if cat else None
        # Strip alpha from color (#RRGGBBAA -> #RRGGBB)
        raw_color = cat.get("categoryColor") if cat else None
        r["category_color"] = raw_color[:7] if raw_color else None

        # Build tags list: recurring + internal-transfer + category
        tags = []
        if r.get("recurring") == 1 or r.get("recurring") is True:
            tags.append({"name": "recurring"})
        if r.get("type") == "internal_transfer":
            tags.append({"name": "internal-transfer"})
        if cat:
            tags.append({
                "name": cat["name"],
                "emoji": cat.get("emoji"),
                "color": raw_color[:7] if raw_color else None,
            })

        r["tags"] = tags
        results.append(r)

    return results


def main():
    # Accept either a single JSON argument or named flags
    if len(sys.argv) == 2 and sys.argv[1].startswith("{"):
        params = json.loads(sys.argv[1])
        account_id = params.get("account_id") or None
        limit = params.get("limit") or 100
        query = params.get("query") or None
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("--account_id", default=None)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--query", default=None)
        args = parser.parse_args()
        account_id = args.account_id or None
        limit = args.limit
        query = args.query or None

    transactions = fetch_transactions(
        account_id=account_id,
        limit=limit,
        query=query,
    )
    print(json.dumps(transactions, indent=2))


if __name__ == "__main__":
    main()

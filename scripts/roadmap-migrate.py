#!/usr/bin/env python3
"""Create dependency relationships between plan entities on the graph.

Entity creation is handled by plan.list through the entity pipeline.
This script creates the `enables` relationship edges for blocked_by/blocks
dependencies, which the pipeline can't express (self-referential direction).

Usage:
    python3 roadmap-migrate.py --repository all --dry-run
    python3 roadmap-migrate.py --repository all --commit
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIST_PLANS_PY = os.path.join(SCRIPT_DIR, "..", "skills", "roadmap", "list-plans.py")

REPO_NAMES = ["agentos", "agentos-community", "entity-experiments"]
API_BASE = "http://localhost:3456"
AGENT_HEADER = "roadmap-migrate"


def list_plans(repository):
    """Call list-plans.py and return parsed plan data."""
    result = subprocess.run(
        [sys.executable, LIST_PLANS_PY, "--repository", repository, "--json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Warning: list-plans.py failed: {result.stderr}", file=sys.stderr)
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def api_request(method, path, body=None):
    """Make an API request to AgentOS."""
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"X-Agent": AGENT_HEADER, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} {path}: {error_body}")


def resolve_entity_ids():
    """Build a map of service_id → graph entity_id for all plan entities."""
    result = api_request("GET", "/mem/plans?limit=500")
    id_map = {}
    for entity in result.get("data", []):
        service_id = entity.get("service_id") or entity.get("id")
        entity_id = entity.get("_entity_id") or entity.get("id")
        if service_id and entity_id:
            id_map[service_id] = entity_id
    return id_map


def create_enables(from_id, to_id, dry_run=True):
    """Create an enables relationship: from_id enables to_id (graph entity IDs)."""
    if dry_run:
        return True
    try:
        api_request("POST", "/mem/relate", {"from": from_id, "to": to_id, "type": "enables"})
        return True
    except RuntimeError as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            return True
        raise


def main():
    parser = argparse.ArgumentParser(description="Create plan dependency relationships")
    parser.add_argument("--repository", default="all")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--commit", action="store_true", default=False)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    dry_run = not args.commit

    repos = REPO_NAMES if args.repository == "all" else [args.repository]
    all_plans = []
    for repo in repos:
        all_plans.extend(list_plans(repo))

    plan_ids = {p["id"] for p in all_plans}
    total_created = 0
    errors = []

    # Resolve service_id → graph entity_id
    id_map = {}
    if not dry_run:
        if not args.json:
            print(f"\n  Resolving entity IDs from graph...", file=sys.stderr)
        id_map = resolve_entity_ids()
        if not args.json:
            print(f"  Found {len(id_map)} plan entities on graph", file=sys.stderr)

    if not args.json:
        print(f"\n{'Dry run' if dry_run else 'Creating'} dependency edges for {len(all_plans)} plans...", file=sys.stderr)

    for plan in all_plans:
        if plan["data"].get("archived"):
            continue

        for blocker_id in plan["data"].get("blocked_by", []):
            if blocker_id not in plan_ids:
                errors.append(f"Missing: {plan['id']} blocked_by {blocker_id}")
                if not args.json:
                    print(f"  ⚠ Missing: {blocker_id} (from {plan['id']})", file=sys.stderr)
                continue

            try:
                if dry_run:
                    from_graph_id = blocker_id
                    to_graph_id = plan["id"]
                else:
                    from_graph_id = id_map.get(blocker_id)
                    to_graph_id = id_map.get(plan["id"])
                    if not from_graph_id:
                        errors.append(f"No graph entity for {blocker_id}")
                        continue
                    if not to_graph_id:
                        errors.append(f"No graph entity for {plan['id']}")
                        continue

                create_enables(from_graph_id, to_graph_id, dry_run=dry_run)
                total_created += 1
                if not args.json:
                    print(f"  → {blocker_id} enables {plan['id']}", file=sys.stderr)
            except Exception as e:
                errors.append(f"{blocker_id} → {plan['id']}: {e}")

    summary = {
        "status": "dry_run" if dry_run else "success",
        "plans": len(all_plans),
        "relationships_created": total_created,
        "errors": errors,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"\n{'Dry run' if dry_run else 'Done'}:", file=sys.stderr)
        print(f"  Plans: {summary['plans']}", file=sys.stderr)
        print(f"  Relationships: {summary['relationships_created']}", file=sys.stderr)
        if errors:
            print(f"  Errors: {len(errors)}", file=sys.stderr)
        if dry_run:
            print(f"\n  Run with --commit to apply.", file=sys.stderr)


if __name__ == "__main__":
    main()

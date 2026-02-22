#!/usr/bin/env python3
"""List roadmap plan specs from .ROADMAP/ directories.

Reads .ROADMAP/*.md and .ROADMAP/.archived/*.md files for a given repository
and returns structured JSON suitable for the AgentOS entity pipeline.

Usage:
    python3 list-plans.py --repository agentos --json
    python3 list-plans.py --repository all --status ready --json
    python3 list-plans.py --repository agentos-community --priority now --json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_PATHS = {
    "agentos": os.path.expanduser("~/dev/agentos"),
    "agentos-community": os.path.expanduser("~/dev/agentos-community"),
    "entity-experiments": os.path.expanduser("~/dev/entity-experiments"),
}


def parse_frontmatter(text):
    """Parse YAML frontmatter from markdown text. Returns (frontmatter_dict, body_text)."""
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    fm_text = text[3:end].strip()
    body = text[end + 4:].strip()

    fm = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        # Handle list values (blocked_by: [a, b, c] or multiline)
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if inner:
                items = []
                for v in inner.split(","):
                    v = v.strip().strip('"').strip("'")
                    if "  #" in v:
                        v = v[:v.index("  #")].strip()
                    if v and not v.startswith("#"):
                        items.append(v)
                fm[key] = items
            else:
                fm[key] = []
        elif val == "[]" or val.startswith("[]"):
            fm[key] = []
        elif val in ("null", "~", ""):
            fm[key] = None
        else:
            # Strip inline comments from scalar values
            if "  #" in val:
                val = val[:val.index("  #")].strip()
            fm[key] = val

    # Handle multiline list syntax (dash-prefixed items after key)
    current_list_key = None
    lines = fm_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if ":" in line and not line.startswith("-"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "" or val is None:
                # Might be a multiline list
                current_list_key = key
                fm[key] = []
            else:
                current_list_key = None
        elif line.startswith("- ") and current_list_key:
            item = line[2:].strip().strip('"').strip("'")
            # Strip inline YAML comments: "entity-filters  # Done" → "entity-filters"
            if "  #" in item:
                item = item[:item.index("  #")].strip()
            elif item.startswith("#"):
                item = ""
            if item and isinstance(fm.get(current_list_key), list):
                fm[current_list_key].append(item)
        else:
            current_list_key = None
        i += 1

    return fm, body


def extract_title(body):
    """Extract title from first H1 heading."""
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return None


def extract_description(body):
    """Extract first non-heading paragraph as description."""
    in_block = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
            continue
        if in_block:
            continue
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith(">"):
            # blockquote — use it stripped of >
            desc = re.sub(r"^>\s*", "", stripped)
            if len(desc) > 20:
                return desc
            continue
        # First real paragraph
        if len(stripped) > 20:
            return stripped
    return None


def slug_from_path(filepath):
    """Derive plan ID (slug) from filename."""
    return Path(filepath).stem


def title_from_slug(slug):
    """Convert slug to title-case name."""
    return slug.replace("-", " ").title()


def read_plan(filepath, repository, archived=False):
    """Read a .md file and return a plan dict."""
    try:
        text = Path(filepath).read_text(encoding="utf-8")
    except Exception:
        return None

    fm, body = parse_frontmatter(text)
    slug = slug_from_path(filepath)

    title = extract_title(body)
    if not title:
        title = title_from_slug(slug)

    description = extract_description(body)
    priority = fm.get("priority")

    # Compute status
    blocked_by = fm.get("blocked_by") or []
    if not isinstance(blocked_by, list):
        blocked_by = [blocked_by] if blocked_by else []
    blocked_by = [b for b in blocked_by if b]

    blocks = fm.get("blocks") or []
    if not isinstance(blocks, list):
        blocks = [blocks] if blocks else []
    blocks = [b for b in blocks if b]

    # Namespace ID: repo--slug (e.g. agentos--desk)
    plan_id = f"{repository}--{slug}"

    # Namespace dependency references to match
    blocked_by = [f"{repository}--{b}" for b in blocked_by]
    blocks = [f"{repository}--{b}" for b in blocks]

    return {
        "id": plan_id,
        "name": title,
        "description": description,
        "content": body,
        "priority": priority,
        "data": {
            "repository": repository,
            "slug": slug,
            "filepath": str(filepath),
            "archived": archived,
            "blocked_by": blocked_by,
            "blocks": blocks,
        },
    }


def list_plans_for_repo(repository):
    """List all plans for a single repository."""
    repo_path = REPO_PATHS.get(repository)
    if not repo_path:
        print(f"Unknown repository: {repository}", file=sys.stderr)
        return []

    roadmap_dir = Path(repo_path) / ".ROADMAP"
    if not roadmap_dir.exists():
        return []

    plans = []

    # Active plans
    for md_file in sorted(roadmap_dir.glob("*.md")):
        plan = read_plan(md_file, repository, archived=False)
        if plan:
            plans.append(plan)

    # Archived plans
    archived_dir = roadmap_dir / ".archived"
    if archived_dir.exists():
        for md_file in sorted(archived_dir.glob("*.md")):
            plan = read_plan(md_file, repository, archived=True)
            if plan:
                plans.append(plan)

    return plans


def compute_status(plan, all_plan_ids):
    """Compute plan status: done, blocked, or ready."""
    if plan["data"]["archived"]:
        return "done"

    blocked_by = plan["data"].get("blocked_by", [])
    # Check if any blocker is not done (not archived)
    # We'd need all plans to check; for now return "blocked" if has any unresolved blockers
    # The full status computation happens in the entity schema
    for blocker_id in blocked_by:
        if blocker_id in all_plan_ids and not all_plan_ids[blocker_id].get("data", {}).get("archived"):
            return "blocked"

    return "ready"


def main():
    parser = argparse.ArgumentParser(description="List roadmap plan specs")
    parser.add_argument(
        "--repository",
        default="agentos",
        help="Repository name: agentos, agentos-community, entity-experiments, or all",
    )
    parser.add_argument("--status", nargs="?", default="", help="Filter by status: ready, blocked, done")
    parser.add_argument("--priority", nargs="?", default="", help="Filter by priority: now, high")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.repository == "all":
        repos = list(REPO_PATHS.keys())
    else:
        repos = [args.repository]

    all_plans = []
    for repo in repos:
        all_plans.extend(list_plans_for_repo(repo))

    # Build ID map for status computation
    plan_id_map = {p["id"]: p for p in all_plans}

    # Add computed status
    for plan in all_plans:
        plan["status"] = compute_status(plan, plan_id_map)

    # Filter by status (ignore empty/null)
    if args.status and args.status not in ("", "null", "None"):
        all_plans = [p for p in all_plans if p.get("status") == args.status]

    # Filter by priority (ignore empty/null)
    if args.priority and args.priority not in ("", "null", "None"):
        all_plans = [p for p in all_plans if p.get("priority") == args.priority]

    if args.json:
        print(json.dumps(all_plans, ensure_ascii=False, indent=2))
    else:
        for plan in all_plans:
            status = plan.get("status", "?")
            priority = plan.get("priority") or "-"
            print(f"  [{status:7s}] [{priority:4s}] {plan['id']:40s}  {plan['name'][:50]}")


if __name__ == "__main__":
    main()

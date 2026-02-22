#!/usr/bin/env python3
"""Render roadmap tree from the graph.

Queries plan entities from the AgentOS graph and outputs a dependency tree
grouped by priority (NOW > HIGH > CONSIDERING).

Dependencies come from the enables relationship, injected as blocked_by/blocks
arrays by the computed_relationships system.

Returns JSON: {"tree": "...formatted text..."}
"""

import json
import sys
import urllib.request


API = "http://localhost:3456"


def fetch_plans():
    req = urllib.request.Request(
        f"{API}/mem/plans?limit=500",
        headers={"X-Agent": "roadmap-tree"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read()).get("data", [])


def slug(plan_id):
    return plan_id.split("--", 1)[1] if "--" in plan_id else plan_id


def build_tree(plans):
    by_id = {}
    for p in plans:
        sid = p.get("service_id") or p.get("_entity_id")
        by_id[sid] = p

    active = [p for p in plans if not p.get("done")]

    # Build blocks_map from the graph-sourced "blocks" array.
    # plan["blocks"] = [{service_id, done, name}, ...] — plans that depend on this one.
    blocks_map = {}
    for p in active:
        sid = p.get("service_id") or p.get("_entity_id")
        children = [
            b["service_id"] for b in (p.get("blocks") or [])
            if b.get("service_id") and not b.get("done")
        ]
        if children:
            blocks_map[sid] = children

    now = [p for p in active if p.get("priority") == "now"]
    high = [p for p in active if p.get("priority") == "high"]
    rest = [p for p in active if p.get("priority") not in ("now", "high")]

    lines = []

    def get_roots(plan_list):
        """Plans with no active (undone) blockers."""
        roots = []
        for p in plan_list:
            active_blockers = [
                b for b in (p.get("blocked_by") or [])
                if not b.get("done")
            ]
            if not active_blockers:
                roots.append(p)
        return roots

    def print_tree(plan_id, prefix="    ", is_last=True, seen=None):
        if seen is None:
            seen = set()
        if plan_id in seen:
            return
        seen.add(plan_id)
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        lines.append(f"{prefix}{connector}{slug(plan_id)}")
        children = blocks_map.get(plan_id, [])
        child_prefix = prefix + ("    " if is_last else "\u2502   ")
        for i, child in enumerate(children):
            print_tree(child, child_prefix, i == len(children) - 1, seen)

    def show_section(label, plan_list):
        if not plan_list:
            return
        lines.append("")
        lines.append(label)
        roots = get_roots(plan_list)
        shown = set()
        for p in roots:
            sid = p.get("service_id") or p.get("_entity_id")
            lines.append(f"  {slug(sid)}")
            active_children = [
                c for c in blocks_map.get(sid, [])
                if c in by_id and not by_id[c].get("done")
            ]
            for i, child in enumerate(active_children):
                print_tree(child, "  ", i == len(active_children) - 1, shown)

    show_section("\033[32m\033[1m\u25c9 NOW\033[0m", now)
    show_section("\033[33m\033[1m\u25b2 HIGH PRIORITY\033[0m", high)

    if rest:
        show_section("\033[2m\u25e6 CONSIDERING\033[0m", rest)
        standalone_in_rest = [
            p for p in rest
            if not blocks_map.get(p.get("service_id") or p.get("_entity_id"), [])
            and not [b for b in (p.get("blocked_by") or []) if not b.get("done")]
        ]
        rooted = get_roots(rest)
        non_standalone_roots = [r for r in rooted if r not in standalone_in_rest]
        standalone_count = len(standalone_in_rest)
        if standalone_count > 0 and non_standalone_roots:
            lines.append(f"  \033[2m+{standalone_count} standalone\033[0m")

    return "\n".join(lines)


def main():
    try:
        plans = fetch_plans()
    except Exception as e:
        print(json.dumps({"tree": f"  (could not reach graph: {e})"}))
        sys.exit(0)

    if not plans:
        print(json.dumps({"tree": "  (no plans on graph)"}))
        sys.exit(0)

    tree = build_tree(plans)
    print(json.dumps({"tree": tree}))


if __name__ == "__main__":
    main()

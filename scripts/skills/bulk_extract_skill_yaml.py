#!/usr/bin/env python3
"""
Deterministically split readme.md YAML frontmatter into skill.yaml + markdown body.

Algorithm (same intent as extract-skill-yaml.mjs):
  1. File must start with --- then a newline (LF or CRLF).
  2. The frontmatter ends at the *first* line-boundary occurrence of --- after that
     (i.e. first match of \\r?\\n---\\r?\\n in the remainder).
  3. Optional: PyYAML parse the extracted block; require a mapping with an `id` key.

Usage:
  python3 scripts/skills/bulk_extract_skill_yaml.py plan
  python3 scripts/skills/bulk_extract_skill_yaml.py apply --dry-run
  python3 scripts/skills/bulk_extract_skill_yaml.py apply --all-missing
  python3 scripts/skills/bulk_extract_skill_yaml.py apply amazon exa

Requires: pip install pyyaml  (PyYAML)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml as pyyaml
except ImportError:
    pyyaml = None  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"

# First line-boundary --- after the opening frontmatter (non-greedy line discipline).
CLOSING_DELIM = re.compile(r"\r?\n---\r?\n")


def split_frontmatter(text: str) -> tuple[str, str] | None:
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text.startswith("---"):
        return None
    i = 3
    if text[i : i + 2] == "\r\n":
        i += 2
    elif i < len(text) and text[i] == "\n":
        i += 1
    else:
        return None

    rest = text[i:]
    m = CLOSING_DELIM.search(rest)
    if not m:
        return None
    yaml_part = rest[: m.start()]
    body = rest[m.end() :]
    return yaml_part, body


def validate_yaml_block(yaml_text: str, skill_id: str) -> tuple[bool, str]:
    if pyyaml is None:
        return True, "skip (PyYAML not installed; pip install pyyaml)"
    try:
        data = pyyaml.safe_load(yaml_text)
    except Exception as e:
        return False, f"YAML parse error: {e}"
    if not isinstance(data, dict):
        return False, f"expected mapping at top level, got {type(data).__name__}"
    if "id" not in data:
        return False, "missing top-level id"
    if str(data["id"]) != skill_id:
        return False, f"id mismatch: yaml id={data['id']!r} vs dir={skill_id!r}"
    return True, "ok"


def iter_skill_dirs() -> list[Path]:
    out = []
    for p in sorted(SKILLS_DIR.iterdir()):
        if not p.is_dir() or p.name.startswith("."):
            continue
        if (p / "readme.md").is_file():
            out.append(p)
    return out


def skills_missing_yaml() -> list[Path]:
    return [p for p in iter_skill_dirs() if not (p / "skill.yaml").exists()]


def plan() -> int:
    missing = skills_missing_yaml()
    print(f"Skills with readme.md but no skill.yaml: {len(missing)}\n")
    bad = 0
    for d in missing:
        name = d.name
        text = (d / "readme.md").read_text(encoding="utf-8")
        split = split_frontmatter(text)
        if split is None:
            print(f"  FAIL  {name}  (no standard --- … --- frontmatter)")
            bad += 1
            continue
        ypart, _ = split
        ok, msg = validate_yaml_block(ypart, name)
        status = "ok" if ok else "FAIL"
        if not ok:
            bad += 1
        # Count --- lines (informational; body may add more after split)
        n_delim = sum(1 for line in text.splitlines() if line.strip() == "---")
        print(f"  {status:4}  {name:24}  --- lines in file: {n_delim}  {msg}")
    print()
    if bad:
        print(f"Plan: {bad} skill(s) need manual handling.")
        return 1
    print("Plan: all candidates split + validate cleanly.")
    return 0


def apply_skill(d: Path, dry_run: bool) -> tuple[bool, str]:
    name = d.name
    readme = d / "readme.md"
    out_yaml = d / "skill.yaml"
    if out_yaml.exists():
        return True, "skip (skill.yaml exists)"
    text = readme.read_text(encoding="utf-8")
    split = split_frontmatter(text)
    if split is None:
        return False, "no standard frontmatter"
    ypart, body = split
    ok, msg = validate_yaml_block(ypart, name)
    if not ok:
        return False, msg
    yaml_out = ypart.rstrip() + "\n"
    md_out = body.lstrip("\n\r")
    if dry_run:
        return True, f"dry-run: would write {len(yaml_out)}b yaml, {len(md_out)}b readme"
    out_yaml.write_text(yaml_out, encoding="utf-8")
    readme.write_text(md_out, encoding="utf-8")
    return True, "wrote skill.yaml + readme.md"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("plan", help="Report split+validate for every skill missing skill.yaml")

    ap_apply = sub.add_parser("apply", help="Extract skill.yaml for listed skills or --all-missing")
    ap_apply.add_argument("ids", nargs="*", help="Skill directory names")
    ap_apply.add_argument(
        "--all-missing",
        action="store_true",
        help="Every skill under skills/ with readme.md and no skill.yaml",
    )
    ap_apply.add_argument("--dry-run", action="store_true")

    args = ap.parse_args()

    if pyyaml is None and args.cmd == "plan":
        print("WARNING: PyYAML not installed; plan validate step will be skipped.\n", file=sys.stderr)

    if args.cmd == "plan":
        return plan()

    if not args.ids and not args.all_missing:
        ap_apply.error("pass skill ids or --all-missing")

    if args.all_missing:
        targets = skills_missing_yaml()
    else:
        targets = []
        for sid in args.ids:
            d = SKILLS_DIR / sid
            if not d.is_dir():
                print(f"ERROR: unknown skill {sid!r}", file=sys.stderr)
                return 1
            targets.append(d)

    failed = 0
    for d in targets:
        ok, msg = apply_skill(d, args.dry_run)
        tag = "ok" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  {tag:4}  {d.name:24}  {msg}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

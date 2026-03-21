#!/usr/bin/env python3
"""
Check that all local markdown links in docs/ resolve to real files after mdBook build.

Run from repo root:
    mdbook build && python3 scripts/check-links.py
"""

import re, sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
BUILD = Path(__file__).resolve().parent.parent / "target" / "book"

# Match markdown links: [text](target) — skip http/https/mailto
LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
SKIP_PREFIXES = ('http://', 'https://', 'mailto:', '#')


def check_file(md_path):
    """Check all local links in a markdown file resolve in the build output."""
    errors = []
    content = md_path.read_text()
    rel_dir = md_path.parent

    for match in LINK_RE.finditer(content):
        text, target = match.group(1), match.group(2)

        # Strip fragment
        target_no_frag = target.split('#')[0]
        if not target_no_frag or any(target_no_frag.startswith(p) for p in SKIP_PREFIXES):
            continue

        # Resolve the target relative to the source file's directory
        resolved_src = (rel_dir / target_no_frag).resolve()

        # Check source file exists (raw markdown)
        if resolved_src.exists():
            continue

        # If it ends in .html, check the build directory
        if target_no_frag.endswith('.html'):
            # Map source path to build path
            try:
                rel_from_docs = md_path.parent.relative_to(DOCS)
            except ValueError:
                rel_from_docs = Path('.')
            build_target = (BUILD / rel_from_docs / target_no_frag).resolve()
            if build_target.exists():
                continue

        line_num = content[:match.start()].count('\n') + 1
        errors.append((line_num, text, target))

    return errors


def main():
    if not BUILD.exists():
        print("Build directory not found. Run `mdbook build` first.")
        sys.exit(1)

    all_errors = []
    for md in sorted(DOCS.rglob('*.md')):
        errors = check_file(md)
        if errors:
            rel = md.relative_to(DOCS)
            for line, text, target in errors:
                all_errors.append(f"  {rel}:{line} — [{text}]({target})")

    if all_errors:
        print(f"Found {len(all_errors)} broken link(s):\n")
        for e in all_errors:
            print(e)
        sys.exit(1)
    else:
        print(f"All links OK across {sum(1 for _ in DOCS.rglob('*.md'))} files.")


if __name__ == "__main__":
    main()

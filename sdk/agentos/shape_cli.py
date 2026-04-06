"""agent-sdk shapes — shape discovery CLI."""

import os
import sys
from pathlib import Path

import yaml


def _find_shapes_dir() -> Path | None:
    """Find the shapes directory."""
    env = os.environ.get("AGENT_SHAPES_DIR")
    if env:
        p = Path(env)
        if p.is_dir():
            return p
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / "shapes"
        if candidate.is_dir() and (candidate / "event.yaml").exists():
            return candidate
    return None


def _load_all_shapes(shapes_dir: Path) -> dict:
    """Load all shapes from YAML files."""
    shapes = {}
    for f in sorted(shapes_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text())
            if isinstance(data, dict):
                for name, spec in data.items():
                    if isinstance(spec, dict):
                        shapes[name] = spec
        except Exception:
            pass
    return shapes


def _format_type(t: str) -> str:
    """Format a field type for display."""
    return t


def run_shapes(name: str | None):
    """List all shapes or inspect one."""
    shapes_dir = _find_shapes_dir()
    if not shapes_dir:
        print("  Error: shapes directory not found", file=sys.stderr)
        print("  Set AGENT_SHAPES_DIR or run from inside the agentos-community repo", file=sys.stderr)
        sys.exit(1)

    shapes = _load_all_shapes(shapes_dir)

    if not name:
        # List all shapes
        print(f"\n  {len(shapes)} shapes available:\n")
        # Group by rough category based on common patterns
        for shape_name in sorted(shapes.keys()):
            spec = shapes[shape_name]
            fields = spec.get("fields", {})
            relations = spec.get("relations", {})
            field_count = len(fields) if isinstance(fields, dict) else 0
            rel_count = len(relations) if isinstance(relations, dict) else 0
            plural = spec.get("plural", shape_name + "s")
            print(f"  {shape_name:<24} {field_count} fields, {rel_count} relations  ({plural})")
        print()
    else:
        # Inspect one shape
        if name not in shapes:
            # Try fuzzy match
            matches = [s for s in shapes if name.lower() in s.lower()]
            if matches:
                print(f"  Shape '{name}' not found. Did you mean: {', '.join(matches)}")
            else:
                print(f"  Shape '{name}' not found")
            sys.exit(1)

        spec = shapes[name]
        plural = spec.get("plural", name + "s")
        identity = spec.get("identity", "id")
        subtitle = spec.get("subtitle", "")

        print(f"\n  {name} ({plural})")
        print(f"  {'─' * (len(name) + len(plural) + 3)}")
        if identity:
            print(f"  identity: {identity}")
        if subtitle:
            print(f"  subtitle: {subtitle}")

        fields = spec.get("fields", {})
        if isinstance(fields, dict) and fields:
            print(f"\n  Fields ({len(fields)}):")
            # Standard fields always available
            print(f"    {'id':<28} string     (standard)")
            print(f"    {'name':<28} string     (standard)")
            print(f"    {'url':<28} string     (standard)")
            print(f"    {'image':<28} string     (standard)")
            print(f"    {'published':<28} datetime   (standard)")
            print(f"    {'content':<28} string     (standard)")
            for fname, ftype in fields.items():
                ftype_str = str(ftype) if ftype else "string"
                print(f"    {fname:<28} {ftype_str}")

        relations = spec.get("relations", {})
        if isinstance(relations, dict) and relations:
            print(f"\n  Relations ({len(relations)}):")
            for rname, rtype in relations.items():
                rtype_str = str(rtype) if rtype else "?"
                print(f"    {rname:<28} → {rtype_str}")

        # Find which skills use this shape
        skills_dir = shapes_dir.parent / "skills"
        if skills_dir.is_dir():
            using = []
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                for py_file in skill_dir.glob("*.py"):
                    try:
                        content = py_file.read_text()
                        if f'@returns("{name}' in content:
                            using.append(skill_dir.name)
                            break
                    except Exception:
                        pass
            if using:
                print(f"\n  Used by: {', '.join(using)}")

        print()

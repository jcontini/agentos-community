"""Auto-generated TypedDict classes from shape YAML files.

Usage:
    from agentos.shapes import Person, Book, Post

Run `python -m agentos.shapes` to regenerate after shape changes.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

# Try to import generated shapes — they may not exist yet
try:
    from agentos._generated import *  # noqa: F401,F403
except ImportError:
    pass

# Well-known fields present on all shapes (from the engine)
WELL_KNOWN_FIELDS = {
    "id": "str",
    "name": "str",
    "text": "str",
    "url": "str",
    "image": "str",
    "author": "str",
    "datePublished": "str",
    "content": "str",
}

# Shape field type → Python type annotation
_TYPE_MAP = {
    "string": "str",
    "text": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "datetime": "str",
    "url": "str",
    "json": "Any",
    "string[]": "list[str]",
    "integer[]": "list[int]",
}

# Python reserved words that can't be field names
_RESERVED = {
    "from", "import", "class", "return", "def", "if", "else", "for",
    "while", "with", "as", "try", "except", "finally", "raise", "pass",
    "break", "continue", "and", "or", "not", "in", "is", "lambda",
    "global", "nonlocal", "yield", "assert", "del", "True", "False", "None",
}


def _python_type(field_type: str) -> str:
    """Convert a shape field type to a Python type annotation."""
    return _TYPE_MAP.get(field_type, "Any")


def _class_name(shape_name: str) -> str:
    """Convert a shape name to PascalCase class name."""
    return "".join(word.capitalize() for word in shape_name.replace("-", "_").split("_"))


def _load_shapes(shapes_dir: Path) -> dict[str, dict]:
    """Load all shape YAML files from a directory."""
    try:
        import yaml
    except ImportError:
        print("pyyaml required: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    shapes = {}
    for f in sorted(shapes_dir.glob("*.yaml")):
        with open(f) as fh:
            data = yaml.safe_load(fh)
        if data and isinstance(data, dict):
            for name, defn in data.items():
                if isinstance(defn, dict):
                    shapes[name] = defn
    return shapes


def generate(shapes_dir: Path | None = None, output: Path | None = None) -> str:
    """Generate TypedDict classes from shape YAML files.

    Returns the generated Python source code.
    """
    if shapes_dir is None:
        # Default: look relative to this file's location in the community repo
        sdk_dir = Path(__file__).parent.parent
        shapes_dir = sdk_dir.parent / "shapes"
        if not shapes_dir.is_dir():
            # Try AGENTOS_SHAPES_DIR env var
            env_dir = os.environ.get("AGENTOS_SHAPES_DIR")
            if env_dir:
                shapes_dir = Path(env_dir)

    if not shapes_dir.is_dir():
        raise FileNotFoundError(f"Shapes directory not found: {shapes_dir}")

    shapes = _load_shapes(shapes_dir)
    lines = [
        '"""Auto-generated TypedDict classes from shape YAML — do not edit.',
        '',
        f'Generated from {len(shapes)} shapes in {shapes_dir.name}/.',
        'Regenerate with: python -m agentos.shapes',
        '"""',
        '',
        'from __future__ import annotations',
        '',
        'from typing import Any, TypedDict',
        '',
    ]

    # Resolve `also` chains so inherited fields are included
    def resolve_fields(name: str, seen: set | None = None) -> dict[str, str]:
        if seen is None:
            seen = set()
        if name in seen:
            return {}
        seen.add(name)
        defn = shapes.get(name, {})
        fields = {}
        # Inherit from `also` first
        for also_name in defn.get("also", []):
            fields.update(resolve_fields(also_name, seen))
        # Own fields override
        for field_name, field_type in (defn.get("fields") or {}).items():
            fields[field_name] = str(field_type)
        return fields

    def resolve_relations(name: str, seen: set | None = None) -> dict[str, str]:
        if seen is None:
            seen = set()
        if name in seen:
            return {}
        seen.add(name)
        defn = shapes.get(name, {})
        rels = {}
        for also_name in defn.get("also", []):
            rels.update(resolve_relations(also_name, seen))
        for label, target in (defn.get("relations") or {}).items():
            rels[label] = str(target)
        return rels

    for shape_name in sorted(shapes.keys()):
        cls = _class_name(shape_name)
        fields = resolve_fields(shape_name)
        relations = resolve_relations(shape_name)

        lines.append(f"class {cls}(TypedDict, total=False):")

        # Well-known fields first
        for wk_name, wk_type in WELL_KNOWN_FIELDS.items():
            lines.append(f"    {wk_name}: {wk_type}")

        # Shape-declared fields
        for field_name, field_type in sorted(fields.items()):
            if field_name in WELL_KNOWN_FIELDS:
                continue
            # Dot-notation fields → underscore (can't be Python identifiers)
            if "." in field_name:
                safe = field_name.replace(".", "_")
                py_type = _python_type(field_type)
                lines.append(f"    {safe}: {py_type}  # {field_name}")
            elif field_name in _RESERVED:
                lines.append(f"    {field_name}_: {_python_type(field_type)}  # {field_name}")
            else:
                py_type = _python_type(field_type)
                lines.append(f"    {field_name}: {py_type}")

        # Relations as typed fields
        for label, target in sorted(relations.items()):
            is_array = target.endswith("[]")
            target_name = target.rstrip("[]")
            target_cls = _class_name(target_name)
            safe_label = f"{label}_" if label in _RESERVED else label
            if is_array:
                lines.append(f"    {safe_label}: list[{target_cls}]  # {label}" if label in _RESERVED else f"    {safe_label}: list[{target_cls}]")
            else:
                lines.append(f"    {safe_label}: {target_cls}  # {label}" if label in _RESERVED else f"    {safe_label}: {target_cls}")

        lines.append("")
        lines.append("")

    source = "\n".join(lines)

    if output:
        output.write_text(source)
        print(f"Generated {len(shapes)} TypedDict classes → {output}")

    return source


if __name__ == "__main__":
    output_path = Path(__file__).parent / "_generated.py"
    generate(output=output_path)

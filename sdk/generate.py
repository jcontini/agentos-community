#!/usr/bin/env python3
"""Multi-language shape codegen from shapes/*.yaml.

Reads shape YAML definitions, resolves inheritance (`also` chains) and
relations, then emits typed classes for each target language.

Usage:
    python generate.py                        # all languages
    python generate.py --lang python          # Python TypedDicts only
    python generate.py --lang typescript      # TypeScript interfaces only
    python generate.py --lang swift           # Swift Codable structs only
    python generate.py --lang go              # Go structs only
    python generate.py --lang rust            # Rust serde structs only
    python generate.py --shapes-dir ../shapes # custom shapes location
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# =============================================================================
# Intermediate representation
# =============================================================================

STANDARD_FIELDS = [
    ("id", "string"),
    ("name", "string"),
    ("text", "string"),
    ("url", "string"),
    ("image", "string"),
    ("author", "string"),
    ("datePublished", "string"),
    ("content", "string"),
]


@dataclass
class Field:
    name: str           # original YAML name (snake_case, may have dots)
    type: str           # shape type: string, integer, number, boolean, datetime, url, json, string[]
    is_relation: bool
    is_array: bool
    target: str | None  # for relations: target shape name (e.g. "author", "account")


@dataclass
class Shape:
    name: str           # YAML name (snake_case)
    class_name: str     # PascalCase
    fields: list[Field] = field(default_factory=list)


# =============================================================================
# Loader — YAML → intermediate representation
# =============================================================================

def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case. Leaves snake_case unchanged."""
    return re.sub(r"([a-z])([A-Z])", r"\1_\2", name).lower()


def to_class_name(name: str) -> str:
    snake = _camel_to_snake(name).replace("-", "_")
    return "".join(w.capitalize() for w in snake.split("_"))


def load_shapes(shapes_dir: Path) -> list[Shape]:
    try:
        import yaml
    except ImportError:
        print("pyyaml required: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    raw: dict[str, dict] = {}
    for f in sorted(shapes_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        if data and isinstance(data, dict):
            for name, defn in data.items():
                if isinstance(defn, dict):
                    raw[name] = defn

    def resolve_fields(name: str, seen: set | None = None) -> dict[str, str]:
        if seen is None:
            seen = set()
        if name in seen:
            return {}
        seen.add(name)
        defn = raw.get(name, {})
        fields = {}
        for also in defn.get("also", []):
            fields.update(resolve_fields(also, seen))
        for fname, ftype in (defn.get("fields") or {}).items():
            fields[fname] = str(ftype)
        return fields

    def resolve_relations(name: str, seen: set | None = None) -> dict[str, str]:
        if seen is None:
            seen = set()
        if name in seen:
            return {}
        seen.add(name)
        defn = raw.get(name, {})
        rels = {}
        for also in defn.get("also", []):
            rels.update(resolve_relations(also, seen))
        for label, target in (defn.get("relations") or {}).items():
            rels[label] = str(target)
        return rels

    shapes = []
    for shape_name in sorted(raw.keys()):
        s = Shape(name=shape_name, class_name=to_class_name(shape_name))

        # Standard fields first
        for wk_name, wk_type in STANDARD_FIELDS:
            s.fields.append(Field(wk_name, wk_type, False, False, None))

        # Shape-declared fields
        for fname, ftype in sorted(resolve_fields(shape_name).items()):
            if any(sf[0] == fname for sf in STANDARD_FIELDS):
                continue
            is_array = ftype.endswith("[]")
            base = ftype.rstrip("[]") if is_array else ftype
            s.fields.append(Field(fname, ftype, False, is_array, None))

        # Relations
        for label, target in sorted(resolve_relations(shape_name).items()):
            is_array = target.endswith("[]")
            target_name = target.rstrip("[]")
            s.fields.append(Field(label, target, True, is_array, target_name))

        shapes.append(s)

    return shapes


# =============================================================================
# Python emitter — TypedDict
# =============================================================================

_PY_TYPES = {
    "string": "str", "text": "str", "integer": "int", "number": "float",
    "boolean": "bool", "datetime": "str", "url": "str", "json": "Any",
    "string[]": "list[str]", "integer[]": "list[int]",
}

_PY_RESERVED = {
    "from", "import", "class", "return", "def", "if", "else", "for",
    "while", "with", "as", "try", "except", "finally", "raise", "pass",
    "break", "continue", "and", "or", "not", "in", "is", "lambda",
    "global", "nonlocal", "yield", "assert", "del", "True", "False", "None",
}


def emit_python(shapes: list[Shape]) -> str:
    lines = [
        '"""Auto-generated TypedDict classes from shape YAML — do not edit.',
        "",
        f"Generated from {len(shapes)} shapes.",
        "Regenerate with: python generate.py --lang python",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any, TypedDict",
        "",
    ]

    for s in shapes:
        lines.append(f"class {s.class_name}(TypedDict, total=False):")
        for f in s.fields:
            safe = _py_field_name(f.name)
            comment = f"  # {f.name}" if safe != f.name else ""
            ty = _py_type(f, s)
            lines.append(f"    {safe}: {ty}{comment}")
        lines.append("")
        lines.append("")

    return "\n".join(lines)


def _py_field_name(name: str) -> str:
    if "." in name:
        return name.replace(".", "_")
    if name in _PY_RESERVED:
        return f"{name}_"
    return name


def _py_type(f: Field, s: Shape) -> str:
    if f.is_relation:
        cls = to_class_name(f.target)
        return f"list[{cls}]" if f.is_array else cls
    return _PY_TYPES.get(f.type, "Any")


# =============================================================================
# TypeScript emitter — interfaces
# =============================================================================

_TS_TYPES = {
    "string": "string", "text": "string", "integer": "number",
    "number": "number", "boolean": "boolean", "datetime": "string",
    "url": "string", "json": "unknown",
    "string[]": "string[]", "integer[]": "number[]",
}


def emit_typescript(shapes: list[Shape]) -> str:
    lines = [
        "// Auto-generated from shape YAML — do not edit.",
        f"// Generated from {len(shapes)} shapes.",
        "// Regenerate with: python generate.py --lang typescript",
        "",
    ]

    for s in shapes:
        lines.append(f"export interface {s.class_name} {{")
        for f in s.fields:
            name = _ts_field_name(f.name)
            ty = _ts_type(f)
            lines.append(f"    {name}?: {ty};")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def _ts_field_name(name: str) -> str:
    if "." in name:
        return _to_camel(name.replace(".", "_"))
    return _to_camel(name)


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


def _ts_type(f: Field) -> str:
    if f.is_relation:
        cls = to_class_name(f.target)
        return f"{cls}[]" if f.is_array else cls
    return _TS_TYPES.get(f.type, "unknown")


# =============================================================================
# Swift emitter — Codable structs
# =============================================================================

_SWIFT_TYPES = {
    "string": "String", "text": "String", "integer": "Int",
    "number": "Double", "boolean": "Bool", "datetime": "String",
    "url": "String", "json": "AnyCodable",
    "string[]": "[String]", "integer[]": "[Int]",
}

_SWIFT_RESERVED = {
    "class", "struct", "enum", "protocol", "func", "var", "let", "import",
    "return", "if", "else", "for", "while", "switch", "case", "default",
    "break", "continue", "in", "as", "is", "self", "Self", "true", "false",
    "nil", "operator", "typealias", "associatedtype", "throw", "throws",
    "try", "catch", "where", "guard", "repeat", "defer", "do",
}


def emit_swift(shapes: list[Shape]) -> str:
    lines = [
        "// Auto-generated from shape YAML — do not edit.",
        f"// Generated from {len(shapes)} shapes.",
        "// Regenerate with: python generate.py --lang swift",
        "",
        "import Foundation",
        "",
    ]

    for s in shapes:
        lines.append(f"struct {s.class_name}: Codable {{")

        # Properties
        needs_coding_keys = False
        for f in s.fields:
            swift_name = _swift_field_name(f.name)
            ty = _swift_type(f)
            lines.append(f"    var {swift_name}: {ty}?")
            if swift_name != f.name:
                needs_coding_keys = True

        # CodingKeys enum (only if any field name differs)
        if needs_coding_keys:
            lines.append("")
            lines.append("    enum CodingKeys: String, CodingKey {")
            simple = []
            mapped = []
            for f in s.fields:
                swift_name = _swift_field_name(f.name)
                if swift_name == f.name:
                    simple.append(swift_name)
                else:
                    mapped.append((swift_name, f.name))
            if simple:
                lines.append(f"        case {', '.join(simple)}")
            for swift_name, orig in mapped:
                lines.append(f'        case {swift_name} = "{orig}"')
            lines.append("    }")

        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def _swift_field_name(name: str) -> str:
    # Dots to camelCase
    if "." in name:
        name = name.replace(".", "_")
    # snake_case to camelCase
    name = _to_camel(name)
    if name in _SWIFT_RESERVED:
        return f"`{name}`"
    return name


def _swift_type(f: Field) -> str:
    if f.is_relation:
        cls = to_class_name(f.target)
        return f"[{cls}]" if f.is_array else cls
    return _SWIFT_TYPES.get(f.type, "AnyCodable")


# =============================================================================
# Go emitter — structs with json tags
# =============================================================================

_GO_TYPES = {
    "string": "string", "text": "string", "integer": "int",
    "number": "float64", "boolean": "bool", "datetime": "string",
    "url": "string", "json": "any",
    "string[]": "[]string", "integer[]": "[]int",
}

_GO_RESERVED = {
    "break", "case", "chan", "const", "continue", "default", "defer",
    "else", "fallthrough", "for", "func", "go", "goto", "if", "import",
    "interface", "map", "package", "range", "return", "select", "struct",
    "switch", "type", "var",
}


def emit_go(shapes: list[Shape]) -> str:
    lines = [
        "// Auto-generated from shape YAML — do not edit.",
        f"// Generated from {len(shapes)} shapes.",
        "// Regenerate with: python generate.py --lang go",
        "",
        "package shapes",
        "",
    ]

    for s in shapes:
        lines.append(f"type {s.class_name} struct {{")
        for f in s.fields:
            go_name = _go_field_name(f.name)
            ty = _go_type(f)
            tag = f.name
            lines.append(f'\t{go_name} {ty} `json:"{tag},omitempty"`')
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def _go_field_name(name: str) -> str:
    if "." in name:
        name = name.replace(".", "_")
    # Normalize camelCase to snake_case first, then PascalCase
    snake = _camel_to_snake(name)
    result = "".join(w.capitalize() for w in snake.split("_"))
    # Common initialisms
    for initialism in ("Id", "Url", "Html", "Http", "Isbn", "Dns", "Ip", "Ssh", "Ssl", "Tls", "Api"):
        if result.endswith(initialism) or result == initialism:
            result = result[: -len(initialism)] + initialism.upper()
    if result in _GO_RESERVED:
        result += "_"
    return result


def _go_type(f: Field) -> str:
    if f.is_relation:
        cls = to_class_name(f.target)
        return f"[]{cls}" if f.is_array else f"*{cls}"
    base = _GO_TYPES.get(f.type, "any")
    if f.is_array:
        return base  # already has [] prefix for known array types
    return f"*{base}"  # pointer for optional


# =============================================================================
# Rust emitter — serde structs
# =============================================================================

_RUST_TYPES = {
    "string": "String", "text": "String", "integer": "i64",
    "number": "f64", "boolean": "bool", "datetime": "String",
    "url": "String", "json": "serde_json::Value",
    "string[]": "Vec<String>", "integer[]": "Vec<i64>",
}

_RUST_RESERVED = {
    "as", "break", "const", "continue", "crate", "else", "enum", "extern",
    "false", "fn", "for", "if", "impl", "in", "let", "loop", "match",
    "mod", "move", "mut", "pub", "ref", "return", "self", "Self", "static",
    "struct", "super", "trait", "true", "type", "unsafe", "use", "where",
    "while", "async", "await", "dyn",
}


def emit_rust(shapes: list[Shape]) -> str:
    lines = [
        "// Auto-generated from shape YAML — do not edit.",
        f"// Generated from {len(shapes)} shapes.",
        "// Regenerate with: python generate.py --lang rust",
        "",
        "use serde::{Deserialize, Serialize};",
        "",
    ]

    for s in shapes:
        lines.append("#[derive(Debug, Clone, Default, Serialize, Deserialize)]")
        lines.append(f"pub struct {s.class_name} {{")
        for f in s.fields:
            rust_name = _rust_field_name(f.name)
            ty = _rust_type(f)
            rename = ""
            if rust_name != f.name:
                rename = f'    #[serde(rename = "{f.name}")]\n'
            lines.append(f"{rename}    #[serde(skip_serializing_if = \"Option::is_none\")]")
            lines.append(f"    pub {rust_name}: Option<{ty}>,")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def _rust_field_name(name: str) -> str:
    if "." in name:
        name = name.replace(".", "_")
    name = _camel_to_snake(name)
    if name in _RUST_RESERVED:
        return f"r#{name}"
    return name


def _rust_type(f: Field) -> str:
    if f.is_relation:
        cls = to_class_name(f.target)
        return f"Vec<{cls}>" if f.is_array else cls
    return _RUST_TYPES.get(f.type, "serde_json::Value")


# =============================================================================
# CLI
# =============================================================================

EMITTERS = {
    "python": (emit_python, "_generated.py"),
    "typescript": (emit_typescript, "shape.ts"),
    "swift": (emit_swift, "Shape.swift"),
    "go": (emit_go, "shape.go"),
    "rust": (emit_rust, "shape.rs"),
}


def main():
    parser = argparse.ArgumentParser(description="Generate typed shapes for multiple languages")
    parser.add_argument("--lang", choices=list(EMITTERS.keys()), help="Language to generate (default: all)")
    parser.add_argument("--shapes-dir", type=Path, help="Path to shapes/ directory")
    parser.add_argument("--out-dir", type=Path, help="Output directory (default: sdk/generated/)")
    args = parser.parse_args()

    sdk_dir = Path(__file__).parent
    shapes_dir = args.shapes_dir or sdk_dir.parent / "shapes"
    out_dir = args.out_dir or sdk_dir / "generated"

    if not shapes_dir.is_dir():
        print(f"Shapes directory not found: {shapes_dir}", file=sys.stderr)
        sys.exit(1)

    shapes = load_shapes(shapes_dir)
    print(f"Loaded {len(shapes)} shapes from {shapes_dir}")

    out_dir.mkdir(exist_ok=True)

    langs = [args.lang] if args.lang else list(EMITTERS.keys())
    for lang in langs:
        emitter, filename = EMITTERS[lang]
        output = emitter(shapes)
        out_path = out_dir / filename

        # Python also writes to the SDK package location
        if lang == "python":
            pkg_path = sdk_dir / "agentos" / "_generated.py"
            pkg_path.write_text(output)
            print(f"  {lang}: {pkg_path}")

        out_path.write_text(output)
        print(f"  {lang}: {out_path}")


if __name__ == "__main__":
    main()

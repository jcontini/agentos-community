"""agent-sdk validate — offline skill validation.

Checks:
1. Skill dir structure (readme.md + *.py)
2. Frontmatter schema (required fields, no unknown keys)
3. Decorator presence (@returns on every public function)
4. Import safety (no urllib, subprocess, sqlite3 — use SDK modules)
5. camelCase enforcement on output dict keys
6. Shape conformance (field names match declared shape)
"""

import ast
import os
import re
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_FRONTMATTER = {"id", "name"}
KNOWN_FRONTMATTER = {
    "id", "name", "description", "color", "website",
    "connections", "privacy_url", "terms_url", "product",
    "test", "operations", "sources", "accounts",
}

VALID_AUTH_TYPES = {"api_key", "cookies", "oauth", "none"}

# Imports that indicate sandbox violations — must use SDK modules instead.
BLOCKED_IMPORTS = {
    "urllib": "use `from agentos import http` (http.get, http.post)",
    "urllib.request": "use `from agentos import http` (http.get, http.post)",
    "urllib.parse": "use `from agentos import http` (http.get, http.post)",
    "urllib3": "use `from agentos import http` (http.get, http.post)",
    "requests": "use `from agentos import http` (http.get, http.post)",
    "httpx": "use `from agentos import http` (http.get, http.post)",
    "aiohttp": "use `from agentos import http` (http.get, http.post)",
    "subprocess": "use `from agentos import shell` (shell.run)",
    "sqlite3": "use `from agentos import sql` (sql.query, sql.execute)",
    "os.popen": "use `from agentos import shell` (shell.run)",
}

# Modules where we only block specific sub-imports
BLOCKED_FROM_IMPORTS = {
    "urllib": "use `from agentos import http`",
    "urllib.request": "use `from agentos import http`",
    "urllib.parse": "allowed (URL construction is fine)",  # actually ok
}

# urllib.parse is a special case — it's used for URL construction, not HTTP.
# We allow it explicitly.
ALLOWED_URLLIB = {"urllib.parse"}

# snake_case pattern — dict keys that look like shape fields
_SNAKE_RE = re.compile(r"^[a-z]+_[a-z]")


# ---------------------------------------------------------------------------
# Shape loading
# ---------------------------------------------------------------------------

def _find_shapes_dir() -> Path | None:
    """Find the shapes directory. Checks: env var, CWD ancestors, bundled package data."""
    # Check env var first
    env = os.environ.get("AGENT_SHAPES_DIR")
    if env:
        p = Path(env)
        if p.is_dir():
            return p

    # Walk up from CWD looking for shapes/
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / "shapes"
        if candidate.is_dir() and (candidate / "event.yaml").exists():
            return candidate

    # Bundled shapes inside the package
    bundled = Path(__file__).parent / "shapes"
    if bundled.is_dir():
        return bundled

    return None


def _load_shapes(shapes_dir: Path) -> dict[str, dict]:
    """Load all shape definitions from YAML files. Returns {name: {fields, relations}}."""
    shapes = {}
    for f in shapes_dir.glob("*.yaml"):
        try:
            with open(f) as fh:
                content = fh.read()
            # Shape files have the shape name as top-level key
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                for name, spec in data.items():
                    if isinstance(spec, dict):
                        fields = set(spec.get("fields", {}).keys()) if isinstance(spec.get("fields"), dict) else set()
                        relations = set(spec.get("relations", {}).keys()) if isinstance(spec.get("relations"), dict) else set()
                        # Standard fields available on all shapes
                        fields |= {"id", "name", "url", "image", "published", "content", "platform"}
                        shapes[name] = {"fields": fields, "relations": relations, "file": f.name}
        except Exception:
            pass
    return shapes


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def _parse_frontmatter(readme_path: Path) -> tuple[dict | None, list[str]]:
    """Parse YAML frontmatter from readme.md. Returns (data, errors)."""
    errors = []
    try:
        text = readme_path.read_text()
    except Exception as e:
        return None, [f"cannot read readme.md: {e}"]

    if not text.startswith("---"):
        return None, ["readme.md has no YAML frontmatter (must start with ---)"]

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, ["readme.md frontmatter not closed (missing second ---)"]

    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return None, [f"invalid YAML in frontmatter: {e}"]

    if not isinstance(data, dict):
        return None, ["frontmatter is not a YAML mapping"]

    return data, errors


def _check_frontmatter(data: dict) -> list[str]:
    """Validate frontmatter fields. Returns list of errors."""
    errors = []

    # Required fields
    for key in REQUIRED_FRONTMATTER:
        if key not in data:
            errors.append(f"missing required frontmatter field: {key}")

    # Unknown keys
    for key in data:
        if key not in KNOWN_FRONTMATTER:
            # Suggest closest match
            closest = _closest_match(key, KNOWN_FRONTMATTER)
            hint = f" (did you mean '{closest}'?)" if closest else ""
            errors.append(f"unknown frontmatter field: '{key}'{hint}")

    # Connection auth types
    connections = data.get("connections")
    if isinstance(connections, dict):
        for conn_name, conn in connections.items():
            if isinstance(conn, dict):
                auth = conn.get("auth")
                if isinstance(auth, dict):
                    auth_type = auth.get("type")
                    if auth_type and auth_type not in VALID_AUTH_TYPES:
                        errors.append(f"connection '{conn_name}': unknown auth type '{auth_type}' (valid: {', '.join(sorted(VALID_AUTH_TYPES))})")

    return errors


def _closest_match(word: str, candidates: set[str], max_dist: int = 3) -> str | None:
    """Find closest match by edit distance."""
    best = None
    best_dist = max_dist + 1
    for c in candidates:
        d = _edit_distance(word.lower(), c.lower())
        if d < best_dist:
            best_dist = d
            best = c
    return best if best_dist <= max_dist else None


def _edit_distance(a: str, b: str) -> int:
    """Simple Levenshtein distance."""
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for j in range(1, len(b) + 1):
        curr = [j] + [0] * len(a)
        for i in range(1, len(a) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[i] = min(curr[i - 1] + 1, prev[i] + 1, prev[i - 1] + cost)
        prev = curr
    return prev[len(a)]


# ---------------------------------------------------------------------------
# Python AST checks
# ---------------------------------------------------------------------------

def _check_python_file(py_path: Path, shapes: dict) -> tuple[list[str], list[str], list[str]]:
    """Check a Python file. Returns (errors, warnings, info)."""
    errors = []
    warnings = []
    info = []

    try:
        source = py_path.read_text()
    except Exception as e:
        return [f"cannot read {py_path.name}: {e}"], warnings, info

    try:
        tree = ast.parse(source, filename=str(py_path))
    except SyntaxError as e:
        return [f"{py_path.name}: syntax error at line {e.lineno}: {e.msg}"], warnings, info

    # Check imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if module in BLOCKED_IMPORTS and module not in ALLOWED_URLLIB:
                    errors.append(
                        f"{py_path.name}:{node.lineno}: blocked import `{module}` — "
                        f"{BLOCKED_IMPORTS[module]}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in BLOCKED_IMPORTS and module not in ALLOWED_URLLIB:
                errors.append(
                    f"{py_path.name}:{node.lineno}: blocked import `from {module}` — "
                    f"{BLOCKED_IMPORTS[module]}"
                )

    # Check functions
    ops_found = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue  # private function
            ops_found.append(node.name)
            _check_operation(node, py_path, shapes, errors, warnings)

    if ops_found:
        info.append(f"{py_path.name}: {len(ops_found)} operations — {', '.join(ops_found)}")

    # Check for snake_case dict keys in return statements of public functions only
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                _check_dict_keys(node, py_path, errors)

    return errors, warnings, info


def _check_operation(func: ast.FunctionDef, py_path: Path, shapes: dict,
                     errors: list, warnings: list):
    """Check a single operation function."""
    name = func.name

    # Check for @returns decorator
    has_returns = False
    returns_shape = None
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "returns":
            has_returns = True
            if dec.args:
                arg = dec.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    returns_shape = arg.value
    if not has_returns:
        errors.append(f"{py_path.name}:{func.lineno}: `{name}` missing @returns decorator")

    # Check for **params
    has_params = bool(func.args.kwarg)
    if not has_params:
        errors.append(f"{py_path.name}:{func.lineno}: `{name}` missing **params (engine injects auth/context)")

    # Check docstring
    docstring = ast.get_docstring(func)
    if not docstring:
        warnings.append(f"{py_path.name}:{func.lineno}: `{name}` has no docstring (description will be empty)")

    # Check shape reference
    if returns_shape and shapes:
        shape_name = returns_shape.rstrip("[]")
        if shape_name and shape_name not in shapes and not isinstance(returns_shape, dict):
            # Not a known shape — check for close matches
            closest = _closest_match(shape_name, set(shapes.keys()))
            hint = f" (did you mean '{closest}'?)" if closest else ""
            errors.append(f"{py_path.name}:{func.lineno}: `{name}` @returns(\"{returns_shape}\") — shape '{shape_name}' not found{hint}")


def _check_dict_keys(tree: ast.Module, py_path: Path, errors: list):
    """Check for snake_case keys in dict literals inside return statements."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value:
            _check_dict_node(node.value, py_path, errors)


def _check_dict_node(node: ast.expr, py_path: Path, errors: list):
    """Recursively check dict nodes for snake_case keys."""
    if isinstance(node, ast.Dict):
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                k = key.value
                # Skip special keys and private keys
                if k.startswith("_") or k.startswith("__"):
                    continue
                if _SNAKE_RE.match(k):
                    errors.append(
                        f"{py_path.name}:{key.lineno}: snake_case dict key '{k}' "
                        f"in return — use camelCase ('{_to_camel(k)}')"
                    )
        # Check nested dicts
        for val in node.values:
            if val:
                _check_dict_node(val, py_path, errors)
    elif isinstance(node, ast.List):
        for elt in node.elts:
            _check_dict_node(elt, py_path, errors)
    elif isinstance(node, ast.ListComp):
        _check_dict_node(node.elt, py_path, errors)
    elif isinstance(node, ast.DictComp):
        if node.key:
            _check_dict_node(node.key, py_path, errors)


def _to_camel(snake: str) -> str:
    """Convert snake_case to camelCase."""
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _validate_skill(skill_dir: Path, shapes: dict) -> tuple[list[str], list[str], list[str]]:
    """Validate a single skill directory. Returns (errors, warnings, info)."""
    errors = []
    warnings = []
    info = []

    readme = skill_dir / "readme.md"
    if not readme.exists():
        errors.append("missing readme.md")
        return errors, warnings, info

    # Check frontmatter
    fm_data, fm_errors = _parse_frontmatter(readme)
    errors.extend(fm_errors)
    if fm_data:
        errors.extend(_check_frontmatter(fm_data))

    # Find Python files
    py_files = sorted(skill_dir.glob("*.py"))
    if not py_files:
        errors.append("no Python files found (need at least one .py module)")
        return errors, warnings, info

    # Check each Python file
    for py_file in py_files:
        e, w, i = _check_python_file(py_file, shapes)
        errors.extend(e)
        warnings.extend(w)
        info.extend(i)

    # Check test block references
    if fm_data and isinstance(fm_data.get("test"), dict):
        # Collect all operation names from Python files
        all_ops = set()
        for py_file in py_files:
            try:
                tree = ast.parse(py_file.read_text())
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.name.startswith("_"):
                            all_ops.add(node.name)
            except Exception:
                pass
        for test_op in fm_data["test"]:
            if test_op not in all_ops:
                warnings.append(f"test block references '{test_op}' but no matching operation found")

    return errors, warnings, info


def run_validate(target: str, validate_all: bool = False, dry_run: bool = False):
    """Main entry point for validation."""
    # Load shapes
    shapes_dir = _find_shapes_dir()
    shapes = _load_shapes(shapes_dir) if shapes_dir else {}
    if not shapes:
        print("  (shapes not found — skipping shape validation)", file=sys.stderr)

    if validate_all:
        # Validate all skills in the target's parent (or target itself)
        target_path = Path(target).resolve()
        if target_path.name == "skills" or (target_path / "skills").is_dir():
            skills_root = target_path if target_path.name == "skills" else target_path / "skills"
        else:
            # Check if we're inside a skills directory
            skills_root = target_path
            if not any((skills_root / d / "readme.md").exists() for d in os.listdir(skills_root) if (skills_root / d).is_dir()):
                # Try parent
                skills_root = target_path.parent
        _validate_all(skills_root, shapes)
    else:
        skill_dir = Path(target).resolve()
        _validate_one(skill_dir, shapes, dry_run=dry_run)


def _validate_one(skill_dir: Path, shapes: dict, dry_run: bool = False):
    """Validate and print results for one skill."""
    name = skill_dir.name
    errors, warnings, info = _validate_skill(skill_dir, shapes)

    print(f"\n  {name}")
    print(f"  {'─' * len(name)}")

    for line in info:
        print(f"  \033[90m· {line}\033[0m")
    for line in warnings:
        print(f"  \033[33m⚠ {line}\033[0m")
    for line in errors:
        print(f"  \033[31m✗ {line}\033[0m")

    if not errors and not warnings:
        print(f"  \033[32m✓ {len(info)} checks passed, 0 errors\033[0m")
    else:
        print(f"\n  {len(errors)} error(s), {len(warnings)} warning(s)")

    # Dry-run: execute test operations
    if dry_run and not errors:
        _dry_run_skill(skill_dir, shapes)

    if errors:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Dry-run execution
# ---------------------------------------------------------------------------

def _dry_run_skill(skill_dir: Path, shapes: dict):
    """Execute skill operations with test params (no engine needed)."""
    import importlib.util

    readme = skill_dir / "readme.md"
    fm_data, _ = _parse_frontmatter(readme)
    test_block = fm_data.get("test", {}) if fm_data else {}
    if not test_block:
        print(f"  \033[90m  (no test block — skipping dry-run)\033[0m")
        return

    # Patch the agentos bridge to raise on dispatch (no engine)
    try:
        import agentos._bridge as bridge
        original = bridge._dispatch

        def _mock_dispatch(op, params):
            raise RuntimeError(
                f"Engine dispatch '{op}' called — dry-run cannot execute "
                f"operations that need the engine (HTTP, SQL, etc.)"
            )
        bridge._dispatch = _mock_dispatch
    except ImportError:
        print(f"  \033[33m⚠ agentos package not installed — cannot dry-run\033[0m")
        return

    try:
        # Import each Python module in the skill
        modules = {}
        for py_file in sorted(skill_dir.glob("*.py")):
            spec = importlib.util.spec_from_file_location(
                f"_dryrun_{skill_dir.name}_{py_file.stem}", py_file)
            try:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                modules[py_file.stem] = mod
            except Exception as e:
                print(f"  \033[31m✗ dry-run import {py_file.name}: {e}\033[0m")
                continue

        # Find and call test operations
        for op_name, test_config in test_block.items():
            if isinstance(test_config, dict) and test_config.get("skip"):
                print(f"  \033[90m  ⏭ {op_name} — skipped\033[0m")
                continue

            # Find the function
            func = None
            for mod in modules.values():
                func = getattr(mod, op_name, None)
                if func and callable(func):
                    break

            if not func:
                print(f"  \033[33m⚠ {op_name} — function not found\033[0m")
                continue

            params = {}
            if isinstance(test_config, dict):
                params = test_config.get("params", {})

            print(f"  \033[90m  ▶ {op_name}({params or ''})...\033[0m", end="", flush=True)
            try:
                result = func(**params)
                if isinstance(result, list):
                    print(f"\r  \033[32m  ✓ {op_name} — returned {len(result)} record(s)\033[0m")
                elif isinstance(result, dict):
                    print(f"\r  \033[32m  ✓ {op_name} — returned dict ({len(result)} keys)\033[0m")
                else:
                    print(f"\r  \033[32m  ✓ {op_name} — returned {type(result).__name__}\033[0m")
            except RuntimeError as e:
                if "Engine dispatch" in str(e):
                    print(f"\r  \033[33m  ⚠ {op_name} — requires engine (cookie/API auth)\033[0m")
                else:
                    print(f"\r  \033[31m  ✗ {op_name} — {e}\033[0m")
            except Exception as e:
                print(f"\r  \033[31m  ✗ {op_name} — {type(e).__name__}: {e}\033[0m")
    finally:
        # Restore original dispatch
        try:
            bridge._dispatch = original
        except Exception:
            pass


def _validate_all(skills_root: Path, shapes: dict):
    """Validate all skill directories under skills_root."""
    total_errors = 0
    total_warnings = 0
    total_skills = 0
    error_skills = []

    # Sort skill dirs
    skill_dirs = sorted(
        d for d in skills_root.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "readme.md").exists()
    )

    for skill_dir in skill_dirs:
        total_skills += 1
        name = skill_dir.name
        errors, warnings, info = _validate_skill(skill_dir, shapes)

        if errors:
            error_skills.append(name)
            total_errors += len(errors)
            total_warnings += len(warnings)
            print(f"\n  \033[31m✗ {name}\033[0m")
            for line in errors:
                print(f"    \033[31m{line}\033[0m")
            for line in warnings:
                print(f"    \033[33m⚠ {line}\033[0m")
        elif warnings:
            total_warnings += len(warnings)
            print(f"  \033[33m⚠ {name}\033[0m — {len(warnings)} warning(s)")
            for line in warnings:
                print(f"    \033[33m{line}\033[0m")
        else:
            print(f"  \033[32m✓ {name}\033[0m")

    # Summary
    print(f"\n  ─────────────────────────────")
    print(f"  {total_skills} skills checked")
    if total_errors:
        print(f"  \033[31m{total_errors} error(s) in {len(error_skills)} skill(s): {', '.join(error_skills)}\033[0m")
    if total_warnings:
        print(f"  \033[33m{total_warnings} warning(s)\033[0m")
    if not total_errors and not total_warnings:
        print(f"  \033[32mAll clean!\033[0m")

    if total_errors:
        sys.exit(1)

"""agent-sdk new-skill — scaffold a working skill directory."""

import re
from pathlib import Path


_README_TEMPLATE = """---
id: {skill_id}
name: {skill_name}
description: "TODO: one-line description"
color: "#4A90D9"
website: https://example.com

test:
  {first_op}: {{ params: {{ query: "test" }} }}
---

# {skill_name}

TODO: Describe what this skill connects to, what data it provides,
and any setup instructions.
"""

_README_WITH_API_KEY = """---
id: {skill_id}
name: {skill_name}
description: "TODO: one-line description"
color: "#4A90D9"
website: https://example.com

connections:
  api:
    base_url: https://api.example.com
    auth:
      type: api_key
      header:
        x-api-key: .auth.key
    label: API Key
    help_url: https://example.com/api-keys

test:
  {first_op}: {{ params: {{ query: "test" }} }}
---

# {skill_name}

TODO: Describe what this skill connects to, what data it provides,
and any setup instructions.

## Setup

1. Get your API key from https://example.com/api-keys
2. Add credential in AgentOS Settings
"""

_PY_TEMPLATE = '''"""{skill_name} — TODO: describe what this connects to."""

from agentos import http, returns


@returns("{shape}[]")
def {list_op}(query: str = None, limit: int = 10, **params) -> list[dict]:
    """List {shape_plural} matching a query.

    Args:
        query: Search query to filter results
        limit: Max results to return (default 10)
    """
    # TODO: replace with real API call
    return [{{
        "id": "example-1",
        "name": "Example {shape_title}",{extra_fields}
    }}]


@returns("{shape}")
def {get_op}(id: str, **params) -> dict:
    """Get a single {shape} by ID.

    Args:
        id: {shape_title} ID
    """
    # TODO: replace with real API call
    return {{
        "id": id,
        "name": "Example {shape_title}",{extra_fields}
    }}
'''

_SHAPE_EXTRAS = {
    "event": """
        "startDate": "2026-04-10T18:00:00Z",
        "endDate": "2026-04-10T20:00:00Z",
        "timezone": "America/Chicago",
        "eventType": "meetup",
        "status": "confirmed",
        "allDay": False,""",
    "product": """
        "url": "https://example.com/products/1",
        "price": 29.99,
        "currency": "USD",""",
    "post": """
        "url": "https://example.com/posts/1",
        "content": "Example post content",
        "published": "2026-04-06T12:00:00Z",""",
    "email": """
        "subject": "Example Subject",
        "sender": "user@example.com",
        "content": "Email body text",
        "published": "2026-04-06T12:00:00Z",""",
}


def _to_module_name(skill_id: str) -> str:
    """Convert skill-id to python_module name."""
    return skill_id.replace("-", "_")


def _to_display_name(skill_id: str) -> str:
    """Convert skill-id to Display Name."""
    return " ".join(w.capitalize() for w in skill_id.split("-"))


def run_new_skill(name: str, shape: str | None):
    """Scaffold a new skill directory."""
    skill_id = name.lower().strip()
    module_name = _to_module_name(skill_id)
    display_name = _to_display_name(skill_id)
    shape = shape or "result"
    shape_plural = shape + "s" if not shape.endswith("s") else shape
    shape_title = shape.capitalize()

    # Operation names
    list_op = f"list_{shape_plural}" if shape != "result" else "search"
    get_op = f"get_{shape}" if shape != "result" else "get_result"
    first_op = list_op

    # Extra shape-specific fields
    extra_fields = _SHAPE_EXTRAS.get(shape, """
        "url": "https://example.com/items/1",
        "content": "Example content",""")

    # Target directory
    target = Path.cwd() / skill_id
    if target.exists():
        print(f"  Error: directory '{skill_id}/' already exists")
        return

    target.mkdir()

    # Write readme.md
    readme_content = _README_TEMPLATE.format(
        skill_id=skill_id, skill_name=display_name, first_op=first_op)
    (target / "readme.md").write_text(readme_content.lstrip())

    # Write Python module
    py_content = _PY_TEMPLATE.format(
        skill_name=display_name, shape=shape, shape_plural=shape_plural,
        shape_title=shape_title, list_op=list_op, get_op=get_op,
        extra_fields=extra_fields)
    (target / f"{module_name}.py").write_text(py_content.lstrip())

    print(f"""
  Created {skill_id}/
    readme.md        — manifest (frontmatter) + agent instructions
    {module_name}.py     — Python module with stub returning {shape} shape

  Next:
    agent-sdk validate {skill_id}   # check structure
    agentos test {skill_id}       # run + validate shape conformance
""")

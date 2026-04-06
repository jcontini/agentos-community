"""agent-sdk guide -- the single document an AI needs to build a skill.

Printed by `agent-sdk guide`. This is the SDK's documentation.
Community docs (agentos-community/docs/skills/) are legacy -- don't update them.
"""

from pathlib import Path


def print_guide():
    """Print the skill development guide to stdout."""
    guide_path = Path(__file__).parent / "GUIDE.md"
    print(guide_path.read_text().strip())

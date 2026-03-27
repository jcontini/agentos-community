"""agentOS SDK — three imports, entire toolkit.

    from agentos import molt, surf, shape

    molt(s)                        # shed the mess → clean string
    molt('1,234 reviews', int)     # shed the noise → 1234
    molt('August 2010', 'date')    # shed display format → '2010-08'

    with surf(cookies=header) as s:  # surf through WAFs
        resp = s.get(url)

    book: shape.Book = {'id': '123', 'name': 'Karamazov'}
"""

# --- The three pillars ---
from agentos.text import molt
from agentos.http import (
    surf, parse_cookies, get_cookies, require_cookies, parse_cookie,
    skill_error, skill_result, skill_secret,
)
from agentos import shapes as shape

# --- Fine-grained (available when you need specific control) ---
from agentos.text import clean_text, clean_html, clean_sentinel, strip_tags
from agentos.text import parse_int, parse_float
from agentos.dates import parse_date, iso_from_ms, iso_from_seconds

__all__ = [
    # The three pillars
    "molt", "surf", "shape",
    # HTTP helpers
    "parse_cookies", "get_cookies", "require_cookies", "parse_cookie",
    # Skill result helpers
    "skill_error", "skill_result", "skill_secret",
    # Text (fine-grained)
    "clean_text", "clean_html", "clean_sentinel", "strip_tags",
    # Parsers (specific)
    "parse_int", "parse_float", "parse_date",
    "iso_from_ms", "iso_from_seconds",
]

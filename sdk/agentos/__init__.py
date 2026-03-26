"""agentOS SDK — shared utilities for skills.

Primary API:
    from agentos import molt, surf

    molt(s)                       # shed the mess → clean string
    molt('1,234 reviews', int)    # shed the noise → 1234
    molt('August 2010', 'date')   # shed display format → '2010-08'

    with surf(cookies=header) as s:   # surf through WAFs
        resp = s.get(url)

Full API:
    from agentos import molt, surf, get_cookies, parse_cookies
    from agentos import clean_text, clean_html, clean_sentinel  # fine-grained
    from agentos import parse_int, parse_float, parse_date      # specific parsers
    from agentos import iso_from_ms, iso_from_seconds           # timestamp helpers
"""

# --- Primary ---
from agentos.text import molt
from agentos.http import surf, parse_cookies, get_cookies

# --- Fine-grained text cleaning ---
from agentos.text import clean_text, clean_html, clean_sentinel, strip_tags

# --- Specific parsers ---
from agentos.text import parse_int, parse_float
from agentos.dates import parse_date, iso_from_ms, iso_from_seconds

__all__ = [
    # Primary
    "molt",
    # HTTP
    "surf", "parse_cookies", "get_cookies",
    # Text (fine-grained)
    "clean_text", "clean_html", "clean_sentinel", "strip_tags",
    # Parsers (specific)
    "parse_int", "parse_float", "parse_date",
    "iso_from_ms", "iso_from_seconds",
]

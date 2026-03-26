"""agentOS SDK — shared utilities for skills.

Primary API:
    from agentos import molt, http_client

    molt(s)                       # clean string
    molt('1,234 reviews', int)    # parse to int
    molt('August 2010', 'date')   # parse to ISO date

Full API:
    from agentos import molt, http_client, get_cookies, parse_cookies
    from agentos import clean_text, clean_html, clean_sentinel  # fine-grained
    from agentos import parse_int, parse_float, parse_date      # specific parsers
    from agentos import iso_from_ms, iso_from_seconds           # timestamp helpers
"""

# --- Primary: molt (universal clean + parse) ---
from agentos.text import molt

# --- HTTP transport ---
from agentos.http import client as http_client, parse_cookies, get_cookies

# --- Fine-grained text cleaning ---
from agentos.text import clean_text, clean_html, clean_sentinel, strip_tags

# --- Specific parsers ---
from agentos.text import parse_int, parse_float
from agentos.dates import parse_date, iso_from_ms, iso_from_seconds

__all__ = [
    # Primary
    "molt",
    # HTTP
    "http_client", "parse_cookies", "get_cookies",
    # Text (fine-grained)
    "clean_text", "clean_html", "clean_sentinel", "strip_tags",
    # Parsers (specific)
    "parse_int", "parse_float", "parse_date",
    "iso_from_ms", "iso_from_seconds",
]

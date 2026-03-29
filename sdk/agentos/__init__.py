"""agentOS SDK — skills import what they need.

    from agentos import http, molt, shape       # HTTP, text, typed dicts
    from agentos import sql, crypto, oauth      # engine-dispatched modules
    from agentos.macos import keychain, plist   # platform-specific

    resp = http.get("https://api.example.com/data", profile="api")
    molt(s)                        # shed the mess → clean string
    rows = sql.query("SELECT ...", db="~/data.db")
"""

# --- Core modules ---
from agentos.text import molt
from agentos import http
from agentos import shapes as shape

# --- Deprecated: surf (use http.get/http.client instead) ---
from agentos.http import surf

# --- HTTP helpers (still useful) ---
from agentos.http import (
    get_cookies, require_cookies, parse_cookie, parse_cookies,
    skill_error, skill_result, skill_secret,
)

# --- Engine-dispatched modules ---
from agentos import sql
from agentos import crypto
from agentos import oauth

# --- Fine-grained (available when you need specific control) ---
from agentos.text import clean_text, clean_html, clean_sentinel, strip_tags
from agentos.text import parse_int, parse_float
from agentos.dates import parse_date, iso_from_ms, iso_from_seconds

__all__ = [
    # Core modules
    "http", "molt", "shape",
    # Deprecated
    "surf",
    # Engine-dispatched modules
    "sql", "crypto", "oauth",
    # HTTP helpers
    "get_cookies", "require_cookies", "parse_cookie", "parse_cookies",
    # Skill result helpers
    "skill_error", "skill_result", "skill_secret",
    # Text (fine-grained)
    "clean_text", "clean_html", "clean_sentinel", "strip_tags",
    # Parsers (specific)
    "parse_int", "parse_float", "parse_date",
    "iso_from_ms", "iso_from_seconds",
]

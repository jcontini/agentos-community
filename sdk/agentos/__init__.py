"""agentOS SDK — skills import what they need.

    from agentos import molt, surf, shape      # text, HTTP, typed dicts
    from agentos import sql, crypto, oauth      # engine-dispatched modules
    from agentos.macos import keychain, plist   # platform-specific

    molt(s)                        # shed the mess → clean string
    rows = sql.query("SELECT ...", db="~/data.db")
    resp = oauth.exchange(token_url=url, refresh_token=rt, client_id=cid)
"""

# --- The three pillars (legacy, still available) ---
from agentos.text import molt
from agentos.http import (
    surf, parse_cookies, get_cookies, require_cookies, parse_cookie,
    skill_error, skill_result, skill_secret,
)
from agentos import shapes as shape

# --- Engine-dispatched modules ---
from agentos import sql
from agentos import crypto
from agentos import oauth

# --- Fine-grained (available when you need specific control) ---
from agentos.text import clean_text, clean_html, clean_sentinel, strip_tags
from agentos.text import parse_int, parse_float
from agentos.dates import parse_date, iso_from_ms, iso_from_seconds

__all__ = [
    # The three pillars
    "molt", "surf", "shape",
    # Engine-dispatched modules
    "sql", "crypto", "oauth",
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

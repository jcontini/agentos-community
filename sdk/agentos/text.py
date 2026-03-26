"""Text cleaning and parsing utilities for skills.

Primary entry points:
  clean(value)          — smart clean: HTML strip + normalize + sentinel → None
  parse(value, as_type) — clean + convert to int/float/date

Specific functions available for fine-grained control:
  clean_text, clean_html, clean_sentinel, strip_tags,
  parse_int, parse_float
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Any


# ---------------------------------------------------------------------------
# Universal cleaner + parser
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")


def molt(value: Any, as_type: type | str | None = None) -> Any:
    """Shed the outer layer — clean and optionally convert any scraped value.

    Like molting — the messy outer layer falls away, revealing clean data.

    molt(s)                        → clean string (HTML, whitespace, sentinels)
    molt('1,234 reviews', int)     → 1234
    molt('4.5 out of 5', float)    → 4.5
    molt('August 2010', 'date')    → '2010-08'
    molt(1616025600000, 'date')    → '2021-03-18T...'
    molt(None)                     → None

    Works across languages:
      Python:     molt('1,234 reviews', int)
      TypeScript: molt('1,234 reviews', 'int')
      Go:         sdk.Molt('1,234 reviews', sdk.Int)
    """
    if value is None:
        return None

    # No type = clean text
    if as_type is None:
        return _molt_text(value) if isinstance(value, str) else value

    # Integer
    if as_type is int or as_type == "int" or as_type == "integer":
        return parse_int(value)

    # Float
    if as_type is float or as_type == "float" or as_type == "number":
        return parse_float(value)

    # Date
    if as_type == "date" or as_type == "datetime":
        from agentos.dates import parse_date, iso_from_ms
        if isinstance(value, (int, float)):
            if value > 1_000_000_000_000:
                return iso_from_ms(value)
            from agentos.dates import iso_from_seconds
            return iso_from_seconds(value)
        return parse_date(str(value)) if value else None

    # String (explicit)
    if as_type is str or as_type == "str" or as_type == "string":
        return _molt_text(value) if isinstance(value, str) else str(value)

    return _molt_text(value) if isinstance(value, str) else value


def _molt_text(value: str) -> str | None:
    """Internal: clean a string value (HTML strip + normalize + sentinel)."""
    if _TAG_RE.search(value):
        value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
        value = re.sub(r"<[^>]+>", "", value)
    value = html_lib.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return None
    return clean_sentinel(value)

# ---------------------------------------------------------------------------
# Sentinel detection
# ---------------------------------------------------------------------------

_SENTINEL_PATTERNS = [
    "hasn't added any details yet",
    "has not added any details yet",
    "no description available",
    "no description",
    "not available",
    "not specified",
    "not provided",
    "none provided",
    "none available",
    "no data",
    "no information",
]

_SENTINEL_EXACT = {"n/a", "na", "none", "unknown", "null", "undefined", "-", "—", "–"}


def clean_sentinel(s: str | None) -> str | None:
    """Return None if the string is empty or looks like a placeholder."""
    if not s:
        return None
    trimmed = s.strip()
    if not trimmed:
        return None
    lower = trimmed.lower()
    if lower in _SENTINEL_EXACT:
        return None
    for pattern in _SENTINEL_PATTERNS:
        if pattern in lower:
            return None
    return trimmed


# ---------------------------------------------------------------------------
# HTML cleaning
# ---------------------------------------------------------------------------


def clean_html(value: str | None) -> str | None:
    """Strip HTML tags and decode entities, preserving paragraph structure.

    <br> → newline, </p> → double newline, other tags stripped.
    Collapses excessive whitespace.
    """
    if value is None:
        return None
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p\s*>", "\n\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html_lib.unescape(value)
    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = value.strip()
    return value or None


def clean_text(value: str | None) -> str | None:
    """Decode HTML entities and normalize whitespace to single spaces."""
    if value is None:
        return None
    value = html_lib.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def strip_tags(value: str | None) -> str | None:
    """Remove HTML tags and decode entities. No whitespace normalization."""
    if value is None:
        return None
    value = re.sub(r"<[^>]+>", "", value)
    value = html_lib.unescape(value)
    return value.strip() or None


# ---------------------------------------------------------------------------
# Number parsing
# ---------------------------------------------------------------------------


def parse_int(value: Any) -> int | None:
    """Extract an integer from a string, stripping non-digit characters.

    '1,234'   → 1234
    '495 reviews' → 495
    42        → 42
    '2.5K'    → 2500
    None      → None
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    # Handle K/M suffix
    m = re.match(r"^([\d.]+)\s*[Kk]$", s)
    if m:
        return int(float(m.group(1)) * 1000)
    m = re.match(r"^([\d.]+)\s*[Mm]$", s)
    if m:
        return int(float(m.group(1)) * 1_000_000)
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def parse_float(value: Any) -> float | None:
    """Extract a float from a string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(s)
    except ValueError:
        return None

"""Text cleaning utilities for skills.

Handles HTML stripping, sentinel detection, and number parsing.
Skills should return None instead of placeholder strings — the engine
and test harness flag sentinels as warnings.
"""

import html as html_lib
import re
from typing import Any

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

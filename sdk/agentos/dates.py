"""Date parsing utilities for skills.

Converts display dates, fuzzy dates, and timestamps to ISO 8601 partial dates.
Skills should store dates as ISO — the engine and test harness reject display strings.
"""

import re
from datetime import datetime, timezone
from typing import Any

_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def parse_fuzzy_date(s: str | None) -> str | None:
    """Convert a display date to ISO 8601 partial date.

    'August 2010'       → '2010-08'
    'December 13, 2024' → '2024-12-13'
    'in January 2026'   → '2026-01'
    '2024'              → '2024'
    '2024-03-15'        → '2024-03-15'  (passthrough)
    'this month'        → None
    '3 days ago'        → None
    """
    if not s:
        return None
    s = s.strip()
    # Strip leading "in " (e.g. "in January 2026")
    s = re.sub(r"^in\s+", "", s, flags=re.I)

    # Already ISO? (starts with 4 digits)
    if re.match(r"^\d{4}(-\d{2})?(-\d{2})?(T|$)", s):
        return s

    # "Month YYYY"
    m = re.match(r"^([A-Za-z]+)\s+(\d{4})$", s)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            return f"{m.group(2)}-{month}"

    # "Month DD, YYYY" or "Month DD YYYY"
    m = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$", s)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            return f"{m.group(3)}-{month}-{int(m.group(2)):02d}"

    # Year only
    m = re.match(r"^(\d{4})$", s)
    if m:
        return m.group(1)

    return None


def iso_from_ms(value: Any) -> str | None:
    """Convert a millisecond Unix timestamp to ISO 8601 datetime string."""
    if not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return None


def iso_from_seconds(value: Any) -> str | None:
    """Convert a second Unix timestamp to ISO 8601 datetime string."""
    if not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return None

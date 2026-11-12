"""Date Helpers Module.

Provides functions for parsing ISO dates, game detail page expiration dates, and UTC calculations.
"""

import re
from datetime import UTC, datetime, timedelta

MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "oca": 1,
    "şub": 2,
    "nis": 4,
    "haz": 6,
    "tem": 7,
    "ağu": 8,
    "eyl": 9,
    "eki": 10,
    "kas": 11,
    "ara": 12,
}

_ISO_SENTINELS = frozenset({"N/A", "NONE", "UNKNOWN", "UNSPECIFIED"})
_FALLBACK_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%d",
)


def parse_iso_datetime(date_str: str | None) -> datetime | None:
    """Parse a date string into a timezone-aware UTC datetime, or return None."""
    if date_str is None:
        return None

    clean_str = str(date_str).strip()
    if not clean_str or clean_str.upper() in _ISO_SENTINELS:
        return None

    dt: datetime | None = None
    try:
        iso_input = clean_str[:-1] + "+00:00" if clean_str.endswith(("Z", "z")) else clean_str
        dt = datetime.fromisoformat(iso_input)
    except (ValueError, TypeError):
        dt = None

    if dt is None:
        for fmt in _FALLBACK_FORMATS:
            try:
                dt = datetime.strptime(clean_str, fmt)
                break
            except ValueError:
                continue

    if dt is None:
        return None

    try:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (ValueError, OverflowError):
        return None


def parse_iso_date(date_str: str | None) -> str | None:
    """Parse date string into ISO 8601 UTC string (e.g., 2026-08-15T15:00:00Z) or None."""
    dt = parse_iso_datetime(date_str)
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_detail_page_end_date(text: str) -> str | None:
    """Extract exact expiration date from game detail page text.

    Parses 'Available through Sep 23, 2026', '23 Eyl 2026 tarihine kadar geçerli',
    or '(in 46 days)'.
    """
    if not text:
        return None

    now = datetime.now(UTC)

    # 1. Matches "Available through Sep 23, 2026" or "Available until Oct 15, 2026"
    m_eng = re.search(
        r"available\s+(?:through|until)\s+([a-zA-Z]+)\s+(\d{1,2}),?\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if m_eng:
        mon_str = m_eng.group(1).lower()[:3]
        day_str, year_str = m_eng.group(2), m_eng.group(3)
        month = MONTH_MAP.get(mon_str)
        if month:
            try:
                dt = datetime(int(year_str), month, int(day_str), 23, 59, 59, tzinfo=UTC)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, OverflowError):
                return None

    # 2. Matches "23 Eyl 2026 tarihine kadar geçerli"
    m_tr = re.search(
        r"(\d{1,2})\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\s+(\d{4})\s*tarihine",
        text,
        re.IGNORECASE,
    )
    if m_tr:
        day_str, mon_raw, year_str = m_tr.group(1), m_tr.group(2), m_tr.group(3)
        text_tr = mon_raw.replace("İ", "i").replace("I", "ı").lower()[:3]
        month = MONTH_MAP.get(text_tr)
        if month:
            try:
                dt = datetime(int(year_str), month, int(day_str), 23, 59, 59, tzinfo=UTC)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, OverflowError):
                return None

    # 3. Matches "(in X days)" or "(X gün kaldı)"
    m_in_days = re.search(
        r"\((?:in\s+)?(\d+)\s*(?:days?|gün)\s*(?:left|kaldı)?\)",
        text,
        re.IGNORECASE,
    )
    if m_in_days:
        try:
            days = int(m_in_days.group(1))
            dt = (now + timedelta(days=days)).replace(hour=23, minute=59, second=59, microsecond=0)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OverflowError):
            return None

    return None

"""Date Helpers Module.

Provides functions for parsing ISO dates, game detail page expiration dates, and UTC calculations.
"""

import re
from datetime import UTC, datetime, timedelta

MONTH_MAP = {
    # English full names & abbreviations
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
    # Turkish full names & abbreviations (plus ASCII-folded variants)
    "oca": 1,
    "ocak": 1,
    "şub": 2,
    "şubat": 2,
    "sub": 2,
    "subat": 2,
    "mart": 3,
    "nis": 4,
    "nisan": 4,
    "mayıs": 5,
    "mayis": 5,
    "haz": 6,
    "haziran": 6,
    "tem": 7,
    "temmuz": 7,
    "ağu": 8,
    "ağustos": 8,
    "agu": 8,
    "agustos": 8,
    "eyl": 9,
    "eylül": 9,
    "eylul": 9,
    "eki": 10,
    "ekim": 10,
    "kas": 11,
    "kasım": 11,
    "kasim": 11,
    "ara": 12,
    "aralık": 12,
    "aralik": 12,
}

_ISO_SENTINELS = frozenset({"N/A", "NONE", "UNKNOWN", "UNSPECIFIED"})
_FALLBACK_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%d",
)

_ENG_DATE_PREFIX = (
    r"\b(?:available\s+(?:through|until)"
    r"|(?:offer\s+)?ends(?:\s+on)?"
    r"|expires(?:\s+on)?"
    r"|claim\s+by"
    r"|valid\s+(?:through|until))(?:\s*:\s*|\s+)"
)
_ENG_MONTH_FIRST_RE = re.compile(
    rf"{_ENG_DATE_PREFIX}([a-zA-Z]+)\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}})\b)?",
    re.IGNORECASE,
)
_ENG_DAY_FIRST_RE = re.compile(
    rf"{_ENG_DATE_PREFIX}(\d{{1,2}})(?:st|nd|rd|th)?\b\s+([a-zA-Z]+)\.?(?:,?\s+(\d{{4}})\b)?",
    re.IGNORECASE,
)
_TR_UNTIL_RE = re.compile(
    r"\b(\d{1,2})\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\.?(?:\s+(\d{4}))?\s+(?:tarihine|tarihinde\s+sona)\b",
    re.IGNORECASE,
)
_TR_LAST_DATE_RE = re.compile(
    r"\bson\s+(?:geçerlilik\s+)?tarih(?:i)?\s*:?\s*(\d{1,2})\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\.?(?:\s+(\d{4}))?\b",
    re.IGNORECASE,
)
_RELATIVE_DAYS_RE = re.compile(
    r"\((?:in\s+)?(\d+)\s*(?:days?|gün)\s*(?:left|kaldı)?\)|\b(?:ends|expires)\s+in\s+(\d+)\s*days?\b",
    re.IGNORECASE,
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


def _lookup_month(mon_raw: str) -> int | None:
    """Resolve a recognized English or Turkish month name/abbreviation into 1..12."""
    mon_key = mon_raw.replace("İ", "i").replace("I", "ı").lower().rstrip(".")
    return MONTH_MAP.get(mon_key)


def _build_end_datetime(
    year_str: str | None,
    month: int,
    day: int,
    now: datetime,
) -> str | None:
    """Construct end-of-day UTC ISO string, inferring year when omitted."""
    try:
        if year_str is not None:
            dt = datetime(int(year_str), month, day, 23, 59, 59, tzinfo=UTC)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            dt = datetime(now.year, month, day, 23, 59, 59, tzinfo=UTC)
        except ValueError:
            if month == 2 and day == 29 and now.month >= 4:
                dt = datetime(now.year + 1, month, day, 23, 59, 59, tzinfo=UTC)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            return None

        if now - dt > timedelta(days=30):
            dt = datetime(now.year + 1, month, day, 23, 59, 59, tzinfo=UTC)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError):
        return None


def parse_detail_page_end_date(text: str) -> str | None:
    """Extract exact expiration date from game detail page or card text.

    Supports English month-first/day-first phrases (with optional year inference),
    Turkish expiration date formats, and explicit relative-day badges.
    """
    if not text:
        return None

    now = datetime.now(UTC)

    for match in _ENG_MONTH_FIRST_RE.finditer(text):
        month = _lookup_month(match.group(1))
        if month is not None:
            parsed = _build_end_datetime(match.group(3), month, int(match.group(2)), now)
            if parsed is not None:
                return parsed

    for match in _ENG_DAY_FIRST_RE.finditer(text):
        month = _lookup_month(match.group(2))
        if month is not None:
            parsed = _build_end_datetime(match.group(3), month, int(match.group(1)), now)
            if parsed is not None:
                return parsed

    for pattern in (_TR_UNTIL_RE, _TR_LAST_DATE_RE):
        for match in pattern.finditer(text):
            month = _lookup_month(match.group(2))
            if month is not None:
                parsed = _build_end_datetime(match.group(3), month, int(match.group(1)), now)
                if parsed is not None:
                    return parsed

    for match in _RELATIVE_DAYS_RE.finditer(text):
        days_str = match.group(1) or match.group(2)
        if days_str is None:
            continue
        try:
            days = int(days_str)
            dt = (now + timedelta(days=days)).replace(
                hour=23, minute=59, second=59, microsecond=0
            )
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OverflowError):
            continue

    return None

#!/usr/bin/env python3
"""
Date Helpers Module
Provides functions for parsing ISO dates, game detail page expiration dates, and UTC calculations.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'oca': 1, 'şub': 2, 'nis': 4, 'haz': 6, 'tem': 7, 'ağu': 8, 'eyl': 9, 'eki': 10, 'kas': 11, 'ara': 12
}


def parse_iso_date(date_str: Optional[str]) -> Optional[str]:
    """Parse date string into ISO 8601 UTC string (e.g., 2026-08-15T15:00:00Z) or None."""
    if not date_str or str(date_str).upper() in ["N/A", "NONE", "UNKNOWN", "UNSPECIFIED"]:
        return None
    
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(str(date_str).strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
            
    return None


def parse_detail_page_end_date(text: str) -> Optional[str]:
    """
    Extract exact expiration date from game detail page text.
    Parses 'Available through Sep 23, 2026', '23 Eyl 2026 tarihine kadar geçerli', or '(in 46 days)'.
    """
    if not text:
        return None

    now = datetime.now(timezone.utc)

    # 1. Matches "Available through Sep 23, 2026" or "Available until Oct 15, 2026"
    m_eng = re.search(r"available\s+(?:through|until)\s+([a-zA-Z]+)\s+(\d{1,2}),?\s+(\d{4})", text, re.IGNORECASE)
    if m_eng:
        mon_str, day_str, year_str = m_eng.group(1).lower()[:3], m_eng.group(2), m_eng.group(3)
        month = MONTH_MAP.get(mon_str)
        if month:
            dt = datetime(int(year_str), month, int(day_str), 23, 59, 59, tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 2. Matches "23 Eyl 2026 tarihine kadar geçerli"
    m_tr = re.search(r"(\d{1,2})\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\s+(\d{4})\s*tarihine", text, re.IGNORECASE)
    if m_tr:
        day_str, mon_str, year_str = m_tr.group(1), m_tr.group(2).lower()[:3], m_tr.group(3)
        month = MONTH_MAP.get(mon_str)
        if month:
            dt = datetime(int(year_str), month, int(day_str), 23, 59, 59, tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 3. Matches "(in X days)" or "(X gün kaldı)"
    m_in_days = re.search(r"\((?:in\s+)?(\d+)\s*(?:days?|gün)\s*(?:left|kaldı)?\)", text, re.IGNORECASE)
    if m_in_days:
        days = int(m_in_days.group(1))
        dt = now + timedelta(days=days)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 4. Fallback to generic day/hour regex
    m_days = re.search(r"(\d+)\s*(?:gün|days?)(?:\s*(?:kaldı|left|içinde|sona|kalan))?", text, re.IGNORECASE)
    if m_days:
        days = int(m_days.group(1))
        dt = now + timedelta(days=days)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return None

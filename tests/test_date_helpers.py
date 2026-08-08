#!/usr/bin/env python3
"""
Unit tests for date_helpers module.
"""

import pytest
from backend.utils.date_helpers import parse_iso_date, parse_detail_page_end_date


def test_parse_iso_date_valid():
    assert parse_iso_date("2026-08-15 23:59:00") == "2026-08-15T23:59:00Z"
    assert parse_iso_date("2026-08-15T23:59:00Z") == "2026-08-15T23:59:00Z"
    assert parse_iso_date("2026-08-15T23:59:00+00:00") == "2026-08-15T23:59:00Z"
    assert parse_iso_date("2026-08-15") == "2026-08-15T00:00:00Z"


def test_parse_iso_date_invalid():
    assert parse_iso_date(None) is None
    assert parse_iso_date("") is None
    assert parse_iso_date("N/A") is None
    assert parse_iso_date("saçma girdi") is None


def test_parse_detail_page_end_date_valid():
    assert parse_detail_page_end_date("Available through Sep 23, 2026") == "2026-09-23T23:59:59Z"
    assert parse_detail_page_end_date("23 Eyl 2026 tarihine kadar geçerli") == "2026-09-23T23:59:59Z"


def test_parse_detail_page_end_date_no_date():
    # Bu test, kaldırılan 4. agresif fallback regex'inin (sayfa metninde geçen "3 days" gibi ifadeleri yanlışlıkla bitiş tarihi sanması)
    # tekrar koda dahil edilmesini engellemek için yazılmıştır.
    text_without_date = "In 7 Days to Die, survive for 3 days in a post-apocalyptic world with your friends."
    assert parse_detail_page_end_date(text_without_date) is None

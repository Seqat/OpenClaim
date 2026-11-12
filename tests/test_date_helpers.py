"""Unit tests for date_helpers module."""

import re
from datetime import UTC, datetime

from backend.utils.date_helpers import (
    parse_detail_page_end_date,
    parse_iso_date,
    parse_iso_datetime,
)


def test_parse_iso_date_valid():
    assert parse_iso_date("2026-08-15 23:59:00") == "2026-08-15T23:59:00Z"
    assert parse_iso_date("2026-08-15T23:59:00Z") == "2026-08-15T23:59:00Z"
    assert parse_iso_date("2026-08-15T23:59:00+00:00") == "2026-08-15T23:59:00Z"
    assert parse_iso_date("2026-08-15T23:59:00+03:00") == "2026-08-15T20:59:00Z"
    assert parse_iso_date("  2026-08-15  ") == "2026-08-15T00:00:00Z"


def test_parse_iso_date_invalid_and_sentinels():
    assert parse_iso_date(None) is None
    assert parse_iso_date("") is None
    assert parse_iso_date("   ") is None
    assert parse_iso_date("N/A") is None
    assert parse_iso_date("  N/A  ") is None
    assert parse_iso_date(" none ") is None
    assert parse_iso_date(" UNKNOWN ") is None
    assert parse_iso_date(" unspecified ") is None
    assert parse_iso_date("saçma girdi") is None


def test_parse_iso_datetime_returns_utc_datetime():
    dt = parse_iso_datetime("2026-08-15T23:59:00Z")
    assert dt == datetime(2026, 8, 15, 23, 59, 0, tzinfo=UTC)


def test_parse_detail_page_end_date_valid():
    assert parse_detail_page_end_date("Available through Sep 23, 2026") == "2026-09-23T23:59:59Z"
    assert parse_detail_page_end_date("Available until Oct 15, 2026") == "2026-10-15T23:59:59Z"
    assert parse_detail_page_end_date("23 Eyl 2026 tarihine kadar geçerli") == "2026-09-23T23:59:59Z"


def test_parse_detail_page_end_date_turkish_uppercase_i():
    assert parse_detail_page_end_date("15 NİSAN 2026 tarihine kadar") == "2026-04-15T23:59:59Z"
    assert parse_detail_page_end_date("10 KASIM 2026 tarihine kadar") == "2026-11-10T23:59:59Z"
    assert parse_detail_page_end_date("5 MAYIS 2026 tarihine kadar") == "2026-05-05T23:59:59Z"
    assert parse_detail_page_end_date("20 AĞUSTOS 2026 tarihine kadar") == "2026-08-20T23:59:59Z"


def test_parse_detail_page_end_date_relative_and_bounds():
    res_en = parse_detail_page_end_date("Claim soon (in 5 days)")
    assert res_en is not None
    assert re.match(r"^\d{4}-\d{2}-\d{2}T23:59:59Z$", res_en)

    res_tr = parse_detail_page_end_date("Teklif (7 gün kaldı)")
    assert res_tr is not None
    assert re.match(r"^\d{4}-\d{2}-\d{2}T23:59:59Z$", res_tr)

    # OverflowError / ValueError guards
    assert parse_detail_page_end_date("Available through Feb 30, 2026") is None
    assert parse_detail_page_end_date("Available through Sep 00, 2026") is None
    assert parse_detail_page_end_date("32 Eyl 2026 tarihine kadar") is None
    assert parse_detail_page_end_date("(in 99999999999 days)") is None


def test_parse_detail_page_end_date_no_date():
    # Bu test, kaldırılan 4. agresif fallback regex'inin (sayfa metninde geçen "3 days" gibi ifadeleri yanlışlıkla bitiş tarihi sanması)
    # tekrar koda dahil edilmesini engellemek için yazılmıştır.
    text_without_date = "In 7 Days to Die, survive for 3 days in a post-apocalyptic world with your friends."
    assert parse_detail_page_end_date(text_without_date) is None

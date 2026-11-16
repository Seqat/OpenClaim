"""Unit tests for date_helpers module."""

import re
from datetime import UTC, datetime
from unittest.mock import patch

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
    assert parse_detail_page_end_date("Survive with friends in 3 days") is None
    assert parse_detail_page_end_date("Offer ends Dec 2026") is None


def test_parse_detail_page_end_date_english_variants_and_day_first():
    assert parse_detail_page_end_date("Offer ends Dec 25, 2026") == "2026-12-25T23:59:59Z"
    assert parse_detail_page_end_date("Offer ends on Dec 25, 2026") == "2026-12-25T23:59:59Z"
    assert parse_detail_page_end_date("Ends Nov 30, 2026") == "2026-11-30T23:59:59Z"
    assert parse_detail_page_end_date("Ends on Jan 15, 2027") == "2027-01-15T23:59:59Z"
    assert parse_detail_page_end_date("Expires Feb 10, 2027") == "2027-02-10T23:59:59Z"
    assert parse_detail_page_end_date("Expires on Mar 5, 2027") == "2027-03-05T23:59:59Z"
    assert parse_detail_page_end_date("Claim by Dec 16, 2026") == "2026-12-16T23:59:59Z"
    assert parse_detail_page_end_date("Valid through Nov 25, 2026") == "2026-11-25T23:59:59Z"
    assert parse_detail_page_end_date("Valid until Dec 9, 2026") == "2026-12-09T23:59:59Z"
    assert parse_detail_page_end_date("Ends: Dec 2, 2026") == "2026-12-02T23:59:59Z"

    # Day-first variants
    assert parse_detail_page_end_date("Available through 23 Sep 2026") == "2026-09-23T23:59:59Z"
    assert parse_detail_page_end_date("Offer ends 25 Dec, 2026") == "2026-12-25T23:59:59Z"
    assert parse_detail_page_end_date("Expires on 15 Jan 2027") == "2027-01-15T23:59:59Z"
    assert parse_detail_page_end_date("Claim by 16 Dec 2026") == "2026-12-16T23:59:59Z"
    assert parse_detail_page_end_date("Valid until 9th Dec 2026") == "2026-12-09T23:59:59Z"

    # Skips non-month token after earlier prefix
    assert (
        parse_detail_page_end_date("Offer ends at 12. Valid through Dec 25, 2026")
        == "2026-12-25T23:59:59Z"
    )


def test_parse_detail_page_end_date_year_inference():
    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 16, 12, 0, 0, tzinfo=tz or UTC)

    with patch("backend.utils.date_helpers.datetime", _FixedDateTime):
        # Future date in same year -> 2026
        assert parse_detail_page_end_date("Claim by Dec 16") == "2026-12-16T23:59:59Z"
        assert parse_detail_page_end_date("Valid until 16 Dec") == "2026-12-16T23:59:59Z"

        # Within 30 days in the past -> stays 2026
        assert parse_detail_page_end_date("Ends Nov 1") == "2026-11-01T23:59:59Z"
        assert parse_detail_page_end_date("Claim by 18 Oct") == "2026-10-18T23:59:59Z"

        # More than 30 days in the past -> rolls over to 2027
        assert parse_detail_page_end_date("Claim by Oct 15") == "2027-10-15T23:59:59Z"
        assert parse_detail_page_end_date("Expires Jan 15") == "2027-01-15T23:59:59Z"
        assert parse_detail_page_end_date("Offer ends on 5 Feb") == "2027-02-05T23:59:59Z"


def test_parse_detail_page_end_date_year_inference_leap_day():
    class _FixedLate2027(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2027, 12, 15, 12, 0, 0, tzinfo=tz or UTC)

    with patch("backend.utils.date_helpers.datetime", _FixedLate2027):
        assert parse_detail_page_end_date("Claim by Feb 29") == "2028-02-29T23:59:59Z"


def test_parse_detail_page_end_date_turkish_and_relative_variants():
    assert (
        parse_detail_page_end_date("23 Eyl 2026 tarihinde sona erer") == "2026-09-23T23:59:59Z"
    )
    assert parse_detail_page_end_date("Son tarih: 15 Kasım 2026") == "2026-11-15T23:59:59Z"
    assert (
        parse_detail_page_end_date("Son geçerlilik tarihi: 5 Mayıs 2026")
        == "2026-05-05T23:59:59Z"
    )
    assert (
        parse_detail_page_end_date("SON GEÇERLİLİK TARİHİ: 10 EKİM 2026")
        == "2026-10-10T23:59:59Z"
    )
    assert (
        parse_detail_page_end_date("Son geçerlilik tarih 20 Ağustos 2026")
        == "2026-08-20T23:59:59Z"
    )

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 16, 12, 0, 0, tzinfo=tz or UTC)

    with patch("backend.utils.date_helpers.datetime", _FixedDateTime):
        assert parse_detail_page_end_date("Offer ends in 5 days") == "2026-11-21T23:59:59Z"
        assert parse_detail_page_end_date("Expires in 12 days") == "2026-11-28T23:59:59Z"
        assert parse_detail_page_end_date("Ends in 1 day") == "2026-11-17T23:59:59Z"
        assert parse_detail_page_end_date("(3 days left)") == "2026-11-19T23:59:59Z"
        assert parse_detail_page_end_date("(7 gün kaldı)") == "2026-11-23T23:59:59Z"

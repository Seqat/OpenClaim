#!/usr/bin/env python3
"""
Unit tests for filter_expired_games in backend/main.py.
"""

from datetime import datetime, timedelta, timezone
from backend.main import filter_expired_games


def test_filter_expired_past_outside_grace():
    now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Expired 10 hours ago (beyond 6h grace period)
    games = [
        {"title": "Old Game", "end_date": "2026-08-15T02:00:00Z"},
    ]
    res = filter_expired_games(games, now=now)
    assert len(res) == 0


def test_filter_expired_none_and_empty_end_date():
    now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    games = [
        {"title": "Permanent Game 1", "end_date": None},
        {"title": "Permanent Game 2", "end_date": ""},
        {"title": "Permanent Game 3"},
    ]
    res = filter_expired_games(games, now=now)
    assert len(res) == 3
    assert [g["title"] for g in res] == [
        "Permanent Game 1",
        "Permanent Game 2",
        "Permanent Game 3",
    ]


def test_filter_expired_within_grace_period():
    now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Expired 3 hours ago (within 6h grace period)
    games = [
        {"title": "Recent Expired Game", "end_date": "2026-08-15T09:00:00Z"},
    ]
    res = filter_expired_games(games, now=now)
    assert len(res) == 1
    assert res[0]["title"] == "Recent Expired Game"


def test_filter_expired_future_date():
    now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    games = [
        {"title": "Future Game", "end_date": "2026-08-20T18:00:00Z"},
    ]
    res = filter_expired_games(games, now=now)
    assert len(res) == 1
    assert res[0]["title"] == "Future Game"


def test_filter_expired_unparseable_string(caplog):
    now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    games = [
        {"title": "Unparseable Date Game", "end_date": "not-a-real-date-string"},
    ]
    res = filter_expired_games(games, now=now)
    # Should not raise exception and should keep game
    assert len(res) == 1
    assert res[0]["title"] == "Unparseable Date Game"


def test_filter_expired_custom_now_injected():
    # Test that injected custom now is used instead of system time
    custom_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    games = [
        {"title": "Game 2025", "end_date": "2025-01-01T20:00:00Z"},  # Future relative to custom_now
        {"title": "Game 2024", "end_date": "2024-01-01T00:00:00Z"},  # Past relative to custom_now
    ]
    res = filter_expired_games(games, now=custom_now)
    assert len(res) == 1
    assert res[0]["title"] == "Game 2025"

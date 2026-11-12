"""Unit tests for normalize_and_deduplicate in backend/main.py."""

from backend.main import normalize_and_deduplicate


def test_dedupe_same_title_same_platform():
    games = [
        {"title": "Portal 2", "platform": "Steam", "is_permanent": True},
        {"title": "Portal 2", "platform": "Steam", "is_permanent": False},
    ]
    res = normalize_and_deduplicate(games)
    assert len(res) == 1
    assert res[0]["title"] == "Portal 2"


def test_dedupe_same_title_different_platforms():
    games = [
        {"title": "Control", "platform": "Steam", "is_permanent": True},
        {"title": "Control", "platform": "Epic Games", "is_permanent": False},
    ]
    res = normalize_and_deduplicate(games)
    assert len(res) == 2


def test_dedupe_whitespace_normalization():
    games = [
        {"title": "Game  Name", "platform": "Steam", "is_permanent": True},
        {"title": "Game Name", "platform": "Steam", "is_permanent": False},
    ]
    res = normalize_and_deduplicate(games)
    assert len(res) == 1


def test_dedupe_missing_platform_key():
    games = [
        {"title": "Mystery Game", "is_permanent": True},
        {"title": "Mystery Game", "platform": "Steam", "is_permanent": False},
    ]
    res = normalize_and_deduplicate(games)
    # Should not raise KeyError when 'platform' key is missing
    assert isinstance(res, list)


def test_dedupe_punctuation_normalization():
    games = [
        {"title": "Hero: Origins", "platform": "Steam", "is_permanent": False, "end_date": None},
        {
            "title": "Hero - Origins",
            "platform": "Steam",
            "is_permanent": False,
            "end_date": "2026-09-01T23:59:59Z",
        },
    ]
    res = normalize_and_deduplicate(games)
    assert len(res) == 1
    assert res[0]["end_date"] == "2026-09-01T23:59:59Z"


def test_dedupe_prefers_valid_end_date_over_none_when_temporary():
    games = [
        {
            "id": "old",
            "title": "Timed Game",
            "platform": "Steam",
            "is_permanent": False,
            "end_date": None,
        },
        {
            "id": "dated",
            "title": "Timed Game",
            "platform": "Steam",
            "is_permanent": False,
            "end_date": "2026-09-10T17:00:00Z",
        },
    ]
    res = normalize_and_deduplicate(games)
    assert len(res) == 1
    assert res[0]["id"] == "dated"


def test_dedupe_does_not_replace_valid_end_date_with_none():
    games = [
        {
            "id": "dated",
            "title": "Timed Game",
            "platform": "Steam",
            "is_permanent": False,
            "end_date": "2026-09-10T17:00:00Z",
        },
        {
            "id": "undated",
            "title": "Timed Game",
            "platform": "Steam",
            "is_permanent": False,
            "end_date": None,
        },
    ]
    res = normalize_and_deduplicate(games)
    assert len(res) == 1
    assert res[0]["id"] == "dated"


def test_dedupe_prefers_permanent_over_temporary():
    games = [
        {
            "id": "temp",
            "title": "Evergreen",
            "platform": "Steam",
            "is_permanent": False,
            "end_date": "2026-09-10T17:00:00Z",
        },
        {
            "id": "perm",
            "title": "Evergreen",
            "platform": "Steam",
            "is_permanent": True,
            "end_date": None,
        },
    ]
    res = normalize_and_deduplicate(games)
    assert len(res) == 1
    assert res[0]["id"] == "perm"

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


def test_dedupe_preserves_metadata_when_incoming_wins():
    # Permanent incoming entry without image/store/notices wins over temporary existing entry
    games = [
        {
            "id": "temp",
            "title": "Evergreen",
            "platform": "Steam",
            "is_permanent": False,
            "end_date": "2026-09-10T17:00:00Z",
            "image_url": "https://example.com/evergreen.jpg",
            "store_url": "https://example.com/evergreen",
            "notices": ["alienware_arena"],
        },
        {
            "id": "perm",
            "title": "Evergreen",
            "platform": "Steam",
            "is_permanent": True,
            "end_date": None,
            "image_url": "",
            "store_url": "",
            "notices": [],
        },
    ]
    res = normalize_and_deduplicate(games)
    assert len(res) == 1
    assert res[0]["id"] == "perm"
    assert res[0]["image_url"] == "https://example.com/evergreen.jpg"
    assert res[0]["store_url"] == "https://example.com/evergreen"
    assert res[0]["notices"] == ["alienware_arena"]

    # Temporary incoming entry with valid end_date wins over undated existing entry
    timed_games = [
        {
            "id": "undated",
            "title": "Timed Collision",
            "platform": "Amazon Luna / Prime",
            "is_permanent": False,
            "end_date": None,
            "image_url": "https://m.media-amazon.com/timed.jpg",
            "store_url": "https://luna.amazon.com/timed",
            "notices": ["redeem_in_game"],
        },
        {
            "id": "dated",
            "title": "Timed Collision",
            "platform": "Amazon Luna / Prime",
            "is_permanent": False,
            "end_date": "2026-12-01T23:59:59Z",
            "image_url": "",
            "store_url": "",
            "notices": [],
        },
    ]
    timed_res = normalize_and_deduplicate(timed_games)
    assert len(timed_res) == 1
    assert timed_res[0]["id"] == "dated"
    assert timed_res[0]["end_date"] == "2026-12-01T23:59:59Z"
    assert timed_res[0]["image_url"] == "https://m.media-amazon.com/timed.jpg"
    assert timed_res[0]["store_url"] == "https://luna.amazon.com/timed"
    assert timed_res[0]["notices"] == ["redeem_in_game"]


def test_dedupe_preserves_metadata_when_existing_wins():
    games = [
        {
            "id": "perm",
            "title": "Evergreen",
            "platform": "Steam",
            "is_permanent": True,
            "end_date": None,
            "image_url": "",
            "store_url": "",
            "notices": [],
        },
        {
            "id": "temp",
            "title": "Evergreen",
            "platform": "Steam",
            "is_permanent": False,
            "end_date": "2026-09-10T17:00:00Z",
            "image_url": "https://example.com/evergreen.jpg",
            "store_url": "https://example.com/evergreen",
            "notices": ["newsletter_signup"],
        },
    ]
    res = normalize_and_deduplicate(games)
    assert len(res) == 1
    assert res[0]["id"] == "perm"
    assert res[0]["end_date"] is None
    assert res[0]["image_url"] == "https://example.com/evergreen.jpg"
    assert res[0]["store_url"] == "https://example.com/evergreen"
    assert res[0]["notices"] == ["newsletter_signup"]

    # Input dict must not be mutated in place
    assert games[0]["image_url"] == ""
    assert games[0]["store_url"] == ""
    assert games[0]["notices"] == []


def test_dedupe_does_not_overwrite_present_winner_metadata():
    games = [
        {
            "id": "dated",
            "title": "Keep Winner Fields",
            "platform": "Steam",
            "is_permanent": False,
            "end_date": "2026-12-10T17:00:00Z",
            "image_url": "https://example.com/winner.jpg",
            "store_url": "https://example.com/winner",
            "notices": ["amd_account"],
        },
        {
            "id": "undated",
            "title": "Keep Winner Fields",
            "platform": "Steam",
            "is_permanent": False,
            "end_date": None,
            "image_url": "https://example.com/loser.jpg",
            "store_url": "https://example.com/loser",
            "notices": ["alienware_arena"],
        },
    ]
    res = normalize_and_deduplicate(games)
    assert len(res) == 1
    assert res[0]["id"] == "dated"
    assert res[0]["image_url"] == "https://example.com/winner.jpg"
    assert res[0]["store_url"] == "https://example.com/winner"
    assert res[0]["notices"] == ["amd_account"]

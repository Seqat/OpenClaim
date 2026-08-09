#!/usr/bin/env python3
"""
Unit tests for normalize_and_deduplicate in backend/main.py.
"""

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

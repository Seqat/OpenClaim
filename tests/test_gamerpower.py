#!/usr/bin/env python3
"""
Unit tests for gamerpower scraper module.
"""

from backend.scrapers.gamerpower import clean_title


def test_clean_title():
    assert clean_title("Half-Life 2 (Steam) Giveaway") == "Half-Life 2"
    assert clean_title("Some Game Key Giveaway") == "Some Game"
    assert clean_title("Normal Title") == "Normal Title"
    assert clean_title("") == ""

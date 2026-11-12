"""Unit tests for gamerpower scraper module."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.schemas import BaseScraper
from backend.scrapers.gamerpower import (
    GamerPowerScraper,
    classify_content_type,
    clean_title,
    fetch_gamerpower_games,
    fetch_gamerpower_result,
)


def test_clean_title():
    assert clean_title("Half-Life 2 (Steam) Giveaway") == "Half-Life 2"
    assert clean_title("Some Game Key Giveaway") == "Some Game"
    assert clean_title("Normal Title") == "Normal Title"
    assert clean_title("") == ""
    assert (
        clean_title("Tape 101: Liminal Descent (Playtest) Steam")
        == "Tape 101: Liminal Descent (Playtest)"
    )
    assert clean_title("Free Bomb Bots Arena Gift Pack Keys") == "Free Bomb Bots Arena Gift Pack"
    assert (
        clean_title("Dream of Mirror Online Summer Fun DLC Pack Steam Keys")
        == "Dream of Mirror Online Summer Fun DLC Pack"
    )
    assert clean_title("Mechabellum Epic Games") == "Mechabellum"
    assert clean_title("Mechabellum (Epic Games) Key Giveaway") == "Mechabellum"
    assert clean_title("SteamWorld Dig") == "SteamWorld Dig"
    assert clean_title("The Skeleton Key") == "The Skeleton Key"


def test_classify_content_type_explicit_game_type():
    assert classify_content_type("Full Indie Game", "Game") == "game"
    assert classify_content_type("Dice Legacy", "Game") == "game"
    assert classify_content_type("Loot River", "Game") == "game"
    assert classify_content_type("EVERSPACE 2 Decal DLC Steam", "Game") == "dlc"


def test_fetch_gamerpower_platform_strictness_and_multi_platform():
    payload = [
        # Title contains "Steam" and "Epic", but platform is GOG -> must NOT be classified as Steam/Epic
        {
            "id": 100,
            "title": "SteamWorld Dig: Epic Journey",
            "platforms": "PC, GOG",
            "status": "Active",
            "type": "Game",
            "end_date": "N/A",
            "open_giveaway_url": "https://www.gamerpower.com/open/steamworld",
            "image": "https://www.gamerpower.com/img/steamworld.jpg",
        },
        # Multi-platform listing Steam AND Epic -> emits one entry for each
        {
            "id": 200,
            "title": "Dual Platform Game",
            "platforms": "PC, Steam, Epic Games Store",
            "status": "Active",
            "type": "Game",
            "end_date": "2026-09-01 23:59:00",
            "open_giveaway_url": "https://www.gamerpower.com/open/dual",
            "image": "https://www.gamerpower.com/img/dual.jpg",
        },
        # Invalid entries that must be safely skipped
        "not-a-dict",
        {"id": None, "title": "No ID", "platforms": "PC, Steam", "status": "Active"},
        {"id": 300, "title": "Inactive", "platforms": "PC, Steam", "status": "Expired"},
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = payload

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = None

    with patch("backend.scrapers.gamerpower.requests.Session", return_value=mock_session):
        result = fetch_gamerpower_result()

    assert result.ok is True
    assert result.source == "gamerpower"
    assert result.error is None
    assert len(result.games) == 2

    by_id = {g["id"]: g for g in result.games}
    assert set(by_id.keys()) == {"steam-200", "epicgames-200"}
    assert by_id["steam-200"]["platform"] == "Steam"
    assert by_id["epicgames-200"]["platform"] == "Epic Games"
    assert by_id["steam-200"]["end_date"] == "2026-09-01T23:59:00Z"
    assert by_id["steam-200"]["is_permanent"] is False
    assert by_id["steam-200"]["notices"] == []


def test_fetch_gamerpower_session_mounts_retry_adapter():
    mock_response = MagicMock()
    mock_response.json.return_value = []

    with patch("requests.Session.get", return_value=mock_response) as mock_get:
        result = fetch_gamerpower_result()

    assert result.ok is True
    assert result.games == []
    mock_get.assert_called_once()


def test_fetch_gamerpower_error_returns_failed_result():
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.RequestException("503 Service Unavailable")
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = None

    with patch("backend.scrapers.gamerpower.requests.Session", return_value=mock_session):
        result = fetch_gamerpower_result()
        games = fetch_gamerpower_games()

    assert result.ok is False
    assert result.games == []
    assert "503" in (result.error or "")
    assert games == []


def test_fetch_gamerpower_non_list_returns_failed_result():
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": 0, "status_message": "Error"}

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = None

    with patch("backend.scrapers.gamerpower.requests.Session", return_value=mock_session):
        result = fetch_gamerpower_result()

    assert result.ok is False
    assert result.games == []
    assert result.error is not None


@pytest.mark.asyncio
async def test_gamerpower_scraper_protocol():
    scraper = GamerPowerScraper()
    assert isinstance(scraper, BaseScraper)

    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = None

    with patch("backend.scrapers.gamerpower.requests.Session", return_value=mock_session):
        res = await scraper.fetch()

    assert res.ok is True
    assert res.source == "gamerpower"

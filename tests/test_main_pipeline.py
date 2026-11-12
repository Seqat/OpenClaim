"""Unit tests for backend schemas, atomic persistence, and main pipeline orchestration."""

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend import main as backend_main
from backend.schemas import ScraperResult, validate_game_entry


def _sample_game(
    game_id: str,
    title: str,
    platform: str,
    end_date: str | None = "2099-01-01T00:00:00Z",
    is_permanent: bool = False,
) -> dict:
    return {
        "id": game_id,
        "title": title,
        "platform": platform,
        "store_url": f"https://example.com/{game_id}",
        "image_url": f"https://example.com/{game_id}.jpg",
        "end_date": end_date,
        "is_permanent": is_permanent,
        "content_type": "game",
        "notices": [],
    }


def test_validate_game_entry_normalizes_and_validates():
    valid = validate_game_entry(
        {
            "id": " steam-1 ",
            "title": " Portal ",
            "platform": " Steam ",
            "end_date": "",
            "notices": ["b", "a", "a"],
        }
    )
    assert valid == {
        "id": "steam-1",
        "title": "Portal",
        "platform": "Steam",
        "store_url": "",
        "image_url": "",
        "end_date": None,
        "is_permanent": False,
        "content_type": "game",
        "notices": ["a", "b"],
    }

    with pytest.raises(TypeError):
        validate_game_entry("not-a-dict")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        validate_game_entry({"id": "", "title": "Game", "platform": "Steam"})
    with pytest.raises(ValueError):
        validate_game_entry(
            {"id": "1", "title": "Game", "platform": "Steam", "content_type": "movie"}
        )
    with pytest.raises(TypeError):
        validate_game_entry(
            {"id": "1", "title": "Game", "platform": "Steam", "is_permanent": "yes"}
        )
    with pytest.raises(ValueError):
        validate_game_entry(
            {"id": "1", "title": "Game", "platform": "Steam", "notices": "alienware"}
        )


def test_load_previous_games_handles_formats_and_corrupt_entries(tmp_path: Path):
    obj_file = tmp_path / "obj.json"
    obj_file.write_text(
        json.dumps({"games": [{"id": "1"}, "bad-item", 123, {"id": "2"}]}),
        encoding="utf-8",
    )
    assert backend_main.load_previous_games(obj_file) == [{"id": "1"}, {"id": "2"}]

    arr_file = tmp_path / "arr.json"
    arr_file.write_text(json.dumps([{"id": "3"}, None]), encoding="utf-8")
    assert backend_main.load_previous_games(arr_file) == [{"id": "3"}]

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    assert backend_main.load_previous_games(bad_json) == []
    assert backend_main.load_previous_games(tmp_path / "missing.json") == []


def test_atomic_write_json_writes_cleanly(tmp_path: Path):
    out_file = tmp_path / "games.json"
    backend_main.atomic_write_json(out_file, {"count": 1, "games": [{"id": "steam-1"}]})

    assert json.loads(out_file.read_text(encoding="utf-8")) == {
        "count": 1,
        "games": [{"id": "steam-1"}],
    }
    assert [p.name for p in tmp_path.iterdir()] == ["games.json"]


def test_main_does_not_configure_root_logging_on_import():
    # Importing backend.main should not attach StreamHandlers to root logger
    root_handlers = logging.getLogger().handlers
    assert not any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is backend_main.sys.stdout
        for h in root_handlers
    )


def test_main_pipeline_happy_path_writes_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    out_file = tmp_path / "games.json"
    monkeypatch.setattr(backend_main, "OUTPUT_FILE", out_file)

    gp_res = ScraperResult(
        source="gamerpower",
        games=[_sample_game("steam-1", "Portal 2", "Steam")],
        ok=True,
    )
    luna_res = ScraperResult(
        source="amazon_luna",
        games=[_sample_game("amazon-1", "Steelrising", "Amazon Luna / Prime")],
        ok=True,
    )

    with (
        patch("backend.main.fetch_gamerpower_result", return_value=gp_res),
        patch("backend.main.fetch_amazon_result", AsyncMock(return_value=luna_res)),
    ):
        backend_main.main()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["count"] == 2
    assert {g["id"] for g in data["games"]} == {"steam-1", "amazon-1"}


def test_main_pipeline_retains_active_previous_entries_on_single_source_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    out_file = tmp_path / "games.json"
    previous = {
        "generated_at": "2026-08-14T20:32:56Z",
        "count": 3,
        "games": [
            _sample_game("amazon-active", "Active Luna", "Amazon Luna / Prime", "2099-05-01T00:00:00Z"),
            _sample_game("amazon-expired", "Expired Luna", "Amazon Luna / Prime", "2020-01-01T00:00:00Z"),
            _sample_game("steam-old", "Old Steam", "Steam", "2099-05-01T00:00:00Z"),
        ],
    }
    out_file.write_text(json.dumps(previous), encoding="utf-8")
    monkeypatch.setattr(backend_main, "OUTPUT_FILE", out_file)

    gp_res = ScraperResult(
        source="gamerpower",
        games=[_sample_game("steam-new", "New Steam", "Steam")],
        ok=True,
    )
    luna_res = ScraperResult(
        source="amazon_luna",
        games=[],
        ok=False,
        error="Playwright timeout",
    )

    with (
        patch("backend.main.fetch_gamerpower_result", return_value=gp_res),
        patch("backend.main.fetch_amazon_result", AsyncMock(return_value=luna_res)),
    ):
        backend_main.main()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    ids = {g["id"] for g in data["games"]}
    assert ids == {"steam-new", "amazon-active"}


def test_main_pipeline_aborts_when_all_sources_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    out_file = tmp_path / "games.json"
    original_content = json.dumps(
        {"count": 1, "games": [_sample_game("steam-1", "Kept", "Steam")]}
    )
    out_file.write_text(original_content, encoding="utf-8")
    monkeypatch.setattr(backend_main, "OUTPUT_FILE", out_file)

    gp_res = ScraperResult(source="gamerpower", games=[], ok=False, error="HTTP 500")
    luna_res = ScraperResult(source="amazon_luna", games=[], ok=False, error="Browser crash")

    with (
        patch("backend.main.fetch_gamerpower_result", return_value=gp_res),
        patch("backend.main.fetch_amazon_result", AsyncMock(return_value=luna_res)),
        pytest.raises(SystemExit) as exc_info,
    ):
        backend_main.main()

    assert exc_info.value.code == 1
    assert out_file.read_text(encoding="utf-8") == original_content


def test_main_pipeline_aborts_on_empty_or_sudden_drop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    out_file = tmp_path / "games.json"
    previous_games = [
        _sample_game(f"steam-{i}", f"Game {i}", "Steam") for i in range(10)
    ]
    original_content = json.dumps({"count": 10, "games": previous_games})
    out_file.write_text(original_content, encoding="utf-8")
    monkeypatch.setattr(backend_main, "OUTPUT_FILE", out_file)

    # 2 < 10 * 0.5 -> abort
    gp_res = ScraperResult(
        source="gamerpower",
        games=[_sample_game("steam-0", "Game 0", "Steam")],
        ok=True,
    )
    luna_res = ScraperResult(
        source="amazon_luna",
        games=[_sample_game("amazon-0", "Luna 0", "Amazon Luna / Prime")],
        ok=True,
    )

    with (
        patch("backend.main.fetch_gamerpower_result", return_value=gp_res),
        patch("backend.main.fetch_amazon_result", AsyncMock(return_value=luna_res)),
        pytest.raises(SystemExit) as exc_info,
    ):
        backend_main.main()

    assert exc_info.value.code == 1
    assert out_file.read_text(encoding="utf-8") == original_content

    # Empty final_games -> abort
    gp_empty = ScraperResult(source="gamerpower", games=[], ok=True)
    luna_empty = ScraperResult(source="amazon_luna", games=[], ok=True)
    with (
        patch("backend.main.fetch_gamerpower_result", return_value=gp_empty),
        patch("backend.main.fetch_amazon_result", AsyncMock(return_value=luna_empty)),
        pytest.raises(SystemExit) as exc_empty,
    ):
        backend_main.main()

    assert exc_empty.value.code == 1

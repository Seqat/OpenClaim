"""Unit tests for backend schemas, atomic persistence, and main pipeline orchestration."""

import json
import logging
from pathlib import Path

import pytest

from backend import main as backend_main
from backend.schemas import BaseScraper, ScraperResult, validate_game_entry


class _StubScraper:
    def __init__(
        self,
        source: str,
        platforms: frozenset[str],
        result: ScraperResult,
    ) -> None:
        self.source = source
        self.platforms = platforms
        self._result = result

    async def fetch(self) -> ScraperResult:
        return self._result


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
            "store_url": " https://store.steampowered.com/app/400 ",
            "end_date": "",
            "notices": ["b", " a ", "a"],
        }
    )
    assert valid == {
        "id": "steam-1",
        "title": "Portal",
        "platform": "Steam",
        "store_url": "https://store.steampowered.com/app/400",
        "image_url": "",
        "end_date": None,
        "is_permanent": False,
        "content_type": "game",
        "notices": ["a", "b"],
    }

    with pytest.raises(TypeError):
        validate_game_entry("not-a-dict")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        validate_game_entry(
            {"id": "", "title": "Game", "platform": "Steam", "store_url": "https://example.com"}
        )
    with pytest.raises(ValueError):
        validate_game_entry(
            {"id": "1", "title": "Game", "platform": "Steam", "store_url": ""}
        )
    with pytest.raises(ValueError):
        validate_game_entry(
            {"id": "1", "title": "Game", "platform": "Steam", "store_url": "javascript:alert(1)"}
        )
    with pytest.raises(ValueError):
        validate_game_entry(
            {
                "id": "1",
                "title": "Game",
                "platform": "Steam",
                "store_url": "https://example.com",
                "image_url": "ftp://example.com/img.png",
            }
        )
    with pytest.raises(ValueError):
        validate_game_entry(
            {
                "id": "1",
                "title": "Game",
                "platform": "Steam",
                "store_url": "https://example.com",
                "content_type": "movie",
            }
        )
    with pytest.raises(TypeError):
        validate_game_entry(
            {
                "id": "1",
                "title": "Game",
                "platform": "Steam",
                "store_url": "https://example.com",
                "is_permanent": "yes",
            }
        )
    with pytest.raises(ValueError):
        validate_game_entry(
            {
                "id": "1",
                "title": "Game",
                "platform": "Steam",
                "store_url": "https://example.com",
                "notices": "alienware",
            }
        )
    with pytest.raises(ValueError):
        validate_game_entry(
            {
                "id": "1",
                "title": "Game",
                "platform": "Steam",
                "store_url": "https://example.com",
                "notices": ["   "],
            }
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
    summary_file = tmp_path / "step_summary.md"
    monkeypatch.setattr(backend_main, "OUTPUT_FILE", out_file)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

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
    monkeypatch.setattr(
        backend_main,
        "SCRAPERS",
        (
            _StubScraper("gamerpower", frozenset({"Steam", "Epic Games"}), gp_res),
            _StubScraper("amazon_luna", frozenset({"Amazon Luna / Prime"}), luna_res),
        ),
    )

    backend_main.main([])

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["count"] == 2
    assert {g["id"] for g in data["games"]} == {"steam-1", "amazon-1"}
    summary_text = summary_file.read_text(encoding="utf-8")
    assert "**Active deals:** 2" in summary_text
    assert "`gamerpower`: OK (1)" in summary_text


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
    scrapers = (
        _StubScraper("gamerpower", frozenset({"Steam", "Epic Games"}), gp_res),
        _StubScraper("amazon_luna", frozenset({"Amazon Luna / Prime"}), luna_res),
    )
    assert all(isinstance(s, BaseScraper) for s in scrapers)
    monkeypatch.setattr(backend_main, "SCRAPERS", scrapers)

    backend_main.main([])

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
    monkeypatch.setattr(
        backend_main,
        "SCRAPERS",
        (
            _StubScraper("gamerpower", frozenset({"Steam", "Epic Games"}), gp_res),
            _StubScraper("amazon_luna", frozenset({"Amazon Luna / Prime"}), luna_res),
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        backend_main.main([])

    assert exc_info.value.code == 1
    assert out_file.read_text(encoding="utf-8") == original_content


def test_main_pipeline_aborts_on_empty_or_sudden_drop_and_allows_override(
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
    monkeypatch.setattr(
        backend_main,
        "SCRAPERS",
        (
            _StubScraper("gamerpower", frozenset({"Steam", "Epic Games"}), gp_res),
            _StubScraper("amazon_luna", frozenset({"Amazon Luna / Prime"}), luna_res),
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        backend_main.main([])

    assert exc_info.value.code == 1
    assert out_file.read_text(encoding="utf-8") == original_content

    # --allow-drop permits writing when the drop is intentional
    backend_main.main(["--allow-drop"])
    written = json.loads(out_file.read_text(encoding="utf-8"))
    assert written["count"] == 2
    assert {g["id"] for g in written["games"]} == {"steam-0", "amazon-0"}

    # Empty final_games -> always abort even with --allow-drop
    gp_empty = ScraperResult(source="gamerpower", games=[], ok=True)
    luna_empty = ScraperResult(source="amazon_luna", games=[], ok=True)
    monkeypatch.setattr(
        backend_main,
        "SCRAPERS",
        (
            _StubScraper("gamerpower", frozenset({"Steam", "Epic Games"}), gp_empty),
            _StubScraper("amazon_luna", frozenset({"Amazon Luna / Prime"}), luna_empty),
        ),
    )
    with pytest.raises(SystemExit) as exc_empty:
        backend_main.main(["--allow-drop"])

    assert exc_empty.value.code == 1


def test_main_pipeline_drops_invalid_entries_before_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    out_file = tmp_path / "games.json"
    monkeypatch.setattr(backend_main, "OUTPUT_FILE", out_file)

    bad_entry = _sample_game("steam-bad", "Broken URL", "Steam")
    bad_entry["store_url"] = "javascript:alert(1)"
    good_entry = _sample_game("steam-ok", "Valid Game", "Steam")

    monkeypatch.setattr(
        backend_main,
        "SCRAPERS",
        (
            _StubScraper(
                "gamerpower",
                frozenset({"Steam", "Epic Games"}),
                ScraperResult(source="gamerpower", games=[bad_entry, good_entry], ok=True),
            ),
        ),
    )

    backend_main.main([])
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert [g["id"] for g in data["games"]] == ["steam-ok"]


def test_backfill_from_previous_restores_missing_fields_by_id_and_title():
    previous = [
        {
            "id": "amazon-1",
            "title": "Ad Infinitum",
            "platform": "Amazon Luna / Prime",
            "store_url": "https://luna.amazon.com/ad-infinitum",
            "image_url": "https://m.media-amazon.com/ad.jpg",
            "end_date": "2099-11-25T23:59:59Z",
            "is_permanent": False,
            "content_type": "game",
            "notices": ["alienware_arena"],
        },
        {
            "id": "amazon-old-slug",
            "title": "Vampire: The Masquerade - Swansong",
            "platform": "Amazon Luna / Prime",
            "store_url": "https://luna.amazon.com/swansong-old",
            "image_url": "https://m.media-amazon.com/swansong.jpg",
            "end_date": "2099-11-18T23:59:59Z",
            "is_permanent": False,
            "content_type": "game",
            "notices": ["newsletter_signup"],
        },
    ]
    incoming = [
        {
            "id": "amazon-1",
            "title": "Ad Infinitum",
            "platform": "Amazon Luna / Prime",
            "store_url": "https://luna.amazon.com/ad-infinitum",
            "image_url": "",
            "end_date": None,
            "is_permanent": False,
            "content_type": "game",
            "notices": [],
        },
        {
            "id": "amazon-new-uuid",
            "title": "Vampire The Masquerade Swansong",
            "platform": "Amazon Luna / Prime",
            "store_url": "https://luna.amazon.com/swansong-new",
            "image_url": "   ",
            "end_date": "invalid-date",
            "is_permanent": False,
            "content_type": "game",
            "notices": [],
        },
        {
            "id": "steam-different-platform",
            "title": "Ad Infinitum",
            "platform": "Steam",
            "store_url": "https://store.steampowered.com/app/1",
            "image_url": "",
            "end_date": None,
            "is_permanent": False,
            "content_type": "game",
            "notices": [],
        },
    ]

    result = backend_main.backfill_from_previous(incoming, previous)

    # Matched by id (image_url and end_date restored, notices are NOT resurrected)
    assert result[0]["image_url"] == "https://m.media-amazon.com/ad.jpg"
    assert result[0]["end_date"] == "2099-11-25T23:59:59Z"
    assert result[0]["notices"] == []

    # Matched by (platform, norm_title) despite different id and punctuation
    assert result[1]["id"] == "amazon-new-uuid"
    assert result[1]["image_url"] == "https://m.media-amazon.com/swansong.jpg"
    assert result[1]["end_date"] == "2099-11-18T23:59:59Z"
    assert result[1]["notices"] == []

    # Cross-platform entry with identical title must not match
    assert result[2]["image_url"] == ""
    assert result[2]["end_date"] is None
    assert result[2]["notices"] == []

    # Input dicts were not mutated in place
    assert incoming[0]["image_url"] == ""
    assert incoming[0]["end_date"] is None
    assert incoming[0]["notices"] == []


def test_backfill_from_previous_preserves_existing_and_permanent_and_prefers_complete():
    previous = [
        # Incomplete entries appear first and last to verify score-based preference
        {
            "id": "amazon-dup",
            "title": "Duplicate Luna",
            "platform": "Amazon Luna / Prime",
            "image_url": "",
            "end_date": None,
            "is_permanent": False,
            "notices": [],
        },
        {
            "id": "amazon-dup",
            "title": "Duplicate Luna",
            "platform": "Amazon Luna / Prime",
            "image_url": "https://m.media-amazon.com/dup.jpg",
            "end_date": "2099-12-01T23:59:59Z",
            "is_permanent": False,
            "notices": ["amd_account"],
        },
        {
            "id": "steam-perm",
            "title": "Permanent Deal",
            "platform": "Steam",
            "image_url": "https://steam.example.com/perm.jpg",
            "end_date": "2099-01-01T00:00:00Z",
            "is_permanent": False,
            "notices": ["redeem_in_game"],
        },
        {
            "id": "steam-keep",
            "title": "Keep Fresh",
            "platform": "Steam",
            "image_url": "https://steam.example.com/old.jpg",
            "end_date": "2099-02-01T00:00:00Z",
            "is_permanent": False,
            "notices": ["alienware_arena"],
        },
    ]
    incoming = [
        {
            "id": "amazon-dup",
            "title": "Duplicate Luna",
            "platform": "Amazon Luna / Prime",
            "image_url": "",
            "end_date": None,
            "is_permanent": False,
            "notices": [],
        },
        {
            "id": "steam-perm",
            "title": "Permanent Deal",
            "platform": "Steam",
            "image_url": "",
            "end_date": None,
            "is_permanent": True,
            "notices": [],
        },
        {
            "id": "steam-keep",
            "title": "Keep Fresh",
            "platform": "Steam",
            "image_url": "https://steam.example.com/new.jpg",
            "end_date": "2099-09-01T00:00:00Z",
            "is_permanent": False,
            "notices": ["dungeonloot_account"],
        },
    ]

    result = backend_main.backfill_from_previous(incoming, previous)

    # Complete duplicate won over incomplete duplicate (notices stay fresh)
    assert result[0]["image_url"] == "https://m.media-amazon.com/dup.jpg"
    assert result[0]["end_date"] == "2099-12-01T23:59:59Z"
    assert result[0]["notices"] == []

    # Permanent deal restores image_url but NEVER receives an end_date or stale notices
    assert result[1]["image_url"] == "https://steam.example.com/perm.jpg"
    assert result[1]["end_date"] is None
    assert result[1]["notices"] == []

    # Valid values on incoming are never overwritten
    assert result[2]["image_url"] == "https://steam.example.com/new.jpg"
    assert result[2]["end_date"] == "2099-09-01T00:00:00Z"
    assert result[2]["notices"] == ["dungeonloot_account"]


def test_main_pipeline_backfills_missing_fields_when_scraper_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    out_file = tmp_path / "games.json"
    previous = {
        "generated_at": "2099-01-01T00:00:00Z",
        "count": 3,
        "games": [
            {
                **_sample_game(
                    "amazon-1",
                    "Radiolight",
                    "Amazon Luna / Prime",
                    "2099-12-16T23:59:59Z",
                ),
                "image_url": "https://m.media-amazon.com/radiolight.jpg",
                "notices": ["alienware_arena"],
            },
            {
                **_sample_game(
                    "amazon-expired",
                    "Expired Deal",
                    "Amazon Luna / Prime",
                    "2020-01-01T00:00:00Z",
                ),
                "image_url": "https://m.media-amazon.com/expired.jpg",
            },
            _sample_game("steam-1", "Portal 2", "Steam", "2099-12-31T23:59:59Z"),
        ],
    }
    out_file.write_text(json.dumps(previous), encoding="utf-8")
    monkeypatch.setattr(backend_main, "OUTPUT_FILE", out_file)

    gp_res = ScraperResult(
        source="gamerpower",
        games=[_sample_game("steam-1", "Portal 2", "Steam", "2099-12-31T23:59:59Z")],
        ok=True,
    )
    # Amazon scraper succeeds, but detail page timed out and lazy-load missed image
    luna_res = ScraperResult(
        source="amazon_luna",
        games=[
            {
                **_sample_game("amazon-1", "Radiolight", "Amazon Luna / Prime", None),
                "image_url": "",
                "notices": [],
            },
            _sample_game("amazon-2", "WarBreeds", "Amazon Luna / Prime", "2099-01-08T23:59:59Z"),
        ],
        ok=True,
    )
    monkeypatch.setattr(
        backend_main,
        "SCRAPERS",
        (
            _StubScraper("gamerpower", frozenset({"Steam", "Epic Games"}), gp_res),
            _StubScraper("amazon_luna", frozenset({"Amazon Luna / Prime"}), luna_res),
        ),
    )

    backend_main.main([])

    data = json.loads(out_file.read_text(encoding="utf-8"))
    by_id = {g["id"]: g for g in data["games"]}
    assert set(by_id) == {"amazon-1", "amazon-2", "steam-1"}
    assert by_id["amazon-1"]["image_url"] == "https://m.media-amazon.com/radiolight.jpg"
    assert by_id["amazon-1"]["end_date"] == "2099-12-16T23:59:59Z"
    assert by_id["amazon-1"]["notices"] == []
    assert by_id["amazon-2"]["image_url"] == "https://example.com/amazon-2.jpg"

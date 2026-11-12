#!/usr/bin/env python3
"""Schema and structural integrity validation for games.json."""

import json
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMES_JSON_PATH = REPO_ROOT / "games.json"

REQUIRED_GAME_FIELDS = (
    "id",
    "title",
    "platform",
    "store_url",
    "image_url",
    "end_date",
    "is_permanent",
)
VALID_CONTENT_TYPES = {"game", "dlc"}


def _parse_iso_timestamp(value: Any, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp string or raise ValueError."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty ISO timestamp string")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid ISO-8601 timestamp: {value!r}") from exc


def _validate_game_entry(entry: Any, index: int, seen_ids: set[str]) -> None:
    """Validate a single game entry dictionary against the OpenClaim schema."""
    if not isinstance(entry, dict):
        raise ValueError(f"games[{index}] must be a JSON object")

    for field in REQUIRED_GAME_FIELDS:
        if field not in entry:
            raise ValueError(f"games[{index}] ({entry.get('id', '?')}) missing field '{field}'")

    game_id = entry["id"]
    if not isinstance(game_id, str) or not game_id.strip():
        raise ValueError(f"games[{index}].id must be a non-empty string")
    if game_id in seen_ids:
        raise ValueError(f"Duplicate game id found: {game_id!r}")
    seen_ids.add(game_id)

    for str_field in ("title", "platform"):
        val = entry[str_field]
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"games[{index}] ({game_id}).{str_field} must be a non-empty string")

    store_url = entry["store_url"]
    if not isinstance(store_url, str) or not store_url.startswith(("http://", "https://")):
        raise ValueError(
            f"games[{index}] ({game_id}).store_url must be an http(s) URL: {store_url!r}"
        )

    image_url = entry["image_url"]
    if not isinstance(image_url, str) or (
        image_url != "" and not image_url.startswith(("http://", "https://"))
    ):
        raise ValueError(
            f"games[{index}] ({game_id}).image_url must be empty or an http(s) URL: {image_url!r}"
        )

    end_date = entry["end_date"]
    if end_date is not None:
        _parse_iso_timestamp(end_date, f"games[{index}] ({game_id}).end_date")

    if not isinstance(entry["is_permanent"], bool):
        raise ValueError(f"games[{index}] ({game_id}).is_permanent must be a boolean")

    if "content_type" in entry:
        content_type = entry["content_type"]
        if content_type not in VALID_CONTENT_TYPES:
            raise ValueError(
                f"games[{index}] ({game_id}).content_type must be one of "
                f"{sorted(VALID_CONTENT_TYPES)}, got {content_type!r}"
            )
    else:
        warnings.warn(
            f"games[{index}] ({game_id}) is missing optional legacy field 'content_type'",
            UserWarning,
            stacklevel=2,
        )

    if "notices" in entry:
        notices = entry["notices"]
        if not isinstance(notices, list) or not all(
            isinstance(item, str) and bool(item.strip()) for item in notices
        ):
            raise ValueError(
                f"games[{index}] ({game_id}).notices must be a list of non-empty strings"
            )


def validate_games_data(data: Any) -> None:
    """Validate the top-level games.json payload and every contained game entry."""
    if not isinstance(data, dict):
        raise ValueError("Top-level games.json payload must be a JSON object")

    if "generated_at" not in data:
        raise ValueError("Missing top-level field 'generated_at'")
    _parse_iso_timestamp(data["generated_at"], "generated_at")

    if "games" not in data or not isinstance(data["games"], list):
        raise ValueError("Top-level field 'games' must be a list")

    count = data.get("count")
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("Top-level field 'count' must be an integer")
    if count != len(data["games"]):
        raise ValueError(
            f"Top-level count ({count}) does not match len(games) ({len(data['games'])})"
        )

    seen_ids: set[str] = set()
    for idx, entry in enumerate(data["games"]):
        _validate_game_entry(entry, idx, seen_ids)


def validate_games_file(path: Path = GAMES_JSON_PATH) -> dict[str, Any]:
    """Load and validate a games.json file from disk."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    validate_games_data(data)
    return data


def _sample_game(**overrides: Any) -> dict[str, Any]:
    game: dict[str, Any] = {
        "id": "steam-1",
        "title": "Sample Game",
        "platform": "Steam",
        "store_url": "https://store.steampowered.com/app/1",
        "image_url": "https://cdn.example.com/1.jpg",
        "end_date": "2026-12-31T23:59:59Z",
        "is_permanent": False,
        "content_type": "game",
    }
    game.update(overrides)
    return game


def test_committed_games_json_matches_schema() -> None:
    data = validate_games_file(GAMES_JSON_PATH)
    assert data["count"] == len(data["games"])
    assert len(data["games"]) > 0


def test_valid_payload_with_notices_and_optional_content_type() -> None:
    payload = {
        "generated_at": "2026-08-14T20:32:56Z",
        "count": 2,
        "games": [
            _sample_game(id="steam-1", notices=["alienware_arena"]),
            _sample_game(id="epic-2", platform="Epic Games", end_date=None, is_permanent=True),
        ],
    }
    del payload["games"][1]["content_type"]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validate_games_data(payload)
    assert len(caught) == 1


def test_rejects_count_mismatch_and_bool_count() -> None:
    for bad_count in (2, True):
        payload = {
            "generated_at": "2026-08-14T20:32:56Z",
            "count": bad_count,
            "games": [_sample_game()],
        }
        try:
            validate_games_data(payload)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for count={bad_count!r}")


def test_rejects_duplicate_ids() -> None:
    payload = {
        "generated_at": "2026-08-14T20:32:56Z",
        "count": 2,
        "games": [_sample_game(id="dup-1"), _sample_game(id="dup-1")],
    }
    try:
        validate_games_data(payload)
    except ValueError as exc:
        assert "Duplicate game id" in str(exc)
    else:
        raise AssertionError("Expected ValueError for duplicate ids")


def test_rejects_invalid_generated_at_and_required_fields() -> None:
    bad_ts = {"generated_at": "not-a-date", "count": 0, "games": []}
    try:
        validate_games_data(bad_ts)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for invalid generated_at")

    missing = _sample_game()
    del missing["store_url"]
    try:
        validate_games_data(
            {"generated_at": "2026-08-14T20:32:56Z", "count": 1, "games": [missing]}
        )
    except ValueError as exc:
        assert "store_url" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing store_url")


def test_rejects_invalid_content_type_and_notices() -> None:
    bad_ct = {
        "generated_at": "2026-08-14T20:32:56Z",
        "count": 1,
        "games": [_sample_game(content_type="soundtrack")],
    }
    try:
        validate_games_data(bad_ct)
    except ValueError as exc:
        assert "content_type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid content_type")

    for bad_notices in ("alienware_arena", [123], [""]):
        payload = {
            "generated_at": "2026-08-14T20:32:56Z",
            "count": 1,
            "games": [_sample_game(notices=bad_notices)],
        }
        try:
            validate_games_data(payload)
        except ValueError as exc:
            assert "notices" in str(exc)
        else:
            raise AssertionError(f"Expected ValueError for notices={bad_notices!r}")


if __name__ == "__main__":
    validate_games_file(GAMES_JSON_PATH)
    print(f"Schema validation passed for {GAMES_JSON_PATH}")
    sys.exit(0)

"""Shared schemas and scraper contracts for the OpenClaim backend."""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

VALID_CONTENT_TYPES = frozenset({"game", "dlc"})
GAME_ENTRY_FIELDS = (
    "id",
    "title",
    "platform",
    "store_url",
    "image_url",
    "end_date",
    "is_permanent",
    "content_type",
    "notices",
)


@dataclass
class ScraperResult:
    """Structured result returned by each scraper source."""

    source: str
    games: list[dict[str, Any]]
    ok: bool
    error: str | None = None


@runtime_checkable
class BaseScraper(Protocol):
    """Protocol implemented by all OpenClaim giveaway scrapers."""

    source: str

    async def fetch(self) -> ScraperResult:
        """Fetch giveaway entries for this source."""
        ...


def validate_game_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a game entry against the canonical OpenClaim schema."""
    if not isinstance(entry, dict):
        raise TypeError(f"Game entry must be a dict, got {type(entry).__name__}")

    normalized: dict[str, Any] = {}
    for required_key in ("id", "title", "platform"):
        raw_val = entry.get(required_key)
        if not isinstance(raw_val, str) or not raw_val.strip():
            raise ValueError(f"Game entry missing or empty required string field '{required_key}'")
        normalized[required_key] = raw_val.strip()

    for url_key in ("store_url", "image_url"):
        raw_url = entry.get(url_key, "")
        if raw_url is None:
            raw_url = ""
        if not isinstance(raw_url, str):
            raise TypeError(f"Game entry field '{url_key}' must be a string")
        normalized[url_key] = raw_url.strip()

    raw_end_date = entry.get("end_date")
    if raw_end_date is not None:
        if not isinstance(raw_end_date, str):
            raise ValueError("Game entry field 'end_date' must be a string or None")
        raw_end_date = raw_end_date.strip() or None
    normalized["end_date"] = raw_end_date

    raw_perm = entry.get("is_permanent", False)
    if not isinstance(raw_perm, bool):
        raise TypeError("Game entry field 'is_permanent' must be a bool")
    normalized["is_permanent"] = raw_perm

    raw_content_type = entry.get("content_type", "game")
    if raw_content_type is None:
        raw_content_type = "game"
    if not isinstance(raw_content_type, str) or raw_content_type not in VALID_CONTENT_TYPES:
        raise ValueError(
            f"Game entry field 'content_type' must be one of {sorted(VALID_CONTENT_TYPES)}, "
            f"got {raw_content_type!r}"
        )
    normalized["content_type"] = raw_content_type

    raw_notices = entry.get("notices", [])
    if raw_notices is None:
        raw_notices = []
    if not isinstance(raw_notices, list) or not all(isinstance(n, str) for n in raw_notices):
        raise ValueError("Game entry field 'notices' must be a list of strings")
    normalized["notices"] = sorted(set(raw_notices))

    return normalized

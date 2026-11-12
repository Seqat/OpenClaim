"""OpenClaim - Automated Free Games Tracker Data Pipeline Entry Point.

Executes GamerPower and Amazon Luna scrapers, normalizes and deduplicates results,
and outputs games.json to the project root directory.
"""

import asyncio
import json
import logging
import os
import re
import sys
import tempfile
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.schemas import ScraperResult
from backend.scrapers.gamerpower import fetch_gamerpower_result
from backend.scrapers.luna import fetch_amazon_result
from backend.utils.date_helpers import parse_iso_datetime

logger = logging.getLogger("backend_main")

OUTPUT_FILE = PROJECT_ROOT / "games.json"

SOURCE_PLATFORMS: dict[str, frozenset[str]] = {
    "gamerpower": frozenset({"Steam", "Epic Games"}),
    "amazon_luna": frozenset({"Amazon Luna / Prime"}),
}


def _has_valid_end_date(game: dict[str, Any]) -> bool:
    """Return True if the entry has a parseable non-empty end_date."""
    raw_end_date = game.get("end_date")
    if raw_end_date is None or (isinstance(raw_end_date, str) and not raw_end_date.strip()):
        return False
    return parse_iso_datetime(str(raw_end_date)) is not None


def normalize_and_deduplicate(games_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize and deduplicate game entries based on platform and game title."""
    deduped: dict[tuple[str, str], dict[str, Any]] = {}

    for game in games_list:
        if not isinstance(game, dict):
            continue

        platform = str(game.get("platform") or "")
        title = str(game.get("title") or "").strip()
        if not title:
            continue

        norm_title = re.sub(r"[^\w\s]", " ", title.casefold())
        norm_title = re.sub(r"\s+", " ", norm_title).strip()
        norm_key = (platform, norm_title)

        if norm_key in deduped:
            existing = deduped[norm_key]
            existing_perm = bool(existing.get("is_permanent"))
            new_perm = bool(game.get("is_permanent"))
            if (new_perm and not existing_perm) or (
                not existing_perm
                and not new_perm
                and not _has_valid_end_date(existing)
                and _has_valid_end_date(game)
            ):
                deduped[norm_key] = game
        else:
            deduped[norm_key] = game

    result = list(deduped.values())
    result.sort(key=lambda g: (str(g.get("platform") or ""), str(g.get("title") or "")))
    return result


def filter_expired_games(
    games: list[dict[str, Any]],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Filter out games whose end_date has expired beyond a 6-hour grace period.

    Retains games with missing/empty end_dates, future end_dates, or unparseable end_dates.
    """
    if now is None:
        now = datetime.now(UTC)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    else:
        now = now.astimezone(UTC)

    retained: list[dict[str, Any]] = []
    for game in games:
        if not isinstance(game, dict):
            continue

        raw_end_date = game.get("end_date")
        if raw_end_date is None or (isinstance(raw_end_date, str) and not raw_end_date.strip()):
            retained.append(game)
            continue

        end_dt = parse_iso_datetime(str(raw_end_date))
        if end_dt is None:
            logger.warning(
                f"Could not parse end_date '{raw_end_date}' for game "
                f"'{game.get('title', 'Unknown')}'. Keeping game."
            )
            retained.append(game)
            continue

        # Drop only if current time is past end_date + 6 hours grace period
        try:
            grace_deadline = end_dt + timedelta(hours=6)
        except OverflowError:
            retained.append(game)
            continue

        if now > grace_deadline:
            continue

        retained.append(game)

    return retained


def load_previous_games(output_file: Path | None = None) -> list[dict[str, Any]]:
    """Safely load prior game entries from games.json (supporting array and object formats)."""
    target = output_file if output_file is not None else OUTPUT_FILE
    if not target.exists():
        return []

    try:
        with open(target, encoding="utf-8") as f:
            prev_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Could not read existing {target}: {e}")
        return []

    raw_list: Any
    if isinstance(prev_data, list):
        raw_list = prev_data
    elif isinstance(prev_data, dict) and isinstance(prev_data.get("games"), list):
        raw_list = prev_data["games"]
    else:
        return []

    return [g for g in raw_list if isinstance(g, dict)]


def atomic_write_json(output_file: Path, data: dict[str, Any]) -> None:
    """Atomically write JSON data via a temp file in output_file.parent and os.replace."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        dir=output_file.parent,
        prefix=f".{output_file.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, output_file)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


async def _run_sync_scraper(source: str, fn: Callable[[], ScraperResult]) -> ScraperResult:
    try:
        return await asyncio.to_thread(fn)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Unexpected exception in {source} scraper: {exc}")
        return ScraperResult(source=source, games=[], ok=False, error=str(exc))


async def _run_async_scraper(source: str, coro: Awaitable[ScraperResult]) -> ScraperResult:
    try:
        return await coro
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Unexpected exception in {source} scraper: {exc}")
        return ScraperResult(source=source, games=[], ok=False, error=str(exc))


async def fetch_all_sources() -> list[ScraperResult]:
    """Run GamerPower and Amazon Luna scrapers concurrently."""
    results = await asyncio.gather(
        _run_sync_scraper("gamerpower", fetch_gamerpower_result),
        _run_async_scraper("amazon_luna", fetch_amazon_result()),
    )
    return list(results)


def main() -> None:
    """Run the OpenClaim backend fetch, merge, filter, and atomic write pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger.info("Starting OpenClaim free games fetch pipeline...")

    previous_games = load_previous_games(OUTPUT_FILE)
    active_previous_games = filter_expired_games(previous_games)

    results = asyncio.run(fetch_all_sources())
    if all(not r.ok for r in results):
        logger.error("All scrapers failed. Aborting write to preserve existing games.json.")
        sys.exit(1)

    combined_games: list[dict[str, Any]] = []
    for result in results:
        if result.ok:
            combined_games.extend(result.games)
        else:
            source_platforms = SOURCE_PLATFORMS.get(result.source, frozenset())
            retained_prev = [
                g for g in active_previous_games if g.get("platform") in source_platforms
            ]
            logger.warning(
                f"Scraper '{result.source}' failed ({result.error}). "
                f"Retaining {len(retained_prev)} previously active entries for this source."
            )
            combined_games.extend(retained_prev)

    deduped_games = normalize_and_deduplicate(combined_games)
    final_games = filter_expired_games(deduped_games)

    expired_count = len(deduped_games) - len(final_games)
    logger.info(
        f"Total deduplicated games: {len(deduped_games)}. "
        f"Filtered out {expired_count} expired games. "
        f"Active free games: {len(final_games)}"
    )

    if not final_games:
        logger.error(
            "No free games fetched. Scrapers might be failing. "
            "Aborting write to prevent saving empty file."
        )
        sys.exit(1)

    all_succeeded = all(r.ok for r in results)
    if (
        all_succeeded
        and active_previous_games
        and len(final_games) < len(active_previous_games) * 0.5
    ):
        logger.error(
            f"Sudden drop in free games count (fetched {len(final_games)}, "
            f"previously active {len(active_previous_games)}). "
            "Scrapers might be broken. Aborting write."
        )
        sys.exit(1)

    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    output_data = {
        "generated_at": now_utc,
        "count": len(final_games),
        "games": final_games,
    }

    atomic_write_json(OUTPUT_FILE, output_data)
    logger.info(f"Successfully saved {len(final_games)} games to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

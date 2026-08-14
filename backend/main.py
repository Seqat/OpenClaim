#!/usr/bin/env python3
"""
OpenClaim - Automated Free Games Tracker Data Pipeline Entry Point
Executes GamerPower and Amazon Luna scrapers, normalizes and deduplicates results,
and outputs games.json to the project root directory.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scrapers.gamerpower import fetch_gamerpower_games
from backend.scrapers.luna import fetch_amazon_games
from backend.utils.date_helpers import parse_iso_date

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("backend_main")

OUTPUT_FILE = PROJECT_ROOT / "games.json"


def normalize_and_deduplicate(games_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize and deduplicate game entries based on platform and game title."""
    deduped: Dict[tuple, Dict[str, Any]] = {}
    
    for game in games_list:
        platform = game.get("platform", "")
        title = game.get("title", "").strip()
        if not title:
            continue
            
        norm_title = re.sub(r"[^\w\s]", "", title.casefold())
        norm_title = re.sub(r"\s+", " ", norm_title).strip()
        norm_key = (platform, norm_title)
        
        if norm_key in deduped:
            existing = deduped[norm_key]
            if game.get("is_permanent") and not existing.get("is_permanent"):
                deduped[norm_key] = game
        else:
            deduped[norm_key] = game
            
    result = list(deduped.values())
    result.sort(key=lambda g: (g.get("platform", ""), g.get("title", "")))
    return result


def filter_expired_games(
    games: List[Dict[str, Any]], now: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Filter out games whose end_date has expired beyond a 6-hour grace period.
    Retains games with missing/empty end_dates, future end_dates, or unparseable end_dates.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    retained: List[Dict[str, Any]] = []
    for game in games:
        raw_end_date = game.get("end_date")
        if raw_end_date is None or (isinstance(raw_end_date, str) and not raw_end_date.strip()):
            retained.append(game)
            continue

        parsed_iso = parse_iso_date(str(raw_end_date))
        if parsed_iso is None:
            logger.warning(
                f"Could not parse end_date '{raw_end_date}' for game '{game.get('title', 'Unknown')}'. Keeping game."
            )
            retained.append(game)
            continue

        try:
            end_dt = datetime.fromisoformat(parsed_iso.replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Failed to convert parsed ISO date '{parsed_iso}' to datetime for game '{game.get('title', 'Unknown')}': {e}. Keeping game."
            )
            retained.append(game)
            continue

        # Drop only if current time is past end_date + 6 hours grace period
        if now > end_dt + timedelta(hours=6):
            continue

        retained.append(game)

    return retained


def main():
    logger.info("Starting OpenClaim free games fetch pipeline...")
    
    gamerpower_games = fetch_gamerpower_games()
    amazon_games = asyncio.run(fetch_amazon_games())

    all_games = gamerpower_games + amazon_games
    deduped_games = normalize_and_deduplicate(all_games)
    final_games = filter_expired_games(deduped_games)
    
    expired_count = len(deduped_games) - len(final_games)
    logger.info(
        f"Total deduplicated games: {len(deduped_games)}. "
        f"Filtered out {expired_count} expired games. "
        f"Active free games: {len(final_games)}"
    )
    
    # 1. Read existing games.json to support both array and object formats
    previous_games: List[Dict[str, Any]] = []
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                if isinstance(prev_data, list):
                    previous_games = prev_data
                elif isinstance(prev_data, dict) and isinstance(prev_data.get("games"), list):
                    previous_games = prev_data["games"]
        except Exception as e:
            logger.warning(f"Could not read existing {OUTPUT_FILE}: {e}")

    # 2. Check if final_games is empty
    if not final_games:
        logger.error("No free games fetched. Scrapers might be failing. Aborting write to prevent saving empty file.")
        sys.exit(1)

    # 3. Check for sudden drop in game count (< 50% of previous active count)
    active_previous_games = filter_expired_games(previous_games)
    if active_previous_games and len(final_games) < len(active_previous_games) * 0.5:
        logger.error(
            f"Sudden drop in free games count (fetched {len(final_games)}, previously active {len(active_previous_games)}). "
            "Scrapers might be broken. Aborting write."
        )
        sys.exit(1)

    # 4. Save output schema object
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output_data = {
        "generated_at": now_utc,
        "count": len(final_games),
        "games": final_games
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Successfully saved {len(final_games)} games to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

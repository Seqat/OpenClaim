#!/usr/bin/env python3
"""
OpenClaim - Automated Free Games Tracker Data Pipeline Entry Point
Executes GamerPower and Amazon Luna scrapers, normalizes and deduplicates results,
and outputs games.json to the project root directory.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Any

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scrapers.gamerpower import fetch_gamerpower_games
from backend.scrapers.luna import fetch_amazon_games

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


def main():
    logger.info("Starting OpenClaim free games fetch pipeline...")
    
    gamerpower_games = fetch_gamerpower_games()
    amazon_games = asyncio.run(fetch_amazon_games())

    all_games = gamerpower_games + amazon_games
    final_games = normalize_and_deduplicate(all_games)
    
    logger.info(f"Total deduplicated free games: {len(final_games)}")
    
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

    # 3. Check for sudden drop in game count (< 50% of previous count)
    if previous_games and len(final_games) < len(previous_games) * 0.5:
        logger.error(
            f"Sudden drop in free games count (fetched {len(final_games)}, previously {len(previous_games)}). "
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

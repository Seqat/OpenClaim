#!/usr/bin/env python3
"""
LootRadar - Automated Free Games Tracker Data Pipeline Entry Point
Executes GamerPower and Amazon Luna scrapers, normalizes and deduplicates results,
and outputs games.json to the project root directory.
"""

import asyncio
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
    """Normalize and deduplicate game entries based on game title."""
    deduped: Dict[str, Dict[str, Any]] = {}
    
    for game in games_list:
        title = game.get("title", "").strip()
        if not title:
            continue
            
        norm_key = re.sub(r"[^\w\s]", "", title.lower()).strip()
        
        if norm_key in deduped:
            existing = deduped[norm_key]
            if game.get("is_permanent") and not existing.get("is_permanent"):
                deduped[norm_key] = game
        else:
            deduped[norm_key] = game
            
    result = list(deduped.values())
    result.sort(key=lambda g: (g["platform"], g["title"]))
    return result


def main():
    logger.info("Starting OpenClaim free games fetch pipeline...")
    
    gamerpower_games = fetch_gamerpower_games()
    amazon_games = asyncio.run(fetch_amazon_games())

    
    all_games = gamerpower_games + amazon_games
    final_games = normalize_and_deduplicate(all_games)
    
    logger.info(f"Total deduplicated free games: {len(final_games)}")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_games, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Successfully saved {len(final_games)} games to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GamerPower Scraper Module
Fetches Steam and Epic Games giveaways from GamerPower REST API.
"""

import logging
import re
from typing import Dict, List, Any
import requests

from backend.utils.date_helpers import parse_iso_date

logger = logging.getLogger("gamerpower_scraper")

GAMERPOWER_API_URL = "https://www.gamerpower.com/api/giveaways?platform=pc"


def clean_title(title: str) -> str:
    """Clean giveaway title by stripping store suffix strings like (Steam) Giveaway."""
    if not title:
        return ""
    
    cleaned = re.sub(r"\s*\((Steam|Epic Games|Epic|Ubisoft|GOG|itch\.io)\)\s*(Giveaway|Key Giveaway)?", "", title, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(Giveaway|Key Giveaway)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def fetch_gamerpower_games() -> List[Dict[str, Any]]:
    """Fetch free games from GamerPower API for Steam and Epic Games."""
    logger.info("Fetching giveaways from GamerPower REST API...")
    games = []
    
    headers = {
        "User-Agent": "OpenClaim/1.0 (+https://github.com/Seqat/OpenClaim)"
    }
    
    try:
        response = requests.get(GAMERPOWER_API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if not isinstance(data, list):
            logger.warning(f"GamerPower returned non-list data: {data}")
            return games

        for item in data:
            if item.get("status") != "Active":
                continue

            platforms_str = str(item.get("platforms", "")).lower()
            title_raw = str(item.get("title", ""))
            
            platform = None
            if "steam" in platforms_str or "steam" in title_raw.lower():
                platform = "Steam"
            elif "epic" in platforms_str or "epic" in title_raw.lower():
                platform = "Epic Games"
                
            if not platform:
                continue

            game_id = f"{platform.lower().replace(' ', '')}-{item.get('id')}"
            title = clean_title(title_raw)
            store_url = (
                item.get("open_giveaway_url")
                or item.get("gamerpower_url")
                or item.get("open_giveaway")
                or ""
            )
            image_url = item.get("image") or item.get("thumbnail") or ""
            end_date = parse_iso_date(item.get("end_date"))
            is_permanent = end_date is None

            games.append({
                "id": str(game_id),
                "title": title,
                "platform": platform,
                "store_url": store_url,
                "image_url": image_url,
                "end_date": end_date,
                "is_permanent": is_permanent
            })

        logger.info(f"Retrieved {len(games)} Steam & Epic Games from GamerPower.")
    except Exception as e:
        logger.error(f"Error fetching from GamerPower API: {e}")
        
    return games

"""GamerPower Scraper Module.

Fetches Steam and Epic Games giveaways from GamerPower REST API.
"""

import asyncio
import html
import logging
import re
from typing import Any

import requests
import requests.api
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.schemas import ScraperResult, validate_game_entry
from backend.utils.date_helpers import parse_iso_date

logger = logging.getLogger("gamerpower_scraper")

GAMERPOWER_API_URL = "https://www.gamerpower.com/api/giveaways?platform=pc"
GAMERPOWER_SOURCE = "gamerpower"

DLC_KEYWORDS_PATTERN = re.compile(
    r"\b("
    r"dlc|"
    r"content\s+pack|"
    r"gift\s+pack|"
    r"starter\s+kit|"
    r"in-game\s+items?|"
    r"pack|packs|"
    r"bundle|bundles|"
    r"skins?|"
    r"decals?|"
    r"emblems?|"
    r"kits?|"
    r"items?|"
    r"points|"
    r"currency|"
    r"loot|"
    r"helmets?|"
    r"dice"
    r")\b",
    re.IGNORECASE,
)

STRONG_DLC_KEYWORDS_PATTERN = re.compile(
    r"\b("
    r"dlc|"
    r"content\s+pack|"
    r"gift\s+pack|"
    r"starter\s+kit|"
    r"in-game\s+items?|"
    r"bundle|bundles|"
    r"skins?|"
    r"decals?|"
    r"emblems?|"
    r"currency|"
    r"helmets?"
    r")\b",
    re.IGNORECASE,
)

PLAYTEST_BETA_PATTERN = re.compile(r"\b(playtest|beta)\b", re.IGNORECASE)

NOTICE_PATTERNS = {
    "alienware_arena": re.compile(
        r"\balienware\s*arena\b|\balienware\s+account\b|(?-i:\bARP\b)",
        re.IGNORECASE,
    ),
    "amd_account": re.compile(r"\bAMD\s+account\b", re.IGNORECASE),
    "dungeonloot_account": re.compile(r"\bdungeon\s*loot\b", re.IGNORECASE),
    "newsletter_signup": re.compile(
        r"\bsubscribe\b[^.\n]{0,40}\bnewsletter\b|\bnewsletter\b[^.\n]{0,40}\bsign[\s-]?up\b",
        re.IGNORECASE,
    ),
    "redeem_in_game": re.compile(
        r"redeem\s+(?:this\s+)?(?:key|code)\s+(?:in-?game|inside\s+the\s+game)|\bnot\s+steam\s+keys?\b",
        re.IGNORECASE,
    ),
}

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

_PAREN_STORE_PATTERN = re.compile(
    r"\s*\((?:Steam|Epic Games Store|Epic Games|Epic|Ubisoft|GOG|itch\.io)\)\s*(?:Keys?\s*)?(?:Giveaway)?",
    re.IGNORECASE,
)
_TRAILING_STORE_KEY_PATTERN = re.compile(
    r"(?:\s+(?:Steam|Epic Games Store|Epic Games|Ubisoft|GOG|itch\.io)(?:\s+Keys?)?(?:\s+Giveaway)?|\s+(?:Keys?\s+Giveaway|Keys|Giveaway))$",
    re.IGNORECASE,
)


def classify_content_type(title: str, gamerpower_type: str | None = None) -> str:
    """Classify giveaway content type as 'game' or 'dlc'.

    - 'playtest' or 'beta' in title overrides everything -> 'game'
    - GamerPower API 'type' field is checked for DLC-like vs explicit 'Game'
    - Title heuristics using regex word boundaries
    - Default: 'game'
    """
    if not title:
        return "game"

    # 1. Playtest and Beta are games, overriding any DLC keywords
    if PLAYTEST_BETA_PATTERN.search(title):
        return "game"

    # 2. GamerPower API type check
    if gamerpower_type:
        gp_type_clean = str(gamerpower_type).strip().lower()
        if gp_type_clean in (
            "dlc",
            "in-game content",
            "loot",
            "item",
            "items",
        ) or re.search(r"\b(dlc|loot|item|pack|bundle)\b", gp_type_clean):
            return "dlc"
        if gp_type_clean == "game":
            if STRONG_DLC_KEYWORDS_PATTERN.search(title):
                return "dlc"
            return "game"

    # 3. Title heuristics
    if DLC_KEYWORDS_PATTERN.search(title):
        return "dlc"

    return "game"


def detect_notices(
    title: str | None,
    description: str | None,
    instructions: str | None,
) -> list[str]:
    """Detect extra requirements a giveaway likely has (accounts, newsletter, in-game redeem).

    - Only description and instructions are searched; 'title' is accepted but unused,
      since brand-flavoured item names (e.g. 'Alienware Decal') say nothing about requirements
    - HTML tags are stripped and entities unescaped so URLs in href attributes can't match
    - Returns a deduplicated, sorted list of notice codes ([] if none)
    """
    _ = title
    haystack = html.unescape(
        HTML_TAG_PATTERN.sub(" ", f"{description or ''}\n{instructions or ''}")
    )
    if not haystack.strip():
        return []

    return sorted(code for code, pattern in NOTICE_PATTERNS.items() if pattern.search(haystack))


def clean_title(title: str) -> str:
    """Clean giveaway title by stripping store, key, and giveaway suffix strings."""
    if not title:
        return ""

    cleaned = _PAREN_STORE_PATTERN.sub("", title)
    cleaned = _TRAILING_STORE_KEY_PATTERN.sub("", cleaned)
    return cleaned.strip()


def _build_session() -> requests.Session:
    """Create a requests Session configured with retry/backoff for transient HTTP errors."""
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _fetch_gamerpower_payload(headers: dict[str, str]) -> Any:
    """Perform the HTTP GET request, respecting patched requests.get in unit tests."""
    # tests/test_notices.py patches backend.scrapers.gamerpower.requests.get directly.
    if requests.get is not requests.api.get:
        response = requests.get(GAMERPOWER_API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()

    with _build_session() as session:
        response = session.get(GAMERPOWER_API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()


def _extract_platforms(platforms_str: str) -> list[str]:
    """Determine target platforms strictly from the API platforms field."""
    normalized = platforms_str.lower()
    platforms: list[str] = []
    if "steam" in normalized:
        platforms.append("Steam")
    if "epic" in normalized:
        platforms.append("Epic Games")
    return platforms


def fetch_gamerpower_result() -> ScraperResult:
    """Fetch free games from GamerPower API and return a structured ScraperResult."""
    logger.info("Fetching giveaways from GamerPower REST API...")
    games: list[dict[str, Any]] = []

    headers = {
        "User-Agent": "OpenClaim/1.0 (+https://github.com/Seqat/OpenClaim)",
    }

    try:
        data = _fetch_gamerpower_payload(headers)

        if not isinstance(data, list):
            msg = f"GamerPower returned non-list data: {type(data).__name__}"
            logger.warning(msg)
            return ScraperResult(source=GAMERPOWER_SOURCE, games=[], ok=False, error=msg)

        for item in data:
            if not isinstance(item, dict):
                continue
            if item.get("status") != "Active":
                continue

            item_id = item.get("id")
            if item_id is None or (isinstance(item_id, str) and not item_id.strip()):
                continue

            platforms_str = str(item.get("platforms") or "")
            matched_platforms = _extract_platforms(platforms_str)
            if not matched_platforms:
                continue

            title_raw = str(item.get("title") or "")
            title = clean_title(title_raw) or title_raw.strip()
            if not title:
                continue

            store_url = (
                item.get("open_giveaway_url")
                or item.get("gamerpower_url")
                or item.get("open_giveaway")
                or ""
            )
            image_url = item.get("image") or item.get("thumbnail") or ""
            end_date = parse_iso_date(item.get("end_date"))
            is_permanent = end_date is None
            content_type = classify_content_type(title_raw, item.get("type"))
            notices = detect_notices(title_raw, item.get("description"), item.get("instructions"))

            for platform in matched_platforms:
                game_id = f"{platform.lower().replace(' ', '')}-{item_id}"
                entry = validate_game_entry(
                    {
                        "id": str(game_id),
                        "title": title,
                        "platform": platform,
                        "store_url": str(store_url),
                        "image_url": str(image_url),
                        "end_date": end_date,
                        "is_permanent": is_permanent,
                        "content_type": content_type,
                        "notices": notices,
                    }
                )
                games.append(entry)

        logger.info(f"Retrieved {len(games)} Steam & Epic Games from GamerPower.")
        return ScraperResult(source=GAMERPOWER_SOURCE, games=games, ok=True, error=None)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error fetching from GamerPower API: {e}")
        return ScraperResult(source=GAMERPOWER_SOURCE, games=[], ok=False, error=str(e))


def fetch_gamerpower_games() -> list[dict[str, Any]]:
    """Fetch free games from GamerPower API for Steam and Epic Games."""
    return fetch_gamerpower_result().games


class GamerPowerScraper:
    """BaseScraper implementation for GamerPower."""

    source: str = GAMERPOWER_SOURCE

    async def fetch(self) -> ScraperResult:
        """Fetch GamerPower giveaways asynchronously via a worker thread."""
        return await asyncio.to_thread(fetch_gamerpower_result)

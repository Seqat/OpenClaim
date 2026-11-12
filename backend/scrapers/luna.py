"""Amazon Luna / Prime Scraper Module.

Scrapes claimable free games from Amazon Luna / Prime Gaming using Playwright headless Chromium.
"""

import asyncio
import logging
import re
import time
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import async_playwright

from backend.schemas import ScraperResult, validate_game_entry
from backend.utils.date_helpers import parse_detail_page_end_date

logger = logging.getLogger("luna_scraper")

AMAZON_GAMING_URL = "https://luna.amazon.com/claims/home"
LUNA_SOURCE = "amazon_luna"
LUNA_PLATFORM = "Amazon Luna / Prime"
CARD_LINK_SELECTOR = 'a[href*="/claims/"], a[href*="/dp/"]'
BLOCKED_RESOURCE_TYPES = frozenset({"image", "media", "font", "stylesheet"})

_IGNORED_TITLES = frozenset(
    {
        "claim games",
        "play now",
        "all",
        "claim",
        "talep et",
        "top games to claim",
        "game",
    }
)
_PLAY_NOW_PATTERN = re.compile(r"play now|şimdi oyna", re.IGNORECASE)
_CLAIM_ACTION_PATTERN = re.compile(
    r"claim|talep|oyunu talep et|get game|oyunu al",
    re.IGNORECASE,
)

_EXTRACT_CARDS_JS = """() => {
    const links = document.querySelectorAll('a[href*="/claims/"], a[href*="/dp/"]');
    const items = [];
    for (const link of links) {
        const card = link.closest('div[class*="Card"], div[class*="card"], article, section') || link.parentElement;
        if (!card) continue;

        const cardText = card.innerText || '';
        let title = '';
        const primaryTitleEl = card.querySelector('h1, h2, h3, h4, [class*="title"], [class*="Title"]');
        if (primaryTitleEl && primaryTitleEl.innerText.trim().length > 1) {
            title = primaryTitleEl.innerText.trim();
        } else {
            const pEl = card.querySelector('p');
            if (pEl && pEl.innerText.trim().length > 1) {
                title = pEl.innerText.trim();
            }
        }
        if (!title) {
            title = link.getAttribute('aria-label') || link.getAttribute('title') || '';
        }

        let imgUrl = '';
        const imgs = card.querySelectorAll('img');
        for (const img of imgs) {
            const srcset = img.getAttribute('srcset');
            const dataSrc = img.getAttribute('data-src');
            const src = img.getAttribute('src');
            let candidate = '';
            if (srcset) {
                candidate = srcset.split(',')[0].trim().split(' ')[0];
            } else if (dataSrc) {
                candidate = dataSrc;
            } else if (src) {
                candidate = src;
            }
            if (candidate && !candidate.startsWith('data:image/svg')) {
                imgUrl = candidate;
                break;
            }
        }

        if (!imgUrl) {
            const els = card.querySelectorAll('div, span, a');
            for (const el of els) {
                const bg = window.getComputedStyle(el).backgroundImage;
                if (bg && bg !== 'none' && bg.includes('url(')) {
                    const match = bg.match(/url\\(["']?(.*?)["']?\\)/);
                    if (match && match[1] && !match[1].startsWith('data:image/svg')) {
                        imgUrl = match[1];
                        break;
                    }
                }
            }
        }

        items.push({
            href: link.getAttribute('href') || '',
            card_text: cardText,
            title: title,
            img_url: imgUrl,
        });
    }
    return items;
}"""


def clean_amazon_title(title: str) -> str:
    """Clean title extracted from Amazon Gaming offer cards."""
    if not title:
        return ""

    cleaned = re.sub(r"^(Go to|Get game|Claim|Play)\s+", "", title, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(detail page|-\s*Prime Gaming|on Luna)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def build_amazon_id(store_url: str, fallback_title: str) -> str:
    """Build a stable ID from the amzn1.pg.item.<uuid> segment in store_url."""
    m = re.search(r"(amzn1\.pg\.item\.[0-9a-f-]+)", store_url or "", re.IGNORECASE)
    if m:
        return f"amazon-{m.group(1)}"
    slug = re.sub(r"[^a-z0-9]+", "-", (fallback_title or "").casefold()).strip("-")
    return f"amazon-{slug}" if slug else "amazon-unknown"


async def _handle_asset_route(route: Any) -> None:
    """Abort non-essential assets (images, media, fonts, stylesheets) by resource type."""
    if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
        await route.abort()
    else:
        await route.continue_()


def _parse_extracted_cards(raw_cards: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Filter, deduplicate, and normalize raw card dictionaries extracted from the DOM."""
    raw_items: list[dict[str, str]] = []
    seen_titles: set[str] = set()

    for card in raw_cards:
        if not isinstance(card, dict):
            continue
        card_text = str(card.get("card_text") or "")
        if _PLAY_NOW_PATTERN.search(card_text):
            continue
        if not _CLAIM_ACTION_PATTERN.search(card_text):
            continue

        raw_title = str(card.get("title") or "").split("\n")[0].strip()
        title_text = clean_amazon_title(raw_title)
        if not title_text or title_text.lower() in _IGNORED_TITLES:
            continue

        norm_title = title_text.casefold()
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)

        href = str(card.get("href") or "").strip()
        store_url = urljoin(AMAZON_GAMING_URL, href) if href else ""

        img_raw = str(card.get("img_url") or "").strip()
        image_url = urljoin(AMAZON_GAMING_URL, img_raw) if img_raw else ""

        raw_items.append(
            {
                "title": title_text,
                "store_url": store_url,
                "image_url": image_url,
            }
        )

    return raw_items


async def _scroll_until_stable(
    page: Any,
    selector: str = CARD_LINK_SELECTOR,
    max_scrolls: int = 12,
) -> None:
    """Scroll to page bottom until the matching card count stabilizes."""
    prev_count = -1
    stable_rounds = 0
    for _ in range(max_scrolls):
        current_count = await page.locator(selector).count()
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(350)
        new_count = await page.locator(selector).count()
        if new_count == current_count and new_count == prev_count:
            stable_rounds += 1
            if stable_rounds >= 2:
                break
        else:
            stable_rounds = 0
        prev_count = new_count


async def fetch_detail_page_end_date(
    context: Any,
    item: dict[str, Any],
    idx: int,
    total: int,
    semaphore: asyncio.Semaphore,
) -> str | None:
    """Fetch detail page date with asset blocking, SPA hydration polling, and 8000ms timeout."""
    store_url = item.get("store_url")
    if not store_url or not str(store_url).startswith("http"):
        return None

    async with semaphore:
        page = await context.new_page()
        end_date = None
        try:
            await page.route("**/*", _handle_asset_route)
            logger.info(f"[{idx + 1}/{total}] Checking detail page: {item['title']}...")

            await page.goto(store_url, wait_until="domcontentloaded", timeout=8000)

            start_poll = time.time()
            while time.time() - start_poll < 3.5:
                detail_text = await page.inner_text("body", timeout=2000)
                end_date = parse_detail_page_end_date(detail_text)
                if end_date:
                    break
                await page.wait_for_timeout(250)

            if end_date:
                logger.info(f"  -> {item['title']} end_date: {end_date}")
            else:
                logger.info(f"  -> {item['title']} end_date: null (No expiration date text found)")
        except Exception as err:  # noqa: BLE001
            logger.warning(
                f"Timeout/Error fetching detail page for {item['title']} (falling back): {err}"
            )
        finally:
            await page.close()

        return end_date


async def fetch_amazon_result() -> ScraperResult:
    """Scrape Amazon Prime Gaming / Luna claimable free games and return a ScraperResult."""
    logger.info("Scraping Amazon Luna / Prime Gaming via Playwright...")
    games: list[dict[str, Any]] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 900},
                    locale="en-US",
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                main_page = await context.new_page()

                logger.info(f"Navigating directly to {AMAZON_GAMING_URL}...")
                await main_page.goto(AMAZON_GAMING_URL, wait_until="domcontentloaded", timeout=30000)
                await main_page.wait_for_timeout(3000)

                try:
                    tab_btn = await main_page.query_selector(
                        'button:has-text("Claim Games"), '
                        'button:has-text("Oyunları Talep Edin"), '
                        '[role="tab"]:has-text("Claim"), '
                        '[role="tab"]:has-text("Talep")'
                    )
                    if tab_btn:
                        await tab_btn.click()
                        await main_page.wait_for_timeout(1500)
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"Tab button interaction note: {e}")

                await _scroll_until_stable(main_page)
                raw_cards = await main_page.evaluate(_EXTRACT_CARDS_JS)
                if not isinstance(raw_cards, list):
                    raw_cards = []
                logger.info(f"Found {len(raw_cards)} card links on Luna claims home page.")

                raw_items = _parse_extracted_cards(raw_cards)

                logger.info(
                    f"Fetching exact expiration dates for {len(raw_items)} "
                    "Amazon games concurrently (5 tabs)..."
                )
                semaphore = asyncio.Semaphore(5)
                tasks = [
                    fetch_detail_page_end_date(context, item, idx, len(raw_items), semaphore)
                    for idx, item in enumerate(raw_items)
                ]
                end_date_results = await asyncio.gather(*tasks, return_exceptions=True)

                for item, result in zip(raw_items, end_date_results):
                    if isinstance(result, BaseException):
                        logger.warning(
                            f"Detail page task failed for {item['title']}: {result}"
                        )
                        end_date: str | None = None
                    else:
                        end_date = result

                    entry = validate_game_entry(
                        {
                            "id": build_amazon_id(item["store_url"], item["title"]),
                            "title": item["title"],
                            "platform": LUNA_PLATFORM,
                            "store_url": item["store_url"],
                            "image_url": item["image_url"],
                            "end_date": end_date,
                            "is_permanent": False,
                            "content_type": "game",
                            "notices": [],
                        }
                    )
                    games.append(entry)
            finally:
                await browser.close()

        logger.info(f"Retrieved {len(games)} claimable games from Amazon Luna / Prime Gaming.")
        return ScraperResult(source=LUNA_SOURCE, games=games, ok=True, error=None)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error scraping Amazon Gaming with Playwright: {e}")
        return ScraperResult(source=LUNA_SOURCE, games=[], ok=False, error=str(e))


async def fetch_amazon_games() -> list[dict[str, Any]]:
    """Scrape Amazon Prime Gaming / Luna claimable free games using Playwright headless Chromium."""
    return (await fetch_amazon_result()).games


class LunaScraper:
    """BaseScraper implementation for Amazon Luna / Prime Gaming."""

    source: str = LUNA_SOURCE

    async def fetch(self) -> ScraperResult:
        """Fetch Amazon Luna giveaways asynchronously."""
        return await fetch_amazon_result()

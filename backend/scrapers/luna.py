"""Amazon Luna / Prime Scraper Module.

Scrapes claimable free games from Amazon Luna / Prime Gaming using Playwright headless Chromium.
"""

import asyncio
import hashlib
import logging
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright

from backend.schemas import ScraperResult, validate_game_entry
from backend.utils.date_helpers import parse_detail_page_end_date

logger = logging.getLogger("luna_scraper")

AMAZON_GAMING_URL = "https://luna.amazon.com/claims/home"
LUNA_SOURCE = "amazon_luna"
LUNA_PLATFORM = "Amazon Luna / Prime"
CARD_LINK_SELECTOR = 'a[href*="/claims/"], a[href*="/dp/"]'
BLOCKED_RESOURCE_TYPES = frozenset({"image", "media", "font"})

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

_SCROLL_STEP_JS = r"""async (selector) => {
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const getScrollHeight = () => Math.max(
        document.body ? document.body.scrollHeight : 0,
        document.documentElement ? document.documentElement.scrollHeight : 0
    );
    const step = Math.max(Math.floor(window.innerHeight * 0.75), 400);
    for (let y = 0, i = 0; y <= getScrollHeight() && i < 40; y += step, i++) {
        window.scrollTo(0, y);
        await sleep(50);
    }
    window.scrollTo(0, getScrollHeight());
    const links = document.querySelectorAll(selector);
    for (const el of links) {
        el.scrollIntoView({block: "center", inline: "center"});
        await sleep(20);
    }
    window.scrollTo(0, getScrollHeight());
}"""

_DETAIL_FALLBACK_IMAGE_JS = r"""() => {
    const isValidImgUrl = (url) => {
        if (!url) return false;
        const trimmed = url.trim();
        if (!trimmed) return false;
        const lower = trimmed.toLowerCase();
        return !lower.startsWith('data:image/') && !lower.startsWith('blob:');
    };

    const og = document.querySelector('meta[property="og:image"]');
    const ogContent = og ? og.getAttribute('content') : '';
    if (isValidImgUrl(ogContent)) return ogContent.trim();

    const tw = document.querySelector('meta[name="twitter:image"]');
    const twContent = tw ? tw.getAttribute('content') : '';
    if (isValidImgUrl(twContent)) return twContent.trim();

    const imgs = document.querySelectorAll('img[src*="media-amazon.com"]');
    for (const img of imgs) {
        const src = img.currentSrc || img.getAttribute('src') || '';
        if (isValidImgUrl(src)) return src.trim();
    }
    return '';
}"""

_EXTRACT_CARDS_JS = r"""() => {
    const isValidImgUrl = (url) => {
        if (!url) return false;
        const trimmed = url.trim();
        if (!trimmed) return false;
        const lower = trimmed.toLowerCase();
        return !lower.startsWith('data:image/') && !lower.startsWith('blob:');
    };

    const pickFromSrcset = (srcset) => {
        if (!srcset) return '';
        const parts = srcset.split(/,(?:\s+|(?=(?:https?:|\/\/|\/)))/i);
        for (const part of parts) {
            const candidate = part.trim().split(/\s+/)[0];
            if (isValidImgUrl(candidate)) return candidate;
        }
        return '';
    };

    const countDistinctDpItems = (root) => {
        const dpLinks = root.querySelectorAll('a[href*="/dp/"]');
        const distinct = new Set();
        for (const dpLink of dpLinks) {
            const dpHref = dpLink.getAttribute('href') || '';
            const match = dpHref.match(/amzn1\.pg\.item\.[0-9a-f-]+/i);
            distinct.add(match ? match[0].toLowerCase() : dpHref.split('?')[0]);
        }
        return distinct.size;
    };

    const extractBgImage = (root) => {
        const els = [root, ...root.querySelectorAll('div, span, a')];
        for (const el of els) {
            const bg = window.getComputedStyle(el).backgroundImage;
            if (bg && bg !== 'none' && bg.includes('url(')) {
                const match = bg.match(/url\(["']?(.*?)["']?\)/);
                if (match && match[1] && isValidImgUrl(match[1])) {
                    return match[1].trim();
                }
            }
        }
        return '';
    };

    const links = document.querySelectorAll('a[href*="/claims/"], a[href*="/dp/"]');
    const items = [];
    for (const link of links) {
        let card = link.closest(
            'div[class*="Card"], div[class*="card"], [data-a-target*="card"], [data-a-target*="offer"], article, section, li'
        ) || link.parentElement;
        if (!card) continue;

        const safeAncestors = [];
        if (!card.querySelector('img')) {
            let probe = card;
            for (let depth = 0; depth < 4; depth++) {
                const parent = probe.parentElement;
                if (!parent || parent.tagName === 'BODY' || parent.tagName === 'HTML') {
                    break;
                }
                if (countDistinctDpItems(parent) > 1) {
                    break;
                }
                safeAncestors.push(parent);
                probe = parent;
                if (probe.querySelector('img, picture source[srcset]')) {
                    card = probe;
                    break;
                }
            }
        }

        const cardText = card.innerText || '';
        let title = '';
        const headingEl = card.querySelector('h1, h2, h3, h4');
        if (headingEl && headingEl.innerText.trim().length > 1) {
            title = headingEl.innerText.trim();
        } else {
            const titleClassEl = card.querySelector(
                '[class*="title"]:not([class*="subtitle"]):not([class*="entitlement"]), ' +
                '[class*="Title"]:not([class*="Subtitle"]):not([class*="Entitlement"])'
            );
            if (titleClassEl && titleClassEl.innerText.trim().length > 1) {
                title = titleClassEl.innerText.trim();
            } else {
                const pEl = card.querySelector('p');
                if (pEl && pEl.innerText.trim().length > 1) {
                    title = pEl.innerText.trim();
                }
            }
        }
        if (!title) {
            title = link.getAttribute('aria-label') || link.getAttribute('title') || '';
        }

        let imgUrl = '';
        const sources = card.querySelectorAll('picture source[srcset]');
        for (const source of sources) {
            const candidate = pickFromSrcset(source.getAttribute('srcset'));
            if (candidate) {
                imgUrl = candidate;
                break;
            }
        }

        if (!imgUrl) {
            const imgs = card.querySelectorAll('img');
            for (const img of imgs) {
                const candidates = [
                    img.currentSrc,
                    pickFromSrcset(img.getAttribute('srcset')),
                    img.getAttribute('data-src'),
                    img.getAttribute('src'),
                ];
                for (const candidate of candidates) {
                    if (isValidImgUrl(candidate)) {
                        imgUrl = candidate.trim();
                        break;
                    }
                }
                if (imgUrl) break;
            }
        }

        if (!imgUrl) {
            imgUrl = extractBgImage(card);
        }

        if (!imgUrl && safeAncestors.length > 0) {
            for (const ancestor of safeAncestors) {
                imgUrl = extractBgImage(ancestor);
                if (imgUrl) break;
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


_AMAZON_LAUNCHER_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("-microsoft-store", "redeem_microsoft_store"),
    ("-ms-store", "redeem_microsoft_store"),
    ("-msstore", "redeem_microsoft_store"),
    ("-xbox", "redeem_microsoft_store"),
    ("-ea-app", "redeem_ea_app"),
    ("-origin", "redeem_ea_app"),
    ("-ea", "redeem_ea_app"),
    ("-ubisoft", "redeem_ubisoft"),
    ("-uplay", "redeem_ubisoft"),
    ("-legacy", "redeem_legacy_games"),
    ("-epic", "redeem_epic"),
    ("-gog", "redeem_gog"),
    ("-aga", "redeem_amazon_app"),
)


def detect_amazon_notices(store_url: str) -> list[str]:
    """Detect redemption store/launcher notice code from Amazon Luna claim URL slug."""
    if not store_url:
        return []
    path = urlparse(store_url).path
    match = re.search(r"/claims/([^/]+)", path, re.IGNORECASE)
    if not match:
        return []
    offer_slug = match.group(1).lower()
    for suffix, code in _AMAZON_LAUNCHER_SUFFIXES:
        if offer_slug.endswith(suffix):
            return [code]
    return []


def build_amazon_id(store_url: str, fallback_title: str) -> str:
    """Build a stable ID from the amzn1.pg.item.<uuid> segment in store_url."""
    m = re.search(r"(amzn1\.pg\.item\.[0-9a-f-]+)", store_url or "", re.IGNORECASE)
    if m:
        return f"amazon-{m.group(1)}"
    slug = re.sub(r"[^a-z0-9]+", "-", (fallback_title or "").casefold()).strip("-")
    if slug:
        return f"amazon-{slug}"
    if store_url or fallback_title:
        digest = hashlib.sha256(f"{store_url or ''}|{fallback_title or ''}".encode()).hexdigest()
        return f"amazon-{digest[:12]}"
    return "amazon-unknown"


async def _handle_asset_route(route: Any) -> None:
    """Fulfill stylesheets with empty CSS, abort heavy assets, and allow scripts/data."""
    url = str(getattr(route.request, "url", ""))
    path = urlparse(url).path.lower()
    if route.request.resource_type == "stylesheet" or path.endswith(".css"):
        await route.fulfill(status=200, body="", content_type="text/css")
    elif route.request.resource_type in BLOCKED_RESOURCE_TYPES:
        await route.abort()
    else:
        await route.continue_()


def _is_valid_image_url(url: str) -> bool:
    """Return True if a raw image URL is non-empty and not an inline data/blob URI."""
    lowered = url.strip().lower()
    return bool(lowered) and not lowered.startswith(("data:image/", "blob:"))


def _parse_extracted_cards(raw_cards: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Filter, merge duplicates by normalized title, and normalize extracted card dicts."""
    items_by_title: dict[str, dict[str, str]] = {}

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

        href = str(card.get("href") or "").strip()
        store_url = urljoin(AMAZON_GAMING_URL, href) if href else ""

        img_raw = str(card.get("img_url") or "").strip()
        image_url = urljoin(AMAZON_GAMING_URL, img_raw) if _is_valid_image_url(img_raw) else ""

        card_end_date = parse_detail_page_end_date(card_text) or ""

        norm_title = title_text.casefold()
        existing = items_by_title.get(norm_title)
        if existing is not None:
            if image_url and not existing["image_url"]:
                existing["image_url"] = image_url
            if (
                "amzn1.pg.item." not in existing["store_url"].casefold()
                and "amzn1.pg.item." in store_url.casefold()
            ):
                existing["store_url"] = store_url
            if card_end_date and not existing["card_end_date"]:
                existing["card_end_date"] = card_end_date
            continue

        items_by_title[norm_title] = {
            "title": title_text,
            "store_url": store_url,
            "image_url": image_url,
            "card_end_date": card_end_date,
        }

    return list(items_by_title.values())


async def _scroll_until_stable(
    page: Any,
    selector: str = CARD_LINK_SELECTOR,
    max_scrolls: int = 12,
) -> None:
    """Scroll incrementally and trigger IntersectionObserver until card count stabilizes."""
    prev_count = -1
    stable_rounds = 0
    for _ in range(max_scrolls):
        current_count = await page.locator(selector).count()
        await page.evaluate(_SCROLL_STEP_JS, selector)
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
    """Fetch detail page end date and fallback cover image with SPA hydration polling."""
    card_fallback_date = item.get("card_end_date") or None
    store_url = item.get("store_url")
    if not store_url or not str(store_url).startswith("http"):
        return card_fallback_date

    async with semaphore:
        page = await context.new_page()
        end_date: str | None = None
        try:
            await page.route("**/*", _handle_asset_route)
            logger.info(f"[{idx + 1}/{total}] Checking detail page: {item['title']}...")

            await page.goto(store_url, wait_until="domcontentloaded", timeout=12000)

            start_poll = time.monotonic()
            while time.monotonic() - start_poll < 5.0:
                try:
                    detail_text = await page.inner_text("body", timeout=2000)
                except Exception as text_err:  # noqa: BLE001
                    logger.debug(
                        f"Detail page inner_text note for {item['title']}: {text_err}"
                    )
                    detail_text = ""
                end_date = parse_detail_page_end_date(detail_text)
                if end_date:
                    break
                await page.wait_for_timeout(250)

            if not item.get("image_url"):
                try:
                    fallback_img = await page.evaluate(_DETAIL_FALLBACK_IMAGE_JS)
                    if isinstance(fallback_img, str) and _is_valid_image_url(fallback_img):
                        item["image_url"] = urljoin(AMAZON_GAMING_URL, fallback_img.strip())
                except Exception as img_err:  # noqa: BLE001
                    logger.debug(
                        f"Detail page fallback image extraction note for {item['title']}: {img_err}"
                    )

            if end_date:
                logger.info(f"  -> {item['title']} end_date: {end_date}")
            elif card_fallback_date:
                logger.info(
                    f"  -> {item['title']} end_date: {card_fallback_date} (from card text fallback)"
                )
            else:
                logger.info(f"  -> {item['title']} end_date: null (No expiration date text found)")
        except Exception as err:  # noqa: BLE001
            logger.warning(
                f"Timeout/Error fetching detail page for {item['title']} (falling back): {err}"
            )
        finally:
            await page.close()

        return end_date or card_fallback_date


async def fetch_amazon_result() -> ScraperResult:
    """Scrape Amazon Prime Gaming / Luna claimable free games and return a ScraperResult."""
    logger.info("Scraping Amazon Luna / Prime Gaming via Playwright...")
    games: list[dict[str, Any]] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                raw_version = getattr(browser, "version", "")
                major_match = (
                    re.search(r"(\d+)", raw_version) if isinstance(raw_version, str) else None
                )
                chrome_major = major_match.group(1) if major_match else "134"
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        f"(KHTML, like Gecko) Chrome/{chrome_major}.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 900},
                    locale="en-US",
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
                await main_page.close()

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
                        end_date: str | None = item.get("card_end_date") or None
                    else:
                        end_date = result or item.get("card_end_date") or None

                    store_url = str(item.get("store_url") or "").strip()
                    if not store_url.startswith(("http://", "https://")):
                        logger.warning(
                            f"Skipping Amazon Luna item '{item.get('title')}' due to invalid store_url: {store_url!r}"
                        )
                        continue

                    try:
                        entry = validate_game_entry(
                            {
                                "id": build_amazon_id(store_url, item["title"]),
                                "title": item["title"],
                                "platform": LUNA_PLATFORM,
                                "store_url": store_url,
                                "image_url": item["image_url"],
                                "end_date": end_date,
                                "is_permanent": False,
                                "content_type": "game",
                                "notices": detect_amazon_notices(store_url),
                            }
                        )
                    except (ValueError, TypeError) as exc:
                        logger.warning(
                            f"Skipping invalid Amazon Luna entry '{item.get('title')}': {exc}"
                        )
                        continue
                    games.append(entry)
            finally:
                await browser.close()

        if not games:
            logger.warning("No claimable games found on Amazon Luna.")
            return ScraperResult(
                source=LUNA_SOURCE,
                games=[],
                ok=False,
                error="No claimable games found on Amazon Luna",
            )

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
    platforms: frozenset[str] = frozenset({LUNA_PLATFORM})

    async def fetch(self) -> ScraperResult:
        """Fetch Amazon Luna giveaways asynchronously."""
        return await fetch_amazon_result()

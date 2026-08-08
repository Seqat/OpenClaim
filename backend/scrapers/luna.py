#!/usr/bin/env python3
"""
Amazon Luna / Prime Scraper Module
Scrapes claimable free games from Amazon Luna / Prime Gaming using Playwright headless Chromium.
"""

import asyncio
import logging
import re
import time
from typing import Dict, List, Any, Optional
from playwright.async_api import async_playwright

from backend.utils.date_helpers import parse_detail_page_end_date

logger = logging.getLogger("luna_scraper")

AMAZON_GAMING_URL = "https://luna.amazon.com/claims/home"


def clean_amazon_title(title: str) -> str:
    """Clean title extracted from Amazon Gaming offer cards."""
    if not title:
        return ""
    
    cleaned = re.sub(r"^(Go to|Get game|Claim|Play)\s+", "", title, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(detail page|-\s*Prime Gaming|on Luna)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


async def fetch_detail_page_end_date(
    context: Any,
    item: Dict[str, Any],
    idx: int,
    total: int,
    semaphore: asyncio.Semaphore
) -> Optional[str]:
    """Fetch detail page date with asset blocking, domcontentloaded wait, dynamic SPA hydration polling, and 8000ms timeout."""
    store_url = item.get("store_url")
    if not store_url or not store_url.startswith("http"):
        return None
        
    async with semaphore:
        page = await context.new_page()
        end_date = None
        try:
            # 1. Asset Blocking: Abort images, fonts, media to speed up load; fulfill CSS with empty string to avoid module load errors
            await page.route(
                "**/*.{png,jpg,jpeg,webp,svg,css,woff,woff2,gif}",
                lambda route: route.fulfill(status=200, body="", content_type="text/css")
                if ".css" in route.request.url.lower()
                else route.abort()
            )
            
            logger.info(f"[{idx+1}/{total}] Checking detail page: {item['title']}...")
            
            # 3. Page Load Strategy & 4. Timeout Tuning (8000ms)
            await page.goto(store_url, wait_until="domcontentloaded", timeout=8000)
            
            # Dynamic SPA Hydration Polling: Poll every 250ms (up to 3.5s) until JS renders date text
            start_poll = time.time()
            while time.time() - start_poll < 3.5:
                detail_text = await page.inner_text("body")
                end_date = parse_detail_page_end_date(detail_text)
                if end_date:
                    break
                await page.wait_for_timeout(250)
                
            if end_date:
                logger.info(f"  -> {item['title']} end_date: {end_date}")
            else:
                logger.info(f"  -> {item['title']} end_date: null (No expiration date text found)")
        except Exception as err:
            logger.warning(f"Timeout/Error fetching detail page for {item['title']} (falling back): {err}")
        finally:
            await page.close()
            
        return end_date




async def fetch_amazon_games() -> List[Dict[str, Any]]:
    """Scrape Amazon Prime Gaming / Luna claimable free games using Playwright headless Chromium async."""
    logger.info("Scraping Amazon Luna / Prime Gaming via Playwright...")
    games = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900}
            )
            main_page = await context.new_page()
            
            # Target URL and Direct Navigation
            logger.info(f"Navigating directly to {AMAZON_GAMING_URL}...")
            await main_page.goto(AMAZON_GAMING_URL, wait_until="domcontentloaded", timeout=30000)
            await main_page.wait_for_timeout(3000)
            
            # Ensure "Claim Games" / "Oyunları Talep Edin" tab is active
            try:
                tab_btn = await main_page.query_selector(
                    'button:has-text("Claim Games"), button:has-text("Oyunları Talep Edin"), [role="tab"]:has-text("Claim"), [role="tab"]:has-text("Talep")'
                )
                if tab_btn:
                    await tab_btn.click()
                    await main_page.wait_for_timeout(1500)
            except Exception as e:
                logger.debug(f"Tab button interaction note: {e}")
            
            card_locators = main_page.locator('a[href*="/claims/"], a[href*="/dp/"]')
            count = await card_locators.count()
            logger.info(f"Found {count} card links on Luna claims home page.")
            
            raw_items = []
            seen_titles = set()
            
            for i in range(count):
                link_loc = card_locators.nth(i)
                card_handle = await link_loc.evaluate_handle("""a => {
                    return a.closest('div[class*="Card"], div[class*="card"], article, section') || a.parentElement;
                }""")
                
                if not card_handle:
                    continue
                    
                card_text = await card_handle.evaluate("el => el.innerText || ''")
                
                # Exclude "Play Now" / "Şimdi Oyna"
                if re.search(r"play now|şimdi oyna", card_text, re.IGNORECASE):
                    continue
                    
                # Require claim action text
                if not re.search(r"claim|talep|oyunu talep et|get game|oyunu al", card_text, re.IGNORECASE):
                    continue
                    
                # Image Lazy-Load: scroll card into view & wait 200ms
                try:
                    await link_loc.scroll_into_view_if_needed()
                    await main_page.wait_for_timeout(200)
                except Exception:
                    pass
                    
                # Extract Title
                title_text = await card_handle.evaluate("""card => {
                    let title = '';
                    const titleEl = card.querySelector('h1, h2, h3, h4, [class*="title"], [class*="Title"], p');
                    if (titleEl && titleEl.innerText.trim().length > 1) {
                        title = titleEl.innerText.trim();
                    }
                    return title;
                }""")
                
                if not title_text:
                    aria_label = await link_loc.get_attribute("aria-label")
                    title_attr = await link_loc.get_attribute("title")
                    title_text = aria_label or title_attr or ""
                    
                title_text = clean_amazon_title(title_text.split('\n')[0].strip())
                if not title_text or title_text.lower() in ['claim games', 'play now', 'all', 'claim', 'talep et', 'top games to claim', 'game']:
                    continue
                    
                norm_title = title_text.lower()
                if norm_title in seen_titles:
                    continue
                seen_titles.add(norm_title)
                
                # Store URL
                href = (await link_loc.get_attribute("href")) or ""
                store_url = href if href.startswith("http") else f"https://luna.amazon.com{href}"
                
                # Image Extraction
                img_url = await card_handle.evaluate("""card => {
                    let found = '';
                    const imgs = card.querySelectorAll('img');
                    for (const img of imgs) {
                        const srcset = img.getAttribute('srcset');
                        const dataSrc = img.getAttribute('data-src');
                        const src = img.getAttribute('src');
                        
                        let candidate = '';
                        if (srcset) {
                            const first = srcset.split(',')[0].trim().split(' ')[0];
                            candidate = first;
                        } else if (dataSrc) {
                            candidate = dataSrc;
                        } else if (src) {
                            candidate = src;
                        }
                        
                        if (candidate && !candidate.startsWith('data:image/svg')) {
                            found = candidate;
                            break;
                        }
                    }
                    
                    if (!found) {
                        const divs = card.querySelectorAll('div, span, a');
                        for (const div of divs) {
                            const style = window.getComputedStyle(div);
                            const bg = style.backgroundImage;
                            if (bg && bg !== 'none' && bg.includes('url(')) {
                                const match = bg.match(/url\\(["']?(.*?)["']?\\)/);
                                if (match && match[1] && !match[1].startsWith('data:image/svg')) {
                                    found = match[1];
                                    break;
                                }
                            }
                        }
                    }
                    
                    return found;
                }""")
                
                if img_url and not img_url.startswith("http"):
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    elif img_url.startswith("/"):
                        img_url = "https://luna.amazon.com" + img_url
                        
                raw_items.append({
                    "title": title_text,
                    "store_url": store_url,
                    "image_url": img_url
                })

            # Fetch exact end_date for each game concurrently using 5 tabs
            logger.info(f"Fetching exact expiration dates for {len(raw_items)} Amazon games concurrently (5 tabs)...")
            semaphore = asyncio.Semaphore(5)
            tasks = [
                fetch_detail_page_end_date(context, item, idx, len(raw_items), semaphore)
                for idx, item in enumerate(raw_items)
            ]
            end_dates = await asyncio.gather(*tasks)

            for idx, (item, end_date) in enumerate(zip(raw_items, end_dates)):
                games.append({
                    "id": f"amazon-game-{idx + 1}",
                    "title": item["title"],
                    "platform": "Amazon Luna / Prime",
                    "store_url": item["store_url"],
                    "image_url": item["image_url"],
                    "end_date": end_date,
                    "is_permanent": False
                })

            await browser.close()

        logger.info(f"Retrieved {len(games)} claimable games from Amazon Luna / Prime Gaming.")
    except Exception as e:
        logger.error(f"Error scraping Amazon Gaming with Playwright: {e}")
        
    return games


"""Unit tests for Amazon Luna scraper module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.schemas import BaseScraper
from backend.scrapers.luna import (
    LunaScraper,
    _handle_asset_route,
    _parse_extracted_cards,
    build_amazon_id,
    clean_amazon_title,
    fetch_amazon_games,
    fetch_amazon_result,
)


def test_clean_amazon_title_and_build_id():
    assert clean_amazon_title("Claim Airship: Kingdoms Adrift") == "Airship: Kingdoms Adrift"
    assert clean_amazon_title("Go to Steelrising detail page") == "Steelrising"
    assert clean_amazon_title("") == ""

    url = "https://luna.amazon.com/claims/steelrising-epic/dp/amzn1.pg.item.2e34e997-a137-48b3-9b5c-ad2eb51c45f7?ingress=amzn"
    assert build_amazon_id(url, "Steelrising") == (
        "amazon-amzn1.pg.item.2e34e997-a137-48b3-9b5c-ad2eb51c45f7"
    )
    assert build_amazon_id("https://luna.amazon.com/claims/steelrising", "Steelrising!") == (
        "amazon-steelrising"
    )


def test_parse_extracted_cards_filters_and_resolves_urls():
    raw_cards = [
        {
            "href": "/claims/game-one/dp/amzn1.pg.item.11111111-1111-1111-1111-111111111111",
            "card_text": "Game One\nClaim game",
            "title": "Game One",
            "img_url": "//cdn.example.com/one.jpg",
        },
        {
            "href": "game-two/dp/amzn1.pg.item.22222222-2222-2222-2222-222222222222",
            "card_text": "Game Two\nOyunu Talep Et",
            "title": "Game Two",
            "img_url": "/images/two.jpg",
        },
        # Duplicate title (case-insensitive)
        {
            "href": "/claims/game-one-dup",
            "card_text": "game one\nClaim",
            "title": "game one",
            "img_url": "",
        },
        # Play Now excluded
        {
            "href": "/claims/cloud-game",
            "card_text": "Cloud Game\nPlay Now",
            "title": "Cloud Game",
            "img_url": "",
        },
        # Missing claim action excluded
        {
            "href": "/claims/info-only",
            "card_text": "Info Only",
            "title": "Info Only",
            "img_url": "",
        },
    ]

    parsed = _parse_extracted_cards(raw_cards)
    assert len(parsed) == 2
    assert parsed[0]["title"] == "Game One"
    assert (
        parsed[0]["store_url"]
        == "https://luna.amazon.com/claims/game-one/dp/amzn1.pg.item.11111111-1111-1111-1111-111111111111"
    )
    assert parsed[0]["image_url"] == "https://cdn.example.com/one.jpg"

    assert parsed[1]["title"] == "Game Two"
    assert (
        parsed[1]["store_url"]
        == "https://luna.amazon.com/claims/game-two/dp/amzn1.pg.item.22222222-2222-2222-2222-222222222222"
    )
    assert parsed[1]["image_url"] == "https://luna.amazon.com/images/two.jpg"


@pytest.mark.asyncio
async def test_handle_asset_route_blocks_only_asset_types():
    for blocked in ("image", "media", "font", "stylesheet"):
        route = MagicMock()
        route.request.resource_type = blocked
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()
        await _handle_asset_route(route)
        route.abort.assert_awaited_once()
        route.continue_.assert_not_awaited()

    for allowed in ("document", "script", "xhr", "fetch"):
        route = MagicMock()
        route.request.resource_type = allowed
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()
        await _handle_asset_route(route)
        route.continue_.assert_awaited_once()
        route.abort.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_amazon_result_success_and_detail_exception_handling():
    locator_mock = MagicMock()
    locator_mock.count = AsyncMock(return_value=2)

    main_page = MagicMock()
    main_page.goto = AsyncMock()
    main_page.wait_for_timeout = AsyncMock()
    main_page.query_selector = AsyncMock(return_value=None)
    main_page.locator.return_value = locator_mock
    main_page.evaluate = AsyncMock(
        side_effect=[
            None,  # first scroll
            None,  # second scroll
            None,  # third scroll (stabilized)
            [
                {
                    "href": "/claims/steelrising/dp/amzn1.pg.item.11111111-1111-1111-1111-111111111111",
                    "card_text": "Steelrising\nClaim",
                    "title": "Steelrising",
                    "img_url": "https://img.example.com/steel.jpg",
                },
                {
                    "href": "/claims/deponia/dp/amzn1.pg.item.22222222-2222-2222-2222-222222222222",
                    "card_text": "Deponia\nClaim",
                    "title": "Deponia",
                    "img_url": "https://img.example.com/deponia.jpg",
                },
            ],
        ]
    )

    detail_page_1 = MagicMock()
    detail_page_1.route = AsyncMock()
    detail_page_1.goto = AsyncMock()
    detail_page_1.inner_text = AsyncMock(return_value="Available through Sep 23, 2026")
    detail_page_1.wait_for_timeout = AsyncMock()
    detail_page_1.close = AsyncMock()

    detail_page_2 = MagicMock()
    detail_page_2.route = AsyncMock()
    detail_page_2.goto = AsyncMock(side_effect=RuntimeError("Timeout"))
    detail_page_2.close = AsyncMock()

    context = MagicMock()
    context.new_page = AsyncMock(side_effect=[main_page, detail_page_1, detail_page_2])

    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    playwright_ctx = MagicMock()
    playwright_ctx.chromium.launch = AsyncMock(return_value=browser)

    async_pw_cm = MagicMock()
    async_pw_cm.__aenter__ = AsyncMock(return_value=playwright_ctx)
    async_pw_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.scrapers.luna.async_playwright", return_value=async_pw_cm):
        result = await fetch_amazon_result()

    assert result.ok is True
    assert result.source == "amazon_luna"
    assert len(result.games) == 2

    context_kwargs = browser.new_context.call_args.kwargs
    assert context_kwargs["locale"] == "en-US"
    assert "Accept-Language" in context_kwargs["extra_http_headers"]

    browser.close.assert_awaited_once()
    detail_page_1.close.assert_awaited_once()
    detail_page_2.close.assert_awaited_once()

    by_title = {g["title"]: g for g in result.games}
    assert by_title["Steelrising"]["end_date"] == "2026-09-23T23:59:59Z"
    assert by_title["Steelrising"]["notices"] == []
    assert by_title["Deponia"]["end_date"] is None
    assert by_title["Deponia"]["notices"] == []


@pytest.mark.asyncio
async def test_fetch_amazon_result_closes_browser_on_navigation_error():
    main_page = MagicMock()
    main_page.goto = AsyncMock(side_effect=RuntimeError("Navigation crashed"))

    context = MagicMock()
    context.new_page = AsyncMock(return_value=main_page)

    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    playwright_ctx = MagicMock()
    playwright_ctx.chromium.launch = AsyncMock(return_value=browser)

    async_pw_cm = MagicMock()
    async_pw_cm.__aenter__ = AsyncMock(return_value=playwright_ctx)
    async_pw_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.scrapers.luna.async_playwright", return_value=async_pw_cm):
        result = await fetch_amazon_result()

    assert result.ok is False
    assert result.games == []
    assert "Navigation crashed" in (result.error or "")
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_amazon_games_and_protocol():
    scraper = LunaScraper()
    assert isinstance(scraper, BaseScraper)

    fake_result = MagicMock(games=[{"id": "amazon-1"}], ok=True)
    with patch("backend.scrapers.luna.fetch_amazon_result", AsyncMock(return_value=fake_result)):
        games = await fetch_amazon_games()
        res = await scraper.fetch()

    assert games == [{"id": "amazon-1"}]
    assert res is fake_result

"""Unit tests for Amazon Luna scraper module."""

import asyncio
import itertools
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.schemas import BaseScraper
from backend.scrapers.luna import (
    _DETAIL_FALLBACK_IMAGE_JS,
    _SCROLL_STEP_JS,
    BLOCKED_RESOURCE_TYPES,
    CARD_LINK_SELECTOR,
    LunaScraper,
    _handle_asset_route,
    _parse_extracted_cards,
    _scroll_until_stable,
    build_amazon_id,
    clean_amazon_title,
    fetch_amazon_games,
    fetch_amazon_result,
    fetch_detail_page_end_date,
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
    assert parsed[0]["card_end_date"] == ""
    assert parsed[1]["card_end_date"] == ""


def test_parse_extracted_cards_merges_duplicates_and_extracts_card_date():
    raw_cards = [
        # First card has weak link, data:image placeholder, and no date
        {
            "href": "/claims/steelrising",
            "card_text": "Steelrising\nClaim game",
            "title": "Steelrising",
            "img_url": "data:image/svg+xml;base64,PHN2Zz4=",
        },
        # Second duplicate card has amzn1.pg.item URL, real image, and card expiration date
        {
            "href": "/claims/steelrising-epic/dp/amzn1.pg.item.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "card_text": "steelrising\nClaim\nOffer ends Dec 16, 2026",
            "title": "steelrising",
            "img_url": "//m.media-amazon.com/images/I/steel.jpg",
        },
        # Blob URI ignored
        {
            "href": "/claims/blob-game/dp/amzn1.pg.item.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "card_text": "Blob Game\nClaim\nExpires Jan 5, 2027",
            "title": "Blob Game",
            "img_url": "blob:https://luna.amazon.com/1234",
        },
    ]

    parsed = _parse_extracted_cards(raw_cards)
    assert len(parsed) == 2

    assert parsed[0]["title"] == "Steelrising"
    assert (
        parsed[0]["store_url"]
        == "https://luna.amazon.com/claims/steelrising-epic/dp/amzn1.pg.item.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )
    assert parsed[0]["image_url"] == "https://m.media-amazon.com/images/I/steel.jpg"
    assert parsed[0]["card_end_date"] == "2026-12-16T23:59:59Z"

    assert parsed[1]["title"] == "Blob Game"
    assert parsed[1]["image_url"] == ""
    assert parsed[1]["card_end_date"] == "2027-01-05T23:59:59Z"


@pytest.mark.asyncio
async def test_handle_asset_route_fulfills_stylesheets_and_blocks_only_asset_types():
    assert BLOCKED_RESOURCE_TYPES == frozenset({"image", "media", "font"})

    for blocked in ("image", "media", "font"):
        route = MagicMock()
        route.request.resource_type = blocked
        route.request.url = "https://m.media-amazon.com/asset.bin"
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()
        route.fulfill = AsyncMock()
        await _handle_asset_route(route)
        route.abort.assert_awaited_once()
        route.continue_.assert_not_awaited()
        route.fulfill.assert_not_awaited()

    for res_type, url in (
        ("stylesheet", "https://m.media-amazon.com/main.chunk"),
        ("other", "https://m.media-amazon.com/styles.CSS?v=2"),
    ):
        route = MagicMock()
        route.request.resource_type = res_type
        route.request.url = url
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()
        route.fulfill = AsyncMock()
        await _handle_asset_route(route)
        route.fulfill.assert_awaited_once_with(
            status=200,
            body="",
            content_type="text/css",
        )
        route.abort.assert_not_awaited()
        route.continue_.assert_not_awaited()

    for allowed in ("document", "script", "xhr", "fetch"):
        route = MagicMock()
        route.request.resource_type = allowed
        route.request.url = "https://luna.amazon.com/api/data"
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()
        route.fulfill = AsyncMock()
        await _handle_asset_route(route)
        route.continue_.assert_awaited_once()
        route.abort.assert_not_awaited()
        route.fulfill.assert_not_awaited()


@pytest.mark.asyncio
async def test_scroll_until_stable_incremental_and_stabilization():
    locator_mock = MagicMock()
    # Round 0: 2->4 (grows), Round 1: 4->6 (grows), Round 2: 6->6 (stable 1), Round 3: 6->6 (stable 2)
    locator_mock.count = AsyncMock(side_effect=[2, 4, 4, 6, 6, 6, 6, 6])

    page = MagicMock()
    page.locator.return_value = locator_mock
    page.evaluate = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    await _scroll_until_stable(page)

    assert page.evaluate.await_count == 4
    for call in page.evaluate.call_args_list:
        assert call.args == (_SCROLL_STEP_JS, CARD_LINK_SELECTOR)
    assert "scrollIntoView" in _SCROLL_STEP_JS


@pytest.mark.asyncio
async def test_fetch_amazon_result_success_and_detail_exception_handling():
    event_log: list[str] = []

    locator_mock = MagicMock()
    locator_mock.count = AsyncMock(return_value=2)

    main_page = MagicMock()
    main_page.goto = AsyncMock()
    main_page.wait_for_timeout = AsyncMock()
    main_page.query_selector = AsyncMock(return_value=None)
    main_page.locator.return_value = locator_mock
    main_page.close = AsyncMock(side_effect=lambda: event_log.append("main_page.close"))
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
    detail_page_1.evaluate = AsyncMock()
    detail_page_1.wait_for_timeout = AsyncMock()
    detail_page_1.close = AsyncMock()

    detail_page_2 = MagicMock()
    detail_page_2.route = AsyncMock()
    detail_page_2.goto = AsyncMock(side_effect=RuntimeError("Timeout"))
    detail_page_2.close = AsyncMock()

    pages = [main_page, detail_page_1, detail_page_2]

    async def new_page_side_effect():
        page = pages.pop(0)
        if page is main_page:
            event_log.append("main_page.new")
        else:
            event_log.append("detail_page.new")
        return page

    context = MagicMock()
    context.new_page = AsyncMock(side_effect=new_page_side_effect)

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
    assert "user_agent" in context_kwargs
    assert "viewport" in context_kwargs
    assert "extra_http_headers" not in context_kwargs

    main_page.close.assert_awaited_once()
    assert event_log.index("main_page.close") < event_log.index("detail_page.new")

    detail_page_1.goto.assert_awaited_once_with(
        "https://luna.amazon.com/claims/steelrising/dp/amzn1.pg.item.11111111-1111-1111-1111-111111111111",
        wait_until="domcontentloaded",
        timeout=12000,
    )
    detail_page_1.evaluate.assert_not_awaited()

    browser.close.assert_awaited_once()
    detail_page_1.close.assert_awaited_once()
    detail_page_2.close.assert_awaited_once()

    by_title = {g["title"]: g for g in result.games}
    assert by_title["Steelrising"]["end_date"] == "2026-09-23T23:59:59Z"
    assert by_title["Steelrising"]["notices"] == []
    assert by_title["Deponia"]["end_date"] is None
    assert by_title["Deponia"]["notices"] == []


@pytest.mark.asyncio
async def test_fetch_detail_page_end_date_fallback_image_and_card_date():
    detail_page = MagicMock()
    detail_page.route = AsyncMock()
    detail_page.goto = AsyncMock()
    detail_page.inner_text = AsyncMock(return_value="No date on detail page")
    detail_page.wait_for_timeout = AsyncMock()
    detail_page.evaluate = AsyncMock(return_value="//m.media-amazon.com/images/I/fallback.jpg")
    detail_page.close = AsyncMock()

    context = MagicMock()
    context.new_page = AsyncMock(return_value=detail_page)

    item = {
        "title": "Ad Infinitum",
        "store_url": "https://luna.amazon.com/claims/ad-infinitum/dp/amzn1.pg.item.1234",
        "image_url": "",
        "card_end_date": "2026-11-25T23:59:59Z",
    }

    with patch("backend.scrapers.luna.time.time", side_effect=[0.0, 0.0, 5.1]):
        end_date = await fetch_detail_page_end_date(
            context, item, 0, 1, asyncio.Semaphore(1)
        )

    assert end_date == "2026-11-25T23:59:59Z"
    assert item["image_url"] == "https://m.media-amazon.com/images/I/fallback.jpg"
    detail_page.goto.assert_awaited_once_with(
        item["store_url"], wait_until="domcontentloaded", timeout=12000
    )
    detail_page.evaluate.assert_awaited_once_with(_DETAIL_FALLBACK_IMAGE_JS)
    detail_page.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_detail_page_end_date_ignores_invalid_fallback_image_and_handles_missing_url():
    detail_page = MagicMock()
    detail_page.route = AsyncMock()
    detail_page.goto = AsyncMock()
    detail_page.inner_text = AsyncMock(return_value="Offer ends Dec 20, 2026")
    detail_page.wait_for_timeout = AsyncMock()
    detail_page.evaluate = AsyncMock(return_value="data:image/gif;base64,R0lGOD")
    detail_page.close = AsyncMock()

    context = MagicMock()
    context.new_page = AsyncMock(return_value=detail_page)

    item_with_url = {
        "title": "Kiborg",
        "store_url": "https://luna.amazon.com/claims/kiborg/dp/amzn1.pg.item.5678",
        "image_url": "",
        "card_end_date": "",
    }
    end_date = await fetch_detail_page_end_date(
        context, item_with_url, 0, 1, asyncio.Semaphore(1)
    )
    assert end_date == "2026-12-20T23:59:59Z"
    assert item_with_url["image_url"] == ""

    item_no_url = {
        "title": "No Url",
        "store_url": "",
        "image_url": "",
        "card_end_date": "2026-12-01T23:59:59Z",
    }
    assert (
        await fetch_detail_page_end_date(context, item_no_url, 0, 1, asyncio.Semaphore(1))
        == "2026-12-01T23:59:59Z"
    )


@pytest.mark.asyncio
async def test_fetch_amazon_result_empty_games_returns_failure():
    locator_mock = MagicMock()
    locator_mock.count = AsyncMock(return_value=0)

    main_page = MagicMock()
    main_page.goto = AsyncMock()
    main_page.wait_for_timeout = AsyncMock()
    main_page.query_selector = AsyncMock(return_value=None)
    main_page.locator.return_value = locator_mock
    main_page.close = AsyncMock()
    main_page.evaluate = AsyncMock(side_effect=[None, None, None, []])

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
    assert result.source == "amazon_luna"
    assert result.games == []
    assert result.error == "No claimable games found on Amazon Luna"
    main_page.close.assert_awaited_once()
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_amazon_result_falls_back_to_card_end_date_and_detail_cover_image():
    locator_mock = MagicMock()
    locator_mock.count = AsyncMock(return_value=2)

    main_page = MagicMock()
    main_page.goto = AsyncMock()
    main_page.wait_for_timeout = AsyncMock()
    main_page.query_selector = AsyncMock(return_value=None)
    main_page.locator.return_value = locator_mock
    main_page.close = AsyncMock()
    main_page.evaluate = AsyncMock(
        side_effect=[
            None,
            None,
            None,
            [
                {
                    "href": "/claims/game-a/dp/amzn1.pg.item.11111111-1111-1111-1111-111111111111",
                    "card_text": "Game A\nClaim\nEnds Dec 16, 2026",
                    "title": "Game A",
                    "img_url": "",
                },
                {
                    "href": "/claims/game-b/dp/amzn1.pg.item.22222222-2222-2222-2222-222222222222",
                    "card_text": "Game B\nClaim\nEnds Dec 10, 2026",
                    "title": "Game B",
                    "img_url": "https://m.media-amazon.com/images/I/b.jpg",
                },
            ],
        ]
    )

    detail_a = MagicMock()
    detail_a.route = AsyncMock()
    detail_a.goto = AsyncMock()
    detail_a.inner_text = AsyncMock(return_value="Game details without date")
    detail_a.wait_for_timeout = AsyncMock()
    detail_a.evaluate = AsyncMock(return_value="https://m.media-amazon.com/images/I/a-og.jpg")
    detail_a.close = AsyncMock()

    detail_b = MagicMock()
    detail_b.route = AsyncMock()
    detail_b.goto = AsyncMock()
    detail_b.inner_text = AsyncMock(return_value="Available through Dec 20, 2026")
    detail_b.wait_for_timeout = AsyncMock()
    detail_b.evaluate = AsyncMock()
    detail_b.close = AsyncMock()

    context = MagicMock()
    context.new_page = AsyncMock(side_effect=[main_page, detail_a, detail_b])

    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    playwright_ctx = MagicMock()
    playwright_ctx.chromium.launch = AsyncMock(return_value=browser)

    async_pw_cm = MagicMock()
    async_pw_cm.__aenter__ = AsyncMock(return_value=playwright_ctx)
    async_pw_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("backend.scrapers.luna.async_playwright", return_value=async_pw_cm),
        patch("backend.scrapers.luna.time.time", side_effect=itertools.count(0, 3)),
    ):
        result = await fetch_amazon_result()

    assert result.ok is True
    by_title = {g["title"]: g for g in result.games}
    assert by_title["Game A"]["image_url"] == "https://m.media-amazon.com/images/I/a-og.jpg"
    assert by_title["Game A"]["end_date"] == "2026-12-16T23:59:59Z"
    assert by_title["Game B"]["image_url"] == "https://m.media-amazon.com/images/I/b.jpg"
    assert by_title["Game B"]["end_date"] == "2026-12-20T23:59:59Z"


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

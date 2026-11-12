import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
    state,
    getActiveLocale,
    normalizePlatform,
    isGameExpired,
    getProcessedGames,
    getFacetCounts,
    toggleClaimed,
    isClaimed,
    readStateFromURL,
    buildURLSearchParams
} from '../../frontend/js/state.js';
import {
    safeUrl,
    escapeHTML,
    escapeAttribute,
    getNoticeLines,
    createGameCardHTML
} from '../../frontend/js/ui.js';
import { translations, setLanguage } from '../../frontend/js/i18n.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, '../..');

function resetStateForTest() {
    state.games = [];
    state.currentPlatformFilter = 'all';
    state.currentContentFilter = 'all';
    state.currentSortOption = 'smart';
    state.currentViewMode = 'grid';
    state.searchQuery = '';
    state.currentLang = 'TR';
    state.hideExpired = false;
    state.claimedIds = new Set();
    state.isLoading = false;
    state.hasError = false;
    state.errorMessage = '';
    state.generatedAt = null;
}

beforeEach(() => {
    resetStateForTest();
});

// ============================================================================
// state.js tests
// ============================================================================

test('normalizePlatform maps known platforms and defaults to other', () => {
    assert.equal(normalizePlatform('Steam'), 'steam');
    assert.equal(normalizePlatform('Epic Games Store'), 'epic');
    assert.equal(normalizePlatform('Amazon Luna / Prime'), 'amazon');
    assert.equal(normalizePlatform('Prime Gaming'), 'amazon');
    assert.equal(normalizePlatform('GOG'), 'other');
    assert.equal(normalizePlatform(''), 'other');
    assert.equal(normalizePlatform(null), 'other');
});

test('getActiveLocale returns tr-TR for TR and en-US for EN', () => {
    assert.equal(getActiveLocale('TR'), 'tr-TR');
    assert.equal(getActiveLocale('EN'), 'en-US');
    state.currentLang = 'EN';
    assert.equal(getActiveLocale(), 'en-US');
});

test('isGameExpired evaluates end_date against reference timestamp', () => {
    const now = Date.parse('2026-08-15T12:00:00Z');
    assert.equal(isGameExpired({ end_date: '2026-08-15T11:59:59Z' }, now), true);
    assert.equal(isGameExpired({ end_date: '2026-08-15T12:00:00Z' }, now), true);
    assert.equal(isGameExpired({ end_date: '2026-08-15T12:00:01Z' }, now), false);
    assert.equal(isGameExpired({ end_date: null }, now), false);
    assert.equal(isGameExpired({ end_date: 'not-a-date' }, now), false);
});

test('getProcessedGames filters by content, platform, searchQuery (Turkish locale), and hideExpired', () => {
    const now = Date.parse('2026-08-15T12:00:00Z');
    state.games = [
        { id: '1', title: 'İstanbul Efsanesi', platform: 'Steam', content_type: 'game', end_date: '2026-08-20T00:00:00Z' },
        { id: '2', title: 'Space Pack', platform: 'Epic Games', content_type: 'dlc', end_date: '2026-08-18T00:00:00Z' },
        { id: '3', title: 'Old Offer', platform: 'Steam', content_type: 'game', end_date: '2026-08-10T00:00:00Z' },
        { id: '4', title: 'Prime Quest', platform: 'Amazon Luna / Prime', content_type: 'game', end_date: null }
    ];

    // Turkish uppercase/lowercase folding for İ -> i
    state.currentLang = 'TR';
    state.searchQuery = 'istanbul';
    let result = getProcessedGames(now);
    assert.deepEqual(result.map(g => g.id), ['1']);

    // Content filter: DLC only
    state.searchQuery = '';
    state.currentContentFilter = 'dlc';
    result = getProcessedGames(now);
    assert.deepEqual(result.map(g => g.id), ['2']);

    // Platform filter + hideExpired
    state.currentContentFilter = 'all';
    state.currentPlatformFilter = 'steam';
    result = getProcessedGames(now);
    assert.deepEqual(result.map(g => g.id), ['1', '3']); // active first, expired last

    state.hideExpired = true;
    result = getProcessedGames(now);
    assert.deepEqual(result.map(g => g.id), ['1']);
});

test('getProcessedGames sorts Turkish characters with tr-TR locale and puts expired deals last', () => {
    const now = Date.parse('2026-08-15T12:00:00Z');
    state.currentLang = 'TR';
    state.currentSortOption = 'alphabetical';
    state.games = [
        { id: 'exp', title: 'AAA Expired', platform: 'Steam', end_date: '2026-08-01T00:00:00Z' },
        { id: 'd', title: 'Dune', platform: 'Steam', end_date: '2026-08-20T00:00:00Z' },
        { id: 'c', title: 'Çember', platform: 'Steam', end_date: '2026-08-20T00:00:00Z' },
        { id: 'a', title: 'Atlas', platform: 'Steam', end_date: '2026-08-20T00:00:00Z' }
    ];

    const alpha = getProcessedGames(now);
    assert.deepEqual(alpha.map(g => g.id), ['a', 'c', 'd', 'exp']);

    state.currentSortOption = 'expiring';
    state.games = [
        { id: 'exp', title: 'Expired First Date', platform: 'Steam', end_date: '2026-08-01T00:00:00Z' },
        { id: 'later', title: 'Later', platform: 'Steam', end_date: '2026-08-25T00:00:00Z' },
        { id: 'sooner', title: 'Sooner', platform: 'Steam', end_date: '2026-08-16T00:00:00Z' },
        { id: 'perm', title: 'Permanent', platform: 'Steam', end_date: null }
    ];
    const expiring = getProcessedGames(now);
    assert.deepEqual(expiring.map(g => g.id), ['sooner', 'later', 'perm', 'exp']);
});

test('getFacetCounts computes accurate counts across platform and content facets', () => {
    const now = Date.parse('2026-08-15T12:00:00Z');
    state.games = [
        { id: '1', title: 'Game A', platform: 'Steam', content_type: 'game', end_date: '2026-08-20T00:00:00Z' },
        { id: '2', title: 'DLC B', platform: 'Steam', content_type: 'dlc', end_date: '2026-08-20T00:00:00Z' },
        { id: '3', title: 'Game C', platform: 'Epic Games', content_type: 'game', end_date: '2026-08-01T00:00:00Z' },
        { id: '4', title: 'Game D', platform: 'GOG', content_type: 'game', end_date: null }
    ];

    state.currentPlatformFilter = 'steam';
    state.currentContentFilter = 'all';
    const counts = getFacetCounts(now);
    assert.deepEqual(counts.platform, { all: 4, steam: 2, epic: 1, amazon: 0, other: 1 });
    assert.deepEqual(counts.content, { all: 2, games: 1, dlc: 1 });

    state.hideExpired = true;
    const activeCounts = getFacetCounts(now);
    assert.equal(activeCounts.platform.epic, 0);
    assert.equal(activeCounts.platform.all, 3);
});

test('toggleClaimed and isClaimed toggle deal IDs cleanly', () => {
    assert.equal(isClaimed('deal-1'), false);
    assert.equal(toggleClaimed('deal-1'), true);
    assert.equal(isClaimed('deal-1'), true);
    assert.equal(toggleClaimed('deal-1'), false);
    assert.equal(isClaimed('deal-1'), false);
    assert.equal(toggleClaimed(''), false);
});

test('readStateFromURL and buildURLSearchParams validate and round-trip URL query state', () => {
    const parsed = readStateFromURL('?platform=epic&content=dlc&sort=expiring&q=Hades&expired=hide');
    assert.equal(parsed.platform, 'epic');
    assert.equal(state.currentPlatformFilter, 'epic');
    assert.equal(state.currentContentFilter, 'dlc');
    assert.equal(state.currentSortOption, 'expiring');
    assert.equal(state.searchQuery, 'hades');
    assert.equal(state.hideExpired, true);

    const params = buildURLSearchParams(state);
    assert.equal(params.get('platform'), 'epic');
    assert.equal(params.get('content'), 'dlc');
    assert.equal(params.get('sort'), 'expiring');
    assert.equal(params.get('q'), 'hades');
    assert.equal(params.get('expired'), 'hide');

    // Invalid params should be ignored
    resetStateForTest();
    readStateFromURL('?platform=invalid&content=bogus&sort=weird');
    assert.equal(state.currentPlatformFilter, 'all');
    assert.equal(state.currentContentFilter, 'all');
    assert.equal(state.currentSortOption, 'smart');
    assert.equal(buildURLSearchParams(state).toString(), '');
});

// ============================================================================
// ui.js tests
// ============================================================================

test('safeUrl blocks XSS protocols and malformed URLs while allowing http/https', () => {
    assert.equal(safeUrl('https://store.steampowered.com/app/123'), 'https://store.steampowered.com/app/123');
    assert.equal(safeUrl('http://example.com/deal'), 'http://example.com/deal');
    assert.equal(safeUrl('  HTTPS://epicgames.com/store  '), 'https://epicgames.com/store');
    assert.equal(safeUrl('javascript:alert(1)'), '#');
    assert.equal(safeUrl('JAVASCRIPT:alert(1)'), '#');
    assert.equal(safeUrl('data:text/html,<script>alert(1)</script>'), '#');
    assert.equal(safeUrl('vbscript:msgbox(1)'), '#');
    assert.equal(safeUrl('not a valid url', ''), '');
    assert.equal(safeUrl(null), '#');
});

test('escapeHTML and escapeAttribute escape special HTML characters', () => {
    assert.equal(escapeHTML(`<script>"'&</script>`), '&lt;script&gt;&quot;&#039;&amp;&lt;/script&gt;');
    assert.equal(escapeAttribute(`" onclick="alert('xss')"`), '&quot; onclick=&quot;alert(&#039;xss&#039;)&quot;');
    assert.equal(escapeHTML(''), '');
    assert.equal(escapeAttribute(null), '');
});

test('getNoticeLines translates known notice codes, deduplicates, and ignores unknown', () => {
    const notices = getNoticeLines(
        { notices: ['amd_account', 'unknown_code', 'amd_account', 'redeem_in_game', 123] },
        translations.EN
    );
    assert.deepEqual(notices, [
        translations.EN.notice_amd_account,
        translations.EN.notice_redeem_in_game
    ]);
    assert.deepEqual(getNoticeLines({ notices: null }, translations.TR), []);
    assert.deepEqual(getNoticeLines({}, translations.TR), []);
});

test('createGameCardHTML escapes XSS payloads, includes a11y/perf attrs, and reflects claimed state', () => {
    state.currentLang = 'EN';
    state.claimedIds = new Set(['g-xss']);

    const html = createGameCardHTML({
        id: 'g-xss',
        title: 'Bad <img src=x onerror=alert(1)> Game',
        platform: 'Itch.io "Special"',
        store_url: 'javascript:alert(1)',
        image_url: 'https://cdn.example.com/cover.jpg?a=1&b=2',
        end_date: '2026-09-01T00:00:00Z',
        is_permanent: false,
        content_type: 'dlc',
        notices: ['newsletter_signup']
    });

    assert.ok(!html.includes('<img src=x onerror=alert(1)>'));
    assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;'));
    assert.ok(html.includes('href="#"'));
    assert.ok(html.includes('decoding="async"'));
    assert.ok(html.includes('referrerpolicy="no-referrer"'));
    assert.ok(html.includes('data-is-permanent="false"'));
    assert.ok(html.includes('class="game-card is-claimed"'));
    assert.ok(html.includes('aria-pressed="true"'));
    assert.ok(html.includes('class="dlc-badge"'));
    assert.ok(html.includes(translations.EN.notice_newsletter_signup));
    assert.ok(!html.includes('M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 002-2V7a2 2 0 00-2-2H5z'));
});

// ============================================================================
// i18n.js & index.html parity tests
// ============================================================================

test('TR and EN translation dictionaries have 100% key parity and distinct TR time units', () => {
    const trKeys = Object.keys(translations.TR).sort();
    const enKeys = Object.keys(translations.EN).sort();
    assert.deepEqual(trKeys, enKeys);
    assert.notEqual(translations.TR.timer_hour_unit, translations.TR.timer_second_unit);
    assert.equal(translations.TR.timer_second_unit, 'sn');

    // setLanguage runs cleanly in Node without document global
    setLanguage('EN');
    assert.equal(state.currentLang, 'EN');
});

test('Every data-i18n* key in index.html exists in both TR and EN, and index.html has required a11y/SEO elements', () => {
    const indexHtml = fs.readFileSync(path.join(ROOT_DIR, 'index.html'), 'utf8');

    const attrPattern = /data-i18n(?:|-placeholder|-aria)="([^"]+)"/g;
    const usedKeys = new Set();
    for (const match of indexHtml.matchAll(attrPattern)) {
        usedKeys.add(match[1]);
    }

    assert.ok(usedKeys.size > 0, 'Expected data-i18n* attributes in index.html');
    for (const key of usedKeys) {
        assert.ok(Object.hasOwn(translations.TR, key), `Missing TR translation key: ${key}`);
        assert.ok(Object.hasOwn(translations.EN, key), `Missing EN translation key: ${key}`);
    }

    assert.ok(indexHtml.includes('<h1 '), 'Expected semantic <h1> in index.html');
    assert.ok(!indexHtml.includes('role="tablist"'), 'Broken role="tablist" should be removed');
    assert.ok(indexHtml.includes('id="last-updated"'), 'Expected #last-updated footer span');
    assert.ok(indexHtml.includes('id="hide-expired-checkbox"'), 'Expected hide-expired toggle');
    assert.ok(indexHtml.includes('<link rel="canonical"'), 'Expected canonical link tag');
    assert.ok(indexHtml.includes('<meta name="theme-color"'), 'Expected theme-color meta tag');
    assert.ok(indexHtml.includes('<noscript>'), 'Expected noscript fallback');
});

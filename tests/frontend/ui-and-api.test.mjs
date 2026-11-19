import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { fetchGamesData } from '../../frontend/js/api.js';
import {
    state,
    getInitialLanguage,
    getProcessedGames,
    getFacetCounts,
    readStateFromURL,
    buildURLSearchParams
} from '../../frontend/js/state.js';
import {
    createGameCardHTML,
    renderGames,
    renderErrorState,
    renderEmptyState,
    setupImageErrorDelegation,
    updateAllTimers
} from '../../frontend/js/ui.js';
import { translations } from '../../frontend/js/i18n.js';

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
    state.hideClaimed = false;
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
// api.js tests
// ============================================================================

test('fetchGamesData handles object payloads, legacy arrays, malformed payloads, and HTTP errors', async () => {
    const prevFetch = globalThis.fetch;

    try {
        globalThis.fetch = async (url, options) => {
            assert.equal(url, './games.json');
            assert.deepEqual(options, { cache: 'no-cache' });
            return {
                ok: true,
                status: 200,
                json: async () => ({
                    generated_at: ' 2026-11-16T12:14:44Z ',
                    games: [{ id: 'steam-1', title: 'Portal' }]
                })
            };
        };
        const objRes = await fetchGamesData();
        assert.deepEqual(objRes, {
            games: [{ id: 'steam-1', title: 'Portal' }],
            generatedAt: '2026-11-16T12:14:44Z'
        });

        globalThis.fetch = async () => ({
            ok: true,
            status: 200,
            json: async () => [{ id: 'epic-1', title: 'Legacy' }]
        });
        const arrRes = await fetchGamesData();
        assert.deepEqual(arrRes, {
            games: [{ id: 'epic-1', title: 'Legacy' }],
            generatedAt: null
        });

        globalThis.fetch = async () => ({
            ok: true,
            status: 200,
            json: async () => null
        });
        const nullRes = await fetchGamesData();
        assert.deepEqual(nullRes, { games: [], generatedAt: null });

        globalThis.fetch = async () => ({
            ok: false,
            status: 503
        });
        await assert.rejects(fetchGamesData(), /HTTP 503/);
    } finally {
        globalThis.fetch = prevFetch;
    }
});

// ============================================================================
// Locale search regression, hideClaimed & navigator.languages tests
// ============================================================================

test('TR locale search matches English uppercase I titles as well as Turkish İ', () => {
    const now = Date.parse('2026-11-16T12:00:00Z');
    state.currentLang = 'TR';
    state.games = [
        { id: '1', title: 'RIDE 6 Welcome Bikes Pack', platform: 'Steam', end_date: null },
        { id: '2', title: 'DAVE THE DIVER - Godzilla Content Pack', platform: 'Steam', end_date: null },
        { id: '3', title: 'Ad Infinitum', platform: 'Amazon Luna / Prime', end_date: null },
        { id: '4', title: 'Payday 2: Free In-game Items', platform: 'Steam', end_date: null },
        { id: '5', title: 'İstanbul Efsanesi', platform: 'Steam', end_date: null }
    ];

    for (const [query, expectedId] of [
        ['ride', '1'],
        ['diver', '2'],
        ['infinitum', '3'],
        ['items', '4'],
        ['istanbul', '5']
    ]) {
        state.searchQuery = query;
        const matched = getProcessedGames(now);
        assert.deepEqual(matched.map(g => g.id), [expectedId], `Query '${query}' failed`);
    }

    // Even uppercase query pre-folded with tr-TR locale ('ITEMS' -> 'ıtems') matches
    state.searchQuery = 'ITEMS'.toLocaleLowerCase('tr-TR');
    assert.deepEqual(getProcessedGames(now).map(g => g.id), ['4']);
});

test('hideClaimed filters games, updates facet counts, and round-trips through URL params', () => {
    const now = Date.parse('2026-11-16T12:00:00Z');
    state.games = [
        { id: 's1', title: 'Game 1', platform: 'Steam', content_type: 'game', end_date: null },
        { id: 's2', title: 'DLC 2', platform: 'Steam', content_type: 'dlc', end_date: null },
        { id: 'e1', title: 'Epic 3', platform: 'Epic Games', content_type: 'game', end_date: null }
    ];
    state.claimedIds = new Set(['s1']);

    state.hideClaimed = true;
    const processed = getProcessedGames(now);
    assert.deepEqual(processed.map(g => g.id), ['e1', 's2']);

    const counts = getFacetCounts(now);
    assert.deepEqual(counts.platform, { all: 2, steam: 1, epic: 1, amazon: 0, other: 0 });
    assert.deepEqual(counts.content, { all: 2, games: 1, dlc: 1 });

    resetStateForTest();
    const parsed = readStateFromURL('?claimed=hide');
    assert.equal(parsed.claimed, true);
    assert.equal(state.hideClaimed, true);
    assert.equal(buildURLSearchParams(state).get('claimed'), 'hide');

    readStateFromURL('?claimed=show');
    assert.equal(state.hideClaimed, false);
    assert.equal(buildURLSearchParams(state).has('claimed'), false);
});

test('getInitialLanguage checks navigator.languages and falls back to EN for non-TR locales', () => {
    const prevNavDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
    const prevStorageDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');

    Object.defineProperty(globalThis, 'localStorage', {
        value: { getItem: () => null },
        configurable: true,
        writable: true
    });

    try {
        for (const [langs, expected] of [
            [['tr-TR'], 'TR'],
            [['de-DE', 'en-US'], 'EN'],
            [['fr-FR'], 'EN'],
            [['de-DE', 'tr-TR'], 'TR']
        ]) {
            Object.defineProperty(globalThis, 'navigator', {
                value: { languages: langs, language: langs[0] },
                configurable: true,
                writable: true
            });
            assert.equal(getInitialLanguage(), expected, `Failed for ${JSON.stringify(langs)}`);
        }
    } finally {
        if (prevNavDescriptor) {
            Object.defineProperty(globalThis, 'navigator', prevNavDescriptor);
        } else {
            delete globalThis.navigator;
        }
        if (prevStorageDescriptor) {
            Object.defineProperty(globalThis, 'localStorage', prevStorageDescriptor);
        } else {
            delete globalThis.localStorage;
        }
    }
});

// ============================================================================
// ui.js DOM & caching behavior tests
// ============================================================================

test('renderGames is a no-op while isLoading is true and renderErrorState updates #results-status', () => {
    const attrs = new Map();
    const gridEl = {
        innerHTML: '<div class="skeleton-card"></div>',
        dataset: { imgErrorDelegated: 'true' },
        setAttribute: (k, v) => attrs.set(k, String(v)),
        getAttribute: (k) => attrs.get(k) ?? null
    };
    const statusEl = { textContent: '' };

    const prevDoc = globalThis.document;
    globalThis.document = {
        getElementById: (id) => {
            if (id === 'games-grid') return gridEl;
            if (id === 'results-status') return statusEl;
            return null;
        },
        querySelectorAll: () => []
    };

    try {
        state.isLoading = true;
        renderGames();
        assert.equal(gridEl.innerHTML, '<div class="skeleton-card"></div>');

        state.isLoading = false;
        state.currentLang = 'EN';
        renderErrorState('HTTP 500');
        assert.equal(gridEl.getAttribute('aria-busy'), 'false');
        assert.equal(statusEl.textContent, `${translations.EN.error_title}: HTTP 500`);
    } finally {
        renderEmptyState();
        if (prevDoc === undefined) delete globalThis.document;
        else globalThis.document = prevDoc;
    }
});

test('setupImageErrorDelegation immediately switches already-broken images to fallback', () => {
    const fallbackEl = {
        classList: { contains: (cls) => cls === 'card-img-fallback' },
        style: { display: 'none' }
    };
    const brokenCardImg = {
        tagName: 'IMG',
        complete: true,
        naturalWidth: 0,
        classList: { contains: (cls) => cls === 'card-img' },
        style: { display: '' },
        nextElementSibling: fallbackEl
    };
    const loadedCardImg = {
        tagName: 'IMG',
        complete: true,
        naturalWidth: 600,
        classList: { contains: (cls) => cls === 'card-img' },
        style: { display: '' },
        nextElementSibling: { classList: { contains: () => true }, style: { display: 'none' } }
    };
    const container = {
        dataset: {},
        addEventListener: () => {},
        querySelectorAll: (sel) => (sel === 'img' ? [brokenCardImg, loadedCardImg] : [])
    };

    setupImageErrorDelegation(container);
    assert.equal(container.dataset.imgErrorDelegated, 'true');
    assert.equal(brokenCardImg.style.display, 'none');
    assert.equal(fallbackEl.style.display, 'flex');
    assert.equal(loadedCardImg.style.display, '');
});

test('updateAllTimers caches tooltip attributes when lang and endDate are unchanged', () => {
    const futureIso = new Date(Date.now() + 36 * 60 * 60 * 1000).toISOString();
    const attrs = new Map();
    let setTitleCalls = 0;

    const badge = {
        dataset: { endDate: futureIso, isPermanent: 'false' },
        textContent: '',
        className: 'countdown-badge',
        getAttribute: (name) => (attrs.has(name) ? attrs.get(name) : null),
        setAttribute: (name, val) => {
            if (name === 'title') setTitleCalls += 1;
            attrs.set(name, String(val));
        },
        hasAttribute: (name) => attrs.has(name),
        removeAttribute: (name) => {
            attrs.delete(name);
        }
    };

    const prevDoc = globalThis.document;
    globalThis.document = {
        hidden: false,
        getElementById: () => null,
        querySelectorAll: (sel) => (sel === '.countdown-badge' ? [badge] : [])
    };

    try {
        state.currentLang = 'EN';
        updateAllTimers();
        assert.equal(setTitleCalls, 1);
        assert.ok(badge.getAttribute('data-tooltip'));
        assert.equal(badge.getAttribute('tabindex'), '0');

        // Repeat tick under identical lang & endDate should not recompute/re-set title
        updateAllTimers();
        assert.equal(setTitleCalls, 1);

        // Switching language updates tooltip once
        state.currentLang = 'TR';
        updateAllTimers();
        assert.equal(setTitleCalls, 2);
    } finally {
        renderEmptyState();
        if (prevDoc === undefined) delete globalThis.document;
        else globalThis.document = prevDoc;
    }
});

test('createGameCardHTML uses inline SVGs, Luna notices, default is_permanent=false, and accessible tooltips', () => {
    state.currentLang = 'EN';
    const html = createGameCardHTML({
        id: 'amazon-1',
        title: 'WarBreeds',
        platform: 'Amazon Luna / Prime',
        store_url: 'https://luna.amazon.com/claims/warbreeds-gog/dp/amzn1.pg.item.123',
        image_url: 'https://m.media-amazon.com/images/I/wb.jpg',
        end_date: '2026-12-20T23:59:59Z',
        notices: ['redeem_gog']
    });

    assert.ok(!html.includes('cdn.jsdelivr.net'));
    assert.ok(html.includes('<svg class="platform-icon"'));
    assert.ok(html.includes('data-is-permanent="false"'));
    assert.ok(html.includes(translations.EN.notice_redeem_gog));
    assert.ok(html.includes('data-tooltip="'));
    assert.ok(html.includes('tabindex="0"'));
});

test('index.html has CSP meta, twitter:image, skip link, hide-claimed, share button, and no CDN icons', () => {
    const indexHtml = fs.readFileSync(path.join(ROOT_DIR, 'index.html'), 'utf8');
    assert.ok(indexHtml.includes('http-equiv="Content-Security-Policy"'));
    assert.ok(indexHtml.includes('name="twitter:image"'));
    assert.ok(indexHtml.includes('class="skip-link"'));
    assert.ok(indexHtml.includes('id="hide-claimed-checkbox"'));
    assert.ok(indexHtml.includes('id="share-filters-btn"'));
    assert.ok(!indexHtml.includes('cdn.jsdelivr.net'));
});

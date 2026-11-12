/**
 * OpenClaim - State Manager Module
 * Manages application state, filters, sorting, view mode, language,
 * claimed deals, URL query sync, and localStorage persistence.
 */

const VALID_PLATFORMS = new Set(['all', 'steam', 'epic', 'amazon', 'other']);
const VALID_CONTENTS = new Set(['all', 'games', 'dlc']);
const VALID_SORTS = new Set(['smart', 'alphabetical', 'expiring']);

// Application State
export const state = {
    games: [],
    currentPlatformFilter: 'all',
    currentContentFilter: 'all',
    currentSortOption: 'smart',
    currentViewMode: 'grid',
    searchQuery: '',
    currentLang: 'TR',
    hideExpired: false,
    claimedIds: new Set(),
    isLoading: false,
    hasError: false,
    errorMessage: '',
    generatedAt: null,
    timerInterval: null
};

function getSafeLocalStorage() {
    try {
        if (typeof localStorage !== 'undefined') {
            return localStorage;
        }
    } catch {
        return null;
    }
    return null;
}

/**
 * Return BCP 47 locale tag for the active UI language.
 */
export function getActiveLocale(lang = state.currentLang) {
    return lang === 'EN' ? 'en-US' : 'tr-TR';
}

/**
 * Determine initial language priority:
 * localStorage > navigator.language > Default: TR
 */
export function getInitialLanguage() {
    const storage = getSafeLocalStorage();
    if (storage) {
        try {
            const saved = storage.getItem('openclaim_lang');
            if (saved === 'TR' || saved === 'EN') {
                return saved;
            }
        } catch (e) {
            console.warn('localStorage read error:', e);
        }
    }

    const navLang = (typeof navigator !== 'undefined' && navigator.language ? navigator.language : '').toLowerCase();
    if (navLang.startsWith('tr')) {
        return 'TR';
    }
    if (navLang.startsWith('en')) {
        return 'EN';
    }

    return 'TR';
}

/**
 * Determine initial view mode priority:
 * localStorage > Default: 'grid'
 */
export function getInitialViewMode() {
    const storage = getSafeLocalStorage();
    if (storage) {
        try {
            const saved = storage.getItem('openclaim_view');
            if (saved === 'grid' || saved === 'list') {
                return saved;
            }
        } catch (e) {
            console.warn('localStorage read error:', e);
        }
    }
    return 'grid';
}

/**
 * Determine initial content filter priority:
 * localStorage > Default: 'all'
 */
export function getInitialContentFilter() {
    const storage = getSafeLocalStorage();
    if (storage) {
        try {
            const saved = storage.getItem('openclaim_content');
            if (saved === 'all' || saved === 'games' || saved === 'dlc') {
                return saved;
            }
        } catch (e) {
            console.warn('localStorage read error:', e);
        }
    }
    return 'all';
}

/**
 * Determine initial hide-expired toggle state from localStorage.
 */
export function getInitialHideExpired() {
    const storage = getSafeLocalStorage();
    if (storage) {
        try {
            return storage.getItem('openclaim_hide_expired') === 'true';
        } catch (e) {
            console.warn('localStorage read error:', e);
        }
    }
    return false;
}

/**
 * Load persisted claimed deal IDs from localStorage.
 */
export function getInitialClaimedIds() {
    const storage = getSafeLocalStorage();
    if (storage) {
        try {
            const raw = storage.getItem('openclaim_claimed');
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    return new Set(parsed.filter(id => id !== null && id !== undefined).map(String));
                }
            }
        } catch (e) {
            console.warn('localStorage claimedIds read error:', e);
        }
    }
    return new Set();
}

/**
 * Save current language to localStorage
 */
export function saveLanguage(lang) {
    state.currentLang = lang === 'EN' ? 'EN' : 'TR';
    const storage = getSafeLocalStorage();
    if (storage) {
        try {
            storage.setItem('openclaim_lang', state.currentLang);
        } catch (e) {
            console.warn('localStorage write error:', e);
        }
    }
}

/**
 * Save current view mode to localStorage
 */
export function saveViewMode(mode) {
    state.currentViewMode = mode === 'list' ? 'list' : 'grid';
    const storage = getSafeLocalStorage();
    if (storage) {
        try {
            storage.setItem('openclaim_view', state.currentViewMode);
        } catch (e) {
            console.warn('localStorage write error:', e);
        }
    }
}

/**
 * Save current content filter to localStorage
 */
export function saveContentFilter(filter) {
    state.currentContentFilter = VALID_CONTENTS.has(filter) ? filter : 'all';
    const storage = getSafeLocalStorage();
    if (storage) {
        try {
            storage.setItem('openclaim_content', state.currentContentFilter);
        } catch (e) {
            console.warn('localStorage write error:', e);
        }
    }
}

/**
 * Save hide-expired preference to state and localStorage
 */
export function saveHideExpired(val) {
    state.hideExpired = Boolean(val);
    const storage = getSafeLocalStorage();
    if (storage) {
        try {
            storage.setItem('openclaim_hide_expired', state.hideExpired ? 'true' : 'false');
        } catch (e) {
            console.warn('localStorage write error:', e);
        }
    }
}

/**
 * Persist claimedIds Set to localStorage
 */
export function saveClaimedIds(ids = state.claimedIds) {
    const storage = getSafeLocalStorage();
    if (storage) {
        try {
            storage.setItem('openclaim_claimed', JSON.stringify(Array.from(ids)));
        } catch (e) {
            console.warn('localStorage claimedIds write error:', e);
        }
    }
}

/**
 * Check whether a game ID is marked as claimed
 */
export function isClaimed(id) {
    if (id === null || id === undefined || id === '') return false;
    return state.claimedIds.has(String(id));
}

/**
 * Toggle claimed status for a game ID and persist to localStorage
 * @returns {boolean} New claimed status
 */
export function toggleClaimed(id) {
    if (id === null || id === undefined || id === '') return false;
    const key = String(id);
    if (state.claimedIds.has(key)) {
        state.claimedIds.delete(key);
        saveClaimedIds();
        return false;
    }
    state.claimedIds.add(key);
    saveClaimedIds();
    return true;
}

/**
 * Parse URL query params into valid state overrides and apply them to state.
 * Supported params: platform, content, sort, q, expired
 */
export function readStateFromURL(searchString) {
    const rawSearch = typeof searchString === 'string'
        ? searchString
        : (typeof window !== 'undefined' && window.location ? window.location.search : '');

    const params = new URLSearchParams(rawSearch);
    const parsed = {};

    const platform = params.get('platform');
    if (platform && VALID_PLATFORMS.has(platform)) {
        state.currentPlatformFilter = platform;
        parsed.platform = platform;
    }

    const content = params.get('content');
    if (content && VALID_CONTENTS.has(content)) {
        state.currentContentFilter = content;
        parsed.content = content;
    }

    const sort = params.get('sort');
    if (sort && VALID_SORTS.has(sort)) {
        state.currentSortOption = sort;
        parsed.sort = sort;
    }

    if (params.has('q')) {
        const qRaw = (params.get('q') || '').trim();
        const locale = getActiveLocale();
        state.searchQuery = qRaw.toLocaleLowerCase(locale);
        parsed.q = qRaw;
    }

    const expired = params.get('expired');
    if (expired === 'hide' || expired === '1' || expired === 'true') {
        state.hideExpired = true;
        parsed.expired = true;
    } else if (expired === 'show' || expired === '0' || expired === 'false') {
        state.hideExpired = false;
        parsed.expired = false;
    }

    return parsed;
}

/**
 * Build URLSearchParams representing current non-default filter/sort/search state.
 */
export function buildURLSearchParams(currentState = state) {
    const params = new URLSearchParams();
    if (currentState.currentPlatformFilter && currentState.currentPlatformFilter !== 'all') {
        params.set('platform', currentState.currentPlatformFilter);
    }
    if (currentState.currentContentFilter && currentState.currentContentFilter !== 'all') {
        params.set('content', currentState.currentContentFilter);
    }
    if (currentState.currentSortOption && currentState.currentSortOption !== 'smart') {
        params.set('sort', currentState.currentSortOption);
    }
    if (currentState.searchQuery && currentState.searchQuery.trim() !== '') {
        params.set('q', currentState.searchQuery.trim());
    }
    if (currentState.hideExpired) {
        params.set('expired', 'hide');
    }
    return params;
}

/**
 * Sync current filter/sort/search/expired state to browser URL via history.replaceState.
 */
export function syncStateToURL() {
    if (typeof window === 'undefined' || typeof history === 'undefined' || !window.location) {
        return;
    }
    const params = buildURLSearchParams(state);
    const qs = params.toString();
    const nextUrl = `${window.location.pathname}${qs ? `?${qs}` : ''}${window.location.hash || ''}`;
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash || ''}`;
    if (nextUrl !== currentUrl) {
        try {
            history.replaceState(null, '', nextUrl);
        } catch (e) {
            console.warn('history.replaceState error:', e);
        }
    }
}

/**
 * Map raw platform string to normalized key: steam | epic | amazon | other
 */
export function normalizePlatform(platformStr) {
    if (!platformStr) return 'other';
    const lower = String(platformStr).toLowerCase();
    if (lower.includes('steam')) return 'steam';
    if (lower.includes('epic')) return 'epic';
    if (lower.includes('amazon') || lower.includes('luna') || lower.includes('prime')) return 'amazon';
    return 'other';
}

/**
 * Check whether a game deal has expired at `now`.
 */
export function isGameExpired(game, now = Date.now()) {
    if (!game || !game.end_date) return false;
    const endTime = new Date(game.end_date).getTime();
    return !isNaN(endTime) && endTime <= now;
}

function matchesSearch(game, query, locale) {
    if (!query) return true;
    const titleMatch = (game.title || '').toLocaleLowerCase(locale).includes(query);
    const platformMatch = (game.platform || '').toLocaleLowerCase(locale).includes(query);
    return titleMatch || platformMatch;
}

function matchesContent(game, contentFilter) {
    const contentType = game.content_type || 'game';
    if (contentFilter === 'games' && contentType !== 'game') return false;
    if (contentFilter === 'dlc' && contentType !== 'dlc') return false;
    return true;
}

/**
 * Compute live faceted counts for platform tabs and content filter buttons.
 */
export function getFacetCounts(now = Date.now()) {
    const locale = getActiveLocale();
    const query = (state.searchQuery || '').trim().toLocaleLowerCase(locale);

    const platformCounts = { all: 0, steam: 0, epic: 0, amazon: 0, other: 0 };
    const contentCounts = { all: 0, games: 0, dlc: 0 };

    for (const game of state.games) {
        if (state.hideExpired && isGameExpired(game, now)) continue;
        if (!matchesSearch(game, query, locale)) continue;

        const platformKey = normalizePlatform(game.platform);
        const contentType = game.content_type || 'game';

        // Platform facet counts respect current content filter
        if (matchesContent(game, state.currentContentFilter)) {
            platformCounts.all += 1;
            platformCounts[platformKey] += 1;
        }

        // Content facet counts respect current platform filter
        if (state.currentPlatformFilter === 'all' || platformKey === state.currentPlatformFilter) {
            contentCounts.all += 1;
            if (contentType === 'dlc') {
                contentCounts.dlc += 1;
            } else {
                contentCounts.games += 1;
            }
        }
    }

    return { platform: platformCounts, content: contentCounts };
}

/**
 * Filter and Sort games logic
 * Critical Rule: Expired games (end_date <= now) are ALWAYS sent to the end of the list
 * (or hidden when state.hideExpired is true).
 */
export function getProcessedGames(now = Date.now()) {
    const locale = getActiveLocale();
    const query = (state.searchQuery || '').trim().toLocaleLowerCase(locale);

    // 1. Filter by Content Type, Platform, Search Query, and optional hideExpired
    const filtered = state.games.filter(game => {
        if (!matchesContent(game, state.currentContentFilter)) {
            return false;
        }

        const platformKey = normalizePlatform(game.platform);
        if (state.currentPlatformFilter !== 'all' && platformKey !== state.currentPlatformFilter) {
            return false;
        }

        if (!matchesSearch(game, query, locale)) {
            return false;
        }

        if (state.hideExpired && isGameExpired(game, now)) {
            return false;
        }

        return true;
    });

    // 2. Separate Active Games vs Expired Games
    const activeGames = [];
    const expiredGames = [];

    for (const game of filtered) {
        if (isGameExpired(game, now)) {
            expiredGames.push(game);
        } else {
            activeGames.push(game);
        }
    }

    // Helper comparison function for expiring date
    function compareExpiring(a, b) {
        const timeA = a.end_date ? new Date(a.end_date).getTime() : Infinity;
        const timeB = b.end_date ? new Date(b.end_date).getTime() : Infinity;
        const validA = !isNaN(timeA) ? timeA : Infinity;
        const validB = !isNaN(timeB) ? timeB : Infinity;

        if (validA !== validB) {
            return validA - validB;
        }
        return (a.title || '').localeCompare(b.title || '', locale, { sensitivity: 'base' });
    }

    // Comparison Function based on currentSortOption
    const compareFn = (a, b) => {
        if (state.currentSortOption === 'alphabetical') {
            return (a.title || '').localeCompare(b.title || '', locale, { sensitivity: 'base' });
        }
        if (state.currentSortOption === 'expiring') {
            return compareExpiring(a, b);
        }
        // Default: 'smart' (Smart Sort)
        // 1. Platform alphabetical (Amazon Luna -> Epic Games -> Steam)
        const platformCmp = (a.platform || '').localeCompare(b.platform || '', locale, { sensitivity: 'base' });
        if (platformCmp !== 0) {
            return platformCmp;
        }
        // 2. Inside each platform: expiring soonest
        return compareExpiring(a, b);
    };

    // Sort active and expired subsets independently
    activeGames.sort(compareFn);
    expiredGames.sort(compareFn);

    // Expired games are ALWAYS appended at the very end
    return [...activeGames, ...expiredGames];
}

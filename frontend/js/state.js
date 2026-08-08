/**
 * OpenClaim - State Manager Module
 * Manages application state, filters, sorting, view mode, language,
 * and syncs preferences with localStorage.
 */

// Application State
export const state = {
    games: [],
    currentPlatformFilter: 'all',
    currentSortOption: 'smart',
    currentViewMode: 'grid',
    searchQuery: '',
    currentLang: 'TR',
    timerInterval: null
};

/**
 * Determine initial language priority:
 * localStorage > navigator.language > Default: TR
 */
export function getInitialLanguage() {
    try {
        const saved = localStorage.getItem('openclaim_lang') || localStorage.getItem('lootradar_lang');
        if (saved && (saved === 'TR' || saved === 'EN')) {
            return saved;
        }
    } catch (e) {
        console.warn('localStorage read error:', e);
    }

    const navLang = (navigator.language || '').toLowerCase();
    if (navLang.startsWith('tr')) {
        return 'TR';
    } else if (navLang.startsWith('en')) {
        return 'EN';
    }

    return 'TR';
}

/**
 * Determine initial view mode priority:
 * localStorage > Default: 'grid'
 */
export function getInitialViewMode() {
    try {
        const saved = localStorage.getItem('openclaim_view');
        if (saved && (saved === 'grid' || saved === 'list')) {
            return saved;
        }
    } catch (e) {
        console.warn('localStorage read error:', e);
    }
    return 'grid';
}

/**
 * Save current language to localStorage
 */
export function saveLanguage(lang) {
    state.currentLang = lang;
    try {
        localStorage.setItem('openclaim_lang', lang);
    } catch (e) {
        console.warn('localStorage write error:', e);
    }
}

/**
 * Save current view mode to localStorage
 */
export function saveViewMode(mode) {
    state.currentViewMode = mode === 'list' ? 'list' : 'grid';
    try {
        localStorage.setItem('openclaim_view', state.currentViewMode);
    } catch (e) {
        console.warn('localStorage write error:', e);
    }
}

/**
 * Map raw platform string to normalized key: steam | epic | amazon | other
 */
export function normalizePlatform(platformStr) {
    if (!platformStr) return 'other';
    const lower = platformStr.toLowerCase();
    if (lower.includes('steam')) return 'steam';
    if (lower.includes('epic')) return 'epic';
    if (lower.includes('amazon') || lower.includes('luna') || lower.includes('prime')) return 'amazon';
    return 'other';
}

/**
 * Filter and Sort games logic
 * Critical Rule: Expired games (end_date < now) are ALWAYS sent to the end of the list.
 */
export function getProcessedGames() {
    const now = Date.now();

    // 1. Filter by Platform & Search Query
    const filtered = state.games.filter(game => {
        const platformKey = normalizePlatform(game.platform);
        
        if (state.currentPlatformFilter !== 'all' && platformKey !== state.currentPlatformFilter) {
            return false;
        }

        if (state.searchQuery) {
            const titleMatch = (game.title || '').toLowerCase().includes(state.searchQuery);
            const platformMatch = (game.platform || '').toLowerCase().includes(state.searchQuery);
            return titleMatch || platformMatch;
        }

        return true;
    });

    // 2. Separate Active Games vs Expired Games
    const activeGames = [];
    const expiredGames = [];

    filtered.forEach(game => {
        if (game.end_date) {
            const endTime = new Date(game.end_date).getTime();
            if (!isNaN(endTime) && endTime <= now) {
                expiredGames.push(game);
                return;
            }
        }
        activeGames.push(game);
    });

    // Helper comparison function for expiring date
    function compareExpiring(a, b) {
        const timeA = a.end_date ? new Date(a.end_date).getTime() : Infinity;
        const timeB = b.end_date ? new Date(b.end_date).getTime() : Infinity;
        const validA = !isNaN(timeA) ? timeA : Infinity;
        const validB = !isNaN(timeB) ? timeB : Infinity;

        if (validA !== validB) {
            return validA - validB;
        }
        return (a.title || '').localeCompare(b.title || '', undefined, { sensitivity: 'base' });
    }

    // Comparison Function based on currentSortOption
    const compareFn = (a, b) => {
        if (state.currentSortOption === 'alphabetical') {
            return (a.title || '').localeCompare(b.title || '', undefined, { sensitivity: 'base' });
        } else if (state.currentSortOption === 'expiring') {
            return compareExpiring(a, b);
        } else {
            // Default: 'smart' (Smart Sort)
            // 1. Platform alphabetical (Amazon Luna -> Epic Games -> Steam)
            const pA = (a.platform || '').toLowerCase();
            const pB = (b.platform || '').toLowerCase();
            if (pA !== pB) {
                return pA.localeCompare(pB);
            }
            // 2. Inside each platform: expiring soonest
            return compareExpiring(a, b);
        }
    };

    // Sort active and expired subsets independently
    activeGames.sort(compareFn);
    expiredGames.sort(compareFn);

    // Expired games are ALWAYS appended at the very end
    return [...activeGames, ...expiredGames];
}

/**
 * OpenClaim - Main Frontend Entry Point (ES6 Module)
 * Connects API, State, i18n, and UI modules, binds event listeners,
 * and initializes the application.
 */

import { fetchGamesData } from './api.js';
import {
    state,
    getActiveLocale,
    getInitialLanguage,
    getInitialViewMode,
    getInitialContentFilter,
    getInitialHideExpired,
    getInitialHideClaimed,
    getInitialClaimedIds,
    saveHideExpired,
    saveHideClaimed,
    toggleClaimed,
    readStateFromURL,
    syncStateToURL
} from './state.js';
import { setLanguage, translations } from './i18n.js';
import {
    getElements,
    showSkeletonLoaders,
    applyViewMode,
    applyContentFilter,
    applyPlatformFilterUI,
    updateStatsRibbon,
    renderGames,
    startTimerLoop,
    renderErrorState,
    toggleClearSearchButton,
    setupImageErrorDelegation
} from './ui.js';

const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000;
let footerIntervalId = null;
let debouncedSearchRender = null;
let listenersBound = false;
let shareCopiedTimeoutId = null;

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function formatRelativeTime(targetMs, locale) {
    const diffSeconds = Math.round((targetMs - Date.now()) / 1000);
    const absSeconds = Math.abs(diffSeconds);

    if (typeof Intl === 'undefined' || typeof Intl.RelativeTimeFormat !== 'function') {
        return '';
    }

    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
    if (absSeconds < 60) {
        return rtf.format(diffSeconds, 'second');
    }
    const diffMinutes = Math.round(diffSeconds / 60);
    if (Math.abs(diffMinutes) < 60) {
        return rtf.format(diffMinutes, 'minute');
    }
    const diffHours = Math.round(diffMinutes / 60);
    if (Math.abs(diffHours) < 24) {
        return rtf.format(diffHours, 'hour');
    }
    const diffDays = Math.round(diffHours / 24);
    return rtf.format(diffDays, 'day');
}

function renderFooterTimestamp() {
    const { lastUpdatedEl } = getElements();
    if (!lastUpdatedEl) return;

    if (!state.generatedAt) {
        lastUpdatedEl.textContent = '';
        lastUpdatedEl.classList.remove('is-stale');
        lastUpdatedEl.hidden = true;
        return;
    }

    const parsedDate = new Date(state.generatedAt);
    const ms = parsedDate.getTime();
    if (isNaN(ms)) {
        lastUpdatedEl.textContent = '';
        lastUpdatedEl.classList.remove('is-stale');
        lastUpdatedEl.hidden = true;
        return;
    }

    const locale = getActiveLocale();
    const t = translations[state.currentLang] || translations.TR;
    const formattedDate = new Intl.DateTimeFormat(locale, {
        dateStyle: 'medium',
        timeStyle: 'short'
    }).format(parsedDate);
    const relativeStr = formatRelativeTime(ms, locale);

    let text = (t.footer_last_updated || 'Last updated: {date} ({relative})')
        .replace('{date}', formattedDate)
        .replace('{relative}', relativeStr);

    const isStale = (Date.now() - ms) > STALE_THRESHOLD_MS;
    if (isStale) {
        const staleLabel = t.footer_stale_warning || 'Stale data (>24h)';
        text += ` · ${staleLabel}`;
    }

    lastUpdatedEl.textContent = text;
    lastUpdatedEl.classList.toggle('is-stale', isStale);
    lastUpdatedEl.hidden = false;
}

function renderCurrentState() {
    renderFooterTimestamp();
    if (state.hasError) {
        renderErrorState(state.errorMessage);
        return;
    }
    if (!state.isLoading) {
        renderGames(resetAllFilters);
    }
}

function syncControlsFromState() {
    const { searchInput, sortSelect, hideExpiredCheckbox, hideClaimedCheckbox } = getElements();
    if (searchInput) searchInput.value = state.searchQuery || '';
    if (sortSelect) sortSelect.value = state.currentSortOption || 'smart';
    if (hideExpiredCheckbox) hideExpiredCheckbox.checked = Boolean(state.hideExpired);
    if (hideClaimedCheckbox) hideClaimedCheckbox.checked = Boolean(state.hideClaimed);
    toggleClearSearchButton();
    applyPlatformFilterUI();
    applyContentFilter(state.currentContentFilter, false);
}

async function initApp() {
    state.currentLang = getInitialLanguage();
    state.currentViewMode = getInitialViewMode();
    state.currentContentFilter = getInitialContentFilter();
    state.hideExpired = getInitialHideExpired();
    state.hideClaimed = getInitialHideClaimed();
    state.claimedIds = getInitialClaimedIds();

    // Apply URL query overrides (without clobbering saved localStorage defaults)
    readStateFromURL();

    state.isLoading = true;
    state.hasError = false;
    state.errorMessage = '';

    setLanguage(state.currentLang, null, false);
    applyViewMode(state.currentViewMode, false);
    syncControlsFromState();

    showSkeletonLoaders();
    setupEventListeners();

    try {
        const { games, generatedAt } = await fetchGamesData();
        state.isLoading = false;
        state.hasError = false;
        state.errorMessage = '';
        state.games = games;
        state.generatedAt = generatedAt;

        renderFooterTimestamp();
        if (footerIntervalId) clearInterval(footerIntervalId);
        footerIntervalId = setInterval(renderFooterTimestamp, 60_000);
        updateStatsRibbon();
        renderGames(resetAllFilters);
        startTimerLoop(() => renderGames(resetAllFilters));
    } catch (error) {
        console.error('games.json fetch error:', error);
        state.isLoading = false;
        state.hasError = true;
        state.errorMessage = error && error.message ? error.message : 'Unknown error';
        renderErrorState(state.errorMessage);
    }
}

function resetAllFilters() {
    const { searchInput, sortSelect, hideExpiredCheckbox, hideClaimedCheckbox } = getElements();

    debouncedSearchRender?.cancel();
    if (searchInput) searchInput.value = '';
    state.searchQuery = '';
    state.currentPlatformFilter = 'all';
    state.currentSortOption = 'smart';
    state.hideExpired = false;
    state.hideClaimed = false;
    if (sortSelect) sortSelect.value = 'smart';
    if (hideExpiredCheckbox) hideExpiredCheckbox.checked = false;
    if (hideClaimedCheckbox) hideClaimedCheckbox.checked = false;

    toggleClearSearchButton();
    // Do NOT overwrite localStorage openclaim_content preference on temporary filter reset
    applyContentFilter('all', false);
    applyPlatformFilterUI();
    syncStateToURL();

    renderGames(resetAllFilters);
}

function scrollToTop() {
    const prefersReducedMotion = typeof window.matchMedia === 'function'
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({
        top: 0,
        behavior: prefersReducedMotion ? 'auto' : 'smooth'
    });
}

function debounce(fn, delay = 150) {
    let timeoutId;
    const debounced = function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            timeoutId = undefined;
            fn.apply(this, args);
        }, delay);
    };
    debounced.cancel = () => {
        clearTimeout(timeoutId);
        timeoutId = undefined;
    };
    return debounced;
}

function setupEventListeners() {
    const {
        gridContainer,
        searchInput,
        clearSearchBtn,
        sortSelect,
        filterTabsContainer,
        contentFilterContainer,
        viewToggleContainer,
        langToggleContainer,
        hideExpiredCheckbox,
        hideClaimedCheckbox,
        shareFiltersBtn,
        backToTopBtn
    } = getElements();

    // Platform icons in #filter-tabs fallback on CDN failure
    if (filterTabsContainer) {
        setupImageErrorDelegation(filterTabsContainer);
    }

    // Header logo click resets filters and scrolls to top without appending '#'
    const logoLink = document.querySelector('.logo');
    if (logoLink) {
        logoLink.addEventListener('click', (e) => {
            if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            e.preventDefault();
            resetAllFilters();
            scrollToTop();
        });
    }

    // Delegated click handler on #games-grid for mark-claimed toggle buttons
    if (gridContainer) {
        setupImageErrorDelegation(gridContainer);
        gridContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.claim-toggle-btn');
            if (!btn) return;
            e.preventDefault();
            e.stopPropagation();

            const dealId = btn.dataset.claimId;
            if (!dealId) return;
            toggleClaimed(dealId);
            renderGames(resetAllFilters);
        });
    }

    if (!listenersBound) {
        listenersBound = true;
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                renderFooterTimestamp();
            }
        });

        document.addEventListener('keydown', (e) => {
            const activeSearch = getElements().searchInput;
            if (!activeSearch) return;

            if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
                const target = e.target;
                const tag = target && target.tagName ? target.tagName.toUpperCase() : '';
                if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target?.isContentEditable) {
                    return;
                }
                e.preventDefault();
                activeSearch.focus();
                return;
            }

            if (e.key === 'Escape' && document.activeElement === activeSearch) {
                if (activeSearch.value) {
                    debouncedSearchRender?.cancel();
                    activeSearch.value = '';
                    state.searchQuery = '';
                    toggleClearSearchButton();
                    syncStateToURL();
                    renderGames(resetAllFilters);
                } else {
                    activeSearch.blur();
                }
            }
        });
    }

    // Search Input Listener with 150ms Debounce
    if (searchInput) {
        debouncedSearchRender = debounce(() => {
            syncStateToURL();
            renderGames(resetAllFilters);
        }, 150);

        searchInput.addEventListener('input', (e) => {
            const locale = getActiveLocale();
            state.searchQuery = e.target.value.trim().toLocaleLowerCase(locale);
            toggleClearSearchButton();
            debouncedSearchRender();
        });
    }

    // Clear Search Button
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            debouncedSearchRender?.cancel();
            if (searchInput) {
                searchInput.value = '';
                state.searchQuery = '';
                toggleClearSearchButton();
                syncStateToURL();
                searchInput.focus();
                renderGames(resetAllFilters);
            }
        });
    }

    // Sort Dropdown Listener
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            state.currentSortOption = e.target.value || 'smart';
            syncStateToURL();
            renderGames(resetAllFilters);
        });
    }

    // Hide Expired Toggle Listener
    if (hideExpiredCheckbox) {
        hideExpiredCheckbox.addEventListener('change', (e) => {
            saveHideExpired(e.target.checked);
            syncStateToURL();
            renderGames(resetAllFilters);
        });
    }

    // Hide Claimed Toggle Listener
    if (hideClaimedCheckbox) {
        hideClaimedCheckbox.addEventListener('change', (e) => {
            saveHideClaimed(e.target.checked);
            syncStateToURL();
            renderGames(resetAllFilters);
        });
    }

    // Share Current Filtered URL Button
    if (shareFiltersBtn) {
        shareFiltersBtn.addEventListener('click', async () => {
            syncStateToURL();
            const urlToCopy = window.location.href;
            try {
                if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
                    await navigator.clipboard.writeText(urlToCopy);
                }
                shareFiltersBtn.classList.add('copied');
                if (shareCopiedTimeoutId) clearTimeout(shareCopiedTimeoutId);
                shareCopiedTimeoutId = setTimeout(() => {
                    shareFiltersBtn.classList.remove('copied');
                    shareCopiedTimeoutId = null;
                }, 1800);

                const statusEl = document.getElementById('results-status');
                const t = translations[state.currentLang] || translations.TR;
                if (statusEl && t.share_link_copied) {
                    statusEl.textContent = t.share_link_copied;
                }
            } catch (err) {
                console.warn('Clipboard copy failed:', err);
            }
        });
    }

    // Platform Filter Tabs
    if (filterTabsContainer) {
        filterTabsContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.filter-btn');
            if (!btn) return;

            state.currentPlatformFilter = btn.dataset.platform || 'all';
            applyPlatformFilterUI();
            syncStateToURL();
            renderGames(resetAllFilters);
        });
    }

    // Content Type Filter Listener (All / Games / DLC)
    if (contentFilterContainer) {
        contentFilterContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.content-btn');
            if (!btn) return;
            const filter = btn.dataset.contentFilter;
            if (filter && filter !== state.currentContentFilter) {
                applyContentFilter(filter, true);
                syncStateToURL();
                renderGames(resetAllFilters);
            }
        });
    }

    // View Mode Toggle Listener (Grid / List)
    if (viewToggleContainer) {
        viewToggleContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.view-btn');
            if (!btn) return;
            const mode = btn.dataset.view;
            if (mode && mode !== state.currentViewMode) {
                applyViewMode(mode);
            }
        });
    }

    // Language Toggle Listener
    if (langToggleContainer) {
        langToggleContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-lang-btn]');
            if (!btn) return;
            const lang = btn.dataset.langBtn;
            if (lang && lang !== state.currentLang) {
                // Re-normalize search query under new locale if present
                if (searchInput && searchInput.value) {
                    state.searchQuery = searchInput.value.trim().toLocaleLowerCase(getActiveLocale(lang));
                }
                setLanguage(lang, renderCurrentState);
            }
        });
    }

    // Back to Top Button Listener & Scroll Monitor
    if (backToTopBtn) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 300) {
                backToTopBtn.classList.add('visible');
            } else {
                backToTopBtn.classList.remove('visible');
            }
        }, { passive: true });

        backToTopBtn.addEventListener('click', scrollToTop);
    }
}

// Expose setLanguage globally for window.OpenClaim API
window.OpenClaim = {
    setLanguage: (lang) => {
        const { searchInput } = getElements();
        if (searchInput && searchInput.value) {
            state.searchQuery = searchInput.value.trim().toLocaleLowerCase(getActiveLocale(lang));
        }
        setLanguage(lang, renderCurrentState);
    }
};

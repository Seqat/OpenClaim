/**
 * OpenClaim - Main Frontend Entry Point (ES6 Module)
 * Connects API, State, i18n, and UI modules, binds event listeners,
 * and initializes the application.
 */

import { fetchGamesData } from './api.js';
import { state, getInitialLanguage, getInitialViewMode } from './state.js';
import { setLanguage } from './i18n.js';
import {
    getElements,
    showSkeletonLoaders,
    applyViewMode,
    updateStatsRibbon,
    renderGames,
    startTimerLoop,
    renderErrorState,
    toggleClearSearchButton
} from './ui.js';

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    state.currentLang = getInitialLanguage();
    state.currentViewMode = getInitialViewMode();

    setLanguage(state.currentLang, () => {
        if (state.games.length > 0) renderGames(resetAllFilters);
    });

    applyViewMode(state.currentViewMode);
    showSkeletonLoaders();
    setupEventListeners();

    try {
        const { games, generatedAt } = await fetchGamesData();
        state.games = games;

        if (generatedAt) {
            const footerP = document.querySelector('footer p');
            if (footerP) {
                const formattedDate = new Date(generatedAt).toLocaleString();
                footerP.textContent += ` · Son güncelleme: ${formattedDate}`;
            }
        }

        updateStatsRibbon();
        renderGames(resetAllFilters);
        startTimerLoop();
    } catch (error) {
        console.error('games.json fetch error:', error);
        renderErrorState(error.message);
    }
}

function resetAllFilters() {
    const { searchInput, sortSelect, filterTabsContainer } = getElements();

    if (searchInput) searchInput.value = '';
    state.searchQuery = '';
    state.currentPlatformFilter = 'all';
    state.currentSortOption = 'smart';
    if (sortSelect) sortSelect.value = 'smart';
    toggleClearSearchButton();

    if (filterTabsContainer) {
        const allTabs = filterTabsContainer.querySelectorAll('.filter-btn');
        allTabs.forEach(t => {
            const isAll = t.dataset.platform === 'all';
            t.classList.toggle('active', isAll);
            t.setAttribute('aria-selected', isAll ? 'true' : 'false');
        });
    }

    renderGames(resetAllFilters);
}

function debounce(fn, delay = 150) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

function setupEventListeners() {
    const {
        searchInput,
        clearSearchBtn,
        sortSelect,
        filterTabsContainer,
        viewToggleContainer,
        langToggleContainer,
        backToTopBtn
    } = getElements();

    // Search Input Listener with 150ms Debounce
    if (searchInput) {
        const debouncedRender = debounce(() => {
            renderGames(resetAllFilters);
        }, 150);

        searchInput.addEventListener('input', (e) => {
            state.searchQuery = e.target.value.trim().toLowerCase();
            toggleClearSearchButton();
            debouncedRender();
        });
    }

    // Clear Search Button
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            if (searchInput) {
                searchInput.value = '';
                state.searchQuery = '';
                toggleClearSearchButton();
                searchInput.focus();
                renderGames(resetAllFilters);
            }
        });
    }

    // Sort Dropdown Listener
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            state.currentSortOption = e.target.value || 'smart';
            renderGames(resetAllFilters);
        });
    }

    // Platform Filter Tabs
    if (filterTabsContainer) {
        filterTabsContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.filter-btn');
            if (!btn) return;

            const allTabs = filterTabsContainer.querySelectorAll('.filter-btn');
            allTabs.forEach(t => {
                t.classList.remove('active');
                t.setAttribute('aria-selected', 'false');
            });

            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');

            state.currentPlatformFilter = btn.dataset.platform || 'all';
            renderGames(resetAllFilters);
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
                setLanguage(lang, () => renderGames(resetAllFilters));
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

        backToTopBtn.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
}

// Expose setLanguage globally for window.OpenClaim API
window.OpenClaim = {
    setLanguage: (lang) => setLanguage(lang, () => renderGames(resetAllFilters))
};

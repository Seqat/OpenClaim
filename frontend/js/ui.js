/**
 * OpenClaim - UI Rendering Engine Module
 * Renders game cards, skeleton loading states, empty/error states,
 * stats ribbon, view mode toggles, and live countdown timers.
 */

import { state, getProcessedGames, normalizePlatform, saveViewMode } from './state.js';
import { translations } from './i18n.js';

// Simple Icons CDN URLs
export const PLATFORM_LOGOS = {
    steam: 'https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/steam.svg',
    epic: 'https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/epicgames.svg',
    amazon: 'https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/amazonluna.svg'
};

// Generic Gamepad SVG for non-mainstream platforms
export const GAMEPAD_ICON_SVG = `<svg class="platform-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><rect x="2" y="6" width="20" height="12" rx="4"/><path d="M6 12h4m-2-2v4m7-2h.01m3 0h.01"/></svg>`;

// DOM Elements
export function getElements() {
    return {
        gridContainer: document.getElementById('games-grid'),
        searchInput: document.getElementById('search-input'),
        clearSearchBtn: document.getElementById('clear-search-btn'),
        sortSelect: document.getElementById('sort-select'),
        filterTabsContainer: document.getElementById('filter-tabs'),
        viewToggleContainer: document.getElementById('view-toggle'),
        langToggleContainer: document.getElementById('lang-toggle'),
        backToTopBtn: document.getElementById('back-to-top'),
        totalCountEl: document.getElementById('total-count'),
        steamCountEl: document.getElementById('steam-count'),
        epicCountEl: document.getElementById('epic-count'),
        amazonCountEl: document.getElementById('amazon-count')
    };
}

/**
 * Render skeleton cards while fetching data
 */
export function showSkeletonLoaders() {
    const { gridContainer } = getElements();
    if (!gridContainer) return;
    const skeletons = Array(8).fill(0).map(() => `
        <div class="skeleton-card">
            <div class="skeleton-media"></div>
            <div class="skeleton-body">
                <div class="skeleton-line meta"></div>
                <div class="skeleton-line title"></div>
                <div class="skeleton-line btn"></div>
            </div>
        </div>
    `).join('');
    gridContainer.innerHTML = skeletons;
}

/**
 * Apply View Mode ('grid' or 'list') to container and toggle buttons
 */
export function applyViewMode(mode) {
    saveViewMode(mode);
    const { gridContainer, viewToggleContainer } = getElements();

    if (gridContainer) {
        gridContainer.classList.toggle('view-list', state.currentViewMode === 'list');
    }

    if (viewToggleContainer) {
        const btns = viewToggleContainer.querySelectorAll('.view-btn');
        btns.forEach(btn => {
            const isMatch = btn.dataset.view === state.currentViewMode;
            btn.classList.toggle('active', isMatch);
            btn.setAttribute('aria-pressed', isMatch ? 'true' : 'false');
        });
    }
}

/**
 * Toggle visibility of clear search button
 */
export function toggleClearSearchButton() {
    const { clearSearchBtn } = getElements();
    if (!clearSearchBtn) return;
    clearSearchBtn.style.display = state.searchQuery.length > 0 ? 'inline-flex' : 'none';
}

/**
 * Calculate stats for stats ribbon
 */
export function updateStatsRibbon() {
    const { totalCountEl, steamCountEl, epicCountEl, amazonCountEl } = getElements();
    const total = state.games.length;
    const steam = state.games.filter(g => normalizePlatform(g.platform) === 'steam').length;
    const epic = state.games.filter(g => normalizePlatform(g.platform) === 'epic').length;
    const amazon = state.games.filter(g => normalizePlatform(g.platform) === 'amazon').length;

    if (totalCountEl) totalCountEl.textContent = total;
    if (steamCountEl) steamCountEl.textContent = steam;
    if (epicCountEl) epicCountEl.textContent = epic;
    if (amazonCountEl) amazonCountEl.textContent = amazon;
}

function safeUrl(url, fallback = '#') {
    const s = String(url || '').trim();
    return /^https?:\/\//i.test(s) ? s : fallback;
}

/**
 * Generate HTML string for single game card
 */
export function createGameCardHTML(game) {
    const platformKey = normalizePlatform(game.platform);
    const isPermanent = game.is_permanent ?? true;
    const t = translations[state.currentLang] || translations.TR;

    let platformLabel = 'PC';
    let platformImgTag = '';

    if (platformKey === 'steam') {
        platformLabel = 'Steam';
        platformImgTag = `<img src="${PLATFORM_LOGOS.steam}" alt="Steam" class="platform-icon" />`;
    } else if (platformKey === 'epic') {
        platformLabel = 'Epic Games';
        platformImgTag = `<img src="${PLATFORM_LOGOS.epic}" alt="Epic Games" class="platform-icon" />`;
    } else if (platformKey === 'amazon') {
        platformLabel = 'Amazon Prime';
        platformImgTag = `<img src="${PLATFORM_LOGOS.amazon}" alt="Amazon Prime" class="platform-icon" />`;
    } else {
        platformLabel = escapeHTML(game.platform || 'PC');
        platformImgTag = GAMEPAD_ICON_SVG;
    }

    const validatedImage = safeUrl(game.image_url, '');
    const hasImage = Boolean(validatedImage);
    const imageSrc = hasImage ? escapeAttribute(validatedImage) : '';

    const storeUrl = escapeAttribute(safeUrl(game.store_url));
    const safeTitle = escapeHTML(game.title || 'Game');
    const endDateAttr = game.end_date ? escapeAttribute(game.end_date) : '';
    const claimAria = escapeAttribute((t.card_claim_aria || '').replace('{title}', game.title || 'Game'));

    return `
        <article class="game-card" data-id="${escapeAttribute(game.id || '')}">
            <div class="card-media">
                ${hasImage ? `
                    <img 
                        src="${imageSrc}" 
                        alt="${safeTitle}" 
                        class="card-img" 
                        loading="lazy" 
                    >
                ` : ''}
                <div class="card-img-fallback" style="${hasImage ? 'display: none;' : 'display: flex;'}">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 002-2V7a2 2 0 00-2-2H5z" />
                    </svg>
                    <span>${safeTitle}</span>
                </div>
            </div>

            <div class="card-body">
                <div class="card-info-section">
                    <div class="card-meta-row">
                        <div class="platform-badge ${platformKey}">
                            ${platformImgTag}
                            <span>${platformLabel}</span>
                        </div>
                        <div 
                            class="countdown-badge" 
                            data-end-date="${endDateAttr}"
                            data-is-permanent="${isPermanent}"
                        >
                            ${t.timer_calculating}
                        </div>
                    </div>

                    <h3 class="card-title" title="${safeTitle}">${safeTitle}</h3>
                </div>

                <div class="card-actions-row">
                    <a 
                        href="${storeUrl}" 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        class="claim-btn"
                        aria-label="${claimAria}"
                    >
                        <span>${t.card_claim_btn}</span>
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                        </svg>
                    </a>
                </div>
            </div>
        </article>
    `;
}

let cachedTimerEls = null;

document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        updateAllTimers();
    }
});

/**
 * Render game cards grid/list
 */
export function renderGames(onResetFilters) {
    const { gridContainer } = getElements();
    if (!gridContainer) return;
    const processed = getProcessedGames();
    const t = translations[state.currentLang] || translations.TR;

    const statusEl = document.getElementById('results-status');
    if (statusEl) {
        const statusText = (t.results_count || '{count} results found').replace('{count}', processed.length);
        statusEl.textContent = statusText;
    }

    if (processed.length === 0) {
        cachedTimerEls = null;
        renderEmptyState(onResetFilters);
        return;
    }

    gridContainer.innerHTML = processed.map(game => createGameCardHTML(game)).join('');

    const cardImgs = gridContainer.querySelectorAll('.card-img');
    cardImgs.forEach(img => {
        img.addEventListener('error', () => {
            img.style.display = 'none';
            if (img.nextElementSibling) {
                img.nextElementSibling.style.display = 'flex';
            }
        });
    });
    
    cachedTimerEls = null;
    // Immediately update timers for newly rendered cards
    updateAllTimers();
}

/**
 * Start timer loop that ticks every 1 second
 */
export function startTimerLoop() {
    if (state.timerInterval) clearInterval(state.timerInterval);
    state.timerInterval = setInterval(updateAllTimers, 1000);
}

/**
 * Update countdown text on all displayed cards
 */
export function updateAllTimers() {
    if (document.hidden) return;

    if (!cachedTimerEls) {
        cachedTimerEls = document.querySelectorAll('.countdown-badge');
    }
    const timerEls = cachedTimerEls;
    const now = Date.now();
    const t = translations[state.currentLang] || translations.TR;

    timerEls.forEach(el => {
        const endDateStr = el.dataset.endDate;
        const isPermanent = el.dataset.isPermanent === 'true';

        if (!endDateStr || endDateStr.trim() === '' || endDateStr === 'null') {
            if (isPermanent) {
                el.textContent = t.timer_unlimited;
                el.className = 'countdown-badge no-expiry';
            } else {
                el.textContent = t.timer_limited;
                el.className = 'countdown-badge';
            }
            return;
        }

        const targetTime = new Date(endDateStr).getTime();
        
        if (isNaN(targetTime)) {
            el.textContent = isPermanent ? t.timer_permanent_short : t.timer_limited_short;
            el.className = 'countdown-badge';
            return;
        }

        const diff = targetTime - now;

        if (diff <= 0) {
            el.textContent = t.timer_expired;
            el.className = 'countdown-badge expired';
        } else {
            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((diff % (1000 * 60)) / 1000);

            let formatted = '';
            if (days > 0) {
                formatted = `${days}${t.timer_day_unit} ${padZero(hours)}${t.timer_hour_unit} ${padZero(minutes)}${t.timer_minute_unit}`;
            } else {
                formatted = `${padZero(hours)}${t.timer_hour_unit} ${padZero(minutes)}${t.timer_minute_unit} ${padZero(seconds)}${t.timer_second_unit}`;
            }

            el.textContent = formatted;

            if (diff < 24 * 60 * 60 * 1000) {
                el.className = 'countdown-badge urgent';
            } else {
                el.className = 'countdown-badge';
            }
        }
    });
}

/**
 * Render empty state when search/filter returns zero games
 */
export function renderEmptyState(onResetFilters) {
    cachedTimerEls = null;
    const { gridContainer } = getElements();
    if (!gridContainer) return;
    const t = translations[state.currentLang] || translations.TR;
    gridContainer.innerHTML = `
        <div class="empty-state">
            <svg class="empty-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 class="empty-title">${t.empty_title}</h3>
            <p class="empty-desc">${t.empty_desc}</p>
            <button type="button" class="reset-filter-btn" id="reset-filters-btn">
                ${t.empty_reset_btn}
            </button>
        </div>
    `;

    const resetBtn = document.getElementById('reset-filters-btn');
    if (resetBtn && typeof onResetFilters === 'function') {
        resetBtn.addEventListener('click', onResetFilters);
    }
}

/**
 * Render error state if games.json fails to fetch
 */
export function renderErrorState(message) {
    const { gridContainer } = getElements();
    if (!gridContainer) return;
    const t = translations[state.currentLang] || translations.TR;
    const errDesc = (t.error_desc || '').replace('{error}', escapeHTML(message));

    gridContainer.innerHTML = `
        <div class="empty-state">
            <svg class="empty-icon" style="color: #ef4444;" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h3 class="empty-title">${t.error_title}</h3>
            <p class="empty-desc">${errDesc}</p>
            <button type="button" class="reset-filter-btn" id="error-refresh-btn">
                ${t.error_refresh_btn}
            </button>
        </div>
    `;

    const refreshBtn = document.getElementById('error-refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => location.reload());
    }
}

function padZero(num) {
    return num < 10 ? `0${num}` : num;
}

export function escapeHTML(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

export function escapeAttribute(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/**
 * OpenClaim - UI Rendering Engine Module
 * Renders game cards, skeleton loading states, empty/error states,
 * stats ribbon, faceted counts, view mode toggles, and live countdown timers.
 */

import {
    state,
    getProcessedGames,
    getFacetCounts,
    normalizePlatform,
    isClaimed,
    saveViewMode,
    saveContentFilter
} from './state.js';
import { translations } from './i18n.js';

// Simple Icons CDN URLs
export const PLATFORM_LOGOS = {
    steam: 'https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/steam.svg',
    epic: 'https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/epicgames.svg',
    amazon: 'https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/amazonluna.svg'
};

// Generic Gamepad SVG for non-mainstream platforms
export const GAMEPAD_ICON_SVG = `<svg class="platform-icon" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><rect x="2" y="6" width="20" height="12" rx="4"/><path d="M6 12h4m-2-2v4m7-2h.01m3 0h.01"/></svg>`;

// Inline fallback SVGs when CDN platform icons fail to load
export const PLATFORM_FALLBACK_SVGS = {
    steam: `<svg class="platform-icon" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M12 2a10 10 0 0 0-9.95 9.04l5.33 2.2a2.84 2.84 0 0 1 1.6-.49l2.4-3.47v-.05a3.78 3.78 0 1 1 3.78 3.78h-.09l-3.42 2.44a2.85 2.85 0 0 1-5.6.86L2.46 14.8A10 10 0 1 0 12 2zm-3.02 15.22a2.14 2.14 0 1 0 2.14-2.14h-.05l1.02.42a1.57 1.57 0 1 1-1.2 2.9l-.91-.38a2.14 2.14 0 0 0-1-.8zm6.18-6.48a2.52 2.52 0 1 0-2.52-2.52 2.52 2.52 0 0 0 2.52 2.52z"/></svg>`,
    epic: `<svg class="platform-icon" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M4 3h16a1 1 0 0 1 1 1v11.6a2 2 0 0 1-.82 1.62l-7.6 5.54a1 1 0 0 1-1.16 0l-7.6-5.54A2 2 0 0 1 3 15.6V4a1 1 0 0 1 1-1zm3.5 3.5v10h2.2v-4h3.6v-2H9.7v-2h4.2v-2H7.5z"/></svg>`,
    amazon: `<svg class="platform-icon" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M12 3a9 9 0 0 0-8.48 12.02 6.5 6.5 0 0 1 11.4-4.78 4.5 4.5 0 0 0-5.74 6.66A7 7 0 0 0 21 12a9 9 0 0 0-9-9zm-7.5 14.2c3.8 2.9 11.2 3.1 15.2.3.4-.3.1-.9-.4-.7-4.1 1.6-10.3 1.4-14.3-.3-.5-.2-.9.4-.5.7z"/></svg>`
};

const CLAIM_ARROW_SVG = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>`;
const CHECK_ICON_SVG = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.25"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>`;
const FALLBACK_MEDIA_SVG = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><rect x="2" y="6" width="20" height="12" rx="4" stroke-width="1.5"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M6 12h4m-2-2v4m7-2h.01m3 0h.01"/></svg>`;

// DOM Elements
export function getElements() {
    if (typeof document === 'undefined') return {};
    return {
        gridContainer: document.getElementById('games-grid'),
        searchInput: document.getElementById('search-input'),
        clearSearchBtn: document.getElementById('clear-search-btn'),
        sortSelect: document.getElementById('sort-select'),
        filterTabsContainer: document.getElementById('filter-tabs'),
        contentFilterContainer: document.getElementById('content-filter'),
        viewToggleContainer: document.getElementById('view-toggle'),
        langToggleContainer: document.getElementById('lang-toggle'),
        hideExpiredCheckbox: document.getElementById('hide-expired-checkbox'),
        backToTopBtn: document.getElementById('back-to-top'),
        totalCountEl: document.getElementById('total-count'),
        steamCountEl: document.getElementById('steam-count'),
        epicCountEl: document.getElementById('epic-count'),
        amazonCountEl: document.getElementById('amazon-count'),
        lastUpdatedEl: document.getElementById('last-updated')
    };
}

/**
 * Replace a broken platform CDN <img> with its inline SVG fallback.
 */
export function handlePlatformIconError(imgEl) {
    if (!imgEl || !imgEl.parentNode) return;
    const key = imgEl.dataset.platformIcon;
    const svgHTML = (key && PLATFORM_FALLBACK_SVGS[key]) ? PLATFORM_FALLBACK_SVGS[key] : GAMEPAD_ICON_SVG;
    const tpl = document.createElement('template');
    tpl.innerHTML = svgHTML.trim();
    const svgNode = tpl.content.firstElementChild;
    if (svgNode) {
        imgEl.replaceWith(svgNode);
    }
}

/**
 * Attach capture-phase error listener once to a container for card & platform images.
 */
export function setupImageErrorDelegation(container) {
    if (!container || container.dataset.imgErrorDelegated === 'true') return;
    container.dataset.imgErrorDelegated = 'true';
    container.addEventListener('error', (e) => {
        const target = e.target;
        if (!target || target.tagName !== 'IMG') return;

        if (target.classList.contains('card-img')) {
            target.style.display = 'none';
            if (target.nextElementSibling && target.nextElementSibling.classList.contains('card-img-fallback')) {
                target.nextElementSibling.style.display = 'flex';
            }
        } else if (target.classList.contains('platform-icon')) {
            handlePlatformIconError(target);
        }
    }, true);
}

/**
 * Render skeleton cards while fetching data
 */
export function showSkeletonLoaders() {
    const { gridContainer } = getElements();
    if (!gridContainer) return;
    const skeletons = Array(8).fill(0).map(() => `
        <div class="skeleton-card" aria-hidden="true">
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
 * Apply Content Filter ('all', 'games', 'dlc') to toggle buttons and state.
 * Pass persist=false when resetting temporarily or loading from URL.
 */
export function applyContentFilter(filter, persist = true) {
    const normalized = (filter === 'games' || filter === 'dlc') ? filter : 'all';
    if (persist) {
        saveContentFilter(normalized);
    } else {
        state.currentContentFilter = normalized;
    }

    const { contentFilterContainer } = getElements();
    if (contentFilterContainer) {
        const btns = contentFilterContainer.querySelectorAll('.content-btn');
        btns.forEach(btn => {
            const isMatch = btn.dataset.contentFilter === state.currentContentFilter;
            btn.classList.toggle('active', isMatch);
            btn.setAttribute('aria-pressed', isMatch ? 'true' : 'false');
        });
    }
}

/**
 * Sync platform tabs UI active/aria-pressed states with state.currentPlatformFilter.
 */
export function applyPlatformFilterUI() {
    const { filterTabsContainer } = getElements();
    if (!filterTabsContainer) return;
    const allTabs = filterTabsContainer.querySelectorAll('.filter-btn');
    allTabs.forEach(t => {
        const isMatch = (t.dataset.platform || 'all') === state.currentPlatformFilter;
        t.classList.toggle('active', isMatch);
        t.setAttribute('aria-pressed', isMatch ? 'true' : 'false');
    });
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
 * Calculate stats for header stats ribbon
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

/**
 * Update live faceted counts on platform tabs and content filter buttons.
 */
export function updateFacetCounts() {
    if (typeof document === 'undefined') return;
    const counts = getFacetCounts();

    const platformBadges = document.querySelectorAll('#filter-tabs [data-count-for]');
    platformBadges.forEach(badge => {
        const key = badge.dataset.countFor;
        if (key && Object.hasOwn(counts.platform, key)) {
            badge.textContent = counts.platform[key];
        }
    });

    const contentBadges = document.querySelectorAll('#content-filter [data-count-for]');
    contentBadges.forEach(badge => {
        const key = badge.dataset.countFor;
        if (key && Object.hasOwn(counts.content, key)) {
            badge.textContent = counts.content[key];
        }
    });
}

/**
 * Validate URL using the WHATWG URL parser, allowing only http: and https:.
 */
export function safeUrl(url, fallback = '#') {
    const s = String(url || '').trim();
    if (!s) return fallback;
    try {
        const parsed = new URL(s);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
            return parsed.href;
        }
    } catch {
        return fallback;
    }
    return fallback;
}

// Known notice codes -> i18n keys. Unknown codes from games.json are ignored.
const NOTICE_I18N_KEYS = {
    alienware_arena: 'notice_alienware_arena',
    amd_account: 'notice_amd_account',
    dungeonloot_account: 'notice_dungeonloot_account',
    newsletter_signup: 'notice_newsletter_signup',
    redeem_in_game: 'notice_redeem_in_game'
};

const NOTICE_ICON_SVG = `<svg class="notice-icon" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4m0 4h.01"/></svg>`;

/**
 * Translated notice lines for a game. Missing/null/non-array `notices`
 * (older games.json) and unknown codes yield no lines.
 */
export function getNoticeLines(game, t) {
    if (!game || !t) return [];
    const codes = Array.isArray(game.notices) ? game.notices : [];
    const lines = [];
    for (const code of new Set(codes)) {
        if (typeof code !== 'string' || !Object.hasOwn(NOTICE_I18N_KEYS, code)) continue;
        const text = t[NOTICE_I18N_KEYS[code]];
        if (text) lines.push(text);
    }
    return lines;
}

function getPlatformPresentation(game) {
    const platformKey = normalizePlatform(game.platform);
    if (platformKey === 'steam') {
        return {
            platformKey,
            platformLabel: 'Steam',
            platformImgTag: `<img src="${PLATFORM_LOGOS.steam}" alt="" data-platform-icon="steam" class="platform-icon" />`
        };
    }
    if (platformKey === 'epic') {
        return {
            platformKey,
            platformLabel: 'Epic Games',
            platformImgTag: `<img src="${PLATFORM_LOGOS.epic}" alt="" data-platform-icon="epic" class="platform-icon" />`
        };
    }
    if (platformKey === 'amazon') {
        return {
            platformKey,
            platformLabel: 'Amazon Prime',
            platformImgTag: `<img src="${PLATFORM_LOGOS.amazon}" alt="" data-platform-icon="amazon" class="platform-icon" />`
        };
    }
    return {
        platformKey,
        platformLabel: escapeHTML(game.platform || 'PC'),
        platformImgTag: GAMEPAD_ICON_SVG
    };
}

/**
 * Generate HTML string for single game card
 */
export function createGameCardHTML(game) {
    const isPermanent = game.is_permanent ?? true;
    const isDLC = (game.content_type === 'dlc');
    const t = translations[state.currentLang] || translations.TR;
    const { platformKey, platformLabel, platformImgTag } = getPlatformPresentation(game);

    const validatedImage = safeUrl(game.image_url, '');
    const hasImage = Boolean(validatedImage);
    const imageSrc = hasImage ? escapeAttribute(validatedImage) : '';

    const storeUrl = escapeAttribute(safeUrl(game.store_url));
    const safeTitle = escapeHTML(game.title || 'Game');
    const endDateAttr = game.end_date ? escapeAttribute(game.end_date) : '';
    const isPermanentAttr = escapeAttribute(String(isPermanent));
    const gameIdAttr = escapeAttribute(game.id || '');
    const claimAria = escapeAttribute((t.card_claim_aria || '').replace('{title}', game.title || 'Game'));

    const claimed = isClaimed(game.id);
    const claimMarkText = claimed ? (t.card_claimed_badge || 'Claimed') : (t.card_mark_claimed || 'Mark Claimed');
    const claimToggleAria = escapeAttribute(
        ((claimed ? t.card_unclaim_aria : t.card_claim_mark_aria) || '').replace('{title}', game.title || 'Game')
    );

    const noticeLines = getNoticeLines(game, t);
    const noticesHTML = noticeLines.length
        ? `<ul class="card-notices">${noticeLines.map(line => `<li class="card-notice">${NOTICE_ICON_SVG}<span>${escapeHTML(line)}</span></li>`).join('')}</ul>`
        : '';

    return `
        <article class="game-card${claimed ? ' is-claimed' : ''}" data-id="${gameIdAttr}" data-image-url="${imageSrc}">
            <div class="card-media">
                ${hasImage ? `
                    <img 
                        src="${imageSrc}" 
                        alt="${safeTitle}" 
                        class="card-img" 
                        loading="lazy" 
                        decoding="async" 
                        referrerpolicy="no-referrer"
                    >
                ` : ''}
                <div class="card-img-fallback" style="${hasImage ? 'display: none;' : 'display: flex;'}">
                    ${FALLBACK_MEDIA_SVG}
                    <span>${safeTitle}</span>
                </div>
            </div>

            <div class="card-body">
                <div class="card-info-section${noticesHTML ? ' has-notices' : ''}">
                    <div class="card-meta-row">
                        <div class="card-meta-left">
                            <div class="platform-badge ${platformKey}">
                                ${platformImgTag}
                                <span>${platformLabel}</span>
                            </div>
                            ${isDLC ? `<span class="dlc-badge">${escapeHTML(t.card_dlc_badge || 'DLC')}</span>` : ''}
                        </div>
                        <div 
                            class="countdown-badge" 
                            data-end-date="${endDateAttr}"
                            data-is-permanent="${isPermanentAttr}"
                        >
                            ${t.timer_calculating}
                        </div>
                    </div>

                    <h2 class="card-title" title="${safeTitle}">${safeTitle}</h2>
                    ${noticesHTML}
                </div>

                <div class="card-actions-row">
                    <a 
                        href="${storeUrl}" 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        class="claim-btn"
                        aria-label="${claimAria}"
                    >
                        <span>${escapeHTML(t.card_claim_btn)}</span>
                        ${CLAIM_ARROW_SVG}
                    </a>
                    ${gameIdAttr ? `
                        <button
                            type="button"
                            class="claim-toggle-btn${claimed ? ' active' : ''}"
                            data-claim-id="${gameIdAttr}"
                            aria-pressed="${claimed ? 'true' : 'false'}"
                            aria-label="${claimToggleAria}"
                        >
                            ${CHECK_ICON_SVG}
                            <span>${escapeHTML(claimMarkText)}</span>
                        </button>
                    ` : ''}
                </div>
            </div>
        </article>
    `;
}

function createCardElementFromHTML(html) {
    const tpl = document.createElement('template');
    tpl.innerHTML = html.trim();
    return tpl.content.firstElementChild;
}

/**
 * Update an existing .game-card DOM element in-place without recreating loaded <img> nodes.
 */
function syncCardElement(cardEl, game, t) {
    const claimed = isClaimed(game.id);
    cardEl.classList.toggle('is-claimed', claimed);

    const validatedImage = safeUrl(game.image_url, '');
    if ((cardEl.dataset.imageUrl || '') !== validatedImage) {
        const fresh = createCardElementFromHTML(createGameCardHTML(game));
        cardEl.replaceWith(fresh);
        return fresh;
    }

    const titleText = game.title || 'Game';
    const titleEl = cardEl.querySelector('.card-title');
    if (titleEl) {
        if (titleEl.textContent !== titleText) titleEl.textContent = titleText;
        if (titleEl.getAttribute('title') !== titleText) titleEl.setAttribute('title', titleText);
    }

    const dlcBadge = cardEl.querySelector('.dlc-badge');
    if (dlcBadge) {
        const dlcText = t.card_dlc_badge || 'DLC';
        if (dlcBadge.textContent !== dlcText) dlcBadge.textContent = dlcText;
    }

    const countdownEl = cardEl.querySelector('.countdown-badge');
    if (countdownEl) {
        const endDateVal = game.end_date || '';
        const isPermVal = String(game.is_permanent ?? true);
        if (countdownEl.dataset.endDate !== endDateVal) countdownEl.dataset.endDate = endDateVal;
        if (countdownEl.dataset.isPermanent !== isPermVal) countdownEl.dataset.isPermanent = isPermVal;
    }

    // Update notices in current language
    const infoSection = cardEl.querySelector('.card-info-section');
    if (infoSection) {
        const noticeLines = getNoticeLines(game, t);
        const existingList = infoSection.querySelector('.card-notices');
        if (noticeLines.length > 0) {
            infoSection.classList.add('has-notices');
            const listHTML = noticeLines
                .map(line => `<li class="card-notice">${NOTICE_ICON_SVG}<span>${escapeHTML(line)}</span></li>`)
                .join('');
            if (existingList) {
                if (existingList.innerHTML !== listHTML) {
                    existingList.innerHTML = listHTML;
                }
            } else {
                const ul = document.createElement('ul');
                ul.className = 'card-notices';
                ul.innerHTML = listHTML;
                infoSection.appendChild(ul);
            }
        } else {
            infoSection.classList.remove('has-notices');
            if (existingList) existingList.remove();
        }
    }

    // Update claim link
    const claimBtn = cardEl.querySelector('.claim-btn');
    if (claimBtn) {
        const storeUrl = safeUrl(game.store_url);
        if (claimBtn.getAttribute('href') !== storeUrl) claimBtn.setAttribute('href', storeUrl);
        const claimAria = (t.card_claim_aria || '').replace('{title}', titleText);
        claimBtn.setAttribute('aria-label', claimAria);
        const span = claimBtn.querySelector('span');
        if (span && span.textContent !== t.card_claim_btn) {
            span.textContent = t.card_claim_btn;
        }
    }

    // Update mark-claimed toggle button
    const toggleBtn = cardEl.querySelector('.claim-toggle-btn');
    if (toggleBtn) {
        toggleBtn.classList.toggle('active', claimed);
        toggleBtn.setAttribute('aria-pressed', claimed ? 'true' : 'false');
        const toggleAria = ((claimed ? t.card_unclaim_aria : t.card_claim_mark_aria) || '').replace('{title}', titleText);
        toggleBtn.setAttribute('aria-label', toggleAria);
        const labelSpan = toggleBtn.querySelector('span');
        const nextLabel = claimed ? (t.card_claimed_badge || 'Claimed') : (t.card_mark_claimed || 'Mark Claimed');
        if (labelSpan && labelSpan.textContent !== nextLabel) {
            labelSpan.textContent = nextLabel;
        }
    }

    return cardEl;
}

let cachedTimerEls = null;
let registeredExpireCallback = null;

if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            updateAllTimers(registeredExpireCallback);
        }
    });
}

/**
 * Render game cards grid/list using DOM diffing/reconciliation by data-id
 */
export function renderGames(onResetFilters) {
    if (state.hasError) {
        renderErrorState(state.errorMessage);
        return;
    }

    const { gridContainer } = getElements();
    if (!gridContainer) return;

    setupImageErrorDelegation(gridContainer);

    const processed = getProcessedGames();
    const t = translations[state.currentLang] || translations.TR;

    updateFacetCounts();

    const statusEl = document.getElementById('results-status');
    if (statusEl) {
        let statusText = (t.results_count || '{count} results found').replace('{count}', processed.length);
        if (state.generatedAt) {
            const genMs = new Date(state.generatedAt).getTime();
            if (!isNaN(genMs) && (Date.now() - genMs) > 24 * 60 * 60 * 1000 && t.results_stale_notice) {
                statusText += ` · ${t.results_stale_notice}`;
            }
        }
        statusEl.textContent = statusText;
    }

    if (processed.length === 0) {
        cachedTimerEls = null;
        renderEmptyState(onResetFilters);
        return;
    }

    // Map existing .game-card elements by data-id for reuse
    const existingCards = new Map();
    Array.from(gridContainer.children).forEach(child => {
        if (child.classList.contains('game-card') && child.dataset.id) {
            existingCards.set(child.dataset.id, child);
        } else {
            child.remove();
        }
    });

    const orderedNodes = processed.map(game => {
        const idStr = game && game.id ? String(game.id) : '';
        let cardEl = idStr ? existingCards.get(idStr) : null;
        if (cardEl) {
            existingCards.delete(idStr);
            cardEl = syncCardElement(cardEl, game, t);
        } else {
            cardEl = createCardElementFromHTML(createGameCardHTML(game));
        }
        return cardEl;
    });

    // Remove cards no longer matching filters
    existingCards.forEach(staleEl => staleEl.remove());

    // Reconcile order minimally so intact nodes and loaded images don't flicker
    orderedNodes.forEach((node, index) => {
        const currentAtIndex = gridContainer.children[index];
        if (currentAtIndex !== node) {
            gridContainer.insertBefore(node, currentAtIndex || null);
        }
    });

    cachedTimerEls = null;
    updateAllTimers(registeredExpireCallback);
}

/**
 * Start timer loop that ticks every 1 second
 */
export function startTimerLoop(onExpire) {
    registeredExpireCallback = typeof onExpire === 'function' ? onExpire : null;
    if (state.timerInterval) clearInterval(state.timerInterval);
    state.timerInterval = setInterval(() => updateAllTimers(registeredExpireCallback), 1000);
}

/**
 * Update countdown text on all displayed cards, skipping redundant DOM writes
 */
export function updateAllTimers(onExpire = registeredExpireCallback) {
    if (typeof document === 'undefined' || document.hidden) return;

    if (!cachedTimerEls) {
        cachedTimerEls = document.querySelectorAll('.countdown-badge');
    }
    const timerEls = cachedTimerEls;
    const now = Date.now();
    const t = translations[state.currentLang] || translations.TR;
    let newlyExpired = false;

    timerEls.forEach(el => {
        const endDateStr = el.dataset.endDate;
        const isPermanent = el.dataset.isPermanent === 'true';
        let nextText = '';
        let nextClass = 'countdown-badge';

        if (!endDateStr || endDateStr.trim() === '' || endDateStr === 'null') {
            if (isPermanent) {
                nextText = t.timer_unlimited;
                nextClass = 'countdown-badge no-expiry';
            } else {
                nextText = t.timer_limited;
                nextClass = 'countdown-badge';
            }
        } else {
            const targetTime = new Date(endDateStr).getTime();

            if (isNaN(targetTime)) {
                nextText = isPermanent ? t.timer_permanent_short : t.timer_limited_short;
                nextClass = 'countdown-badge';
            } else {
                const diff = targetTime - now;

                if (diff <= 0) {
                    nextText = t.timer_expired;
                    nextClass = 'countdown-badge expired';
                    if (el.dataset.wasActive === 'true') {
                        el.dataset.wasActive = 'false';
                        newlyExpired = true;
                    }
                } else {
                    el.dataset.wasActive = 'true';
                    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

                    if (days > 0) {
                        nextText = `${days}${t.timer_day_unit} ${padZero(hours)}${t.timer_hour_unit} ${padZero(minutes)}${t.timer_minute_unit}`;
                    } else {
                        nextText = `${padZero(hours)}${t.timer_hour_unit} ${padZero(minutes)}${t.timer_minute_unit} ${padZero(seconds)}${t.timer_second_unit}`;
                    }

                    nextClass = diff < 24 * 60 * 60 * 1000 ? 'countdown-badge urgent' : 'countdown-badge';
                }
            }
        }

        if (el.textContent !== nextText) {
            el.textContent = nextText;
        }
        if (el.className !== nextClass) {
            el.className = nextClass;
        }
    });

    if (newlyExpired && typeof onExpire === 'function') {
        onExpire();
    }
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
            <svg class="empty-icon" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 class="empty-title">${escapeHTML(t.empty_title)}</h2>
            <p class="empty-desc">${escapeHTML(t.empty_desc)}</p>
            <button type="button" class="reset-filter-btn" id="reset-filters-btn">
                ${escapeHTML(t.empty_reset_btn)}
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
    cachedTimerEls = null;
    const { gridContainer } = getElements();
    if (!gridContainer) return;
    const t = translations[state.currentLang] || translations.TR;
    const errDesc = (t.error_desc || '').replace('{error}', escapeHTML(message));

    gridContainer.innerHTML = `
        <div class="empty-state">
            <svg class="empty-icon" style="color: #ef4444;" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h2 class="empty-title">${escapeHTML(t.error_title)}</h2>
            <p class="empty-desc">${errDesc}</p>
            <button type="button" class="reset-filter-btn" id="error-refresh-btn">
                ${escapeHTML(t.error_refresh_btn)}
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

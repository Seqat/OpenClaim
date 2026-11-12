/**
 * OpenClaim - i18n Internationalization Module
 * Translation dictionary (TR / EN) and language switcher logic.
 */

import { state, saveLanguage } from './state.js';

export const translations = {
    TR: {
        doc_title: "OpenClaim | Anlık Ücretsiz Oyun Takibi",
        header_home_aria: "OpenClaim Ana Sayfa",
        header_lang_aria: "Dil Seçimi",
        lang_tr_aria: "Türkçe",
        lang_en_aria: "İngilizce",
        stat_total: "Toplam Fırsat:",
        stat_steam: "Steam:",
        stat_epic: "Epic:",
        stat_amazon: "Amazon:",
        search_placeholder: "Oyun adı veya platform ara...",
        search_aria: "Oyun arama",
        clear_search_aria: "Aramayı temizle",
        filter_platform_aria: "Platform Filtresi",
        filter_all: "Tümü",
        filter_steam: "Steam",
        filter_epic: "Epic Games",
        filter_amazon: "Amazon Luna / Prime",
        filter_other: "Diğer",

        // Content Filter Labels
        header_content_aria: "İçerik türü filtresi",
        content_all: "Tümü",
        content_games: "Oyunlar",
        content_dlc: "DLC & Eşyalar",

        // Sort, View & Toggle Labels
        sort_label: "Sıralama:",
        sort_smart: "Akıllı Sıralama",
        sort_alphabetical: "Alfabetik (A-Z)",
        sort_expiring: "Bitiş Süresine Göre",
        hide_expired_label: "Süresi dolanları gizle",
        hide_expired_aria: "Süresi dolan fırsatları gizle",
        header_view_aria: "Görünüm Seçimi",
        grid_view_aria: "Kart Görünümü",
        list_view_aria: "Liste Görünümü",
        back_to_top_aria: "En Üste Dön",

        // Card Labels
        card_dlc_badge: "DLC",
        card_claim_btn: "Mağazaya Git",
        card_claim_aria: "{title} mağaza sayfasına git",
        card_mark_claimed: "Aldım",
        card_claimed_badge: "Alındı",
        card_claim_mark_aria: "{title} fırsatını alındı olarak işaretle",
        card_unclaim_aria: "{title} fırsatının alındı işaretini kaldır",

        // Card Notices (hedged: the data is heuristic)
        notice_alienware_arena: "Ücretsiz Alienware Arena hesabı (ve ARP puanı) gerekebilir",
        notice_amd_account: "AMD hesabı gerekebilir",
        notice_dungeonloot_account: "Ücretsiz DungeonLoot hesabı gerekebilir",
        notice_newsletter_signup: "Bülten aboneliği gerekebilir",
        notice_redeem_in_game: "Anahtarın Steam yerine oyun içinde kullanılması gerekebilir",

        // Countdown Statuses
        timer_unlimited: "♾️ Kalıcı",
        timer_limited: "🎁 Prime",
        timer_permanent_short: "♾️ Kalıcı",
        timer_limited_short: "🎁 Prime",
        timer_expired: "Süresi Doldu",
        timer_calculating: "Hesaplanıyor...",
        timer_day_unit: "g",
        timer_hour_unit: "s",
        timer_minute_unit: "d",
        timer_second_unit: "sn",

        // Empty State
        empty_title: "Fırsat Bulunamadı",
        empty_desc: "Aradığınız kriterlere uygun ücretsiz oyun veya fırsat bulunamadı. Filtreleri temizleyerek tekrar deneyebilirsiniz.",
        empty_reset_btn: "Filtreleri Temizle",
        results_count: "{count} sonuç bulundu",
        results_stale_notice: "Veri güncel olmayabilir (>24s)",

        // Error State
        error_title: "Veri Yüklenemedi",
        error_desc: "Oyun listesi (./games.json) yüklenirken bir hata oluştu: {error}",
        error_refresh_btn: "Sayfayı Yenile",

        // Footer
        footer_text: "OpenClaim © 2026. Steam, Epic Games ve Amazon Prime / Luna veri akışlarıyla otomatik güncellenir.",
        footer_last_updated: "Son güncelleme: {date} ({relative})",
        footer_stale_warning: "Eski veri (>24 saat)"
    },
    EN: {
        doc_title: "OpenClaim | Instant Free Games Tracker",
        header_home_aria: "OpenClaim Home",
        header_lang_aria: "Language Switcher",
        lang_tr_aria: "Turkish",
        lang_en_aria: "English",
        stat_total: "Total Deals:",
        stat_steam: "Steam:",
        stat_epic: "Epic:",
        stat_amazon: "Amazon:",
        search_placeholder: "Search games or platforms...",
        search_aria: "Search games",
        clear_search_aria: "Clear search",
        filter_platform_aria: "Platform Filter",
        filter_all: "All",
        filter_steam: "Steam",
        filter_epic: "Epic Games",
        filter_amazon: "Amazon Luna / Prime",
        filter_other: "Other",

        // Content Filter Labels
        header_content_aria: "Content type filter",
        content_all: "All",
        content_games: "Games",
        content_dlc: "DLC & Items",

        // Sort, View & Toggle Labels
        sort_label: "Sort by:",
        sort_smart: "Smart Sort",
        sort_alphabetical: "Alphabetical (A-Z)",
        sort_expiring: "Expiring Soonest",
        hide_expired_label: "Hide expired",
        hide_expired_aria: "Hide expired deals",
        header_view_aria: "View Mode",
        grid_view_aria: "Grid View",
        list_view_aria: "List View",
        back_to_top_aria: "Back to Top",

        // Card Labels
        card_dlc_badge: "DLC",
        card_claim_btn: "Go to Store",
        card_claim_aria: "Go to store page for {title}",
        card_mark_claimed: "Mark Claimed",
        card_claimed_badge: "Claimed",
        card_claim_mark_aria: "Mark {title} as claimed",
        card_unclaim_aria: "Unmark {title} as claimed",

        // Card Notices (hedged: the data is heuristic)
        notice_alienware_arena: "May require a free Alienware Arena account (and ARP points)",
        notice_amd_account: "May require an AMD account",
        notice_dungeonloot_account: "May require a free DungeonLoot account",
        notice_newsletter_signup: "May require a newsletter signup",
        notice_redeem_in_game: "Key may need to be redeemed in-game, not on Steam",

        // Countdown Statuses
        timer_unlimited: "♾️ Permanent",
        timer_limited: "🎁 Prime",
        timer_permanent_short: "♾️ Permanent",
        timer_limited_short: "🎁 Prime",
        timer_expired: "Expired",
        timer_calculating: "Calculating...",
        timer_day_unit: "d",
        timer_hour_unit: "h",
        timer_minute_unit: "m",
        timer_second_unit: "s",

        // Empty State
        empty_title: "No Deals Found",
        empty_desc: "No free games or deals match your search criteria. Try clearing filters and searching again.",
        empty_reset_btn: "Clear Filters",
        results_count: "{count} results found",
        results_stale_notice: "Data may be stale (>24h)",

        // Error State
        error_title: "Failed to Load Data",
        error_desc: "An error occurred while loading the game list (./games.json): {error}",
        error_refresh_btn: "Refresh Page",

        // Footer
        footer_text: "OpenClaim © 2026. Automatically updated with Steam, Epic Games, and Amazon Prime / Luna streams.",
        footer_last_updated: "Last updated: {date} ({relative})",
        footer_stale_warning: "Stale data (>24h)"
    }
};

/**
 * Set active UI language and update DOM elements
 * @param {string} lang - 'TR' or 'EN'
 * @param {Function} renderCallback - Callback function to re-render UI
 */
export function setLanguage(lang, renderCallback) {
    if (!translations[lang]) lang = 'TR';
    saveLanguage(lang);

    if (typeof document === 'undefined') {
        if (typeof renderCallback === 'function') {
            renderCallback();
        }
        return;
    }

    document.documentElement.lang = lang.toLowerCase();

    // Update document title
    if (translations[lang].doc_title) {
        document.title = translations[lang].doc_title;
    }

    // Update text nodes with data-i18n attribute
    const i18nElements = document.querySelectorAll('[data-i18n]');
    i18nElements.forEach(el => {
        const key = el.dataset.i18n;
        if (translations[lang][key]) {
            el.textContent = translations[lang][key];
        }
    });

    // Update placeholders with data-i18n-placeholder attribute
    const placeholderElements = document.querySelectorAll('[data-i18n-placeholder]');
    placeholderElements.forEach(el => {
        const key = el.dataset.i18nPlaceholder;
        if (translations[lang][key]) {
            el.placeholder = translations[lang][key];
        }
    });

    // Update aria-labels with data-i18n-aria attribute
    const ariaElements = document.querySelectorAll('[data-i18n-aria]');
    ariaElements.forEach(el => {
        const key = el.dataset.i18nAria;
        if (translations[lang][key]) {
            el.setAttribute('aria-label', translations[lang][key]);
        }
    });

    // Update language toggle buttons active state
    const langBtns = document.querySelectorAll('[data-lang-btn]');
    langBtns.forEach(btn => {
        const isSelected = btn.dataset.langBtn === lang;
        btn.classList.toggle('active', isSelected);
        btn.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
    });

    if (typeof renderCallback === 'function') {
        renderCallback();
    }
}

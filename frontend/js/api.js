/**
 * OpenClaim - API Module
 * Responsible for fetching ./games.json data.
 */

export async function fetchGamesData() {
    const response = await fetch(`./games.json?t=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    if (Array.isArray(data)) {
        return { games: data, generatedAt: null };
    }
    if (data && typeof data === 'object') {
        return {
            games: Array.isArray(data.games) ? data.games : [],
            generatedAt: data.generated_at || null
        };
    }
    return { games: [], generatedAt: null };
}

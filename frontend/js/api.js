/**
 * OpenClaim - API Module
 * Responsible for fetching ./games.json data.
 */

export async function fetchGamesData() {
    const response = await fetch('./games.json', { cache: 'no-cache' });
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
            generatedAt: typeof data.generated_at === 'string' && data.generated_at.trim()
                ? data.generated_at.trim()
                : null
        };
    }
    return { games: [], generatedAt: null };
}

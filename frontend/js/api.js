/**
 * OpenClaim - API Module
 * Responsible for fetching ./games.json data.
 */

export async function fetchGamesData() {
    const response = await fetch('./games.json');
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    return Array.isArray(data) ? data : [];
}

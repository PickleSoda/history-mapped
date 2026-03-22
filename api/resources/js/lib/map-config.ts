export const HISTORICAL_BASEMAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty';

/**
 * Load and normalize a MapLibre style document.
 *
 * Ensures `projection` is always present for MapLibre v5 compatibility.
 */
export async function loadHistoricalBasemapStyle(styleUrl: string = HISTORICAL_BASEMAP_STYLE_URL): Promise<Record<string, unknown>> {
    const response = await fetch(styleUrl);
    if (!response.ok) {
        throw new Error(`Failed to fetch style ${styleUrl} (HTTP ${response.status})`);
    }

    const style = (await response.json()) as Record<string, unknown>;

    return {
        ...style,
        projection: style.projection ?? { type: 'mercator' },
    };
}

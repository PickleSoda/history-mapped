import type { StyleSpecification } from 'maplibre-gl';

export const HISTORICAL_BASEMAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty';

/**
 * Load and normalize a MapLibre style document.
 *
 * Ensures `projection` is always present for MapLibre v5 compatibility.
 */
export async function loadHistoricalBasemapStyle(styleUrl: string = HISTORICAL_BASEMAP_STYLE_URL): Promise<StyleSpecification> {
    const response = await fetch(styleUrl);
    if (!response.ok) {
        throw new Error(`Failed to fetch style ${styleUrl} (HTTP ${response.status})`);
    }

    const style = (await response.json()) as StyleSpecification;

    return {
        ...style,
        projection: style.projection ?? { type: 'mercator' },
    };
}

import type { FilterSpecification, StyleSpecification } from 'maplibre-gl';

/**
 * OpenHistoricalMap main basemap style.
 *
 * Backed by OHM vector tiles with `start_date`/`end_date` properties.
 */
export const OHM_STYLE_URL =
    'https://www.openhistoricalmap.org/map-styles/main/main.json';
export const HISTORICAL_BASEMAP_FALLBACK_STYLE_URL =
    'https://tiles.openfreemap.org/styles/liberty';

export const OHM_ATTRIBUTION =
    '© <a href="https://www.openhistoricalmap.org/" target="_blank" rel="noopener">OpenHistoricalMap</a> contributors';

type StyleLayer = NonNullable<StyleSpecification['layers']>[number];
type FilterableStyleLayer = StyleLayer & {
    source?: string;
    filter?: FilterSpecification;
};

const OHM_NOISY_ICON_LAYER_PREFIXES = [
    'points_from_landuse_',
    'points_of_interest_',
    'points_place_of_worship_',
    'points_religion',
    'points_powertower',
    'transport_points_',
    'transport_area_labels_',
];

const OHM_HIDDEN_LAYER_IDS = new Set([
    'place_areas_plot',
    'city_county_lines_admin_9',
    'city_county_lines_admin_7-8',
    'admin_admin_5-6',
]);

const OHM_EXCLUDED_FEATURE_WIKIDATA_IDS = ['Q1162419'];

function shouldStripSymbolIcon(layerId: string): boolean {
    if (layerId === 'placearea_label') {
        return true;
    }

    return OHM_NOISY_ICON_LAYER_PREFIXES.some((prefix) =>
        layerId.startsWith(prefix),
    );
}

function normalizeLabelFieldToEnglish(layer: StyleLayer): StyleLayer {
    if (layer.type !== 'symbol') {
        return layer;
    }

    const layout = layer.layout ? { ...layer.layout } : {};
    let changed = false;

    if ('text-field' in layout) {
        // Prefer English labels, then international names, then default name.
        layout['text-field'] = [
            'coalesce',
            ['get', 'name_en'],
            ['get', 'name:en'],
            ['get', 'name_int'],
            ['get', 'int_name'],
            ['get', 'name'],
        ];
        changed = true;
    }

    if ('icon-image' in layout && shouldStripSymbolIcon(layer.id)) {
        delete layout['icon-image'];
        changed = true;
    }

    if (!changed) {
        return layer;
    }

    return {
        ...layer,
        layout,
    };
}

function excludeKnownOhmFeatures(layer: StyleLayer): StyleLayer {
    const filterableLayer = layer as FilterableStyleLayer;

    if (filterableLayer.source !== 'ohm') {
        return layer;
    }

    const exclusionFilter: FilterSpecification = [
        '!',
        [
            'in',
            ['get', 'wikidata'],
            ['literal', OHM_EXCLUDED_FEATURE_WIKIDATA_IDS],
        ],
    ];

    if (!filterableLayer.filter) {
        return {
            ...filterableLayer,
            filter: exclusionFilter,
        } as StyleLayer;
    }

    return {
        ...filterableLayer,
        filter: [
            'all',
            filterableLayer.filter as FilterSpecification,
            exclusionFilter,
        ] as FilterSpecification,
    } as StyleLayer;
}

function normalizeOhmLabels(style: StyleSpecification): StyleSpecification {
    return {
        ...style,
        layers: (style.layers ?? [])
            .filter((layer) => !OHM_HIDDEN_LAYER_IDS.has(layer.id))
            .map((layer) =>
                excludeKnownOhmFeatures(normalizeLabelFieldToEnglish(layer)),
            ),
    };
}

/**
 * Load and normalize the OHM basemap style document.
 *
 * Ensures `projection` is always present for MapLibre v5 compatibility.
 */
export async function loadHistoricalBasemapStyle(): Promise<StyleSpecification> {
    try {
        const style = normalizeOhmLabels(await fetchStyle(OHM_STYLE_URL));

        return {
            ...style,
            projection: style.projection ?? { type: 'mercator' },
        };
    } catch (error) {
        console.warn(
            '[map-config] Failed to load OHM style, falling back to OpenFreeMap liberty style',
            error,
        );

        const fallback = await fetchStyle(
            HISTORICAL_BASEMAP_FALLBACK_STYLE_URL,
        );

        return {
            ...fallback,
            projection: fallback.projection ?? { type: 'mercator' },
        };
    }
}

async function fetchStyle(styleUrl: string): Promise<StyleSpecification> {
    const response = await fetch(styleUrl);

    if (!response.ok) {
        throw new Error(
            `Failed to fetch style ${styleUrl} (HTTP ${response.status})`,
        );
    }

    return (await response.json()) as StyleSpecification;
}

/**
 * Dashboard entity map — the admin counterpart of the public SPA's MapCanvas.
 * Viewport-driven: re-queries /api/v1/entities/map for the visible bbox + year
 * and renders group-colored territories, glyph markers and name labels.
 */
import { useQuery } from '@tanstack/react-query';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useRef, useState } from 'react';
import {
    groupColorExpression,
    registerGroupMarkers,
} from '@/lib/entity-map-icons';
import { loadHistoricalBasemapStyle } from '@/lib/map-config';
import { yearToOhmDate } from '@/lib/ohm-date';
import { applyOhmLayerDateFilter } from '@/lib/ohm-layer-date-filter';

const SOURCE_ID = 'entities';
const FILL_LAYER = 'entities-fill';
const LINE_LAYER = 'entities-line';
const SYMBOL_LAYER = 'entities-symbols';
const MOVE_DEBOUNCE_MS = 250;
const EMPTY_FC = { type: 'FeatureCollection', features: [] } as const;

type Bbox = { w: number; s: number; e: number; n: number };

type FeatureCollectionLike = {
    type: 'FeatureCollection';
    features: Array<{ properties?: { id?: string } }>;
};

type Props = {
    year: number;
    onSelect: (id: string | null) => void;
    onCountChange?: (n: number) => void;
    className?: string;
};

export default function DashboardMap({
    year,
    onSelect,
    onCountChange,
    className,
}: Props) {
    const containerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<maplibregl.Map | null>(null);
    const [bbox, setBbox] = useState<Bbox | null>(null);
    const [zoom, setZoom] = useState(2);
    const [mapReady, setMapReady] = useState(false);

    const onSelectRef = useRef(onSelect);
    onSelectRef.current = onSelect;

    // ── init map once ─────────────────────────────────────────────────────────
    useEffect(() => {
        const container = containerRef.current;

        if (!container) {
            return;
        }

        let cancelled = false;
        let mapInstance: maplibregl.Map | null = null;
        let timer: ReturnType<typeof setTimeout>;

        void loadHistoricalBasemapStyle().then((style) => {
            if (cancelled) {
                return;
            }

            const map = new maplibregl.Map({
                container,
                style,
                center: [15, 45],
                zoom: 3.2,
                attributionControl: { compact: true },
            });
            mapInstance = map;
            mapRef.current = map;

            map.on('load', () => {
                void registerGroupMarkers(map).then(() => {
                    if (cancelled) {
                        return;
                    }

                    map.addSource(SOURCE_ID, {
                        type: 'geojson',
                        data: EMPTY_FC as never,
                    });

                    const groupColor = groupColorExpression();
                    map.addLayer({
                        id: FILL_LAYER,
                        type: 'fill',
                        source: SOURCE_ID,
                        filter: [
                            'match',
                            ['geometry-type'],
                            ['Polygon', 'MultiPolygon'],
                            true,
                            false,
                        ],
                        paint: {
                            'fill-color': groupColor,
                            'fill-opacity': 0.15,
                        },
                    });
                    map.addLayer({
                        id: LINE_LAYER,
                        type: 'line',
                        source: SOURCE_ID,
                        filter: [
                            'match',
                            ['geometry-type'],
                            ['Polygon', 'MultiPolygon'],
                            true,
                            false,
                        ],
                        paint: { 'line-color': groupColor, 'line-width': 1 },
                    });
                    map.addLayer({
                        id: SYMBOL_LAYER,
                        type: 'symbol',
                        source: SOURCE_ID,
                        filter: [
                            'match',
                            ['geometry-type'],
                            ['Point', 'MultiPoint'],
                            true,
                            false,
                        ],
                        layout: {
                            'icon-image': [
                                'coalesce',
                                [
                                    'image',
                                    [
                                        'concat',
                                        'marker-',
                                        ['get', 'entity_group'],
                                    ],
                                ],
                                ['image', 'marker-DEFAULT'],
                            ],
                            'icon-size': 0.8,
                            'icon-allow-overlap': true,
                            'icon-anchor': 'bottom',
                            'text-field': ['get', 'name'],
                            'text-size': 11,
                            'text-offset': [0, 0.4],
                            'text-anchor': 'top',
                            'text-optional': true,
                            'text-max-width': 8,
                        },
                        paint: {
                            'text-color': '#2a2722',
                            'text-halo-color': '#ffffff',
                            'text-halo-width': 1.4,
                        },
                    });

                    for (const layerId of [SYMBOL_LAYER, FILL_LAYER]) {
                        map.on('mouseenter', layerId, () => {
                            map.getCanvas().style.cursor = 'pointer';
                        });
                        map.on('mouseleave', layerId, () => {
                            map.getCanvas().style.cursor = '';
                        });
                    }

                    map.on('click', (e) => {
                        const layers = [SYMBOL_LAYER, FILL_LAYER].filter((l) =>
                            map.getLayer(l),
                        );
                        const hit = layers.length
                            ? map.queryRenderedFeatures(e.point, { layers })[0]
                            : undefined;
                        const id = hit?.properties?.id;
                        onSelectRef.current(
                            typeof id === 'string' && id ? id : null,
                        );
                    });

                    // The initial OHM date filter is applied by the year
                    // effect below as soon as mapReady flips true.
                    const publishViewport = () => {
                        const b = map.getBounds();
                        setBbox({
                            w: b.getWest(),
                            s: b.getSouth(),
                            e: b.getEast(),
                            n: b.getNorth(),
                        });
                        setZoom(Math.round(map.getZoom()));
                    };
                    publishViewport();
                    map.on('moveend', () => {
                        clearTimeout(timer);
                        timer = setTimeout(publishViewport, MOVE_DEBOUNCE_MS);
                    });

                    setMapReady(true);
                });
            });
        });

        return () => {
            cancelled = true;
            clearTimeout(timer);
            mapInstance?.remove();
            mapRef.current = null;
        };
        // Mount once; year/bbox sync happens in the effects below.
    }, []);

    // ── re-filter the OHM basemap when the year changes ───────────────────────
    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady) {
            return;
        }

        // yearToOhmDate pads to 4+ digits — normalizeOhmDate rejects e.g.
        // '100' and would silently reset the basemap to unfiltered.
        applyOhmLayerDateFilter(map, yearToOhmDate(year));
    }, [year, mapReady]);

    // ── viewport query (same endpoint + params as the public SPA) ─────────────
    const entitiesQuery = useQuery({
        queryKey: ['dashboard-map-viewport', bbox, zoom, year],
        enabled: bbox !== null,
        placeholderData: (prev) => prev,
        queryFn: async () => {
            const params = new URLSearchParams({
                bbox_min_lng: String(bbox!.w),
                bbox_min_lat: String(bbox!.s),
                bbox_max_lng: String(bbox!.e),
                bbox_max_lat: String(bbox!.n),
                zoom_level: String(zoom),
                min_results: '24',
                limit: '2000',
                year: String(year),
            });
            const response = await fetch(
                `/api/v1/entities/map?${params.toString()}`,
                { headers: { Accept: 'application/json' } },
            );

            if (!response.ok) {
                throw new Error(
                    `Failed to load map entities (${response.status})`,
                );
            }

            return (await response.json()) as FeatureCollectionLike;
        },
    });

    // ── push data + publish count ──────────────────────────────────────────────
    const data = entitiesQuery.data;
    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady || !data) {
            return;
        }

        const source = map.getSource(SOURCE_ID) as
            | maplibregl.GeoJSONSource
            | undefined;
        source?.setData(data as never);
        onCountChange?.(data.features.length);
        // onCountChange is a stable-enough page callback; keyed on data only.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data, mapReady]);

    return <div ref={containerRef} className={className} />;
}

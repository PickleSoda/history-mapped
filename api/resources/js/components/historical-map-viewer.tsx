import { LngLatBounds, Map } from 'maplibre-gl';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
    computeBoundsFromFeatures,
    normalizeToFeatureCollection,
} from '@/lib/geojson';
import type { GeoJsonLike } from '@/lib/geojson';
import { loadHistoricalBasemapStyle } from '@/lib/map-config';
import { normalizeOhmDate } from '@/lib/ohm-date';
import { applyOhmLayerDateFilter } from '@/lib/ohm-layer-date-filter';
import { cn } from '@/lib/utils';
import 'maplibre-gl/dist/maplibre-gl.css';

type Props = {
    baseGeometries: GeoJsonLike[];
    overlayGeometries?: GeoJsonLike[];
    /**
     * OHM-compatible date string (`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`, negative years for BCE).
     * When set, OHM base layers are filtered to features visible on that date.
     */
    timeframeDate?: string | null;
    timeframeStartDate?: string | null;
    timeframeEndDate?: string | null;
    className?: string;
    fitBounds?: boolean;
    onRenderStateChange?: (state: {
        mapReady: boolean;
        baseFeatureCount: number;
        overlayFeatureCount: number;
    }) => void;
};

export default function HistoricalMapViewer({
    baseGeometries,
    overlayGeometries = [],
    className,
    fitBounds = true,
    onRenderStateChange,
    timeframeDate,
    timeframeStartDate,
    timeframeEndDate,
}: Props) {
    const mapContainerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<Map | null>(null);
    const [mapReady, setMapReady] = useState(false);

    const baseData = useMemo(
        () => normalizeToFeatureCollection(baseGeometries),
        [baseGeometries],
    );
    const overlayData = useMemo(
        () => normalizeToFeatureCollection(overlayGeometries),
        [overlayGeometries],
    );

    // Stable ref so the map-init closure always reads the latest timeframeDate
    // without being re-run on date changes.
    const timeframeDateRef = useRef(timeframeDate);
    const timeframeStartDateRef = useRef(timeframeStartDate);
    const timeframeEndDateRef = useRef(timeframeEndDate);
    useEffect(() => {
        timeframeDateRef.current = timeframeDate;
    }, [timeframeDate]);
    useEffect(() => {
        timeframeStartDateRef.current = timeframeStartDate;
    }, [timeframeStartDate]);
    useEffect(() => {
        timeframeEndDateRef.current = timeframeEndDate;
    }, [timeframeEndDate]);

    useEffect(() => {
        let cancelled = false;

        if (!mapContainerRef.current || mapRef.current) {
            return;
        }

        loadHistoricalBasemapStyle()
            .then((style) => {
                if (cancelled || !mapContainerRef.current) {
                    return;
                }

                const map = new Map({
                    container: mapContainerRef.current,
                    style,
                    center: [20, 30],
                    zoom: 2,
                });

                map.on('load', () => {
                    map.addSource('base-geometry', {
                        type: 'geojson',
                        data: { type: 'FeatureCollection', features: [] },
                    });

                    map.addSource('overlay-geometry', {
                        type: 'geojson',
                        data: { type: 'FeatureCollection', features: [] },
                    });

                    map.addLayer({
                        id: 'base-fill',
                        type: 'fill',
                        source: 'base-geometry',
                        filter: ['==', ['geometry-type'], 'Polygon'],
                        paint: {
                            'fill-color': '#2563eb',
                            'fill-opacity': 0.15,
                        },
                    });

                    map.addLayer({
                        id: 'base-line',
                        type: 'line',
                        source: 'base-geometry',
                        paint: {
                            'line-color': '#2563eb',
                            'line-width': 2,
                        },
                    });

                    map.addLayer({
                        id: 'base-point',
                        type: 'circle',
                        source: 'base-geometry',
                        filter: ['==', ['geometry-type'], 'Point'],
                        paint: {
                            'circle-color': '#2563eb',
                            'circle-radius': 5,
                            'circle-stroke-color': '#fff',
                            'circle-stroke-width': 1,
                        },
                    });

                    map.addLayer({
                        id: 'overlay-fill',
                        type: 'fill',
                        source: 'overlay-geometry',
                        filter: ['==', ['geometry-type'], 'Polygon'],
                        paint: {
                            'fill-color': '#f59e0b',
                            'fill-opacity': 0.22,
                        },
                    });

                    map.addLayer({
                        id: 'overlay-line',
                        type: 'line',
                        source: 'overlay-geometry',
                        paint: {
                            'line-color': '#f59e0b',
                            'line-width': 2,
                        },
                    });

                    map.addLayer({
                        id: 'overlay-point',
                        type: 'circle',
                        source: 'overlay-geometry',
                        filter: ['==', ['geometry-type'], 'Point'],
                        paint: {
                            'circle-color': '#f59e0b',
                            'circle-radius': 5,
                            'circle-stroke-color': '#fff',
                            'circle-stroke-width': 1,
                        },
                    });

                    setMapReady(true);
                    setTimeout(() => map.resize(), 0);

                    // Apply initial OHM date filter from the latest timeframe.
                    applyTimeFilter(
                        map,
                        timeframeDateRef.current ?? null,
                        timeframeStartDateRef.current ?? null,
                        timeframeEndDateRef.current ?? null,
                    );
                });

                // Re-apply the OHM date filter whenever style data changes.
                // This matches the plugin docs and keeps filters in sync after style updates.
                map.on('styledata', () => {
                    applyTimeFilter(
                        map,
                        timeframeDateRef.current ?? null,
                        timeframeStartDateRef.current ?? null,
                        timeframeEndDateRef.current ?? null,
                    );
                });

                mapRef.current = map;
            })
            .catch((error) => {
                console.error(error);
            });

        return () => {
            cancelled = true;

            if (mapRef.current) {
                mapRef.current.remove();
                mapRef.current = null;
            }
        };
    }, []);

    // Re-apply the OHM date filter whenever the timeframe changes after mount.
    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady) {
            return;
        }

        applyTimeFilter(
            map,
            timeframeDate ?? null,
            timeframeStartDate ?? null,
            timeframeEndDate ?? null,
        );
    }, [timeframeDate, timeframeStartDate, timeframeEndDate, mapReady]);

    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady) {
            onRenderStateChange?.({
                mapReady,
                baseFeatureCount: baseData.features.length,
                overlayFeatureCount: overlayData.features.length,
            });

            return;
        }

        const applyData = () => {
            const baseSource = map.getSource('base-geometry') as
                | { setData: (data: GeoJSON.FeatureCollection) => void }
                | undefined;
            const overlaySource = map.getSource('overlay-geometry') as
                | { setData: (data: GeoJSON.FeatureCollection) => void }
                | undefined;

            if (!baseSource || !overlaySource) {
                return false;
            }

            baseSource.setData(baseData);
            overlaySource.setData(overlayData);

            if (fitBounds) {
                const combinedFeatures = [
                    ...baseData.features,
                    ...overlayData.features,
                ];
                const bounds = computeBoundsFromFeatures(combinedFeatures);

                if (bounds) {
                    map.fitBounds(
                        new LngLatBounds(
                            [bounds[0], bounds[1]],
                            [bounds[2], bounds[3]],
                        ),
                        {
                            padding: 40,
                            maxZoom: 7,
                            duration: 0,
                        },
                    );
                }
            }

            onRenderStateChange?.({
                mapReady,
                baseFeatureCount: baseData.features.length,
                overlayFeatureCount: overlayData.features.length,
            });

            return true;
        };

        if (applyData()) {
            return;
        }

        const handleIdle = () => {
            applyData();
        };

        map.once('idle', handleIdle);

        return () => {
            map.off('idle', handleIdle);
        };
    }, [baseData, fitBounds, mapReady, onRenderStateChange, overlayData]);

    useEffect(() => {
        if (!mapContainerRef.current || !mapRef.current) {
            return;
        }

        const map = mapRef.current;
        const observer = new ResizeObserver(() => {
            map.resize();
        });

        observer.observe(mapContainerRef.current);

        return () => {
            observer.disconnect();
        };
    }, []);

    return (
        <div ref={mapContainerRef} className={cn('h-105 w-full', className)} />
    );
}

function applyTimeFilter(
    map: Map,
    timeframeDate: string | null,
    timeframeStartDate: string | null,
    timeframeEndDate: string | null,
): void {
    try {
        const normalizedDate = normalizeOhmDate(timeframeDate);
        const normalizedStartDate = normalizeOhmDate(timeframeStartDate);
        const normalizedEndDate = normalizeOhmDate(timeframeEndDate);

        applyOhmLayerDateFilter(
            map,
            normalizedStartDate || normalizedEndDate
                ? { start: normalizedStartDate, end: normalizedEndDate }
                : normalizedDate,
            { includeUndated: true },
        );
    } catch (error) {
        console.warn('[HistoricalMapViewer] Failed to apply OHM date filter', {
            timeframeDate,
            error,
        });
    }
}

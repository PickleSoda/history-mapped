import { useEffect, useMemo, useRef, useState } from 'react';
import { LngLatBounds, Map } from 'maplibre-gl';
import { loadHistoricalBasemapStyle } from '@/lib/map-config';
import { cn } from '@/lib/utils';
import { computeBoundsFromFeatures, normalizeToFeatureCollection, type GeoJsonLike } from '@/lib/geojson';
import 'maplibre-gl/dist/maplibre-gl.css';

type Props = {
    baseGeometries: GeoJsonLike[];
    overlayGeometries?: GeoJsonLike[];
    className?: string;
    fitBounds?: boolean;
    onRenderStateChange?: (state: {
        mapReady: boolean;
        baseFeatureCount: number;
        overlayFeatureCount: number;
    }) => void;
};

const IS_DEV_HOST = typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location.hostname);

export default function HistoricalMapViewer({
    baseGeometries,
    overlayGeometries = [],
    className,
    fitBounds = true,
    onRenderStateChange,
}: Props) {
    const mapContainerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<Map | null>(null);
    const [mapReady, setMapReady] = useState(false);

    const baseData = useMemo(() => normalizeToFeatureCollection(baseGeometries), [baseGeometries]);
    const overlayData = useMemo(() => normalizeToFeatureCollection(overlayGeometries), [overlayGeometries]);

    useEffect(() => {
        let cancelled = false;

        if (!mapContainerRef.current || mapRef.current) {
            return;
        }

        loadHistoricalBasemapStyle()
            .then((style: Record<string, unknown>) => {
                if (cancelled || !mapContainerRef.current) {
                    return;
                }

                const map = new Map({
                    container: mapContainerRef.current,
                    style: style as Parameters<typeof Map.prototype.setStyle>[0],
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
            const baseSource = map.getSource('base-geometry') as { setData: (data: GeoJSON.FeatureCollection) => void } | undefined;
            const overlaySource = map.getSource('overlay-geometry') as { setData: (data: GeoJSON.FeatureCollection) => void } | undefined;

            if (!baseSource || !overlaySource) {
                return false;
            }

            baseSource.setData(baseData);
            overlaySource.setData(overlayData);

            if (fitBounds) {
                const combinedFeatures = [...baseData.features, ...overlayData.features];
                const bounds = computeBoundsFromFeatures(combinedFeatures);
                if (bounds) {
                    map.fitBounds(new LngLatBounds([bounds[0], bounds[1]], [bounds[2], bounds[3]]), {
                        padding: 40,
                        maxZoom: 7,
                        duration: 0,
                    });
                }
            }

            if (IS_DEV_HOST) {
                console.debug('[HistoricalMapViewer] render state', {
                    mapReady,
                    baseFeatureCount: baseData.features.length,
                    overlayFeatureCount: overlayData.features.length,
                });
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

    return <div ref={mapContainerRef} className={cn('h-105 w-full', className)} />;
}

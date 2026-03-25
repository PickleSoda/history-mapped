import { LngLatBounds, Map } from 'maplibre-gl';
import type { MapLayerMouseEvent } from 'maplibre-gl';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import type { MutableRefObject } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import {
    computeBoundsFromFeatures,
    normalizeToFeatureCollection,
} from '@/lib/geojson';
import type { GeoJsonLike } from '@/lib/geojson';
import { loadHistoricalBasemapStyle } from '@/lib/map-config';
import { normalizeOhmDate } from '@/lib/ohm-date';
import { applyOhmLayerDateFilter } from '@/lib/ohm-layer-date-filter';
import { cn } from '@/lib/utils';
import type { Relationship } from '@/types/entity';
import 'maplibre-gl/dist/maplibre-gl.css';

type Props = {
    baseGeometries: GeoJsonLike[];
    overlayGeometries?: GeoJsonLike[];
    overlayRelationship?: Relationship | null;
    hoveredRelationshipId?: string | null;
    hoveredSnapshotId?: string | null;
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
    onFeatureHover?: (feature: any | null) => void;
    onFeatureClick?: (feature: any | null) => void;
};

function HistoricalMapViewer({
    baseGeometries,
    overlayGeometries = [],
    overlayRelationship = null,
    hoveredRelationshipId = null,
    hoveredSnapshotId = null,
    className,
    fitBounds = true,
    onRenderStateChange,
    timeframeDate,
    timeframeStartDate,
    timeframeEndDate,
    onFeatureHover,
    onFeatureClick,
}: Props) {
    const defaultOverlayColor = '#f59e0b';
    const mapContainerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<Map | null>(null);
    const hasAutoFitRef = useRef(false);
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
    const onFeatureHoverRef = useRef(onFeatureHover);
    const onFeatureClickRef = useRef(onFeatureClick);
    const closePopupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const popupHoveredRef = useRef(false);
    const pointHoveredRef = useRef(false);
    // Track popup info, screen position, and hover state
    const [popupInfo, setPopupInfo] = useState<{ feature: any, screen: { x: number, y: number } } | null>(null);

    const clearPopupCloseTimer = useCallback(() => {
        if (closePopupTimerRef.current) {
            clearTimeout(closePopupTimerRef.current);
            closePopupTimerRef.current = null;
        }
    }, []);

    const schedulePopupClose = useCallback(() => {
        clearPopupCloseTimer();
        closePopupTimerRef.current = setTimeout(() => {
            if (!popupHoveredRef.current && !pointHoveredRef.current) {
                setPopupInfo(null);
            }

            closePopupTimerRef.current = null;
        }, 80);
    }, [clearPopupCloseTimer]);

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
        onFeatureHoverRef.current = onFeatureHover;
    }, [onFeatureHover]);
    useEffect(() => {
        onFeatureClickRef.current = onFeatureClick;
    }, [onFeatureClick]);
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
                            'fill-color': defaultOverlayColor,
                            'fill-opacity': 0.22,
                        },
                    });

                    map.addLayer({
                        id: 'overlay-line',
                        type: 'line',
                        source: 'overlay-geometry',
                        paint: {
                            'line-color': defaultOverlayColor,
                            'line-width': 2,
                        },
                    });

                    map.addLayer({
                        id: 'overlay-point',
                        type: 'circle',
                        source: 'overlay-geometry',
                        filter: ['==', ['geometry-type'], 'Point'],
                        paint: {
                            'circle-color': defaultOverlayColor,
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

                const unbindOverlayInteractions = bindOverlayInteractionHandlers({
                    map,
                    clearPopupCloseTimer,
                    schedulePopupClose,
                    onFeatureHoverRef,
                    onFeatureClickRef,
                    pointHoveredRef,
                    popupHoveredRef,
                    setPopupInfo,
                });

                mapRef.current = map;

                if (cancelled) {
                    unbindOverlayInteractions();
                }
            })
            .catch((error) => {
                console.error(error);
            });

        return () => {
            cancelled = true;
            clearPopupCloseTimer();

            if (mapRef.current) {
                mapRef.current.remove();
                mapRef.current = null;
            }
        };
    }, [clearPopupCloseTimer, schedulePopupClose]);

    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady) {
            return;
        }

        const overlayColor = overlayRelationship?.direction === 'incoming'
            ? '#14b8a6'
            : '#f59e0b';
        const hasSelectedRelationship = Boolean(
            overlayRelationship?.relationship_id,
        );
        const hasHover = Boolean(hoveredRelationshipId || hoveredSnapshotId);

        const hoverExpression: any[] = [
            'any',
            hoveredRelationshipId
                ? [
                      '==',
                      [
                          'to-string',
                          ['coalesce', ['get', 'relationship_id'], ''],
                      ],
                      hoveredRelationshipId,
                  ]
                : false,
            hoveredSnapshotId
                ? [
                      '==',
                      ['to-string', ['coalesce', ['get', 'snapshot_id'], '']],
                      hoveredSnapshotId,
                  ]
                : false,
        ];
        const hoverPreviewExpression: any[] = [
            '==',
            ['coalesce', ['get', 'hover_preview'], false],
            true,
        ];

        const fillOpacityExpression: any[] = hasSelectedRelationship
            ? [
                  'case',
                  hoverPreviewExpression,
                  hasHover ? 0.14 : 0.12,
                  0.34,
              ]
            : hasHover
              ? ['case', hoverExpression, 0.36, 0.07]
              : ['case', hoverExpression, 0.28, 0.18];

        const lineWidthExpression: any[] = hasSelectedRelationship
            ? ['case', hoverPreviewExpression, hasHover ? 1.8 : 1.6, 2.8]
            : hasHover
              ? ['case', hoverExpression, 3.1, 1.2]
              : ['case', hoverExpression, 2.8, 2];

        const pointRadiusExpression: any[] = hasSelectedRelationship
            ? ['case', hoverPreviewExpression, hasHover ? 5.5 : 5, 7]
            : hasHover
              ? ['case', hoverExpression, 7, 4]
              : ['case', hoverExpression, 6, 5];

        const pointStrokeExpression: any[] = hasSelectedRelationship
            ? ['case', hoverPreviewExpression, hasHover ? 1.1 : 1, 2]
            : hasHover
              ? ['case', hoverExpression, 2, 1]
              : ['case', hoverExpression, 1.8, 1];

        if (map.getLayer('overlay-fill')) {
            map.setPaintProperty('overlay-fill', 'fill-color', overlayColor);
            map.setPaintProperty(
                'overlay-fill',
                'fill-opacity',
                fillOpacityExpression,
            );
        }

        if (map.getLayer('overlay-line')) {
            map.setPaintProperty('overlay-line', 'line-color', overlayColor);
            map.setPaintProperty(
                'overlay-line',
                'line-width',
                lineWidthExpression,
            );
        }

        if (map.getLayer('overlay-point')) {
            map.setPaintProperty('overlay-point', 'circle-color', overlayColor);
            map.setPaintProperty(
                'overlay-point',
                'circle-radius',
                pointRadiusExpression,
            );
            map.setPaintProperty(
                'overlay-point',
                'circle-stroke-width',
                pointStrokeExpression,
            );
        }
    }, [
        hoveredRelationshipId,
        hoveredSnapshotId,
        mapReady,
        overlayRelationship?.direction,
        overlayRelationship?.relationship_id,
    ]);

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

            if (fitBounds && !hasAutoFitRef.current) {
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
                    hasAutoFitRef.current = true;
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

    const popupProperties = popupInfo?.feature?.properties ?? {};
    const popupTitle = String(
        popupProperties.name ??
        popupProperties.label ??
        overlayRelationship?.related_entity?.name ??
        'Entity',
    );
    const popupType = popupProperties.entity_type ?? overlayRelationship?.related_entity?.entity_type ?? null;
    const popupSummary = popupProperties.summary ?? popupProperties.description ?? overlayRelationship?.description ?? null;
    const popupPrimaryEntries = [
        { key: 'relationship_type', label: 'Relationship', value: popupProperties.relationship_type },
        { key: 'direction', label: 'Direction', value: popupProperties.direction },
        { key: 'entity_group', label: 'Group', value: popupProperties.entity_group },
        { key: 'year_start', label: 'From', value: popupProperties.year_start },
        { key: 'year_end', label: 'To', value: popupProperties.year_end },
    ].filter((entry) => entry.value != null && entry.value !== '');

    const hiddenKeys = new Set([
        'name',
        'label',
        'entity_type',
        'summary',
        'description',
        'relationship_type',
        'direction',
        'entity_group',
        'year_start',
        'year_end',
        'relationship_id',
        'snapshot_id',
    ]);

    const popupEntries = Object.entries(popupProperties)
        .filter(([key, value]) => {
            if (value == null || value === '') {
                return false;
            }

            return !hiddenKeys.has(key);
        })
        .sort(([a], [b]) => a.localeCompare(b));

    return (
        <div ref={mapContainerRef} className={cn('h-105 w-full relative', className)}>
            {popupInfo && popupInfo.feature && (
                <div
                    className="absolute z-20 min-w-[220px] max-w-xs"
                    style={{
                        left: popupInfo.screen.x,
                        top: popupInfo.screen.y - 5,
                        transform: 'translate(-50%, -100%)',
                    }}
                    onMouseEnter={() => {
                        popupHoveredRef.current = true;
                        clearPopupCloseTimer();
                    }}
                    onMouseLeave={() => {
                        popupHoveredRef.current = false;
                        schedulePopupClose();
                    }}
                    onMouseDown={(e) => e.stopPropagation()}
                >
                    <Card className="pointer-events-auto shadow-lg border-primary bg-card text-card-foreground">
                        <CardHeader className="pb-0">
                            <CardTitle className="text-base">
                                {popupTitle}
                            </CardTitle>
                            {popupType && (
                                <Badge variant="secondary" className="w-fit">
                                    {String(popupType)}
                                </Badge>
                            )}
                        </CardHeader>
                        <CardContent className="py-0">
                            {popupSummary && (
                                <div className="mb-1 text-xs text-muted-foreground">
                                    {String(popupSummary)}
                                </div>
                            )}
                            <div className="space-y-1 text-xs max-h-48 overflow-auto">
                                {popupPrimaryEntries.map((entry) => (
                                    <div key={entry.key} className="flex justify-between gap-2">
                                        <span className="text-muted-foreground">{entry.label}:</span>
                                        <span className="font-medium break-all">{String(entry.value)}</span>
                                    </div>
                                ))}
                                {popupPrimaryEntries.length === 0 && popupEntries.length === 0 && (
                                    <div className="text-muted-foreground">No additional details</div>
                                )}
                                {popupEntries.map(([key, value]) => (
                                    <div key={key} className="flex justify-between gap-2">
                                        <span className="text-muted-foreground">{toDisplayLabel(key)}:</span>
                                        <span className="font-medium break-all">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>
                                    </div>
                                ))}
                            </div>
                            {popupProperties.relationship_id && (
                                <Button
                                    variant="default"
                                    size="sm"
                                    className="mt-2 w-full"
                                    onClick={(e: MouseEvent<HTMLButtonElement>) => {
                                        e.stopPropagation();
                                        clearPopupCloseTimer();

                                        if (onFeatureClickRef.current) {
                                            onFeatureClickRef.current(popupInfo.feature);
                                        }

                                        popupHoveredRef.current = false;
                                        pointHoveredRef.current = false;
                                        setPopupInfo(null);
                                    }}
                                >
                                    Focus Relationship
                                </Button>
                            )}
                            {popupProperties.snapshot_id && (
                                <Button
                                    variant="secondary"
                                    size="sm"
                                    className="mt-2 w-full"
                                    onClick={(e: MouseEvent<HTMLButtonElement>) => {
                                        e.stopPropagation();
                                        clearPopupCloseTimer();

                                        if (onFeatureClickRef.current) {
                                            onFeatureClickRef.current(popupInfo.feature);
                                        }

                                        popupHoveredRef.current = false;
                                        pointHoveredRef.current = false;
                                        setPopupInfo(null);
                                    }}
                                >
                                    Focus Snapshot
                                </Button>
                            )}
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}

export default HistoricalMapViewer;

type OverlayInteractionHandlerOptions = {
    map: Map;
    clearPopupCloseTimer: () => void;
    schedulePopupClose: () => void;
    onFeatureHoverRef: MutableRefObject<((feature: any | null) => void) | undefined>;
    onFeatureClickRef: MutableRefObject<((feature: any | null) => void) | undefined>;
    pointHoveredRef: MutableRefObject<boolean>;
    popupHoveredRef: MutableRefObject<boolean>;
    setPopupInfo: (value: { feature: any, screen: { x: number, y: number } } | null) => void;
};

function bindOverlayInteractionHandlers({
    map,
    clearPopupCloseTimer,
    schedulePopupClose,
    onFeatureHoverRef,
    onFeatureClickRef,
    pointHoveredRef,
    popupHoveredRef,
    setPopupInfo,
}: OverlayInteractionHandlerOptions): () => void {
    const handleMouseEnter = (e: MapLayerMouseEvent) => {
        pointHoveredRef.current = true;
        clearPopupCloseTimer();
        map.getCanvas().style.cursor = 'pointer';
        const feature = e.features?.[0];

        if (feature && feature.geometry && feature.geometry.type === 'Point') {
            const coords = feature.geometry.coordinates;
            const lngLat: [number, number] =
                Array.isArray(coords) && coords.length >= 2
                    ? [coords[0], coords[1]]
                    : [0, 0];
            const point = map.project(lngLat);
            setPopupInfo({ feature, screen: { x: point.x, y: point.y } });
        }

        if (onFeatureHoverRef.current) {
            onFeatureHoverRef.current(feature);
        }
    };

    const handleMouseLeave = () => {
        pointHoveredRef.current = false;
        map.getCanvas().style.cursor = '';
        schedulePopupClose();

        if (onFeatureHoverRef.current) {
            onFeatureHoverRef.current(null);
        }
    };

    const handleClick = (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];

        if (onFeatureClickRef.current) {
            onFeatureClickRef.current(feature);
        }

        clearPopupCloseTimer();
        pointHoveredRef.current = false;
        popupHoveredRef.current = false;
        setPopupInfo(null);
    };

    map.on('mouseenter', 'overlay-point', handleMouseEnter);
    map.on('mouseleave', 'overlay-point', handleMouseLeave);
    map.on('click', 'overlay-point', handleClick);

    return () => {
        map.off('mouseenter', 'overlay-point', handleMouseEnter);
        map.off('mouseleave', 'overlay-point', handleMouseLeave);
        map.off('click', 'overlay-point', handleClick);
    };
}

function toDisplayLabel(key: string): string {
    return key
        .replace(/_/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
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

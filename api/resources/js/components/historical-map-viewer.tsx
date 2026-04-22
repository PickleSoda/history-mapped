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
    /**
     * OHM-compatible date string (`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`, negative years for BCE).
     * When set, OHM base layers are filtered to features visible on that date.
     */
    timeframeDate?: string | null;
    timeframeStartDate?: string | null;
    timeframeEndDate?: string | null;
    className?: string;
    fitBounds?: boolean;
    fitBoundsKey?: string | number | null;
    dataVersion?: string | number | null;
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
    className,
    fitBounds = true,
    fitBoundsKey,
    dataVersion,
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

                const unbindOhmInteractions = bindOhmBasemapInteractionHandlers(
                    map,
                );

                mapRef.current = map;

                if (cancelled) {
                    unbindOverlayInteractions();
                    unbindOhmInteractions();
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
        const hasHover = Boolean(hoveredRelationshipId);

        const hoverExpression: any = hoveredRelationshipId
            ? [
                  '==',
                  [
                      'to-string',
                      ['coalesce', ['get', 'relationship_id'], ''],
                  ],
                  hoveredRelationshipId,
              ]
            : false;
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

            // Force new object references so MapLibre reliably applies source updates
            // even when upstream caching keeps deep-equal structures.
            const nextBaseData: GeoJSON.FeatureCollection = {
                type: 'FeatureCollection',
                features: [...baseData.features],
            };
            const nextOverlayData: GeoJSON.FeatureCollection = {
                type: 'FeatureCollection',
                features: [...overlayData.features],
            };

            baseSource.setData(nextBaseData);
            overlaySource.setData(nextOverlayData);

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
    }, [
        baseData,
        dataVersion,
        fitBounds,
        fitBoundsKey,
        mapReady,
        onRenderStateChange,
        overlayData,
    ]);

    useEffect(() => {
        // Allow bounded re-fit cycles (e.g. dashboard year changes) without remounting.
        hasAutoFitRef.current = false;
    }, [fitBoundsKey]);

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
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}

function bindOhmBasemapInteractionHandlers(map: Map): () => void {
    const getInteractiveOhmLayerIds = () => {
        const style = map.getStyle();

        if (!style || !Array.isArray(style.layers)) {
            return {
                labelLayerIds: [] as string[],
                boundaryLayerIds: [] as string[],
            };
        }

        const visibleOhmLayers = style.layers.filter((layer) => {
            if (!('source' in layer) || layer.source !== 'ohm') {
                return false;
            }

            return (
                !('layout' in layer) ||
                layer.layout?.visibility === undefined ||
                layer.layout.visibility !== 'none'
            );
        });

        const labelLayerIds = visibleOhmLayers
            .filter((layer) => layer.type === 'symbol')
            .map((layer) => layer.id);

        const boundaryLayerIds = visibleOhmLayers
            .filter((layer) => layer.type === 'line')
            .map((layer) => layer.id);

        return {
            labelLayerIds,
            boundaryLayerIds,
        };
    };

    const buildIdentifierPayload = (feature: any) => {
        const properties = feature.properties ?? {};

        return {
            id: feature.id ?? null,
            sourceLayer: feature.sourceLayer ?? null,
            wikidata: properties.wikidata ?? null,
            name: properties.name ?? null,
            start_date: properties.start_date ?? null,
            end_date: properties.end_date ?? null,
            osm_type: properties.osm_type ?? null,
            osm_id: properties.osm_id ?? null,
            '@id': properties['@id'] ?? null,
            id_property: properties.id ?? null,
        };
    };

    const getFeatureDedupKey = (feature: any): string => {
        const properties = feature.properties ?? {};

        return JSON.stringify([
            feature.layer?.id ?? null,
            feature.sourceLayer ?? null,
            feature.id ?? null,
            properties['@id'] ?? null,
            properties.osm_id ?? null,
            properties.osm_type ?? null,
            properties.id ?? null,
            properties.name ?? null,
        ]);
    };

    const getDistanceFromClick = (
        feature: any,
        event: MapLayerMouseEvent,
    ): number | null => {
        const geometry = feature.geometry;

        if (!geometry) {
            return null;
        }

        const distanceFromCoordinate = (coordinate: any): number | null => {
            if (!Array.isArray(coordinate) || coordinate.length < 2) {
                return null;
            }

            const projected = map.project([coordinate[0], coordinate[1]]);
            const dx = projected.x - event.point.x;
            const dy = projected.y - event.point.y;

            return Math.sqrt(dx * dx + dy * dy);
        };

        if (geometry.type === 'Point') {
            return distanceFromCoordinate(geometry.coordinates);
        }

        const lineLike = geometry.type === 'LineString'
            ? [geometry.coordinates]
            : geometry.type === 'MultiLineString'
              ? geometry.coordinates
              : [];

        if (lineLike.length === 0) {
            return null;
        }

        let nearestDistance: number | null = null;

        lineLike.forEach((segment: any) => {
            if (!Array.isArray(segment)) {
                return;
            }

            segment.forEach((coordinate: any) => {
                const distance = distanceFromCoordinate(coordinate);

                if (distance === null) {
                    return;
                }

                nearestDistance =
                    nearestDistance === null
                        ? distance
                        : Math.min(nearestDistance, distance);
            });
        });

        return nearestDistance;
    };

    const queryFeaturesInRadius = (
        event: MapLayerMouseEvent,
        layerIds: string[],
        radius: number,
    ): any[] => {
        if (layerIds.length === 0) {
            return [];
        }

        return map.queryRenderedFeatures(
            [
                [
                    Math.max(0, event.point.x - radius),
                    Math.max(0, event.point.y - radius),
                ],
                [event.point.x + radius, event.point.y + radius],
            ],
            { layers: layerIds },
        );
    };

    const toIdentityTokens = (feature: any): Set<string> => {
        const properties = feature.properties ?? {};
        const entries: Array<[string, unknown]> = [
            ['wikidata', properties.wikidata],
            ['@id', properties['@id']],
            ['osm_id', properties.osm_id],
            ['osm_type', properties.osm_type],
            ['id', properties.id],
            ['name', properties.name],
            ['name_en', properties['name:en']],
        ];

        const tokens = entries
            .filter(([, value]) => value != null && String(value).trim() !== '')
            .map(([key, value]) => `${key}:${String(value).toLowerCase()}`);

        return new Set(tokens);
    };

    const hasTokenOverlap = (left: any, right: any): boolean => {
        const leftTokens = toIdentityTokens(left);
        const rightTokens = toIdentityTokens(right);

        for (const token of leftTokens) {
            if (rightTokens.has(token)) {
                return true;
            }
        }

        return false;
    };

    const scoreCandidate = (
        feature: any,
        event: MapLayerMouseEvent,
        source: 'label' | 'boundary',
    ): number => {
        const properties = feature.properties ?? {};
        const distance = getDistanceFromClick(feature, event);
        let score = source === 'label' ? 60 : 30;

        if (distance !== null) {
            score += Math.max(0, 35 - distance);
        }

        if (properties.wikidata) {
            score += 15;
        }

        if (properties.name) {
            score += 10;
        }

        return Math.round(score);
    };

    const handleClick = (e: MapLayerMouseEvent) => {
        if (!map.getStyle()) {
            return;
        }

        const { labelLayerIds, boundaryLayerIds } = getInteractiveOhmLayerIds();
        const hasLabelLayers = labelLayerIds.length > 0;
        const hasBoundaryLayers = boundaryLayerIds.length > 0;

        if (!hasLabelLayers && !hasBoundaryLayers) {
            return;
        }

        const dedupByFeature = (features: any[]) =>
            features.filter((feature, index, collection) => {
                const key = getFeatureDedupKey(feature);

                return (
                    index ===
                    collection.findIndex(
                        (candidate) => getFeatureDedupKey(candidate) === key,
                    )
                );
            });

        const labelSearchRadius = 20;
        const labelFeatures = hasLabelLayers
            ? queryFeaturesInRadius(e, labelLayerIds, labelSearchRadius)
            : [];

        const boundaryFeatures = hasBoundaryLayers
            ? map.queryRenderedFeatures(e.point, { layers: boundaryLayerIds })
            : [];

        const uniqueLabelFeatures = dedupByFeature(labelFeatures);
        const uniqueBoundaryFeatures = dedupByFeature(boundaryFeatures);
        let candidateFeatures =
            uniqueLabelFeatures.length > 0
                ? uniqueLabelFeatures.map((feature) => ({
                      feature,
                      source: 'label' as const,
                  }))
                : uniqueBoundaryFeatures.map((feature) => ({
                      feature,
                      source: 'boundary' as const,
                  }));

        if (candidateFeatures.length === 0) {
            const canvas = map.getCanvas();
            const viewportSpan = Math.max(canvas.width, canvas.height);
            const maxAdaptiveRadius = Math.max(
                320,
                Math.min(900, Math.round(viewportSpan * 0.45)),
            );
            const boundaryFallbackRadii = [60, 160, 320, maxAdaptiveRadius];
            const labelFallbackRadii = [120, 240, 420, maxAdaptiveRadius];
            const collectFirstNonEmpty = (layerIds: string[], radii: number[]) => {
                for (const radius of radii) {
                    const features = dedupByFeature(
                        queryFeaturesInRadius(e, layerIds, radius),
                    );

                    if (features.length > 0) {
                        return features;
                    }
                }

                return [] as any[];
            };
            const expandedBoundaryFeatures = hasBoundaryLayers
                ? collectFirstNonEmpty(boundaryLayerIds, boundaryFallbackRadii)
                : [];
            const expandedLabelFeatures = hasLabelLayers
                ? collectFirstNonEmpty(labelLayerIds, labelFallbackRadii)
                : [];

            if (expandedBoundaryFeatures.length > 0 && expandedLabelFeatures.length > 0) {
                const linkedLabels = expandedLabelFeatures.filter((labelFeature) =>
                    expandedBoundaryFeatures.some((boundaryFeature) =>
                        hasTokenOverlap(labelFeature, boundaryFeature),
                    ),
                );

                if (linkedLabels.length > 0) {
                    candidateFeatures = linkedLabels.map((feature) => ({
                        feature,
                        source: 'label' as const,
                    }));
                } else {
                    candidateFeatures = expandedBoundaryFeatures.map((feature) => ({
                        feature,
                        source: 'boundary' as const,
                    }));
                }
            } else if (expandedBoundaryFeatures.length > 0) {
                candidateFeatures = expandedBoundaryFeatures.map((feature) => ({
                    feature,
                    source: 'boundary' as const,
                }));
            } else if (expandedLabelFeatures.length > 0) {
                candidateFeatures = expandedLabelFeatures.map((feature) => ({
                    feature,
                    source: 'label' as const,
                }));
            }
        }

        if (candidateFeatures.length === 0 && hasLabelLayers) {
            // Final fallback: choose nearest visible label in viewport so interior clicks don't no-op.
            const viewportLabels = dedupByFeature(
                map.queryRenderedFeatures({ layers: labelLayerIds }),
            );

            if (viewportLabels.length > 0) {
                const nearestViewportLabel = viewportLabels
                    .map((feature) => ({
                        feature,
                        distance: getDistanceFromClick(feature, e) ?? Number.MAX_SAFE_INTEGER,
                    }))
                    .sort((a, b) => a.distance - b.distance)[0];

                if (nearestViewportLabel) {
                    candidateFeatures = [
                        {
                            feature: nearestViewportLabel.feature,
                            source: 'label' as const,
                        },
                    ];
                }
            }
        }

        if (candidateFeatures.length === 0) {
            return;
        }

        const rankedCandidates = candidateFeatures
            .map(({ feature, source }) => ({
                feature,
                source,
                score: scoreCandidate(feature, e, source),
                clickDistancePx: getDistanceFromClick(feature, e),
            }))
            .sort((a, b) => b.score - a.score)
            .slice(0, 10);

        rankedCandidates.forEach((candidate, index) => {
            const { feature } = candidate;
            const key = getFeatureDedupKey(feature);

            console.log(`[OHM click ${index + 1}/${rankedCandidates.length}]`, {
                identifierHints: buildIdentifierPayload(feature),
                candidateMeta: {
                    rank: index + 1,
                    score: candidate.score,
                    source: candidate.source,
                    clickDistancePx: candidate.clickDistancePx,
                    dedupKey: key,
                    nearbyBoundaryHits: uniqueBoundaryFeatures.length,
                    nearbyLabelHits: uniqueLabelFeatures.length,
                },
                properties: feature.properties ?? {},
                feature,
            });
        });
    };

    map.on('click', handleClick);

    return () => {
        map.off('click', handleClick);
    };
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

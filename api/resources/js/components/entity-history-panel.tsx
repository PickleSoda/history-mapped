import { useQuery } from '@tanstack/react-query';
import { useCallback, useMemo, useState } from 'react';
import type { TimelineItem, SelectedTimelineItem } from '@/components/entity-history-timeline';
import EntityHistoryTimeline from '@/components/entity-history-timeline';
import HistoricalMapViewer from '@/components/historical-map-viewer';
import TimeframeRangeSelector from '@/components/timeframe-range-selector';
import { normalizeToFeatureCollection } from '@/lib/geojson';
import type { GeoJsonLike } from '@/lib/geojson';
import { yearToOhmDate } from '@/lib/ohm-date';
import type { Relationship } from '@/types/entity';

type Props = {
    entityGeojson: GeoJsonLike;
    entityTerritoryGeojson: GeoJsonLike;
    entityTemporalStart?: string | null;
    entityTemporalEnd?: string | null;
    relationshipsUrl: string;
};


export default function EntityHistoryPanel({
    entityGeojson,
    entityTerritoryGeojson,
    entityTemporalStart,
    entityTemporalEnd,
    relationshipsUrl,
}: Props) {
    const [selectedItem, setSelectedItem] = useState<SelectedTimelineItem>(
        null,
    );
    const [hoveredItem, setHoveredItem] = useState<SelectedTimelineItem>(null);
    const [selectedRange, setSelectedRange] = useState<{
        startYear: number | null;
        endYear: number | null;
    } | null>(null);

    const relationshipsQuery = useQuery({
        queryKey: ['entity-history', 'relationships', relationshipsUrl],
        enabled: Boolean(relationshipsUrl),
        queryFn: async () => {
            const response = await fetch(relationshipsUrl, {
                headers: { Accept: 'application/json' },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return (await response.json()) as {
                outgoing: Relationship[];
                incoming: Relationship[];
            };
        },
    });

    const relationships = useMemo(
        () => [
            ...(relationshipsQuery.data?.outgoing ?? []),
            ...(relationshipsQuery.data?.incoming ?? []),
        ],
        [relationshipsQuery.data?.incoming, relationshipsQuery.data?.outgoing],
    );
    const loading = relationshipsQuery.isLoading;
    const loadError = relationshipsQuery.isError
        ? 'Failed to load timeline data.'
        : null;

    const activeRelationship = useMemo(() => {
        if (selectedItem?.kind !== 'relationship') {
            return null;
        }

        return (
            relationships.find(
                (relationship) => relationship.relationship_id === selectedItem.id,
            ) ?? null
        );
    }, [relationships, selectedItem]);

    const hoveredRelationship = useMemo(() => {
        if (hoveredItem?.kind !== 'relationship') {
            return null;
        }

        return (
            relationships.find(
                (relationship) => relationship.relationship_id === hoveredItem.id,
            ) ?? null
        );
    }, [hoveredItem, relationships]);

    const timelineItems = useMemo<TimelineItem[]>(() => {
        const relationshipItems: TimelineItem[] = relationships.map(
            (relationship) => {
                const direction =
                    relationship.direction === 'incoming' ? '←' : '→';
                const relatedName =
                    relationship.related_entity?.name ?? 'Unknown entity';
                const typeLabel = relationship.relationship_type.replace(
                    /_/g,
                    ' ',
                );

                return {
                    id: `relationship:${relationship.relationship_id}`,
                    kind: 'relationship',
                    startYear: parseYear(relationship.temporal_start),
                    endYear: parseYear(relationship.temporal_end),
                    title: `${direction} ${typeLabel} ${relatedName}`,
                    subtitle: relationship.description ?? undefined,
                    relationship,
                };
            },
        );

        return relationshipItems.sort((a, b) => {
            const aStart = a.startYear ?? Number.POSITIVE_INFINITY;
            const bStart = b.startYear ?? Number.POSITIVE_INFINITY;

            if (aStart !== bStart) {
                return aStart - bStart;
            }

            const aEnd = a.endYear ?? Number.POSITIVE_INFINITY;
            const bEnd = b.endYear ?? Number.POSITIVE_INFINITY;

            return aEnd - bEnd;
        });
    }, [relationships]);

    const baseGeometries = useMemo(
        () => [entityGeojson, entityTerritoryGeojson],
        [entityGeojson, entityTerritoryGeojson],
    );

    const relationshipToOverlayGeometries = useCallback(
        (
            relationship: Relationship,
            extraProperties: Record<string, unknown> = {},
        ): GeoJsonLike[] => {
            const related = relationship.related_entity;

            if (!related) {
                return [];
            }

            const commonProperties = {
                relationship_id: relationship.relationship_id,
                relationship_type: relationship.relationship_type,
                direction: relationship.direction,
                name: related.name,
                entity_type: related.entity_type,
                entity_group: related.entity_group,
                summary: relationship.description,
                year_start: parseYear(relationship.temporal_start),
                year_end: parseYear(relationship.temporal_end),
                ...extraProperties,
            };

            return [
                enrichGeoJson(related.geojson ?? null, commonProperties),
                enrichGeoJson(related.territory_geojson ?? null, commonProperties),
            ].filter((value): value is GeoJsonLike => value != null);
        },
        [],
    );

    const overlayGeometries = useMemo<GeoJsonLike[]>(() => {
        // If a relationship is selected, show selected geometry and optional hovered preview geometry.
        if (activeRelationship?.related_entity) {
            const selectedGeometries = relationshipToOverlayGeometries(
                activeRelationship,
                {
                    hover_preview: false,
                    selected_relationship: true,
                },
            );

            if (
                hoveredRelationship &&
                hoveredRelationship.relationship_id !==
                    activeRelationship.relationship_id
            ) {
                const previewGeometries = relationshipToOverlayGeometries(
                    hoveredRelationship,
                    {
                        hover_preview: true,
                        selected_relationship: false,
                    },
                );

                return [...selectedGeometries, ...previewGeometries];
            }

            return selectedGeometries;
        }

        // Otherwise, show all related entities (all direct relationships)
        const allRelated = relationships.flatMap((relationship) =>
            relationshipToOverlayGeometries(relationship, {
                hover_preview: false,
                selected_relationship: false,
            }),
        );

        return allRelated.length > 0 ? allRelated : [null, null];
    }, [
        activeRelationship,
        hoveredRelationship,
        relationshipToOverlayGeometries,
        relationships,
    ]);

    // Derive OHM date bounds from selected relationship/entity temporal ranges.
    // Combine active selection bounds with entity temporal bounds for comparison.
    const timeframeStartDate = useMemo<string | null>(() => {
        const activeStartYear = parseYear(activeRelationship?.temporal_start ?? null)
            ?? null;
        const entityStartYear = parseYear(entityTemporalStart ?? null);
        const startYear = minYear(activeStartYear, entityStartYear);

        return startYear != null ? yearToOhmDate(startYear) : null;
    }, [activeRelationship, entityTemporalStart]);

    const timeframeEndDate = useMemo<string | null>(() => {
        const activeEndYear = parseYear(activeRelationship?.temporal_end ?? null)
            ?? null;
        const entityEndYear = parseYear(entityTemporalEnd ?? null);
        const endYear = maxYear(activeEndYear, entityEndYear);

        return endYear != null ? yearToOhmDate(endYear) : null;
    }, [activeRelationship, entityTemporalEnd]);

    const derivedStartYear = useMemo(() => {
        const activeStartYear = parseYear(activeRelationship?.temporal_start ?? null)
            ?? null;
        const entityStartYear = parseYear(entityTemporalStart ?? null);

        return minYear(activeStartYear, entityStartYear);
    }, [activeRelationship, entityTemporalStart]);

    const derivedEndYear = useMemo(() => {
        const activeEndYear = parseYear(activeRelationship?.temporal_end ?? null)
            ?? null;
        const entityEndYear = parseYear(entityTemporalEnd ?? null);

        return maxYear(activeEndYear, entityEndYear);
    }, [activeRelationship, entityTemporalEnd]);

    const effectiveStartYear = selectedRange?.startYear ?? derivedStartYear;
    const effectiveEndYear = selectedRange?.endYear ?? derivedEndYear;

    const selectedStartDate = useMemo(
        () =>
            effectiveStartYear != null ? yearToOhmDate(effectiveStartYear) : null,
        [effectiveStartYear],
    );

    const selectedEndDate = useMemo(
        () => (effectiveEndYear != null ? yearToOhmDate(effectiveEndYear) : null),
        [effectiveEndYear],
    );

    // Backward-compatible single-date fallback: start bound first, then end bound.
    const timeframeDate = useMemo<string | null>(() => {
        return timeframeStartDate ?? timeframeEndDate;
    }, [timeframeEndDate, timeframeStartDate]);

    const hasAnyRenderableGeometry = useMemo(() => {
        const base =
            normalizeToFeatureCollection(baseGeometries).features.length;
        const overlay =
            normalizeToFeatureCollection(overlayGeometries).features.length;

        return base + overlay > 0;
    }, [baseGeometries, overlayGeometries]);

    const noop = useCallback(() => {
        return;
    }, []);

    const handleFeatureClick = useCallback((feature: any) => {
        const relId = feature?.properties?.relationship_id;

        if (relId) {
            setSelectedRange(null);
            setSelectedItem({ kind: 'relationship', id: String(relId) });
        }
    }, []);

    const hoveredRelationshipId =
        hoveredItem?.kind === 'relationship' ? hoveredItem.id : null;

    return (
        <div className="flex flex-col gap-4 lg:flex-row">
            <div className="rounded-lg border flex flex-col flex-1 min-w-0 h-[820px] overflow-hidden">
                <div className="border-b px-4 py-3">
                    <h3 className="text-sm font-semibold">Geometry Map</h3>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                        Base geometry is shown in blue. Selected relationship
                        geometry is shown in amber.
                    </p>
                </div>
                <HistoricalMapViewer
                    className="h-[670px] rounded-b-lg"
                    baseGeometries={baseGeometries}
                    overlayGeometries={overlayGeometries}
                    overlayRelationship={activeRelationship}
                    hoveredRelationshipId={hoveredRelationshipId}
                    timeframeDate={timeframeDate}
                    timeframeStartDate={selectedStartDate}
                    timeframeEndDate={selectedEndDate}
                    onFeatureHover={noop}
                    onFeatureClick={handleFeatureClick}
                />
                <TimeframeRangeSelector
                    key={`${derivedStartYear ?? 'none'}:${derivedEndYear ?? 'none'}`}
                    defaultStartYear={derivedStartYear}
                    defaultEndYear={derivedEndYear}
                    onApply={({ startYear, endYear }) => {
                        setSelectedRange({ startYear, endYear });
                    }}
                />
                {!loading && !hasAnyRenderableGeometry && (
                    <div className="border-t px-4 py-2 text-xs text-muted-foreground">
                        No renderable geometry found for this entity or the
                        selected relationship.
                    </div>
                )}
            </div>

            <div className="rounded-lg border flex flex-col flex-1 min-w-0 h-[820px] overflow-hidden">
                <div className="border-b px-4 py-3">
                    <h3 className="text-sm font-semibold">Timeline</h3>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                        Relationships sorted chronologically.
                    </p>
                </div>
                <div className="flex-1 min-h-0">
                    <EntityHistoryTimeline
                        items={timelineItems}
                        loading={loading}
                        loadError={loadError}
                        selectedItem={selectedItem}
                        onHover={setHoveredItem}
                        onSelect={(item) => {
                            setHoveredItem(null);
                            setSelectedRange(null);
                            setSelectedItem(item);
                        }}
                    />
                </div>
            </div>
        </div>
    );
}

function parseYear(value: string | null | undefined): number | null {
    if (value == null || value === '') {
        return null;
    }

    const trimmed = String(value).trim();
    const direct = Number(trimmed);

    if (Number.isFinite(direct)) {
        return direct;
    }

    const match = trimmed.match(/^-?\d+/);

    if (!match) {
        return null;
    }

    const parsed = Number(match[0]);

    return Number.isFinite(parsed) ? parsed : null;
}

function minYear(a: number | null, b: number | null): number | null {
    if (a == null) {
        return b;
    }

    if (b == null) {
        return a;
    }

    return Math.min(a, b);
}

function maxYear(a: number | null, b: number | null): number | null {
    if (a == null) {
        return b;
    }

    if (b == null) {
        return a;
    }

    return Math.max(a, b);
}

function enrichGeoJson(
    value: GeoJsonLike,
    properties: Record<string, unknown>,
): GeoJsonLike {
    if (!value || typeof value !== 'object') {
        return null;
    }

    const candidate = value as {
        type?: string;
        geometry?: unknown;
        properties?: Record<string, unknown>;
        features?: Array<{
            type: 'Feature';
            geometry: unknown;
            properties?: Record<string, unknown>;
        }>;
    };

    if (candidate.type === 'FeatureCollection' && Array.isArray(candidate.features)) {
        return {
            ...candidate,
            features: candidate.features.map((feature) => ({
                ...feature,
                properties: {
                    ...(feature.properties ?? {}),
                    ...properties,
                },
            })),
        };
    }

    if (candidate.type === 'Feature' && candidate.geometry) {
        return {
            ...candidate,
            properties: {
                ...(candidate.properties ?? {}),
                ...properties,
            },
        };
    }

    if (candidate.type) {
        return {
            type: 'Feature',
            geometry: value,
            properties,
        };
    }

    return null;
}
import { useQuery } from '@tanstack/react-query';
import { useCallback, useMemo, useState } from 'react';
import type { TimelineItem, SelectedTimelineItem } from '@/components/entity-history-timeline';
import EntityHistoryTimeline from '@/components/entity-history-timeline';
import HistoricalMapViewer from '@/components/historical-map-viewer';
import TimeframeRangeSelector from '@/components/timeframe-range-selector';
import { normalizeToFeatureCollection } from '@/lib/geojson';
import type { GeoJsonLike } from '@/lib/geojson';
import { yearToOhmDate } from '@/lib/ohm-date';
import type { ConfidenceLevel } from '@/types/entity';

type Props = {
    entityGeojson: GeoJsonLike;
    entityTerritoryGeojson: GeoJsonLike;
    entityTemporalStart?: string | null;
    entityTemporalEnd?: string | null;
    timelineUrl: string;
};

type TimelineEntrySummary = {
    id: string;
    entry_kind: string;
    start_year: number | null;
    end_year: number | null;
    title: string;
    description: string | null;
    has_geom: boolean;
    has_territory_geom: boolean;
    geom: GeoJsonLike;
    source_table: string;
    source_id: string;
    relationship_type: string | null;
    related_entity_id: string | null;
    related_entity_name: string | null;
    confidence?: ConfidenceLevel | null;
};

type TimelineEntryDetail = TimelineEntrySummary & {
    geom: GeoJsonLike;
    territory_geom: GeoJsonLike;
};


export default function EntityHistoryPanel({
    entityGeojson,
    entityTerritoryGeojson,
    entityTemporalStart,
    entityTemporalEnd,
    timelineUrl,
}: Props) {
    const [selectedItem, setSelectedItem] = useState<SelectedTimelineItem>(
        null,
    );
    const [selectedRange, setSelectedRange] = useState<{
        startYear: number | null;
        endYear: number | null;
    } | null>(null);

    const timelineQuery = useQuery({
        queryKey: ['entity-history', 'timeline', timelineUrl],
        enabled: Boolean(timelineUrl),
        queryFn: async () => {
            const response = await fetch(timelineUrl, {
                headers: { Accept: 'application/json' },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return (await response.json()) as { data: TimelineEntrySummary[] };
        },
    });

    const timelineEntries = useMemo(
        () => timelineQuery.data?.data ?? [],
        [timelineQuery.data?.data],
    );

    const activeEntry = useMemo(() => {
        if (selectedItem?.kind !== 'timeline') {
            return null;
        }

        return (
            timelineEntries.find(
                (entry) => entry.id === selectedItem.id,
            ) ?? null
        );
    }, [timelineEntries, selectedItem]);

    const selectedEntryUrl = useMemo(() => {
        if (!activeEntry) {
            return null;
        }

        if (!activeEntry.has_territory_geom && activeEntry.geom) {
            return null;
        }

        if (!activeEntry.has_geom && !activeEntry.has_territory_geom) {
            return null;
        }

        return `${timelineUrl}/${activeEntry.id}`;
    }, [activeEntry, timelineUrl]);

    const selectedEntryQuery = useQuery({
        queryKey: ['entity-history', 'timeline-entry', selectedEntryUrl],
        enabled: Boolean(selectedEntryUrl),
        queryFn: async () => {
            const response = await fetch(selectedEntryUrl as string, {
                headers: { Accept: 'application/json' },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return (await response.json()) as { data: TimelineEntryDetail };
        },
    });

    const activeEntryDetail = useMemo(
        () => selectedEntryQuery.data?.data ?? null,
        [selectedEntryQuery.data?.data],
    );

    const loading = timelineQuery.isLoading;
    const loadError = timelineQuery.isError
        ? 'Failed to load timeline data.'
        : null;

    const timelineItems = useMemo<TimelineItem[]>(() => {
        const entryItems: TimelineItem[] = timelineEntries.map((entry) => ({
            id: entry.id,
            kind: 'timeline',
            startYear: entry.start_year,
            endYear: entry.end_year,
            title: entry.title,
            subtitle: entry.description ?? undefined,
            badgeLabel: entry.relationship_type
                ? entry.relationship_type.replace(/_/g, ' ')
                : entry.entry_kind.replace(/_/g, ' '),
            relatedEntityId: entry.related_entity_id,
        }));

        return entryItems.sort((a, b) => {
            const aStart = a.startYear ?? Number.POSITIVE_INFINITY;
            const bStart = b.startYear ?? Number.POSITIVE_INFINITY;

            if (aStart !== bStart) {
                return aStart - bStart;
            }

            const aEnd = a.endYear ?? Number.POSITIVE_INFINITY;
            const bEnd = b.endYear ?? Number.POSITIVE_INFINITY;

            return aEnd - bEnd;
        });
    }, [timelineEntries]);

    const baseGeometries = useMemo(
        () => [entityGeojson, entityTerritoryGeojson],
        [entityGeojson, entityTerritoryGeojson],
    );

    const entryToOverlayGeometries = useCallback(
        (
            entry: Pick<
                TimelineEntrySummary,
                | 'id'
                | 'relationship_type'
                | 'related_entity_name'
                | 'title'
                | 'description'
                | 'start_year'
                | 'end_year'
                | 'geom'
            > & { territory_geom?: GeoJsonLike | null },
            extraProperties: Record<string, unknown> = {},
        ): GeoJsonLike[] => {
            if (!entry.geom && !entry.territory_geom) {
                return [];
            }

            const commonProperties = {
                relationship_id: entry.id,
                relationship_type: entry.relationship_type,
                direction: 'outgoing',
                name: entry.related_entity_name ?? entry.title,
                summary: entry.description,
                year_start: entry.start_year,
                year_end: entry.end_year,
                ...extraProperties,
            };

            return [
                enrichGeoJson(entry.geom ?? null, commonProperties),
                enrichGeoJson(entry.territory_geom ?? null, commonProperties),
            ].filter((value): value is GeoJsonLike => value != null);
        },
        [],
    );

    const selectedEntryOverlay = useMemo(() => {
        if (activeEntryDetail) {
            return activeEntryDetail;
        }

        if (!activeEntry || !activeEntry.geom) {
            return null;
        }

        return {
            ...activeEntry,
            territory_geom: null,
        };
    }, [activeEntry, activeEntryDetail]);

    const overlayGeometries = useMemo<GeoJsonLike[]>(() => {
        if (selectedEntryOverlay) {
            return entryToOverlayGeometries(selectedEntryOverlay, {
                hover_preview: false,
                selected_relationship: true,
            });
        }

        return timelineEntries.flatMap((entry) =>
            entryToOverlayGeometries(
                {
                    ...entry,
                    territory_geom: null,
                },
                {
                    hover_preview: false,
                    selected_relationship: false,
                },
            ),
        );
    }, [entryToOverlayGeometries, selectedEntryOverlay, timelineEntries]);

    // Derive OHM date bounds from selected relationship/entity temporal ranges.
    // Combine active selection bounds with entity temporal bounds for comparison.
    const timeframeStartDate = useMemo<string | null>(() => {
        const activeStartYear = activeEntry?.start_year ?? null;
        const entityStartYear = parseYear(entityTemporalStart ?? null);
        const startYear = minYear(activeStartYear, entityStartYear);

        return startYear != null ? yearToOhmDate(startYear) : null;
    }, [activeEntry, entityTemporalStart]);

    const timeframeEndDate = useMemo<string | null>(() => {
        const activeEndYear = activeEntry?.end_year ?? null;
        const entityEndYear = parseYear(entityTemporalEnd ?? null);
        const endYear = maxYear(activeEndYear, entityEndYear);

        return endYear != null ? yearToOhmDate(endYear) : null;
    }, [activeEntry, entityTemporalEnd]);

    const derivedStartYear = useMemo(() => {
        const activeStartYear = activeEntry?.start_year ?? null;
        const entityStartYear = parseYear(entityTemporalStart ?? null);

        return minYear(activeStartYear, entityStartYear);
    }, [activeEntry, entityTemporalStart]);

    const derivedEndYear = useMemo(() => {
        const activeEndYear = activeEntry?.end_year ?? null;
        const entityEndYear = parseYear(entityTemporalEnd ?? null);

        return maxYear(activeEndYear, entityEndYear);
    }, [activeEntry, entityTemporalEnd]);

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
            setSelectedItem({ kind: 'timeline', id: String(relId) });
        }
    }, []);

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
                    overlayRelationship={null}
                    hoveredRelationshipId={null}
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
                        Timeline entries sorted chronologically.
                    </p>
                </div>
                <div className="flex-1 min-h-0">
                    <EntityHistoryTimeline
                        items={timelineItems}
                        loading={loading}
                        loadError={loadError}
                        selectedItem={selectedItem}
                        onHover={undefined}
                        onSelect={(item) => {
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
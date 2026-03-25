import { useEffect, useMemo, useState } from 'react';
import HistoricalMapViewer from '@/components/historical-map-viewer';
import TimeframeRangeSelector from '@/components/timeframe-range-selector';
import { Badge } from '@/components/ui/badge';
import { normalizeToFeatureCollection } from '@/lib/geojson';
import type { GeoJsonLike } from '@/lib/geojson';
import { yearToOhmDate } from '@/lib/ohm-date';
import type { GeometrySnapshot, Relationship } from '@/types/entity';

type Props = {
    entityGeojson: GeoJsonLike;
    entityTerritoryGeojson: GeoJsonLike;
    entityTemporalStart?: string | null;
    entityTemporalEnd?: string | null;
    snapshotsUrl: string;
    relationshipsUrl: string;
};

type TimelineItem = {
    id: string;
    kind: 'snapshot' | 'relationship';
    startYear: number | null;
    endYear: number | null;
    title: string;
    subtitle?: string;
    snapshot?: GeometrySnapshot;
    relationship?: Relationship;
};

type SelectedTimelineItem =
    | { kind: 'snapshot'; id: string }
    | { kind: 'relationship'; id: string }
    | null;

export default function EntityHistoryPanel({
    entityGeojson,
    entityTerritoryGeojson,
    entityTemporalStart,
    entityTemporalEnd,
    snapshotsUrl,
    relationshipsUrl,
}: Props) {
    const [snapshots, setSnapshots] = useState<GeometrySnapshot[]>([]);
    const [relationships, setRelationships] = useState<Relationship[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [selectedItem, setSelectedItem] = useState<SelectedTimelineItem>(
        null,
    );
    const [selectedStartYear, setSelectedStartYear] = useState<number | null>(
        null,
    );
    const [selectedEndYear, setSelectedEndYear] = useState<number | null>(null);

    useEffect(() => {
        let cancelled = false;

        async function loadData() {
            setLoading(true);
            setLoadError(null);

            try {
                const [snapshotsRes, relationshipsRes] = await Promise.all([
                    fetch(snapshotsUrl, {
                        headers: { Accept: 'application/json' },
                    }),
                    fetch(relationshipsUrl, {
                        headers: { Accept: 'application/json' },
                    }),
                ]);

                if (!snapshotsRes.ok || !relationshipsRes.ok) {
                    throw new Error(
                        `HTTP ${snapshotsRes.status}/${relationshipsRes.status}`,
                    );
                }

                const snapshotsJson = (await snapshotsRes.json()) as {
                    snapshots: GeometrySnapshot[];
                };
                const relationshipsJson = (await relationshipsRes.json()) as {
                    outgoing: Relationship[];
                    incoming: Relationship[];
                };

                if (cancelled) {
                    return;
                }

                setSnapshots(snapshotsJson.snapshots ?? []);
                setRelationships([
                    ...(relationshipsJson.outgoing ?? []),
                    ...(relationshipsJson.incoming ?? []),
                ]);
            } catch (error) {
                if (!cancelled) {
                    setLoadError('Failed to load timeline data.');
                    console.error(error);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        void loadData();

        return () => {
            cancelled = true;
        };
    }, [relationshipsUrl, snapshotsUrl]);

    const activeSnapshot = useMemo(
        () => {
            if (selectedItem?.kind !== 'snapshot') {
                return null;
            }

            return (
                snapshots.find(
                    (snapshot) => snapshot.snapshot_id === selectedItem.id,
                ) ?? null
            );
        },
        [selectedItem, snapshots],
    );

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

    const timelineItems = useMemo<TimelineItem[]>(() => {
        const snapshotItems: TimelineItem[] = snapshots.map((snapshot) => ({
            id: `snapshot:${snapshot.snapshot_id}`,
            kind: 'snapshot',
            startYear: snapshot.year_start,
            endYear: snapshot.year_end,
            title: snapshot.label ?? 'Geometry Snapshot',
            subtitle: snapshot.description ?? undefined,
            snapshot,
        }));

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

        return [...snapshotItems, ...relationshipItems].sort((a, b) => {
            const aStart = a.startYear ?? Number.POSITIVE_INFINITY;
            const bStart = b.startYear ?? Number.POSITIVE_INFINITY;

            if (aStart !== bStart) {
                return aStart - bStart;
            }

            const aEnd = a.endYear ?? Number.POSITIVE_INFINITY;
            const bEnd = b.endYear ?? Number.POSITIVE_INFINITY;

            return aEnd - bEnd;
        });
    }, [relationships, snapshots]);

    const baseGeometries = useMemo(
        () => [entityGeojson, entityTerritoryGeojson],
        [entityGeojson, entityTerritoryGeojson],
    );

    const overlayGeometries = useMemo(
        () => {
            if (activeSnapshot) {
                return [
                    activeSnapshot.geojson ?? null,
                    activeSnapshot.territory_geojson ?? null,
                ];
            }

            if (activeRelationship?.related_entity) {
                return [
                    activeRelationship.related_entity.geojson ?? null,
                    activeRelationship.related_entity.territory_geojson ?? null,
                ];
            }

            return [null, null];
        },
        [activeRelationship, activeSnapshot],
    );

    // Derive OHM date bounds from snapshot/entity temporal ranges.
    // Prefer active snapshot bounds; fall back to entity temporal bounds.
    const timeframeStartDate = useMemo<string | null>(() => {
        const snapshotStartYear = activeSnapshot?.year_start ?? null;
        const relationshipStartYear = parseYear(
            activeRelationship?.temporal_start ?? null,
        );
        const entityStartYear = parseYear(entityTemporalStart ?? null);
        const startYear = snapshotStartYear ?? relationshipStartYear ?? entityStartYear;

        return startYear != null ? yearToOhmDate(startYear) : null;
    }, [activeRelationship, activeSnapshot, entityTemporalStart]);

    const timeframeEndDate = useMemo<string | null>(() => {
        const snapshotEndYear = activeSnapshot?.year_end ?? null;
        const relationshipEndYear = parseYear(
            activeRelationship?.temporal_end ?? null,
        );
        const entityEndYear = parseYear(entityTemporalEnd ?? null);
        const endYear = snapshotEndYear ?? relationshipEndYear ?? entityEndYear;

        return endYear != null ? yearToOhmDate(endYear) : null;
    }, [activeRelationship, activeSnapshot, entityTemporalEnd]);

    const derivedStartYear = useMemo(() => {
        const snapshotStartYear = activeSnapshot?.year_start ?? null;
        const relationshipStartYear = parseYear(
            activeRelationship?.temporal_start ?? null,
        );
        const entityStartYear = parseYear(entityTemporalStart ?? null);

        return snapshotStartYear ?? relationshipStartYear ?? entityStartYear;
    }, [activeRelationship, activeSnapshot, entityTemporalStart]);

    const derivedEndYear = useMemo(() => {
        const snapshotEndYear = activeSnapshot?.year_end ?? null;
        const relationshipEndYear = parseYear(
            activeRelationship?.temporal_end ?? null,
        );
        const entityEndYear = parseYear(entityTemporalEnd ?? null);

        return snapshotEndYear ?? relationshipEndYear ?? entityEndYear;
    }, [activeRelationship, activeSnapshot, entityTemporalEnd]);

    useEffect(() => {
        setSelectedStartYear(derivedStartYear);
        setSelectedEndYear(derivedEndYear);
    }, [derivedEndYear, derivedStartYear]);

    const selectedStartDate = useMemo(
        () =>
            selectedStartYear != null ? yearToOhmDate(selectedStartYear) : null,
        [selectedStartYear],
    );

    const selectedEndDate = useMemo(
        () => (selectedEndYear != null ? yearToOhmDate(selectedEndYear) : null),
        [selectedEndYear],
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

    return (
        <div className="grid gap-4 lg:grid-cols-[2fr,1fr]">
            <div className="rounded-lg border">
                <div className="border-b px-4 py-3">
                    <h3 className="text-sm font-semibold">Geometry Map</h3>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                        Base geometry is shown in blue. Selected snapshot or
                        relationship geometry is shown in amber.
                    </p>
                </div>
                <HistoricalMapViewer
                    baseGeometries={baseGeometries}
                    overlayGeometries={overlayGeometries}
                    timeframeDate={timeframeDate}
                    timeframeStartDate={selectedStartDate}
                    timeframeEndDate={selectedEndDate}
                />
                <TimeframeRangeSelector
                    key={`${derivedStartYear ?? 'none'}:${derivedEndYear ?? 'none'}`}
                    defaultStartYear={derivedStartYear}
                    defaultEndYear={derivedEndYear}
                    onApply={({ startYear, endYear }) => {
                        setSelectedStartYear(startYear);
                        setSelectedEndYear(endYear);
                    }}
                />
                {!loading && !hasAnyRenderableGeometry && (
                    <div className="border-t px-4 py-2 text-xs text-muted-foreground">
                        No renderable geometry found for this entity or the
                        selected snapshot.
                    </div>
                )}
            </div>

            <div className="rounded-lg border">
                <div className="border-b px-4 py-3">
                    <h3 className="text-sm font-semibold">Timeline</h3>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                        Snapshots and relationships sorted chronologically.
                    </p>
                </div>
                <div className="max-h-105 space-y-2 overflow-y-auto p-3">
                    {loading && (
                        <p className="text-sm text-muted-foreground">
                            Loading timeline…
                        </p>
                    )}
                    {!loading && loadError && (
                        <p className="text-sm text-destructive">{loadError}</p>
                    )}
                    {!loading && !loadError && timelineItems.length === 0 && (
                        <p className="text-sm text-muted-foreground">
                            No snapshots or relationships with timeline data.
                        </p>
                    )}

                    {!loading &&
                        !loadError &&
                        timelineItems.map((item) => {
                            const selected =
                                selectedItem?.kind === item.kind &&
                                ((item.kind === 'snapshot' &&
                                    item.snapshot?.snapshot_id ===
                                        selectedItem.id) ||
                                    (item.kind === 'relationship' &&
                                        item.relationship?.relationship_id ===
                                            selectedItem.id));

                            return (
                                <button
                                    key={item.id}
                                    type="button"
                                    onClick={() => {
                                        const nextSelection =
                                            item.kind === 'snapshot'
                                                ? item.snapshot?.snapshot_id
                                                    ? {
                                                          kind: 'snapshot' as const,
                                                          id: item.snapshot.snapshot_id,
                                                      }
                                                    : null
                                                : item.relationship?.relationship_id
                                                  ? {
                                                        kind: 'relationship' as const,
                                                        id: item.relationship.relationship_id,
                                                    }
                                                  : null;

                                        if (!nextSelection) {
                                            return;
                                        }

                                        setSelectedItem((current) => {
                                            if (
                                                current?.kind === nextSelection.kind &&
                                                current.id === nextSelection.id
                                            ) {
                                                return null;
                                            }

                                            return nextSelection;
                                        });
                                    }}
                                    className={[
                                        'w-full rounded-md border px-3 py-2 text-left',
                                        selected
                                            ? 'border-amber-500 bg-amber-500/5'
                                            : 'hover:bg-muted/50',
                                    ].join(' ')}
                                >
                                    <div className="mb-1 flex items-center justify-between gap-2">
                                        <Badge
                                            variant={
                                                item.kind === 'snapshot'
                                                    ? 'secondary'
                                                    : 'outline'
                                            }
                                        >
                                            {item.kind}
                                        </Badge>
                                        <span className="text-xs text-muted-foreground tabular-nums">
                                            {formatYearRange(
                                                item.startYear,
                                                item.endYear,
                                            )}
                                        </span>
                                    </div>
                                    <p className="text-sm leading-tight font-medium">
                                        {item.title}
                                    </p>
                                    {item.subtitle && (
                                        <p className="mt-1 text-xs leading-snug text-muted-foreground">
                                            {item.subtitle}
                                        </p>
                                    )}
                                </button>
                            );
                        })}
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

function formatYear(year: number | null): string {
    if (year == null) {
        return 'Unknown';
    }

    return year < 0 ? `${Math.abs(year)} BCE` : `${year} CE`;
}

function formatYearRange(start: number | null, end: number | null): string {
    if (start == null && end == null) {
        return 'Undated';
    }

    if (start != null && end != null) {
        return `${formatYear(start)} – ${formatYear(end)}`;
    }

    if (start != null) {
        return `From ${formatYear(start)}`;
    }

    return `Until ${formatYear(end)}`;
}

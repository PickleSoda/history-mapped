import { useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import HistoricalMapViewer from '@/components/historical-map-viewer';
import { normalizeToFeatureCollection, type GeoJsonLike } from '@/lib/geojson';
import type { GeometrySnapshot, Relationship } from '@/types/entity';

type Props = {
    entityGeojson: GeoJsonLike;
    entityTerritoryGeojson: GeoJsonLike;
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
};

const IS_DEV_HOST = typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location.hostname);

export default function EntityHistoryPanel({
    entityGeojson,
    entityTerritoryGeojson,
    snapshotsUrl,
    relationshipsUrl,
}: Props) {
    const [snapshots, setSnapshots] = useState<GeometrySnapshot[]>([]);
    const [relationships, setRelationships] = useState<Relationship[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [activeSnapshotId, setActiveSnapshotId] = useState<string | null>(null);
    const [mapState, setMapState] = useState({
        mapReady: false,
        baseFeatureCount: 0,
        overlayFeatureCount: 0,
    });

    useEffect(() => {
        let cancelled = false;

        async function loadData() {
            setLoading(true);
            setLoadError(null);

            try {
                const [snapshotsRes, relationshipsRes] = await Promise.all([
                    fetch(snapshotsUrl, { headers: { Accept: 'application/json' } }),
                    fetch(relationshipsUrl, { headers: { Accept: 'application/json' } }),
                ]);

                if (!snapshotsRes.ok || !relationshipsRes.ok) {
                    throw new Error(`HTTP ${snapshotsRes.status}/${relationshipsRes.status}`);
                }

                const snapshotsJson = (await snapshotsRes.json()) as { snapshots: GeometrySnapshot[] };
                const relationshipsJson = (await relationshipsRes.json()) as { outgoing: Relationship[]; incoming: Relationship[] };

                if (cancelled) {
                    return;
                }

                setSnapshots(snapshotsJson.snapshots ?? []);
                setRelationships([...(relationshipsJson.outgoing ?? []), ...(relationshipsJson.incoming ?? [])]);

                if ((snapshotsJson.snapshots ?? []).length > 0) {
                    setActiveSnapshotId(snapshotsJson.snapshots[0]!.snapshot_id);
                }
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
        () => snapshots.find((snapshot) => snapshot.snapshot_id === activeSnapshotId) ?? null,
        [activeSnapshotId, snapshots],
    );

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

        const relationshipItems: TimelineItem[] = relationships.map((relationship) => {
            const direction = relationship.direction === 'incoming' ? '←' : '→';
            const relatedName = relationship.related_entity?.name ?? 'Unknown entity';
            const typeLabel = relationship.relationship_type.replace(/_/g, ' ');

            return {
                id: `relationship:${relationship.relationship_id}`,
                kind: 'relationship',
                startYear: parseYear(relationship.temporal_start),
                endYear: parseYear(relationship.temporal_end),
                title: `${direction} ${typeLabel} ${relatedName}`,
                subtitle: relationship.description ?? undefined,
            };
        });

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
        () => [activeSnapshot?.geojson ?? null, activeSnapshot?.territory_geojson ?? null],
        [activeSnapshot],
    );

    const hasAnyRenderableGeometry = useMemo(() => {
        const base = normalizeToFeatureCollection(baseGeometries).features.length;
        const overlay = normalizeToFeatureCollection(overlayGeometries).features.length;

        return base + overlay > 0;
    }, [baseGeometries, overlayGeometries]);

    return (
        <div className="grid gap-4 lg:grid-cols-[2fr,1fr]">
            <div className="rounded-lg border">
                <div className="border-b px-4 py-3">
                    <h3 className="text-sm font-semibold">Geometry Map</h3>
                    <p className="text-muted-foreground mt-0.5 text-xs">Base geometry is shown in blue. Selected snapshot geometry is shown in amber.</p>
                    {IS_DEV_HOST && (
                        <p className="text-muted-foreground mt-1 text-[11px]">
                            Map ready: {String(mapState.mapReady)} · Base: {mapState.baseFeatureCount} · Overlay: {mapState.overlayFeatureCount}
                        </p>
                    )}
                </div>
                <HistoricalMapViewer
                    baseGeometries={baseGeometries}
                    overlayGeometries={overlayGeometries}
                    onRenderStateChange={setMapState}
                />
                {!loading && !hasAnyRenderableGeometry && (
                    <div className="border-t px-4 py-2 text-xs text-muted-foreground">
                        No renderable geometry found for this entity or the selected snapshot.
                    </div>
                )}
            </div>

            <div className="rounded-lg border">
                <div className="border-b px-4 py-3">
                    <h3 className="text-sm font-semibold">Timeline</h3>
                    <p className="text-muted-foreground mt-0.5 text-xs">Snapshots and relationships sorted chronologically.</p>
                </div>
                <div className="max-h-105 space-y-2 overflow-y-auto p-3">
                    {loading && <p className="text-muted-foreground text-sm">Loading timeline…</p>}
                    {!loading && loadError && <p className="text-sm text-destructive">{loadError}</p>}
                    {!loading && !loadError && timelineItems.length === 0 && (
                        <p className="text-muted-foreground text-sm">No snapshots or relationships with timeline data.</p>
                    )}

                    {!loading && !loadError && timelineItems.map((item) => {
                        const selected = item.kind === 'snapshot' && item.snapshot?.snapshot_id === activeSnapshotId;

                        return (
                            <button
                                key={item.id}
                                type="button"
                                onClick={() => item.kind === 'snapshot' && setActiveSnapshotId(item.snapshot?.snapshot_id ?? null)}
                                className={[
                                    'w-full rounded-md border px-3 py-2 text-left',
                                    selected ? 'border-amber-500 bg-amber-500/5' : 'hover:bg-muted/50',
                                ].join(' ')}
                            >
                                <div className="mb-1 flex items-center justify-between gap-2">
                                    <Badge variant={item.kind === 'snapshot' ? 'secondary' : 'outline'}>
                                        {item.kind}
                                    </Badge>
                                    <span className="text-muted-foreground text-xs tabular-nums">
                                        {formatYearRange(item.startYear, item.endYear)}
                                    </span>
                                </div>
                                <p className="text-sm font-medium leading-tight">{item.title}</p>
                                {item.subtitle && (
                                    <p className="text-muted-foreground mt-1 text-xs leading-snug">{item.subtitle}</p>
                                )}
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}

function parseYear(value: string | null): number | null {
    if (value == null || value === '') {
        return null;
    }
    const parsed = Number(value);

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

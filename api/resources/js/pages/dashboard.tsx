import { Head, Link } from '@inertiajs/react';
import { useQuery } from '@tanstack/react-query';
import { CalendarDays, ExternalLink, MapPinned } from 'lucide-react';
import { startTransition, useEffect, useState } from 'react';
import HistoricalMapViewer from '@/components/historical-map-viewer';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import AppLayout from '@/layouts/app-layout';
import type { GeoJsonLike } from '@/lib/geojson';
import { dashboard } from '@/routes';
import { show as showEntity } from '@/routes/entities';
import type { BreadcrumbItem, EntityDetail } from '@/types';

const breadcrumbs: BreadcrumbItem[] = [
    {
        title: 'Dashboard',
        href: dashboard(),
    },
];

type MapFeature = {
    type: 'Feature';
    id: string;
    geometry: GeoJSON.Geometry | null;
    properties: {
        id: string;
        name: string;
        entity_type: string | null;
        entity_group: string | null;
        temporal_start: string | null;
        temporal_end: string | null;
        impact_score: number | null;
        entity_color: string | null;
    };
};

type MapResponse = {
    type: 'FeatureCollection';
    features: MapFeature[];
};

type EntityApiResponse = {
    data: EntityDetail;
};

const DEFAULT_DASHBOARD_YEAR = 100;
const YEAR_STORAGE_KEY = 'historical-dashboard:selected-year';

export default function Dashboard() {
    const [yearInput, setYearInput] = useState(String(DEFAULT_DASHBOARD_YEAR));
    const [selectedYear, setSelectedYear] = useState<number | null>(null);
    const [selectedEntityId, setSelectedEntityId] = useState<string | null>(
        null,
    );

    useEffect(() => {
        const initialYear = getInitialDashboardYear();

        setYearInput(String(initialYear));
        setSelectedYear(initialYear);
    }, []);

    useEffect(() => {
        if (typeof window === 'undefined' || selectedYear === null) {
            return;
        }

        window.sessionStorage.setItem(YEAR_STORAGE_KEY, String(selectedYear));
    }, [selectedYear]);

    const activeYear = selectedYear ?? DEFAULT_DASHBOARD_YEAR;

    const mapQuery = useQuery({
        queryKey: ['dashboard-map', activeYear],
        enabled: selectedYear !== null,
        placeholderData: (previousData) => previousData,
        queryFn: async () => {
            const url = `/api/v1/entities/map/year?${new URLSearchParams({
                year: String(activeYear),
            }).toString()}`;

            const response = await fetch(url, {
                headers: { Accept: 'application/json' },
            });

            if (!response.ok) {
                throw new Error(`Failed to load map data (${response.status})`);
            }

            return (await response.json()) as MapResponse;
        },
    });

    const selectedEntityQuery = useQuery({
        queryKey: ['dashboard-entity', selectedEntityId],
        enabled: selectedEntityId !== null,
        queryFn: async () => {
            const response = await fetch(
                `/api/v1/entities/${selectedEntityId}`,
                {
                    headers: { Accept: 'application/json' },
                },
            );

            if (!response.ok) {
                throw new Error(
                    `Failed to load entity details (${response.status})`,
                );
            }

            const payload = (await response.json()) as
                | EntityApiResponse
                | EntityDetail;

            return unwrapEntityPayload(payload);
        },
    });

    const mapFeatures = mapQuery.data?.features ?? [];
    const selectedEntity = selectedEntityQuery.data ?? null;
    const hasMapData = mapQuery.data !== undefined;

    const handleFeatureClick = (
        feature: { id?: string; properties?: { id?: string } } | null,
    ) => {
        const nextId = feature?.properties?.id ?? feature?.id ?? null;

        startTransition(() => {
            setSelectedEntityId(nextId);
        });
    };

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Historical Dashboard" />
            <div className="flex h-full flex-1 flex-col gap-4 overflow-hidden p-4">
                <section className="relative overflow-hidden rounded-3xl border border-sidebar-border/70 bg-linear-to-br from-stone-50 via-white to-amber-50 shadow-sm dark:border-sidebar-border dark:from-stone-950 dark:via-stone-950 dark:to-stone-900">
                    <div className="absolute inset-y-0 right-0 hidden w-1/3 bg-[radial-gradient(circle_at_top_right,rgba(251,191,36,0.18),transparent_60%)] lg:block" />
                    <div className="relative flex flex-col gap-5 p-5 lg:flex-row lg:items-end lg:justify-between lg:p-6">
                        <div className="max-w-3xl space-y-3">
                            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-amber-200 bg-white/80 px-3 py-1 text-xs font-medium tracking-[0.18em] text-amber-700 uppercase backdrop-blur dark:border-amber-900/60 dark:bg-stone-950/60 dark:text-amber-300">
                                <MapPinned className="size-3.5" />
                                Historical Atlas
                            </div>
                            <div className="space-y-2">
                                <h1 className="font-serif text-3xl tracking-tight text-stone-900 md:text-4xl dark:text-stone-100">
                                    Trace entities across a single historical
                                    year.
                                </h1>
                                <p className="max-w-2xl text-sm leading-6 text-stone-600 dark:text-stone-300">
                                    The map renders entities active in the
                                    selected year when they have a matching
                                    geometry period for map display.
                                </p>
                            </div>
                        </div>

                        <div className="grid gap-3 rounded-2xl border border-stone-200/80 bg-white/90 p-4 shadow-sm backdrop-blur md:grid-cols-[minmax(0,10rem)_auto] md:items-end dark:border-stone-800 dark:bg-stone-950/80">
                            <label className="space-y-2 text-sm font-medium text-stone-700 dark:text-stone-200">
                                <span className="inline-flex items-center gap-2">
                                    <CalendarDays className="size-4" />
                                    Active year
                                </span>
                                <Input
                                    type="number"
                                    value={yearInput}
                                    onChange={(event) => {
                                        const nextInput = event.target.value;
                                        const nextYear = clampYear(nextInput);

                                        setYearInput(nextInput);

                                        startTransition(() => {
                                            setSelectedYear(nextYear);
                                            setSelectedEntityId(null);
                                        });
                                    }}
                                    className="h-11 border-stone-300 bg-white text-base dark:border-stone-700 dark:bg-stone-950"
                                />
                            </label>
                            <div className="grid gap-2 text-sm text-stone-600 dark:text-stone-300">
                                <div>
                                    Showing{' '}
                                    <span className="font-semibold text-stone-900 dark:text-stone-100">
                                        {mapFeatures.length}
                                    </span>{' '}
                                    mapped entities for{' '}
                                    <span className="font-semibold text-stone-900 dark:text-stone-100">
                                        {formatYearLabel(activeYear)}
                                    </span>
                                    .
                                </div>
                                <div className="text-xs tracking-[0.18em] text-stone-500 uppercase dark:text-stone-400">
                                    Global extent • debounced live refresh
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <section className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
                    <div className="overflow-hidden rounded-3xl border border-sidebar-border/70 bg-white shadow-sm dark:border-sidebar-border dark:bg-stone-950">
                        <div className="flex items-center justify-between border-b border-sidebar-border/70 px-4 py-3 dark:border-sidebar-border">
                            <div>
                                <h2 className="text-sm font-semibold text-stone-900 dark:text-stone-100">
                                    Map view
                                </h2>
                                <p className="text-xs text-muted-foreground">
                                    Click a feature to inspect the full entity
                                    record.
                                </p>
                            </div>
                            {mapQuery.isFetching && (
                                <div className="text-xs tracking-[0.18em] text-amber-700 uppercase dark:text-amber-300">
                                    Refreshing
                                </div>
                            )}
                        </div>

                        {mapQuery.isError ? (
                            <div className="flex h-[calc(100vh-18rem)] items-center justify-center px-6 text-center text-sm text-destructive">
                                {(mapQuery.error as Error).message}
                            </div>
                        ) : !hasMapData && mapQuery.isLoading ? (
                            <div className="flex h-[calc(100vh-18rem)] items-center justify-center">
                                <div className="space-y-3 text-center">
                                    <div className="mx-auto size-10 animate-spin rounded-full border-4 border-stone-200 border-t-amber-600 dark:border-stone-800 dark:border-t-amber-400" />
                                    <p className="text-sm text-muted-foreground">
                                        Building the historical layer…
                                    </p>
                                </div>
                            </div>
                        ) : mapFeatures.length > 0 ? (
                            <HistoricalMapViewer
                                className="h-[calc(100vh-18rem)]"
                                baseGeometries={
                                    mapFeatures as unknown as GeoJsonLike[]
                                }
                                timeframeDate={yearToTimeframe(activeYear)}
                                fitBoundsKey={activeYear}
                                dataVersion={mapQuery.dataUpdatedAt}
                                onFeatureClick={handleFeatureClick}
                            />
                        ) : (
                            <div className="flex h-[calc(100vh-18rem)] items-center justify-center px-8 text-center text-sm text-muted-foreground">
                                No mapped entities are active in{' '}
                                {formatYearLabel(activeYear)}.
                            </div>
                        )}
                    </div>

                    <aside className="flex min-h-0 flex-col overflow-hidden rounded-3xl border border-sidebar-border/70 bg-stone-50 shadow-sm dark:border-sidebar-border dark:bg-stone-950">
                        <div className="border-b border-sidebar-border/70 px-4 py-3 dark:border-sidebar-border">
                            <h2 className="text-sm font-semibold text-stone-900 dark:text-stone-100">
                                Selection
                            </h2>
                            <p className="text-xs text-muted-foreground">
                                Summary details for the currently selected
                                entity.
                            </p>
                        </div>

                        <div className="flex-1 overflow-y-auto p-4">
                            {selectedEntityId === null ? (
                                <EmptySelectionState
                                    year={activeYear}
                                    featureCount={mapFeatures.length}
                                />
                            ) : selectedEntityQuery.isLoading ? (
                                <div className="space-y-3 rounded-2xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
                                    <div className="h-4 w-2/3 animate-pulse rounded bg-stone-200 dark:bg-stone-800" />
                                    <div className="h-3 w-full animate-pulse rounded bg-stone-200 dark:bg-stone-800" />
                                    <div className="h-3 w-5/6 animate-pulse rounded bg-stone-200 dark:bg-stone-800" />
                                </div>
                            ) : selectedEntityQuery.isError ||
                              selectedEntity === null ? (
                                <div className="rounded-2xl border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive">
                                    {(
                                        selectedEntityQuery.error as
                                            | Error
                                            | undefined
                                    )?.message ??
                                        'Failed to load entity details.'}
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <div className="rounded-2xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
                                        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                                            <div className="space-y-1">
                                                <h3 className="font-serif text-2xl tracking-tight text-stone-900 dark:text-stone-100">
                                                    {selectedEntity.name}
                                                </h3>
                                                <p className="text-sm text-muted-foreground">
                                                    {formatTypeLabel(
                                                        selectedEntity.entity_type,
                                                    )}
                                                </p>
                                            </div>
                                            {selectedEntity.entity_group && (
                                                <span className="rounded-full border border-stone-300 px-2.5 py-1 text-[11px] font-semibold tracking-[0.18em] text-stone-600 uppercase dark:border-stone-700 dark:text-stone-300">
                                                    {
                                                        selectedEntity.entity_group
                                                    }
                                                </span>
                                            )}
                                        </div>

                                        {selectedEntity.summary && (
                                            <p className="text-sm leading-6 text-stone-700 dark:text-stone-300">
                                                {selectedEntity.summary}
                                            </p>
                                        )}
                                    </div>

                                    <dl className="grid gap-3">
                                        <DetailCard
                                            label="Historical span"
                                            value={
                                                selectedEntity.temporal_display_range ??
                                                buildFallbackRange(
                                                    selectedEntity.temporal_start,
                                                    selectedEntity.temporal_end,
                                                )
                                            }
                                        />
                                        <DetailCard
                                            label="Location"
                                            value={selectedEntity.location_name}
                                        />
                                        <DetailCard
                                            label="Impact score"
                                            value={
                                                selectedEntity.impact_score !=
                                                null
                                                    ? String(
                                                          selectedEntity.impact_score,
                                                      )
                                                    : null
                                            }
                                        />
                                        <DetailCard
                                            label="Verification"
                                            value={formatTypeLabel(
                                                selectedEntity.verification_status,
                                            )}
                                        />
                                    </dl>

                                    <div className="grid gap-2">
                                        <Button
                                            asChild
                                            className="h-10 justify-between rounded-xl bg-stone-900 text-white hover:bg-stone-800 dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-stone-200"
                                        >
                                            <Link
                                                href={
                                                    showEntity(
                                                        selectedEntity.id,
                                                    ).url
                                                }
                                            >
                                                Open full entity record
                                                <ExternalLink className="size-4" />
                                            </Link>
                                        </Button>
                                        <Button
                                            variant="outline"
                                            className="h-10 rounded-xl"
                                            onClick={() =>
                                                setSelectedEntityId(null)
                                            }
                                        >
                                            Clear selection
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </aside>
                </section>
            </div>
        </AppLayout>
    );
}

function EmptySelectionState({
    year,
    featureCount,
}: {
    year: number;
    featureCount: number;
}) {
    return (
        <div className="flex h-full flex-col justify-between rounded-2xl border border-dashed border-stone-300 bg-white/80 p-4 dark:border-stone-700 dark:bg-stone-900/60">
            <div className="space-y-3">
                <div className="inline-flex size-10 items-center justify-center rounded-2xl bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                    <MapPinned className="size-5" />
                </div>
                <div className="space-y-1">
                    <h3 className="text-sm font-semibold text-stone-900 dark:text-stone-100">
                        Nothing selected yet
                    </h3>
                    <p className="text-sm leading-6 text-muted-foreground">
                        Choose a feature on the map to inspect its detail record
                        for {formatYearLabel(year)}.
                    </p>
                </div>
            </div>

            <div className="rounded-2xl bg-stone-100 p-3 text-sm text-stone-700 dark:bg-stone-800 dark:text-stone-300">
                {featureCount} entities are currently visible.
            </div>
        </div>
    );
}

function DetailCard({
    label,
    value,
}: {
    label: string;
    value: string | null | undefined;
}) {
    return (
        <div className="rounded-2xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
            <dt className="text-[11px] font-semibold tracking-[0.18em] text-stone-500 uppercase dark:text-stone-400">
                {label}
            </dt>
            <dd className="mt-1 text-sm leading-6 text-stone-800 dark:text-stone-200">
                {value && value.length > 0 ? value : 'Unknown'}
            </dd>
        </div>
    );
}

function clampYear(value: string): number {
    const parsed = Number.parseInt(value, 10);

    if (!Number.isFinite(parsed)) {
        return DEFAULT_DASHBOARD_YEAR;
    }

    return Math.min(3000, Math.max(-3000, parsed));
}

function getInitialDashboardYear(): number {
    if (typeof window === 'undefined') {
        return DEFAULT_DASHBOARD_YEAR;
    }

    const storedYear = window.sessionStorage.getItem(YEAR_STORAGE_KEY);

    return clampYear(storedYear ?? String(DEFAULT_DASHBOARD_YEAR));
}

function yearToTimeframe(year: number): string {
    return `${year}-01-01`;
}

function formatTypeLabel(value: string | null | undefined): string {
    if (!value) {
        return 'Unknown';
    }

    return value
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatYearLabel(year: number): string {
    return year < 0 ? `${Math.abs(year)} BCE` : `${year} CE`;
}

function buildFallbackRange(start: string | null, end: string | null): string {
    if (start && end) {
        return `${start} to ${end}`;
    }

    return start ?? end ?? 'Unknown';
}

function unwrapEntityPayload(
    payload: EntityApiResponse | EntityDetail,
): EntityDetail {
    return 'data' in payload ? payload.data : payload;
}

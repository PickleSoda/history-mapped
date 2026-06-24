import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type { GeoJsonLike } from '@/lib/geojson';
import { yearToOhmDate } from '@/lib/ohm-date';

const MapEditor = lazy(() => import('@/components/map-editor'));

type GeometryPeriodSummary = {
    geometry_period_id: string;
    entity_id: string;
    period_type: string;
    start_year: number;
    end_year: number;
    description: string | null;
    provenance_mode: 'manual' | 'derived';
    has_geom: boolean;
    has_territory_geom: boolean;
};

type GeometryPeriodDetail = GeometryPeriodSummary & {
    geom: Record<string, unknown> | null;
    territory_geom: Record<string, unknown> | null;
};

type GeometryPeriodPayload = {
    period_type: string;
    start_year: number;
    end_year: number;
    description?: string;
    provenance_mode: 'manual' | 'derived';
    geom?: Record<string, unknown>;
    territory_geom?: Record<string, unknown>;
};

type Props = {
    listUrl: string;
    detailUrlFn?: (periodId: string) => string;
    storeUrl?: string;
    updateUrlFn?: (periodId: string) => string;
    deleteUrlFn?: (periodId: string) => string;
    backfillUrl?: string;
    readOnly?: boolean;
    onSelectPeriod?: (period: GeometryPeriodDetail | null) => void;
};

type BackfillCounts = {
    aliases: number;
    tags: number;
    temporal_ranges: number;
    locations: number;
    geometry_periods: number;
};

const PERIOD_TYPES = [
    'territory',
    'route',
    'spread_zone',
    'movement_path',
    'presence',
] as const;

type GeometryPeriodFormState = {
    period_type: string;
    start_year: string;
    end_year: string;
    description: string;
    provenance_mode: 'manual' | 'derived';
    geom: GeoJsonLike;
    territory_geom: GeoJsonLike;
};

function defaultFormState(): GeometryPeriodFormState {
    return {
        period_type: 'territory',
        start_year: '',
        end_year: '',
        description: '',
        provenance_mode: 'manual',
        geom: null,
        territory_geom: null,
    };
}

function toFormState(period: GeometryPeriodDetail): GeometryPeriodFormState {
    return {
        period_type: period.period_type,
        start_year: String(period.start_year),
        end_year: String(period.end_year),
        description: period.description ?? '',
        provenance_mode: period.provenance_mode,
        geom: period.geom,
        territory_geom: period.territory_geom,
    };
}

function buildPayload(
    form: GeometryPeriodFormState,
): GeometryPeriodPayload | null {
    const startYear = Number(form.start_year);
    const endYear = Number(form.end_year);

    if (!Number.isFinite(startYear) || !Number.isFinite(endYear)) {
        return null;
    }

    if (!form.geom && !form.territory_geom) {
        return null;
    }

    return {
        period_type: form.period_type,
        start_year: startYear,
        end_year: endYear,
        description: form.description || undefined,
        provenance_mode: form.provenance_mode,
        geom: form.geom ?? undefined,
        territory_geom: form.territory_geom ?? undefined,
    };
}

function resolveTimeframeDate(value: string): string | null {
    const year = Number.parseInt(value, 10);

    return Number.isFinite(year) ? yearToOhmDate(year) : null;
}

function describeGeometry(form: GeometryPeriodFormState): string {
    const parts: string[] = [];

    if (form.geom && typeof form.geom === 'object' && 'type' in form.geom) {
        parts.push(`Geom: ${String(form.geom.type)}`);
    }

    if (
        form.territory_geom &&
        typeof form.territory_geom === 'object' &&
        'type' in form.territory_geom
    ) {
        parts.push(`Territory: ${String(form.territory_geom.type)}`);
    }

    return parts.length > 0 ? parts.join(' • ') : 'No geometry drawn yet';
}

export default function EntityGeometryPeriodsPanel({
    listUrl,
    detailUrlFn,
    storeUrl,
    updateUrlFn,
    deleteUrlFn,
    backfillUrl,
    readOnly = false,
    onSelectPeriod,
}: Props) {
    const csrfRef = useRef<string>('');
    const [periods, setPeriods] = useState<GeometryPeriodSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [backfilling, setBackfilling] = useState(false);
    const [backfillMessage, setBackfillMessage] = useState<string | null>(null);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [loadingPeriodId, setLoadingPeriodId] = useState<string | null>(null);

    const [createForm, setCreateForm] =
        useState<GeometryPeriodFormState>(defaultFormState);
    const [editForm, setEditForm] =
        useState<GeometryPeriodFormState>(defaultFormState);

    useEffect(() => {
        const token = document
            .querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
            ?.getAttribute('content');

        csrfRef.current = token ?? '';
    }, []);

    async function loadPeriods() {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(listUrl, {
                headers: { Accept: 'application/json' },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const payload = (await response.json()) as {
                data: GeometryPeriodSummary[];
            };
            setPeriods(payload.data ?? []);
        } catch {
            setError('Failed to load geometry periods.');
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        void loadPeriods();
    }, [listUrl]);

    async function runBackfill() {
        if (!backfillUrl) {
            return;
        }

        setBackfilling(true);
        setError(null);
        setBackfillMessage(null);

        try {
            const response = await fetch(backfillUrl, {
                method: 'POST',
                headers: {
                    Accept: 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const payload = (await response.json()) as {
                data: { counts: BackfillCounts };
            };
            const counts = payload.data.counts;

            setBackfillMessage(
                `Backfilled: ${counts.geometry_periods} geometry period(s), ` +
                    `${counts.locations} location(s), ${counts.temporal_ranges} temporal range(s), ` +
                    `${counts.aliases} alias(es), ${counts.tags} tag(s).`,
            );

            // Reflect any newly-derived periods in the list.
            await loadPeriods();
        } catch {
            setError('Failed to backfill this entity.');
        } finally {
            setBackfilling(false);
        }
    }

    useEffect(() => {
        onSelectPeriod?.(null);
    }, [listUrl, onSelectPeriod]);

    const sortedPeriods = useMemo(() => {
        return [...periods].sort((a, b) => {
            if (a.start_year !== b.start_year) {
                return a.start_year - b.start_year;
            }

            return a.end_year - b.end_year;
        });
    }, [periods]);

    async function loadPeriodDetail(
        periodId: string,
    ): Promise<GeometryPeriodDetail | null> {
        if (!detailUrlFn) {
            return null;
        }

        setLoadingPeriodId(periodId);
        setError(null);

        try {
            const response = await fetch(detailUrlFn(periodId), {
                headers: { Accept: 'application/json' },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const payload = (await response.json()) as {
                data: GeometryPeriodDetail;
            };

            return payload.data;
        } catch {
            setError('Failed to load geometry period detail.');

            return null;
        } finally {
            setLoadingPeriodId((current) =>
                current === periodId ? null : current,
            );
        }
    }

    async function createPeriod() {
        if (!storeUrl) {
            return;
        }

        const payload = buildPayload(createForm);

        if (!payload) {
            setError(
                'Start year, end year, and at least one drawn geometry are required.',
            );

            return;
        }

        setSaving(true);
        setError(null);

        try {
            const response = await fetch(storeUrl, {
                method: 'POST',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            await loadPeriods();
            setCreateForm(defaultFormState());
        } catch {
            setError('Failed to create geometry period.');
        } finally {
            setSaving(false);
        }
    }

    async function updatePeriod(periodId: string) {
        if (!updateUrlFn) {
            return;
        }

        const payload = buildPayload(editForm);

        if (!payload) {
            setError('Valid years and geometry are required for updates.');

            return;
        }

        setSaving(true);
        setError(null);

        try {
            const response = await fetch(updateUrlFn(periodId), {
                method: 'PUT',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            await loadPeriods();
            setEditingId(null);
        } catch {
            setError('Failed to update geometry period.');
        } finally {
            setSaving(false);
        }
    }

    async function beginEditPeriod(period: GeometryPeriodSummary) {
        const detail = await loadPeriodDetail(period.geometry_period_id);

        if (!detail) {
            return;
        }

        setEditForm(toFormState(detail));
        setEditingId(detail.geometry_period_id);
    }

    async function selectPeriod(period: GeometryPeriodSummary) {
        if (!onSelectPeriod) {
            return;
        }

        const detail = await loadPeriodDetail(period.geometry_period_id);

        if (!detail) {
            return;
        }

        onSelectPeriod(detail);
    }

    async function deletePeriod(periodId: string) {
        if (!deleteUrlFn) {
            return;
        }

        setSaving(true);
        setError(null);

        try {
            const response = await fetch(deleteUrlFn(periodId), {
                method: 'DELETE',
                headers: {
                    Accept: 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            await loadPeriods();
        } catch {
            setError('Failed to delete geometry period.');
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="space-y-4">
            {!readOnly && backfillUrl && (
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed p-3">
                    <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => void runBackfill()}
                        disabled={backfilling || saving}
                    >
                        {backfilling
                            ? 'Backfilling…'
                            : 'Backfill from primary location'}
                    </Button>
                    <p className="text-xs text-muted-foreground">
                        Derives territory geometry periods (and other canonical
                        rows) so a primary location shows on the map.
                    </p>
                    {backfillMessage && (
                        <p className="w-full text-sm text-emerald-600 dark:text-emerald-400">
                            {backfillMessage}
                        </p>
                    )}
                </div>
            )}
            {error && <p className="text-sm text-destructive">{error}</p>}
            {loading && (
                <p className="text-sm text-muted-foreground">
                    Loading geometry periods…
                </p>
            )}

            {!loading && sortedPeriods.length === 0 && (
                <p className="text-sm text-muted-foreground">
                    No geometry periods defined yet.
                </p>
            )}

            {!loading && sortedPeriods.length > 0 && (
                <div className="space-y-3">
                    {sortedPeriods.map((period) => {
                        const isEditing =
                            editingId === period.geometry_period_id;

                        return (
                            <div
                                key={period.geometry_period_id}
                                className="rounded-lg border p-3"
                            >
                                {isEditing ? (
                                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                        <Input
                                            aria-label="Edit start year"
                                            value={editForm.start_year}
                                            onChange={(e) =>
                                                setEditForm((prev) => ({
                                                    ...prev,
                                                    start_year: e.target.value,
                                                }))
                                            }
                                            placeholder="Start year"
                                        />
                                        <Input
                                            aria-label="Edit end year"
                                            value={editForm.end_year}
                                            onChange={(e) =>
                                                setEditForm((prev) => ({
                                                    ...prev,
                                                    end_year: e.target.value,
                                                }))
                                            }
                                            placeholder="End year"
                                        />
                                        <Input
                                            aria-label="Edit period type"
                                            value={editForm.period_type}
                                            onChange={(e) =>
                                                setEditForm((prev) => ({
                                                    ...prev,
                                                    period_type: e.target.value,
                                                }))
                                            }
                                            placeholder="Period type"
                                        />
                                        <Input
                                            aria-label="Edit provenance mode"
                                            value={editForm.provenance_mode}
                                            onChange={(e) =>
                                                setEditForm((prev) => ({
                                                    ...prev,
                                                    provenance_mode: e.target
                                                        .value as
                                                        | 'manual'
                                                        | 'derived',
                                                }))
                                            }
                                            placeholder="Provenance mode"
                                        />
                                        <div className="sm:col-span-2">
                                            <Textarea
                                                aria-label="Edit description"
                                                value={editForm.description}
                                                onChange={(e) =>
                                                    setEditForm((prev) => ({
                                                        ...prev,
                                                        description:
                                                            e.target.value,
                                                    }))
                                                }
                                                placeholder="Description"
                                                rows={2}
                                            />
                                        </div>
                                        <div className="space-y-2 rounded-md border p-3 sm:col-span-2">
                                            <div className="flex items-center justify-between gap-3">
                                                <div>
                                                    <p className="text-sm font-medium">
                                                        Geometry
                                                    </p>
                                                    <p className="text-xs text-muted-foreground">
                                                        Use the same map editor
                                                        as the base entity
                                                        geometry. Draw a point
                                                        or line in Geom, or a
                                                        polygon in Territory.
                                                    </p>
                                                </div>
                                                <span className="text-xs text-muted-foreground">
                                                    {describeGeometry(editForm)}
                                                </span>
                                            </div>
                                            <Suspense
                                                fallback={
                                                    <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
                                                        Loading map editor…
                                                    </div>
                                                }
                                            >
                                                <MapEditor
                                                    geojson={editForm.geom}
                                                    territoryGeojson={
                                                        editForm.territory_geom
                                                    }
                                                    timeframeDate={resolveTimeframeDate(
                                                        editForm.start_year,
                                                    )}
                                                    onChange={(
                                                        geom,
                                                        territoryGeom,
                                                    ) => {
                                                        setEditForm((prev) => ({
                                                            ...prev,
                                                            geom,
                                                            territory_geom:
                                                                territoryGeom,
                                                        }));
                                                    }}
                                                />
                                            </Suspense>
                                        </div>
                                        <div className="flex gap-2 sm:col-span-2">
                                            <Button
                                                type="button"
                                                size="sm"
                                                onClick={() =>
                                                    void updatePeriod(
                                                        period.geometry_period_id,
                                                    )
                                                }
                                                disabled={saving}
                                            >
                                                Save
                                            </Button>
                                            <Button
                                                type="button"
                                                size="sm"
                                                variant="outline"
                                                onClick={() =>
                                                    setEditingId(null)
                                                }
                                            >
                                                Cancel
                                            </Button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        <p className="text-sm font-medium">
                                            {period.start_year} -{' '}
                                            {period.end_year}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {period.period_type} |{' '}
                                            {period.provenance_mode}
                                        </p>
                                        {period.description && (
                                            <p className="text-sm text-muted-foreground">
                                                {period.description}
                                            </p>
                                        )}
                                        {!readOnly && (
                                            <div className="flex gap-2">
                                                {onSelectPeriod && (
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        onClick={() =>
                                                            void selectPeriod(
                                                                period,
                                                            )
                                                        }
                                                        disabled={
                                                            loadingPeriodId ===
                                                            period.geometry_period_id
                                                        }
                                                    >
                                                        {loadingPeriodId ===
                                                        period.geometry_period_id
                                                            ? 'Loading…'
                                                            : 'Highlight'}
                                                    </Button>
                                                )}
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() =>
                                                        void beginEditPeriod(
                                                            period,
                                                        )
                                                    }
                                                    disabled={
                                                        loadingPeriodId ===
                                                        period.geometry_period_id
                                                    }
                                                >
                                                    {loadingPeriodId ===
                                                    period.geometry_period_id
                                                        ? 'Loading…'
                                                        : 'Edit'}
                                                </Button>
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="destructive"
                                                    onClick={() =>
                                                        void deletePeriod(
                                                            period.geometry_period_id,
                                                        )
                                                    }
                                                    disabled={saving}
                                                >
                                                    Delete
                                                </Button>
                                            </div>
                                        )}
                                        {readOnly && onSelectPeriod && (
                                            <div className="flex gap-2">
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() =>
                                                        void selectPeriod(
                                                            period,
                                                        )
                                                    }
                                                    disabled={
                                                        loadingPeriodId ===
                                                        period.geometry_period_id
                                                    }
                                                >
                                                    {loadingPeriodId ===
                                                    period.geometry_period_id
                                                        ? 'Loading…'
                                                        : 'Highlight'}
                                                </Button>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {!readOnly && (
                <div className="space-y-2 rounded-lg border p-3">
                    <h4 className="text-sm font-medium">Add Geometry Period</h4>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <Input
                            aria-label="Start year"
                            value={createForm.start_year}
                            onChange={(e) =>
                                setCreateForm((prev) => ({
                                    ...prev,
                                    start_year: e.target.value,
                                }))
                            }
                            placeholder="Start year"
                        />
                        <Input
                            aria-label="End year"
                            value={createForm.end_year}
                            onChange={(e) =>
                                setCreateForm((prev) => ({
                                    ...prev,
                                    end_year: e.target.value,
                                }))
                            }
                            placeholder="End year"
                        />
                        <Input
                            aria-label="Period type"
                            value={createForm.period_type}
                            onChange={(e) =>
                                setCreateForm((prev) => ({
                                    ...prev,
                                    period_type: e.target.value,
                                }))
                            }
                            placeholder="Period type"
                            list="period-types"
                        />
                        <datalist id="period-types">
                            {PERIOD_TYPES.map((value) => (
                                <option key={value} value={value} />
                            ))}
                        </datalist>
                        <Input
                            aria-label="Provenance mode"
                            value={createForm.provenance_mode}
                            onChange={(e) =>
                                setCreateForm((prev) => ({
                                    ...prev,
                                    provenance_mode: e.target.value as
                                        | 'manual'
                                        | 'derived',
                                }))
                            }
                            placeholder="manual or derived"
                        />
                        <div className="sm:col-span-2">
                            <Textarea
                                aria-label="Description"
                                value={createForm.description}
                                onChange={(e) =>
                                    setCreateForm((prev) => ({
                                        ...prev,
                                        description: e.target.value,
                                    }))
                                }
                                placeholder="Why this geometry exists"
                                rows={2}
                            />
                        </div>
                        <div className="space-y-2 rounded-md border p-3 sm:col-span-2">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <p className="text-sm font-medium">
                                        Geometry
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                        Draw a point or line in Geom, or a
                                        polygon in Territory.
                                    </p>
                                </div>
                                <span className="text-xs text-muted-foreground">
                                    {describeGeometry(createForm)}
                                </span>
                            </div>
                            <Suspense
                                fallback={
                                    <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
                                        Loading map editor…
                                    </div>
                                }
                            >
                                <MapEditor
                                    geojson={createForm.geom}
                                    territoryGeojson={createForm.territory_geom}
                                    timeframeDate={resolveTimeframeDate(
                                        createForm.start_year,
                                    )}
                                    onChange={(geom, territoryGeom) => {
                                        setCreateForm((prev) => ({
                                            ...prev,
                                            geom,
                                            territory_geom: territoryGeom,
                                        }));
                                    }}
                                />
                            </Suspense>
                        </div>
                        <div className="sm:col-span-2">
                            <Button
                                type="button"
                                onClick={() => void createPeriod()}
                                disabled={saving}
                            >
                                Add Period
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

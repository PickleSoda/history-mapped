import { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

type GeometryPeriod = {
    geometry_period_id: string;
    entity_id: string;
    period_type: string;
    start_year: number;
    end_year: number;
    description: string | null;
    provenance_mode: 'manual' | 'derived';
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
    storeUrl?: string;
    updateUrlFn?: (periodId: string) => string;
    deleteUrlFn?: (periodId: string) => string;
    readOnly?: boolean;
    onSelectPeriod?: (period: GeometryPeriod | null) => void;
};

const PERIOD_TYPES = ['territory', 'route', 'spread_zone', 'movement_path', 'presence'] as const;

function parsePointCoordinates(geom: Record<string, unknown> | null): { lng: string; lat: string } {
    if (!geom || geom.type !== 'Point' || !Array.isArray(geom.coordinates)) {
        return { lng: '', lat: '' };
    }

    const coordinates = geom.coordinates as unknown[];
    const lng = typeof coordinates[0] === 'number' ? String(coordinates[0]) : '';
    const lat = typeof coordinates[1] === 'number' ? String(coordinates[1]) : '';

    return { lng, lat };
}

export default function EntityGeometryPeriodsPanel({
    listUrl,
    storeUrl,
    updateUrlFn,
    deleteUrlFn,
    readOnly = false,
    onSelectPeriod,
}: Props) {
    const csrfRef = useRef<string>('');
    const [periods, setPeriods] = useState<GeometryPeriod[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);

    const [createForm, setCreateForm] = useState({
        period_type: 'territory',
        start_year: '',
        end_year: '',
        description: '',
        provenance_mode: 'manual' as 'manual' | 'derived',
        lng: '',
        lat: '',
    });

    const [editForm, setEditForm] = useState({
        period_type: 'territory',
        start_year: '',
        end_year: '',
        description: '',
        provenance_mode: 'manual' as 'manual' | 'derived',
        lng: '',
        lat: '',
    });

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

            const payload = (await response.json()) as { data: GeometryPeriod[] };
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

    function buildCreatePayload(): GeometryPeriodPayload | null {
        const startYear = Number(createForm.start_year);
        const endYear = Number(createForm.end_year);
        const lng = Number(createForm.lng);
        const lat = Number(createForm.lat);

        if (!Number.isFinite(startYear) || !Number.isFinite(endYear)) {
            return null;
        }

        if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
            return null;
        }

        return {
            period_type: createForm.period_type,
            start_year: startYear,
            end_year: endYear,
            description: createForm.description || undefined,
            provenance_mode: createForm.provenance_mode,
            geom: {
                type: 'Point',
                coordinates: [lng, lat],
            },
        };
    }

    function buildEditPayload(existing: GeometryPeriod): GeometryPeriodPayload | null {
        const startYear = Number(editForm.start_year);
        const endYear = Number(editForm.end_year);
        const lng = Number(editForm.lng);
        const lat = Number(editForm.lat);

        if (!Number.isFinite(startYear) || !Number.isFinite(endYear)) {
            return null;
        }

        const payload: GeometryPeriodPayload = {
            period_type: editForm.period_type,
            start_year: startYear,
            end_year: endYear,
            description: editForm.description || undefined,
            provenance_mode: editForm.provenance_mode,
        };

        if (Number.isFinite(lng) && Number.isFinite(lat)) {
            payload.geom = {
                type: 'Point',
                coordinates: [lng, lat],
            };
        } else if (existing.geom) {
            payload.geom = existing.geom;
        } else if (existing.territory_geom) {
            payload.territory_geom = existing.territory_geom;
        } else {
            return null;
        }

        return payload;
    }

    async function createPeriod() {
        if (!storeUrl) {
            return;
        }

        const payload = buildCreatePayload();

        if (!payload) {
            setError('Start year, end year, and valid point coordinates are required.');

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
            setCreateForm({
                period_type: 'territory',
                start_year: '',
                end_year: '',
                description: '',
                provenance_mode: 'manual',
                lng: '',
                lat: '',
            });
        } catch {
            setError('Failed to create geometry period.');
        } finally {
            setSaving(false);
        }
    }

    async function updatePeriod(period: GeometryPeriod) {
        if (!updateUrlFn) {
            return;
        }

        const payload = buildEditPayload(period);

        if (!payload) {
            setError('Valid years and geometry are required for updates.');

            return;
        }

        setSaving(true);
        setError(null);

        try {
            const response = await fetch(updateUrlFn(period.geometry_period_id), {
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
            {error && <p className="text-sm text-destructive">{error}</p>}
            {loading && (
                <p className="text-sm text-muted-foreground">Loading geometry periods…</p>
            )}

            {!loading && sortedPeriods.length === 0 && (
                <p className="text-sm text-muted-foreground">No geometry periods defined yet.</p>
            )}

            {!loading && sortedPeriods.length > 0 && (
                <div className="space-y-3">
                    {sortedPeriods.map((period) => {
                        const isEditing = editingId === period.geometry_period_id;

                        return (
                            <div key={period.geometry_period_id} className="rounded-lg border p-3">
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
                                            aria-label="Edit longitude"
                                            value={editForm.lng}
                                            onChange={(e) =>
                                                setEditForm((prev) => ({
                                                    ...prev,
                                                    lng: e.target.value,
                                                }))
                                            }
                                            placeholder="Longitude"
                                        />
                                        <Input
                                            aria-label="Edit latitude"
                                            value={editForm.lat}
                                            onChange={(e) =>
                                                setEditForm((prev) => ({
                                                    ...prev,
                                                    lat: e.target.value,
                                                }))
                                            }
                                            placeholder="Latitude"
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
                                                    provenance_mode: e.target.value as 'manual' | 'derived',
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
                                                        description: e.target.value,
                                                    }))
                                                }
                                                placeholder="Description"
                                                rows={2}
                                            />
                                        </div>
                                        <div className="sm:col-span-2 flex gap-2">
                                            <Button
                                                type="button"
                                                size="sm"
                                                onClick={() => void updatePeriod(period)}
                                                disabled={saving}
                                            >
                                                Save
                                            </Button>
                                            <Button
                                                type="button"
                                                size="sm"
                                                variant="outline"
                                                onClick={() => setEditingId(null)}
                                            >
                                                Cancel
                                            </Button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        <p className="text-sm font-medium">
                                            {period.start_year} - {period.end_year}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {period.period_type} | {period.provenance_mode}
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
                                                        onClick={() => onSelectPeriod(period)}
                                                    >
                                                        Highlight
                                                    </Button>
                                                )}
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => {
                                                        const point = parsePointCoordinates(
                                                            period.geom,
                                                        );
                                                        setEditForm({
                                                            period_type: period.period_type,
                                                            start_year: String(period.start_year),
                                                            end_year: String(period.end_year),
                                                            description:
                                                                period.description ?? '',
                                                            provenance_mode:
                                                                period.provenance_mode,
                                                            lng: point.lng,
                                                            lat: point.lat,
                                                        });
                                                        setEditingId(
                                                            period.geometry_period_id,
                                                        );
                                                    }}
                                                >
                                                    Edit
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
                                                    onClick={() => onSelectPeriod(period)}
                                                >
                                                    Highlight
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
                <div className="rounded-lg border p-3 space-y-2">
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
                            aria-label="Longitude"
                            value={createForm.lng}
                            onChange={(e) =>
                                setCreateForm((prev) => ({
                                    ...prev,
                                    lng: e.target.value,
                                }))
                            }
                            placeholder="Longitude"
                        />
                        <Input
                            aria-label="Latitude"
                            value={createForm.lat}
                            onChange={(e) =>
                                setCreateForm((prev) => ({
                                    ...prev,
                                    lat: e.target.value,
                                }))
                            }
                            placeholder="Latitude"
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
                                    provenance_mode: e.target.value as 'manual' | 'derived',
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

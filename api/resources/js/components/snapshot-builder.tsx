/**
 * SnapshotBuilder — embedded UI for managing geometry snapshots on the entity edit page.
 *
 * Allows listing, creating, editing, and deleting geometry snapshots for an entity.
 * Each snapshot has a year range and at least one geometry drawn via MapEditor.
 *
 * Communicates with GeometrySnapshotController via JSON fetch (not Inertia navigation).
 */

import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { ConfidenceLevel, GeometrySnapshot } from '@/types/entity';

const MapEditor = lazy(() => import('@/components/map-editor'));

// ── Types ─────────────────────────────────────────────────────────────────────

type GeoJsonGeometry = Record<string, unknown> | null;

type SnapshotFormData = {
    year_start: string;
    year_end: string;
    label: string;
    confidence: ConfidenceLevel | '';
    notes: string;
    display_priority: string;
    geojson: GeoJsonGeometry;
    territory_geojson: GeoJsonGeometry;
};

type SnapshotBuilderProps = {
    entityId: string;
    /** Route helpers — passed from parent to avoid Wayfinder import issues in lazy-loaded context */
    listUrl: string;
    storeUrl: string;
    updateUrlFn: (snapshotId: string) => string;
    deleteUrlFn: (snapshotId: string) => string;
};

const CONFIDENCE_OPTIONS: Array<{ value: ConfidenceLevel; label: string }> = [
    { value: 'high', label: 'High' },
    { value: 'medium', label: 'Medium' },
    { value: 'low', label: 'Low' },
    { value: 'unresolved', label: 'Unresolved' },
];

function emptyForm(): SnapshotFormData {
    return {
        year_start: '',
        year_end: '',
        label: '',
        confidence: '',
        notes: '',
        display_priority: '0',
        geojson: null,
        territory_geojson: null,
    };
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function SnapshotBuilder({
    entityId,
    listUrl,
    storeUrl,
    updateUrlFn,
    deleteUrlFn,
}: SnapshotBuilderProps) {
    const [snapshots, setSnapshots] = useState<GeometrySnapshot[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);

    // Editing state
    const [editingId, setEditingId] = useState<string | null>(null); // null = creating new
    const [formOpen, setFormOpen] = useState(false);
    const [form, setForm] = useState<SnapshotFormData>(emptyForm());
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);

    // Keep a stable ref for the entity CSRF token
    const csrfRef = useRef<string>('');
    useEffect(() => {
        const meta = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]');
        csrfRef.current = meta?.content ?? '';
    }, []);

    // Load snapshots on mount
    const reload = useCallback(async () => {
        setLoading(true);
        setLoadError(null);
        try {
            const res = await fetch(listUrl, {
                headers: { Accept: 'application/json', 'X-CSRF-TOKEN': csrfRef.current },
            });
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            const json = (await res.json()) as { snapshots: GeometrySnapshot[] };
            setSnapshots(json.snapshots);
        } catch (err) {
            setLoadError('Failed to load snapshots.');
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [listUrl]);

    useEffect(() => { void reload(); }, [reload]);

    // Open the form for creating
    function openCreate() {
        setEditingId(null);
        setForm(emptyForm());
        setFormErrors({});
        setFormOpen(true);
    }

    // Open the form pre-filled for editing
    function openEdit(snapshot: GeometrySnapshot) {
        setEditingId(snapshot.snapshot_id);
        setForm({
            year_start: String(snapshot.year_start),
            year_end: String(snapshot.year_end),
            label: snapshot.label ?? '',
            confidence: snapshot.confidence ?? '',
            notes: snapshot.notes ?? '',
            display_priority: String(snapshot.display_priority),
            geojson: snapshot.geojson,
            territory_geojson: snapshot.territory_geojson,
        });
        setFormErrors({});
        setFormOpen(true);
    }

    function closeForm() {
        setFormOpen(false);
        setEditingId(null);
    }

    function handleFormChange<K extends keyof SnapshotFormData>(field: K, value: SnapshotFormData[K]) {
        setForm((prev) => ({ ...prev, [field]: value }));
    }

    async function handleSave() {
        setSaving(true);
        setFormErrors({});

        const payload: Record<string, unknown> = {
            year_start: form.year_start !== '' ? Number(form.year_start) : undefined,
            year_end: form.year_end !== '' ? Number(form.year_end) : undefined,
            label: form.label || undefined,
            confidence: form.confidence || undefined,
            notes: form.notes || undefined,
            display_priority: form.display_priority !== '' ? Number(form.display_priority) : 0,
            geojson: form.geojson ?? undefined,
            territory_geojson: form.territory_geojson ?? undefined,
        };

        const isCreating = editingId === null;
        const url = isCreating ? storeUrl : updateUrlFn(editingId!);
        const method = isCreating ? 'POST' : 'PUT';

        try {
            const res = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    Accept: 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
                body: JSON.stringify(payload),
            });

            if (res.status === 422) {
                const json = (await res.json()) as { errors?: Record<string, string[]> };
                const flat: Record<string, string> = {};
                for (const [key, msgs] of Object.entries(json.errors ?? {})) {
                    flat[key] = msgs[0] ?? '';
                }
                setFormErrors(flat);
                return;
            }

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }

            closeForm();
            await reload();
        } catch (err) {
            setFormErrors({ _: 'Save failed. Please try again.' });
            console.error(err);
        } finally {
            setSaving(false);
        }
    }

    async function handleDelete(snapshotId: string) {
        if (!confirm('Delete this snapshot? This cannot be undone.')) {
            return;
        }
        setDeletingId(snapshotId);
        try {
            const res = await fetch(deleteUrlFn(snapshotId), {
                method: 'DELETE',
                headers: { Accept: 'application/json', 'X-CSRF-TOKEN': csrfRef.current },
            });
            if (!res.ok && res.status !== 204) {
                throw new Error(`HTTP ${res.status}`);
            }
            await reload();
        } catch (err) {
            alert('Delete failed. Please try again.');
            console.error(err);
        } finally {
            setDeletingId(null);
        }
    }

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-semibold">Geometry Snapshots</h3>
                    <p className="text-muted-foreground text-xs mt-0.5">
                        Time-varying geometries for this entity (e.g. territorial changes over centuries)
                    </p>
                </div>
                <Button type="button" size="sm" onClick={openCreate} disabled={formOpen}>
                    Add Snapshot
                </Button>
            </div>

            {/* Load error */}
            {loadError && (
                <p className="text-sm text-destructive">{loadError}</p>
            )}

            {/* Snapshot list */}
            {loading ? (
                <div className="text-muted-foreground py-4 text-center text-sm">Loading snapshots…</div>
            ) : snapshots.length === 0 ? (
                <div className="text-muted-foreground rounded-lg border border-dashed py-6 text-center text-sm">
                    No snapshots yet. Add one to record time-varying geometry.
                </div>
            ) : (
                <div className="divide-y rounded-lg border">
                    {snapshots.map((s) => (
                        <SnapshotRow
                            key={s.snapshot_id}
                            snapshot={s}
                            onEdit={() => openEdit(s)}
                            onDelete={() => void handleDelete(s.snapshot_id)}
                            deleting={deletingId === s.snapshot_id}
                        />
                    ))}
                </div>
            )}

            {/* Inline form */}
            {formOpen && (
                <SnapshotForm
                    form={form}
                    errors={formErrors}
                    saving={saving}
                    isEditing={editingId !== null}
                    onChange={handleFormChange}
                    onSave={() => void handleSave()}
                    onCancel={closeForm}
                />
            )}
        </div>
    );
}

// ── SnapshotRow ───────────────────────────────────────────────────────────────

function SnapshotRow({
    snapshot,
    onEdit,
    onDelete,
    deleting,
}: {
    snapshot: GeometrySnapshot;
    onEdit: () => void;
    onDelete: () => void;
    deleting: boolean;
}) {
    const hasGeom = snapshot.geojson !== null;
    const hasTerritoryGeom = snapshot.territory_geojson !== null;
    const yearRange = formatYearRange(snapshot.year_start, snapshot.year_end);

    return (
        <div className="flex items-center justify-between px-4 py-3">
            <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium tabular-nums">{yearRange}</span>
                    {snapshot.label && (
                        <span className="text-muted-foreground text-sm truncate">{snapshot.label}</span>
                    )}
                    {snapshot.confidence && (
                        <span className="bg-muted text-muted-foreground rounded px-1.5 py-0.5 text-[10px] font-medium uppercase">
                            {snapshot.confidence}
                        </span>
                    )}
                </div>
                <div className="text-muted-foreground mt-0.5 flex gap-2 text-xs">
                    {hasGeom && <span>Point/line</span>}
                    {hasTerritoryGeom && <span>Territory polygon</span>}
                    {!hasGeom && !hasTerritoryGeom && (
                        <span className="text-destructive">No geometry</span>
                    )}
                </div>
            </div>
            <div className="ml-4 flex shrink-0 gap-2">
                <Button type="button" variant="outline" size="sm" onClick={onEdit}>
                    Edit
                </Button>
                <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    onClick={onDelete}
                    disabled={deleting}
                >
                    {deleting ? 'Deleting…' : 'Delete'}
                </Button>
            </div>
        </div>
    );
}

// ── SnapshotForm ──────────────────────────────────────────────────────────────

type SnapshotFormProps = {
    form: SnapshotFormData;
    errors: Record<string, string>;
    saving: boolean;
    isEditing: boolean;
    onChange: <K extends keyof SnapshotFormData>(field: K, value: SnapshotFormData[K]) => void;
    onSave: () => void;
    onCancel: () => void;
};

function SnapshotForm({ form, errors, saving, isEditing, onChange, onSave, onCancel }: SnapshotFormProps) {
    const [mapOpen, setMapOpen] = useState(false);

    return (
        <div className="rounded-lg border bg-card p-4 space-y-4">
            <h4 className="text-sm font-semibold">{isEditing ? 'Edit Snapshot' : 'New Snapshot'}</h4>

            {errors['_'] && (
                <p className="text-sm text-destructive">{errors['_']}</p>
            )}

            {/* Year range */}
            <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                    <Label htmlFor="snap-year-start" className="text-xs">
                        Year Start <span className="text-muted-foreground">(negative = BCE)</span>
                    </Label>
                    <Input
                        id="snap-year-start"
                        type="number"
                        value={form.year_start}
                        onChange={(e) => onChange('year_start', e.target.value)}
                        placeholder="-27"
                    />
                    {errors['year_start'] && <p className="text-xs text-destructive">{errors['year_start']}</p>}
                </div>
                <div className="space-y-1">
                    <Label htmlFor="snap-year-end" className="text-xs">Year End</Label>
                    <Input
                        id="snap-year-end"
                        type="number"
                        value={form.year_end}
                        onChange={(e) => onChange('year_end', e.target.value)}
                        placeholder="476"
                    />
                    {errors['year_end'] && <p className="text-xs text-destructive">{errors['year_end']}</p>}
                </div>
            </div>

            {/* Label + confidence */}
            <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                    <Label htmlFor="snap-label" className="text-xs">Label (optional)</Label>
                    <Input
                        id="snap-label"
                        value={form.label}
                        onChange={(e) => onChange('label', e.target.value)}
                        placeholder="e.g. Maximum extent under Trajan"
                        maxLength={500}
                    />
                </div>
                <div className="space-y-1">
                    <Label htmlFor="snap-confidence" className="text-xs">Confidence</Label>
                    <select
                        id="snap-confidence"
                        className="border-input bg-background h-9 w-full rounded-md border px-3 py-1 text-sm"
                        value={form.confidence}
                        onChange={(e) => onChange('confidence', e.target.value as ConfidenceLevel | '')}
                    >
                        <option value="">— select —</option>
                        {CONFIDENCE_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Notes */}
            <div className="space-y-1">
                <Label htmlFor="snap-notes" className="text-xs">Notes (optional)</Label>
                <textarea
                    id="snap-notes"
                    className="border-input bg-background min-h-[80px] w-full rounded-md border px-3 py-2 text-sm"
                    value={form.notes}
                    onChange={(e) => onChange('notes', e.target.value)}
                    placeholder="Editorial notes about this snapshot…"
                    maxLength={5000}
                />
            </div>

            {/* Geometry section */}
            <div className="rounded-md border">
                <button
                    type="button"
                    onClick={() => setMapOpen((v) => !v)}
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium"
                >
                    <span>Geometry</span>
                    <span className="text-muted-foreground">
                        {mapOpen ? 'Collapse' : 'Expand'}
                        {(form.geojson || form.territory_geojson) && (
                            <span className="bg-primary/10 text-primary ml-2 rounded px-1.5 py-0.5 text-[10px] font-semibold">
                                Set
                            </span>
                        )}
                    </span>
                </button>

                {errors['geojson'] && (
                    <p className="px-3 pb-2 text-xs text-destructive">{errors['geojson']}</p>
                )}

                {mapOpen && (
                    <div className="border-t">
                        <Suspense
                            fallback={
                                <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
                                    Loading map…
                                </div>
                            }
                        >
                            <MapEditor
                                geojson={form.geojson}
                                territoryGeojson={form.territory_geojson}
                                onChange={(geo, territory) => {
                                    onChange('geojson', geo);
                                    onChange('territory_geojson', territory);
                                }}
                            />
                        </Suspense>
                    </div>
                )}
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={saving}>
                    Cancel
                </Button>
                <Button type="button" size="sm" onClick={onSave} disabled={saving}>
                    {saving ? 'Saving…' : isEditing ? 'Save Changes' : 'Create Snapshot'}
                </Button>
            </div>
        </div>
    );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatYear(year: number): string {
    if (year < 0) {
        return `${Math.abs(year)} BCE`;
    }
    return `${year} CE`;
}

function formatYearRange(start: number, end: number): string {
    if (start === end) {
        return formatYear(start);
    }
    return `${formatYear(start)} – ${formatYear(end)}`;
}

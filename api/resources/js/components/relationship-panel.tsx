/**
 * RelationshipPanel — embedded UI for managing entity relationships.
 *
 * Allows listing, creating, and deleting relationships for an entity.
 * Outgoing relationships (where this entity is the source) can be deleted.
 * Incoming relationships are shown read-only.
 *
 * Derived presence geometry is created server-side transparently when applicable.
 *
 * Communicates with Admin\RelationshipController via JSON fetch.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { ConfidenceLevel, Relationship } from '@/types/entity';

// ── Constants ─────────────────────────────────────────────────────────────────

const RELATIONSHIP_TYPES: Array<{
    value: string;
    label: string;
    group: string;
}> = [
    // Political
    { value: 'rules', label: 'Rules', group: 'Political' },
    { value: 'governed_by', label: 'Governed By', group: 'Political' },
    { value: 'vassal_of', label: 'Vassal Of', group: 'Political' },
    { value: 'suzerain_of', label: 'Suzerain Of', group: 'Political' },
    { value: 'allied_with', label: 'Allied With', group: 'Political' },
    { value: 'at_war_with', label: 'At War With', group: 'Political' },
    { value: 'succeeded_by', label: 'Succeeded By', group: 'Political' },
    { value: 'preceded_by', label: 'Preceded By', group: 'Political' },
    { value: 'part_of', label: 'Part Of', group: 'Political' },
    { value: 'contains', label: 'Contains', group: 'Political' },
    { value: 'capital_of', label: 'Capital Of', group: 'Political' },
    { value: 'split_from', label: 'Split From', group: 'Political' },
    { value: 'merged_into', label: 'Merged Into', group: 'Political' },
    // Person
    { value: 'born_in', label: 'Born In', group: 'Person' },
    { value: 'died_in', label: 'Died In', group: 'Person' },
    { value: 'resided_in', label: 'Resided In', group: 'Person' },
    { value: 'commanded', label: 'Commanded', group: 'Person' },
    { value: 'founded', label: 'Founded', group: 'Person' },
    { value: 'authored', label: 'Authored', group: 'Person' },
    { value: 'commissioned', label: 'Commissioned', group: 'Person' },
    { value: 'married_to', label: 'Married To', group: 'Person' },
    { value: 'parent_of', label: 'Parent Of', group: 'Person' },
    { value: 'child_of', label: 'Child Of', group: 'Person' },
    { value: 'sibling_of', label: 'Sibling Of', group: 'Person' },
    { value: 'mentor_of', label: 'Mentor Of', group: 'Person' },
    { value: 'student_of', label: 'Student Of', group: 'Person' },
    { value: 'assassinated_by', label: 'Assassinated By', group: 'Person' },
    { value: 'member_of_dynasty', label: 'Member Of Dynasty', group: 'Person' },
    { value: 'patron_of', label: 'Patron Of', group: 'Person' },
    // Military
    { value: 'participated_in', label: 'Participated In', group: 'Military' },
    { value: 'fought_at', label: 'Fought At', group: 'Military' },
    { value: 'defeated_at', label: 'Defeated At', group: 'Military' },
    { value: 'victorious_at', label: 'Victorious At', group: 'Military' },
    { value: 'stationed_at', label: 'Stationed At', group: 'Military' },
    { value: 'recruited_from', label: 'Recruited From', group: 'Military' },
    { value: 'commanded_by', label: 'Commanded By', group: 'Military' },
    // Economic
    { value: 'trades_with', label: 'Trades With', group: 'Economic' },
    { value: 'connects', label: 'Connects', group: 'Economic' },
    { value: 'produces', label: 'Produces', group: 'Economic' },
    { value: 'extracts', label: 'Extracts', group: 'Economic' },
    { value: 'supplies', label: 'Supplies', group: 'Economic' },
    { value: 'controlled_by', label: 'Controlled By', group: 'Economic' },
    { value: 'passes_through', label: 'Passes Through', group: 'Economic' },
    { value: 'minted_by', label: 'Minted By', group: 'Economic' },
    { value: 'used_currency', label: 'Used Currency', group: 'Economic' },
    // Religious/Cultural
    { value: 'adheres_to', label: 'Adheres To', group: 'Religious/Cultural' },
    {
        value: 'official_religion_of',
        label: 'Official Religion Of',
        group: 'Religious/Cultural',
    },
    {
        value: 'persecuted_by',
        label: 'Persecuted By',
        group: 'Religious/Cultural',
    },
    {
        value: 'influenced_by',
        label: 'Influenced By',
        group: 'Religious/Cultural',
    },
    { value: 'inspired', label: 'Inspired', group: 'Religious/Cultural' },
    { value: 'schism_from', label: 'Schism From', group: 'Religious/Cultural' },
    {
        value: 'translated_into',
        label: 'Translated Into',
        group: 'Religious/Cultural',
    },
    { value: 'located_at', label: 'Located At', group: 'Religious/Cultural' },
    { value: 'built_by', label: 'Built By', group: 'Religious/Cultural' },
    {
        value: 'destroyed_by',
        label: 'Destroyed By',
        group: 'Religious/Cultural',
    },
    { value: 'restored_by', label: 'Restored By', group: 'Religious/Cultural' },
    // Causal
    { value: 'caused', label: 'Caused', group: 'Causal' },
    { value: 'resulted_from', label: 'Resulted From', group: 'Causal' },
    { value: 'contributed_to', label: 'Contributed To', group: 'Causal' },
    { value: 'enabled', label: 'Enabled', group: 'Causal' },
    { value: 'prevented', label: 'Prevented', group: 'Causal' },
    { value: 'weakened', label: 'Weakened', group: 'Causal' },
    { value: 'strengthened', label: 'Strengthened', group: 'Causal' },
    // Knowledge
    { value: 'invented', label: 'Invented', group: 'Knowledge' },
    { value: 'adopted', label: 'Adopted', group: 'Knowledge' },
    { value: 'taught_at', label: 'Taught At', group: 'Knowledge' },
    { value: 'spread_to', label: 'Spread To', group: 'Knowledge' },
    { value: 'required_by', label: 'Required By', group: 'Knowledge' },
    { value: 'replaced_by', label: 'Replaced By', group: 'Knowledge' },
    // Diplomatic
    { value: 'signed_by', label: 'Signed By', group: 'Diplomatic' },
    { value: 'violated_by', label: 'Violated By', group: 'Diplomatic' },
    { value: 'guaranteed_by', label: 'Guaranteed By', group: 'Diplomatic' },
    { value: 'mediated_by', label: 'Mediated By', group: 'Diplomatic' },
    { value: 'enforced_by', label: 'Enforced By', group: 'Diplomatic' },
];

const CONFIDENCE_OPTIONS: Array<{ value: ConfidenceLevel; label: string }> = [
    { value: 'high', label: 'High' },
    { value: 'medium', label: 'Medium' },
    { value: 'low', label: 'Low' },
    { value: 'unresolved', label: 'Unresolved' },
];

/** Relationship types that trigger derived presence geometry creation. */
const AUTO_PRESENCE_TYPES = new Set([
    'signed_by',
    'commanded',
    'fought_at',
    'victorious_at',
    'defeated_at',
    'founded',
    'born_in',
    'died_in',
    'resided_in',
    'mediated_by',
    'guaranteed_by',
]);

// ── Types ─────────────────────────────────────────────────────────────────────

type EntitySearchResult = {
    id: string;
    name: string;
    entity_type: string | null;
    entity_group: string | null;
};

type RelationshipFormData = {
    target_entity_id: string;
    target_entity_name: string; // display only
    relationship_type: string;
    temporal_start: string;
    temporal_end: string;
    description: string;
    confidence: ConfidenceLevel | '';
};

type RelationshipPanelProps = {
    entityId: string;
    listUrl: string;
    storeUrl: string;
    updateUrlFn?: (relationshipId: string) => string;
    deleteUrlFn: (relationshipId: string) => string;
    /** If true, shows only the list (no add/delete controls). */
    readonly?: boolean;
};

function emptyForm(): RelationshipFormData {
    return {
        target_entity_id: '',
        target_entity_name: '',
        relationship_type: '',
        temporal_start: '',
        temporal_end: '',
        description: '',
        confidence: '',
    };
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function RelationshipPanel({
    entityId,
    listUrl,
    storeUrl,
    updateUrlFn,
    deleteUrlFn,
    readonly = false,
}: RelationshipPanelProps) {
    const [outgoing, setOutgoing] = useState<Relationship[]>([]);
    const [incoming, setIncoming] = useState<Relationship[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);

    const [formOpen, setFormOpen] = useState(false);
    const [editingRelationshipId, setEditingRelationshipId] = useState<
        string | null
    >(null);
    const [form, setForm] = useState<RelationshipFormData>(emptyForm());
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);

    const csrfRef = useRef<string>('');
    useEffect(() => {
        const meta = document.querySelector<HTMLMetaElement>(
            'meta[name="csrf-token"]',
        );
        csrfRef.current = meta?.content ?? '';
    }, []);

    const reload = useCallback(async () => {
        setLoading(true);
        setLoadError(null);

        try {
            const res = await fetch(listUrl, {
                headers: {
                    Accept: 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
            });

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }

            const json = (await res.json()) as {
                outgoing: Relationship[];
                incoming: Relationship[];
            };
            setOutgoing(json.outgoing);
            setIncoming(json.incoming);
        } catch (err) {
            setLoadError('Failed to load relationships.');
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [listUrl]);

    useEffect(() => {
        void reload();
    }, [reload]);

    function openCreate() {
        setForm(emptyForm());
        setFormErrors({});
        setEditingRelationshipId(null);
        setFormOpen(true);
    }

    function openEdit(relationship: Relationship) {
        setForm({
            target_entity_id: relationship.target_entity_id,
            target_entity_name: relationship.related_entity?.name ?? '',
            relationship_type: relationship.relationship_type,
            temporal_start: relationship.temporal_start ?? '',
            temporal_end: relationship.temporal_end ?? '',
            description: relationship.description ?? '',
            confidence: (relationship.confidence ?? '') as ConfidenceLevel | '',
        });
        setFormErrors({});
        setEditingRelationshipId(relationship.relationship_id);
        setFormOpen(true);
    }

    function closeForm() {
        setFormOpen(false);
        setEditingRelationshipId(null);
    }

    function handleFormChange<K extends keyof RelationshipFormData>(
        field: K,
        value: RelationshipFormData[K],
    ) {
        setForm((prev) => ({ ...prev, [field]: value }));
    }

    async function handleSave() {
        setSaving(true);
        setFormErrors({});

        const isEditing = Boolean(editingRelationshipId);

        if (isEditing && !editingRelationshipId) {
            setFormErrors({ _: 'Missing relationship id for update.' });
            setSaving(false);

            return;
        }

        const payload: Record<string, unknown> = {
            target_entity_id: form.target_entity_id || undefined,
            relationship_type: form.relationship_type || undefined,
            temporal_start: form.temporal_start || null,
            temporal_end: form.temporal_end || null,
            description: form.description || null,
            confidence: form.confidence || null,
        };

        try {
            const method = isEditing ? 'PUT' : 'POST';
            const url = isEditing && updateUrlFn
                ? updateUrlFn(editingRelationshipId!)
                : storeUrl;

            if (isEditing && !updateUrlFn) {
                setFormErrors({ _: 'Update endpoint not configured.' });
                setSaving(false);

                return;
            }

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
                const json = (await res.json()) as {
                    errors?: Record<string, string[]>;
                };
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

    async function handleDelete(relationshipId: string) {
        if (!confirm('Delete this relationship? This cannot be undone.')) {
            return;
        }

        setDeletingId(relationshipId);

        try {
            const res = await fetch(deleteUrlFn(relationshipId), {
                method: 'DELETE',
                headers: {
                    Accept: 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
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

    const totalCount = outgoing.length + incoming.length;

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-semibold">Relationships</h3>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                        Connections to other entities. Presence-type links can
                        derive timeline geometry automatically.
                    </p>
                </div>
                {!readonly && (
                    <Button
                        type="button"
                        size="sm"
                        onClick={openCreate}
                        disabled={formOpen}
                    >
                        Add Relationship
                    </Button>
                )}
            </div>

            {loadError && (
                <p className="text-sm text-destructive">{loadError}</p>
            )}

            {loading ? (
                <div className="py-4 text-center text-sm text-muted-foreground">
                    Loading relationships…
                </div>
            ) : totalCount === 0 ? (
                <div className="rounded-lg border border-dashed py-6 text-center text-sm text-muted-foreground">
                    No relationships yet.
                </div>
            ) : (
                <div className="space-y-3">
                    {outgoing.length > 0 && (
                        <div>
                            <p className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                                Outgoing ({outgoing.length})
                            </p>
                            <div className="divide-y rounded-lg border">
                                {outgoing.map((r) => (
                                    <RelationshipRow
                                        key={r.relationship_id}
                                        relationship={r}
                                        canEdit={!readonly}
                                        onEdit={() => openEdit(r)}
                                        canDelete={!readonly}
                                        onDelete={() =>
                                            void handleDelete(r.relationship_id)
                                        }
                                        deleting={
                                            deletingId === r.relationship_id
                                        }
                                    />
                                ))}
                            </div>
                        </div>
                    )}
                    {incoming.length > 0 && (
                        <div>
                            <p className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                                Incoming ({incoming.length})
                            </p>
                            <div className="divide-y rounded-lg border">
                                {incoming.map((r) => (
                                    <RelationshipRow
                                        key={r.relationship_id}
                                        relationship={r}
                                        canEdit={false}
                                        onEdit={() => openEdit(r)}
                                        canDelete={false}
                                        onDelete={() =>
                                            void handleDelete(r.relationship_id)
                                        }
                                        deleting={false}
                                    />
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Inline add form */}
            {formOpen && (
                <RelationshipForm
                    form={form}
                    errors={formErrors}
                    saving={saving}
                    isEditing={Boolean(editingRelationshipId)}
                    onChange={handleFormChange}
                    onSave={() => void handleSave()}
                    onCancel={closeForm}
                    currentEntityId={entityId}
                />
            )}
        </div>
    );
}

// ── RelationshipRow ───────────────────────────────────────────────────────────

function RelationshipRow({
    relationship,
    canEdit,
    onEdit,
    canDelete,
    onDelete,
    deleting,
}: {
    relationship: Relationship;
    canEdit: boolean;
    onEdit: () => void;
    canDelete: boolean;
    onDelete: () => void;
    deleting: boolean;
}) {
    const typeLabel = relationship.relationship_type.replace(/_/g, ' ');
    const hasDerivedPresence = AUTO_PRESENCE_TYPES.has(
        relationship.relationship_type,
    );
    const entityName = relationship.related_entity?.name ?? '—';
    const relatedIsDraft =
        relationship.related_entity?.verification_status === 'pipeline_draft';
    const temporalRange = formatTemporalRange(
        relationship.temporal_start,
        relationship.temporal_end,
    );

    return (
        <div className="flex items-start justify-between px-4 py-3">
            <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-sm font-medium">{entityName}</span>
                    {relatedIsDraft && (
                        <Badge variant="secondary" className="text-[10px]">
                            draft
                        </Badge>
                    )}
                    <Badge variant="outline" className="text-[10px]">
                        {typeLabel}
                    </Badge>
                    {hasDerivedPresence && (
                        <Badge variant="secondary" className="text-[10px]">
                            derived presence
                        </Badge>
                    )}
                    {relationship.confidence && (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground uppercase">
                            {relationship.confidence}
                        </span>
                    )}
                </div>
                {temporalRange && (
                    <p className="mt-0.5 text-xs text-muted-foreground tabular-nums">
                        {temporalRange}
                    </p>
                )}
                {relationship.description && (
                    <p className="mt-0.5 text-xs text-muted-foreground italic">
                        {relationship.description}
                    </p>
                )}
            </div>
            {(canEdit || canDelete) && (
                <div className="ml-4 shrink-0">
                    <div className="flex items-center gap-2">
                        {canEdit && (
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={onEdit}
                            >
                                Edit
                            </Button>
                        )}
                        {canDelete && (
                            <Button
                                type="button"
                                variant="destructive"
                                size="sm"
                                onClick={onDelete}
                                disabled={deleting}
                            >
                                {deleting ? 'Deleting…' : 'Delete'}
                            </Button>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

// ── RelationshipForm ──────────────────────────────────────────────────────────

function RelationshipForm({
    form,
    errors,
    saving,
    isEditing,
    onChange,
    onSave,
    onCancel,
    currentEntityId,
}: {
    form: RelationshipFormData;
    errors: Record<string, string>;
    saving: boolean;
    isEditing: boolean;
    onChange: <K extends keyof RelationshipFormData>(
        field: K,
        value: RelationshipFormData[K],
    ) => void;
    onSave: () => void;
    onCancel: () => void;
    currentEntityId: string;
}) {
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState<EntitySearchResult[]>(
        [],
    );
    const [searching, setSearching] = useState(false);
    const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    function handleSearchInput(value: string) {
        setSearchQuery(value);

        if (searchTimer.current) {
            clearTimeout(searchTimer.current);
        }

        if (!value.trim()) {
            setSearchResults([]);

            return;
        }

        searchTimer.current = setTimeout(() => {
            void searchEntities(value);
        }, 300);
    }

    async function searchEntities(q: string) {
        setSearching(true);

        try {
            const url = `/api/v1/entities?search=${encodeURIComponent(q)}&per_page=10`;
            const res = await fetch(url, {
                headers: { Accept: 'application/json' },
            });

            if (!res.ok) {
                return;
            }

            const json = (await res.json()) as { data: EntitySearchResult[] };
            // Exclude the current entity from results
            setSearchResults(json.data.filter((e) => e.id !== currentEntityId));
        } finally {
            setSearching(false);
        }
    }

    function selectEntity(entity: EntitySearchResult) {
        onChange('target_entity_id', entity.id);
        onChange('target_entity_name', entity.name);
        setSearchResults([]);
        setSearchQuery('');
    }

    const groupedTypes = RELATIONSHIP_TYPES.reduce<
        Record<string, typeof RELATIONSHIP_TYPES>
    >((acc, t) => {
        if (!acc[t.group]) {
            acc[t.group] = [];
        }

        acc[t.group]!.push(t);

        return acc;
    }, {});

    return (
        <div className="space-y-4 rounded-lg border bg-card p-4">
            <h4 className="text-sm font-semibold">
                {isEditing ? 'Edit Relationship' : 'New Relationship'}
            </h4>

            {errors['_'] && (
                <p className="text-sm text-destructive">{errors['_']}</p>
            )}

            {/* Target entity search */}
            <div className="space-y-1">
                <Label htmlFor="rel-target" className="text-xs">
                    Target Entity <span className="text-destructive">*</span>
                </Label>
                {form.target_entity_id ? (
                    <div className="flex items-center gap-2">
                        <span className="rounded bg-muted px-3 py-1.5 text-sm font-medium">
                            {form.target_entity_name}
                        </span>
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                onChange('target_entity_id', '');
                                onChange('target_entity_name', '');
                            }}
                        >
                            Change
                        </Button>
                    </div>
                ) : (
                    <div className="relative">
                        <Input
                            id="rel-target"
                            value={searchQuery}
                            onChange={(e) => handleSearchInput(e.target.value)}
                            placeholder="Search entities by name…"
                            autoComplete="off"
                        />
                        {searching && (
                            <p className="absolute top-2 right-3 text-xs text-muted-foreground">
                                Searching…
                            </p>
                        )}
                        {searchResults.length > 0 && (
                            <div className="absolute z-10 mt-1 w-full rounded-md border border-border bg-popover shadow-md">
                                {searchResults.map((e) => (
                                    <button
                                        key={e.id}
                                        type="button"
                                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent"
                                        onClick={() => selectEntity(e)}
                                    >
                                        <span className="font-medium">
                                            {e.name}
                                        </span>
                                        {e.entity_type && (
                                            <span className="text-xs text-muted-foreground">
                                                {e.entity_type.replace(
                                                    /_/g,
                                                    ' ',
                                                )}
                                            </span>
                                        )}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                )}
                {errors['target_entity_id'] && (
                    <p className="text-xs text-destructive">
                        {errors['target_entity_id']}
                    </p>
                )}
            </div>

            {/* Relationship type */}
            <div className="space-y-1">
                <Label htmlFor="rel-type" className="text-xs">
                    Relationship Type{' '}
                    <span className="text-destructive">*</span>
                </Label>
                <select
                    id="rel-type"
                    className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                    value={form.relationship_type}
                    onChange={(e) =>
                        onChange('relationship_type', e.target.value)
                    }
                >
                    <option value="">— select type —</option>
                    {Object.entries(groupedTypes).map(([group, types]) => (
                        <optgroup key={group} label={group}>
                            {types.map((t) => (
                                <option key={t.value} value={t.value}>
                                    {t.label}
                                    {AUTO_PRESENCE_TYPES.has(t.value)
                                        ? ' ★'
                                        : ''}
                                </option>
                            ))}
                        </optgroup>
                    ))}
                </select>
                {AUTO_PRESENCE_TYPES.has(form.relationship_type) && (
                    <p className="text-xs text-muted-foreground">
                        ★ This type can auto-create derived presence geometry if the
                        entity has point geometry.
                    </p>
                )}
                {errors['relationship_type'] && (
                    <p className="text-xs text-destructive">
                        {errors['relationship_type']}
                    </p>
                )}
            </div>

            {/* Temporal range */}
            <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                    <Label htmlFor="rel-start" className="text-xs">
                        Temporal Start
                    </Label>
                    <Input
                        id="rel-start"
                        value={form.temporal_start}
                        onChange={(e) =>
                            onChange('temporal_start', e.target.value)
                        }
                        placeholder="e.g. -27 or 1648"
                    />
                </div>
                <div className="space-y-1">
                    <Label htmlFor="rel-end" className="text-xs">
                        Temporal End
                    </Label>
                    <Input
                        id="rel-end"
                        value={form.temporal_end}
                        onChange={(e) =>
                            onChange('temporal_end', e.target.value)
                        }
                        placeholder="e.g. 476"
                    />
                </div>
            </div>

            {/* Description */}
            <div className="space-y-1">
                <Label htmlFor="rel-description" className="text-xs">
                    Description (optional)
                </Label>
                <textarea
                    id="rel-description"
                    className="min-h-[72px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={form.description}
                    onChange={(e) => onChange('description', e.target.value)}
                    placeholder="Context or details about this relationship…"
                    maxLength={2000}
                />
            </div>

            {/* Confidence */}
            <div className="space-y-1">
                <Label htmlFor="rel-confidence" className="text-xs">
                    Confidence
                </Label>
                <select
                    id="rel-confidence"
                    className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                    value={form.confidence}
                    onChange={(e) =>
                        onChange(
                            'confidence',
                            e.target.value as ConfidenceLevel | '',
                        )
                    }
                >
                    <option value="">— select —</option>
                    {CONFIDENCE_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                            {o.label}
                        </option>
                    ))}
                </select>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-2">
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={onCancel}
                    disabled={saving}
                >
                    Cancel
                </Button>
                <Button
                    type="button"
                    size="sm"
                    onClick={onSave}
                    disabled={saving}
                >
                    {saving
                        ? 'Saving…'
                        : isEditing
                          ? 'Save Changes'
                          : 'Create Relationship'}
                </Button>
            </div>
        </div>
    );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTemporalRange(
    start: string | null,
    end: string | null,
): string | null {
    if (!start && !end) {
        return null;
    }

    const fmt = (v: string) => {
        const n = parseInt(v, 10);

        if (isNaN(n)) {
            return v;
        }

        return n < 0 ? `${Math.abs(n)} BCE` : `${n} CE`;
    };

    if (start && end) {
        return `${fmt(start)} – ${fmt(end)}`;
    }

    if (start) {
        return `From ${fmt(start)}`;
    }

    return `Until ${fmt(end!)}`;
}

import { Head, Link, router } from '@inertiajs/react';
import { ArrowLeft, GripVertical, Plus, Trash2, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import AppLayout from '@/layouts/app-layout';
import { update } from '@/routes/chronicles';
import type {
    BreadcrumbItem,
    ChronicleDetail,
    ChronicleEntryFormData,
    ChronicleEntryNewRelationship,
    ChronicleEntrySecondaryForm,
    ChronicleFormData,
} from '@/types';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Chronicles', href: '/chronicles' },
    { title: 'Edit', href: '#' },
];

const ROLE_OPTIONS = ['participant', 'mentioned', 'location', 'outcome'];

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

type Props = {
    chronicle: ChronicleDetail;
    relationshipTypes: string[];
};

type EntitySearchResult = {
    entity_id: string;
    name: string;
    entity_type: string | null;
};

/**
 * Debounced entity search backed by GET /api/v1/entities?search=...
 * Calls onAdd with the picked entity.
 */
function EntityPicker({ onAdd }: { onAdd: (entity: EntitySearchResult) => void }) {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<EntitySearchResult[]>([]);
    const [open, setOpen] = useState(false);

    useEffect(() => {
        const controller = new AbortController();
        const timer = setTimeout(() => {
            if (query.trim().length < 2) {
                setResults([]);
                setOpen(false);

                return;
            }

            fetch(`/api/v1/entities?search=${encodeURIComponent(query)}&per_page=8`, {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
                signal: controller.signal,
            })
                .then((res) => (res.ok ? res.json() : { data: [] }))
                .then((json: { data?: Array<Record<string, unknown>> }) => {
                    const rows = json.data ?? [];
                    setResults(
                        rows.map((row) => ({
                            entity_id: String(row.id ?? row.entity_id ?? ''),
                            name: String(row.name ?? ''),
                            entity_type: (row.entity_type as string | null) ?? null,
                        })),
                    );
                    setOpen(true);
                })
                .catch(() => {
                    /* aborted or network error — ignore */
                });
        }, 300);

        return () => {
            controller.abort();
            clearTimeout(timer);
        };
    }, [query]);

    return (
        <div className="relative">
            <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => results.length > 0 && setOpen(true)}
                placeholder="Search entities to add…"
            />
            {open && results.length > 0 && (
                <div className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-md border bg-popover shadow-md">
                    {results.map((entity) => (
                        <button
                            key={entity.entity_id}
                            type="button"
                            className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-accent"
                            onClick={() => {
                                onAdd(entity);
                                setQuery('');
                                setResults([]);
                                setOpen(false);
                            }}
                        >
                            <span>{entity.name}</span>
                            {entity.entity_type && (
                                <span className="text-xs text-muted-foreground">
                                    {entity.entity_type.replace(/_/g, ' ')}
                                </span>
                            )}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function ChronicleEdit({ chronicle, relationshipTypes }: Props) {
    const [data, setData] = useState<ChronicleFormData>({
        title: chronicle.title ?? '',
        slug: chronicle.slug ?? '',
        source_type: chronicle.source_type ?? 'video_transcript',
        source_reference: chronicle.source_reference ?? '',
        status: chronicle.status ?? 'draft',
        metadata: JSON.stringify(chronicle.metadata ?? {}),
        entries:
            chronicle.entries?.map((e) => ({
                entry_id: e.entry_id,
                sequence_order: e.sequence_order,
                narrative_text: e.narrative_text,
                notes: e.notes ?? '',
                source_evidence: typeof e.source_evidence === 'string' ? e.source_evidence : '',
                // Preserve existing relations/entities — previously hardcoded to
                // null/[], which wiped them on every save.
                primary_relationship_id: e.primary_relationship_id ?? null,
                primary_relationship_label: e.primary_relationship
                    ? `${e.primary_relationship.source_name ?? '?'} —${(e.primary_relationship.relationship_type ?? 'related').replace(/_/g, ' ')}→ ${e.primary_relationship.target_name ?? '?'}`
                    : null,
                new_relationship: null,
                secondary_entities: (e.secondary_entities ?? []).map((s) => ({
                    entity_id: s.entity_id,
                    name: s.name,
                    role: s.role ?? 'mentioned',
                })),
            })) ?? [],
    });
    const [errors, setErrors] = useState<Partial<Record<string, string>>>({});
    const [processing, setProcessing] = useState(false);

    function handleChange(field: keyof ChronicleFormData, value: string) {
        setData((prev) => ({ ...prev, [field]: value }));

        if (field === 'title') {
            const slug = value.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').slice(0, 80);
            setData((prev) => ({ ...prev, slug }));
        }
    }

    function updateEntry(index: number, patch: Partial<ChronicleEntryFormData>) {
        setData((prev) => ({
            ...prev,
            entries: prev.entries.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)),
        }));
    }

    function addEntry() {
        setData((prev) => ({
            ...prev,
            entries: [
                ...prev.entries,
                {
                    sequence_order: prev.entries.length,
                    narrative_text: '',
                    notes: '',
                    source_evidence: '',
                    primary_relationship_id: null,
                    primary_relationship_label: null,
                    new_relationship: null,
                    secondary_entities: [],
                },
            ],
        }));
    }

    function removeEntry(index: number) {
        setData((prev) => ({ ...prev, entries: prev.entries.filter((_, i) => i !== index) }));
    }

    function addSecondaryEntity(index: number, entity: EntitySearchResult) {
        setData((prev) => ({
            ...prev,
            entries: prev.entries.map((entry, i) => {
                if (i !== index) {
                    return entry;
                }

                if (entry.secondary_entities.some((s) => s.entity_id === entity.entity_id)) {
                    return entry; // already attached
                }

                const added: ChronicleEntrySecondaryForm = {
                    entity_id: entity.entity_id,
                    name: entity.name,
                    role: 'mentioned',
                };

                return { ...entry, secondary_entities: [...entry.secondary_entities, added] };
            }),
        }));
    }

    function removeSecondaryEntity(index: number, entityId: string) {
        setData((prev) => ({
            ...prev,
            entries: prev.entries.map((entry, i) =>
                i === index
                    ? { ...entry, secondary_entities: entry.secondary_entities.filter((s) => s.entity_id !== entityId) }
                    : entry,
            ),
        }));
    }

    function setSecondaryRole(index: number, entityId: string, role: string) {
        setData((prev) => ({
            ...prev,
            entries: prev.entries.map((entry, i) =>
                i === index
                    ? {
                          ...entry,
                          secondary_entities: entry.secondary_entities.map((s) =>
                              s.entity_id === entityId ? { ...s, role } : s,
                          ),
                      }
                    : entry,
            ),
        }));
    }

    function setRelationshipField(index: number, field: keyof ChronicleEntryNewRelationship, value: string) {
        setData((prev) => ({
            ...prev,
            entries: prev.entries.map((entry, i) => {
                if (i !== index) {
                    return entry;
                }

                const base = entry.new_relationship ?? {
                    source_entity_id: '',
                    target_entity_id: '',
                    relationship_type: '',
                };

                return { ...entry, new_relationship: { ...base, [field]: value } };
            }),
        }));
    }

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setErrors({});

        // metadata is validated as an object server-side; parse the JSON textarea.
        let metadata: Record<string, JsonValue> = {};

        try {
            metadata = data.metadata.trim() ? JSON.parse(data.metadata) : {};
        } catch {
            setErrors({ metadata: 'Invalid JSON.' });

            return;
        }

        setProcessing(true);

        const payload = {
            title: data.title,
            slug: data.slug,
            source_type: data.source_type,
            source_reference: data.source_reference,
            status: data.status,
            metadata,
            entries: data.entries.map((entry, i) => ({
                entry_id: entry.entry_id,
                sequence_order: i,
                narrative_text: entry.narrative_text,
                notes: entry.notes,
                source_evidence: entry.source_evidence,
                primary_relationship_id: entry.primary_relationship_id,
                secondary_entity_ids: entry.secondary_entities.map((s) => s.entity_id),
                secondary_roles: entry.secondary_entities.map((s) => s.role),
                new_relationship:
                    entry.new_relationship &&
                    entry.new_relationship.source_entity_id &&
                    entry.new_relationship.target_entity_id &&
                    entry.new_relationship.relationship_type
                        ? entry.new_relationship
                        : null,
            })),
        };

        router.put(update.url(chronicle.slug), payload, {
            onError: (formErrors) => setErrors(formErrors),
            onFinish: () => setProcessing(false),
        });
    }

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={`Edit — ${chronicle.title}`} />

            <div className="mx-auto max-w-2xl p-4">
                <div className="mb-6 flex items-center gap-4">
                    <Link href={`/chronicles/${chronicle.slug}`}>
                        <Button variant="outline" size="icon" className="size-8">
                            <ArrowLeft className="size-4" />
                        </Button>
                    </Link>
                    <h1 className="text-2xl font-bold tracking-tight">Edit Chronicle</h1>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    {/* Title */}
                    <div className="space-y-2">
                        <Label htmlFor="title">Title *</Label>
                        <Input
                            id="title"
                            value={data.title}
                            onChange={(e) => handleChange('title', e.target.value)}
                            placeholder="e.g. Battle of Didgori"
                            required
                        />
                        {errors.title && <p className="text-sm text-destructive">{errors.title}</p>}
                    </div>

                    {/* Slug */}
                    <div className="space-y-2">
                        <Label htmlFor="slug">Slug *</Label>
                        <Input
                            id="slug"
                            value={data.slug}
                            onChange={(e) => handleChange('slug', e.target.value)}
                            placeholder="auto-generated-from-title"
                            required
                        />
                        {errors.slug && <p className="text-sm text-destructive">{errors.slug}</p>}
                    </div>

                    {/* Source Type */}
                    <div className="space-y-2">
                        <Label htmlFor="source_type">Source Type</Label>
                        <Select value={data.source_type} onValueChange={(v) => handleChange('source_type', v)}>
                            <SelectTrigger id="source_type">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="video_transcript">Video Transcript</SelectItem>
                                <SelectItem value="article">Article</SelectItem>
                                <SelectItem value="book_excerpt">Book Excerpt</SelectItem>
                                <SelectItem value="manual">Manual</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Source Reference */}
                    <div className="space-y-2">
                        <Label htmlFor="source_reference">Source Reference</Label>
                        <Input
                            id="source_reference"
                            value={data.source_reference}
                            onChange={(e) => handleChange('source_reference', e.target.value)}
                            placeholder="e.g. transcript.txt or URL"
                        />
                    </div>

                    {/* Status */}
                    <div className="space-y-2">
                        <Label htmlFor="status">Status</Label>
                        <Select value={data.status} onValueChange={(v) => handleChange('status', v)}>
                            <SelectTrigger id="status">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="draft">Draft</SelectItem>
                                <SelectItem value="published">Published</SelectItem>
                                <SelectItem value="archived">Archived</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Metadata (JSON) */}
                    <div className="space-y-2">
                        <Label htmlFor="metadata">Metadata (JSON)</Label>
                        <Textarea
                            id="metadata"
                            value={data.metadata}
                            onChange={(e) => handleChange('metadata', e.target.value)}
                            placeholder='{"event_count": 0, "generated_at": "..."}'
                            rows={4}
                        />
                        {errors.metadata && <p className="text-sm text-destructive">{errors.metadata}</p>}
                    </div>

                    {/* Entries Management */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-semibold">Entries</h3>
                            <Button type="button" variant="outline" size="sm" onClick={addEntry}>
                                <Plus className="mr-1.5 size-4" />
                                Add Entry
                            </Button>
                        </div>

                        {data.entries.length === 0 ? (
                            <div className="rounded-lg border p-4 text-center text-sm text-muted-foreground">
                                No entries yet. Click "Add Entry" to create one.
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {data.entries.map((entry, index) => (
                                    <div key={entry.entry_id ?? index} className="rounded-lg border p-4">
                                        <div className="mb-3 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <GripVertical className="size-4 text-muted-foreground" />
                                                <span className="text-sm font-medium">Entry #{index + 1}</span>
                                            </div>
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => removeEntry(index)}
                                            >
                                                <Trash2 className="size-4" />
                                            </Button>
                                        </div>

                                        <div className="space-y-3">
                                            <div className="space-y-1">
                                                <Label>Narrative Text *</Label>
                                                <Textarea
                                                    value={entry.narrative_text}
                                                    onChange={(e) => updateEntry(index, { narrative_text: e.target.value })}
                                                    placeholder="Describe the historical event..."
                                                    rows={3}
                                                />
                                            </div>

                                            <div className="space-y-1">
                                                <Label>Notes</Label>
                                                <Textarea
                                                    value={entry.notes ?? ''}
                                                    onChange={(e) => updateEntry(index, { notes: e.target.value })}
                                                    placeholder="Additional context or analysis..."
                                                    rows={2}
                                                />
                                            </div>

                                            <div className="space-y-1">
                                                <Label>Source Evidence</Label>
                                                <Input
                                                    value={entry.source_evidence ?? ''}
                                                    onChange={(e) => updateEntry(index, { source_evidence: e.target.value })}
                                                    placeholder="e.g. Appian 2.41 or medieval chronicle"
                                                />
                                            </div>

                                            {/* Primary relationship — author one from the entry's entities */}
                                            <div className="space-y-1">
                                                <Label>Primary Relationship</Label>
                                                {entry.primary_relationship_id ? (
                                                    <div className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                                                        <span>{entry.primary_relationship_label ?? entry.primary_relationship_id}</span>
                                                        <Button
                                                            type="button"
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() =>
                                                                updateEntry(index, {
                                                                    primary_relationship_id: null,
                                                                    primary_relationship_label: null,
                                                                })
                                                            }
                                                        >
                                                            <X className="size-4" />
                                                        </Button>
                                                    </div>
                                                ) : entry.secondary_entities.length >= 2 ? (
                                                    <div className="grid grid-cols-3 gap-2">
                                                        <Select
                                                            value={entry.new_relationship?.source_entity_id ?? ''}
                                                            onValueChange={(v) => setRelationshipField(index, 'source_entity_id', v)}
                                                        >
                                                            <SelectTrigger className="text-xs">
                                                                <SelectValue placeholder="Source" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {entry.secondary_entities.map((s) => (
                                                                    <SelectItem key={s.entity_id} value={s.entity_id}>
                                                                        {s.name}
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                        <Select
                                                            value={entry.new_relationship?.relationship_type ?? ''}
                                                            onValueChange={(v) => setRelationshipField(index, 'relationship_type', v)}
                                                        >
                                                            <SelectTrigger className="text-xs">
                                                                <SelectValue placeholder="Type" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {relationshipTypes.map((t) => (
                                                                    <SelectItem key={t} value={t}>
                                                                        {t.replace(/_/g, ' ')}
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                        <Select
                                                            value={entry.new_relationship?.target_entity_id ?? ''}
                                                            onValueChange={(v) => setRelationshipField(index, 'target_entity_id', v)}
                                                        >
                                                            <SelectTrigger className="text-xs">
                                                                <SelectValue placeholder="Target" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {entry.secondary_entities.map((s) => (
                                                                    <SelectItem key={s.entity_id} value={s.entity_id}>
                                                                        {s.name}
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                    </div>
                                                ) : (
                                                    <p className="text-xs text-muted-foreground">
                                                        Add at least two entities below, then pick source → type → target to
                                                        create the relationship on save.
                                                    </p>
                                                )}
                                            </div>

                                            {/* Secondary entities */}
                                            <div className="space-y-1">
                                                <Label>Entities</Label>
                                                {entry.secondary_entities.length > 0 && (
                                                    <div className="flex flex-col gap-2">
                                                        {entry.secondary_entities.map((s) => (
                                                            <div
                                                                key={s.entity_id}
                                                                className="flex items-center gap-2 rounded-md border px-2 py-1.5"
                                                            >
                                                                <Badge variant="secondary" className="flex-1 justify-start">
                                                                    {s.name}
                                                                </Badge>
                                                                <Select
                                                                    value={s.role}
                                                                    onValueChange={(v) => setSecondaryRole(index, s.entity_id, v)}
                                                                >
                                                                    <SelectTrigger className="h-7 w-32 text-xs">
                                                                        <SelectValue />
                                                                    </SelectTrigger>
                                                                    <SelectContent>
                                                                        {ROLE_OPTIONS.map((role) => (
                                                                            <SelectItem key={role} value={role}>
                                                                                {role}
                                                                            </SelectItem>
                                                                        ))}
                                                                    </SelectContent>
                                                                </Select>
                                                                <Button
                                                                    type="button"
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    onClick={() => removeSecondaryEntity(index, s.entity_id)}
                                                                >
                                                                    <X className="size-4" />
                                                                </Button>
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                                <EntityPicker onAdd={(entity) => addSecondaryEntity(index, entity)} />
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2">
                        <Button type="submit" disabled={processing}>
                            {processing ? 'Saving...' : 'Save Changes'}
                        </Button>
                        <Link href={`/chronicles/${chronicle.slug}`}>
                            <Button type="button" variant="outline">
                                Cancel
                            </Button>
                        </Link>
                    </div>
                </form>
            </div>
        </AppLayout>
    );
}

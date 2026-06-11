import { Head, Link, router } from '@inertiajs/react';
import { ArrowLeft, GripVertical, Plus, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import AppLayout from '@/layouts/app-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import type {
    BreadcrumbItem,
    ChronicleDetail,
    ChronicleEntry,
    ChronicleEntryFormData,
    ChronicleFormData,
} from '@/types';
import { update } from '@/routes/chronicles';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Chronicles', href: '/chronicles' },
    { title: 'Edit', href: '#' },
];

type Props = {
    chronicle: ChronicleDetail;
};

export default function ChronicleEdit({ chronicle }: Props) {
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
                source_evidence: e.source_evidence ?? '',
                primary_relationship_id: null,
                secondary_entity_ids: [],
            })) ?? [],
    });
    const [errors, setErrors] = useState<Partial<Record<keyof ChronicleFormData, string>>>({});
    const [processing, setProcessing] = useState(false);

    function handleChange(field: keyof ChronicleFormData, value: string) {
        setData((prev) => ({ ...prev, [field]: value }));
        // Auto-generate slug from title
        if (field === 'title') {
            const slug = value.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').slice(0, 80);
            setData((prev) => ({ ...prev, slug }));
        }
    }

    function handleEntryChange(index: number, field: keyof ChronicleEntryFormData, value: string | string[]) {
        setData((prev) => ({
            ...prev,
            entries: prev.entries?.map((entry, i) =>
                i === index ? { ...entry, [field]: value } : entry,
            ) ?? [],
        }));
    }

    function addEntry() {
        setData((prev) => ({
            ...prev,
            entries: [
                ...(prev.entries ?? []),
                {
                    sequence_order: prev.entries?.length ?? 0,
                    narrative_text: '',
                    notes: '',
                    source_evidence: '',
                    primary_relationship_id: null,
                    secondary_entity_ids: [],
                },
            ],
        }));
    }

    function removeEntry(index: number) {
        setData((prev) => ({
            ...prev,
            entries: prev.entries?.filter((_, i) => i !== index) ?? [],
        }));
    }

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setProcessing(true);
        setErrors({});

        router.put(update.url(chronicle.slug), data, {
            onError: (errors) => setErrors(errors),
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

                        {!data.entries || data.entries.length === 0 ? (
                            <div className="rounded-lg border p-4 text-center text-sm text-muted-foreground">
                                No entries yet. Click "Add Entry" to create one.
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {data.entries.map((entry, index) => (
                                    <div key={index} className="rounded-lg border p-4">
                                        <div className="mb-3 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <GripVertical className="size-4 text-muted-foreground" />
                                                <span className="text-sm font-medium">
                                                    Entry #{index + 1}
                                                </span>
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
                                                    onChange={(e) =>
                                                        handleEntryChange(index, 'narrative_text', e.target.value)
                                                    }
                                                    placeholder="Describe the historical event..."
                                                    rows={3}
                                                />
                                            </div>

                                            <div className="space-y-1">
                                                <Label>Notes</Label>
                                                <Textarea
                                                    value={entry.notes ?? ''}
                                                    onChange={(e) =>
                                                        handleEntryChange(index, 'notes', e.target.value)
                                                    }
                                                    placeholder="Additional context or analysis..."
                                                    rows={2}
                                                />
                                            </div>

                                            <div className="space-y-1">
                                                <Label>Source Evidence</Label>
                                                <Input
                                                    value={entry.source_evidence ?? ''}
                                                    onChange={(e) =>
                                                        handleEntryChange(index, 'source_evidence', e.target.value)
                                                    }
                                                    placeholder="e.g. Appian 2.41 or medieval chronicle"
                                                />
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

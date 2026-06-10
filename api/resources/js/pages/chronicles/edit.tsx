import { Head, Link, router } from '@inertiajs/react';
import { ArrowLeft, Pencil } from 'lucide-react';
import { useState } from 'react';
import AppLayout from '@/layouts/app-layout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { BreadcrumbItem, ChronicleDetail, ChronicleFormData } from '@/types';
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

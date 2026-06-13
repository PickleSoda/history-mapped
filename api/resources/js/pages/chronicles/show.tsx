import { Head, Link, router } from '@inertiajs/react';
import { ArrowLeft, Pencil, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import AppLayout from '@/layouts/app-layout';
import { destroy, edit } from '@/routes/chronicles';
import type { BreadcrumbItem, ChronicleDetail } from '@/types';

type Props = {
    chronicle: ChronicleDetail;
};

const statusColors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
    published: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    archived: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

function formatYear(year: number | null | undefined): string | null {
    if (year === null || year === undefined) {
        return null;
    }

    return year < 0 ? `${Math.abs(year)} BCE` : `${year} CE`;
}

function formatYearRange(start: number | null | undefined, end: number | null | undefined): string | null {
    const s = formatYear(start);
    const e = formatYear(end);

    if (s && e) {
        return s === e ? s : `${s} – ${e}`;
    }

    return s ?? e;
}

export default function ChronicleShow({ chronicle }: Props) {
    const [confirmDelete, setConfirmDelete] = useState(false);
    const [deleting, setDeleting] = useState(false);

    const breadcrumbs: BreadcrumbItem[] = [
        { title: 'Dashboard', href: '/dashboard' },
        { title: 'Chronicles', href: '/chronicles' },
        { title: chronicle.title, href: `/chronicles/${chronicle.slug}` },
    ];

    function handleDelete() {
        setDeleting(true);
        router.delete(destroy(chronicle.slug), {
            onFinish: () => setDeleting(false),
        });
    }

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={chronicle.title} />

            <div className="flex flex-col gap-6 p-4">
                {/* Header */}
                <div className="flex items-center gap-4">
                    <Link href="/chronicles">
                        <Button variant="outline" size="icon" className="size-8">
                            <ArrowLeft className="size-4" />
                        </Button>
                    </Link>
                    <div className="flex-1">
                        <h1 className="text-2xl font-bold tracking-tight">
                            {chronicle.title}
                        </h1>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Badge variant="outline">
                                {chronicle.source_type?.replace(/_/g, ' ') || '—'}
                            </Badge>
                            {chronicle.status && (
                                <Badge className={statusColors[chronicle.status] || ''}>
                                    {chronicle.status}
                                </Badge>
                            )}
                            {formatYearRange(chronicle.start_year, chronicle.end_year) && (
                                <Badge variant="outline">
                                    {formatYearRange(chronicle.start_year, chronicle.end_year)}
                                </Badge>
                            )}
                            {chronicle.impact_score !== null && chronicle.impact_score !== undefined && (
                                <Badge variant="outline">Impact {chronicle.impact_score}</Badge>
                            )}
                            {chronicle.approximate_location && (
                                <Badge variant="outline">
                                    {chronicle.approximate_location.lat.toFixed(1)}, {chronicle.approximate_location.lon.toFixed(1)}
                                </Badge>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Link href={edit(chronicle.slug)}>
                            <Button variant="outline" size="sm">
                                <Pencil className="mr-1.5 size-4" />
                                Edit
                            </Button>
                        </Link>
                        <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setConfirmDelete(true)}
                        >
                            <Trash2 className="mr-1.5 size-4" />
                            Delete
                        </Button>
                    </div>
                </div>

                {/* Metadata */}
                {chronicle.metadata && Object.keys(chronicle.metadata).length > 0 && (
                    <div className="rounded-lg border p-4">
                        <h3 className="mb-2 text-sm font-semibold">Metadata</h3>
                        <pre className="text-xs text-muted-foreground">
                            {JSON.stringify(chronicle.metadata, null, 2)}
                        </pre>
                    </div>
                )}

                {/* Entries */}
                <div className="flex flex-col gap-4">
                    <h2 className="text-xl font-semibold">
                        Entries ({chronicle.entry_count})
                    </h2>

                    {!chronicle.entries || chronicle.entries.length === 0 ? (
                        <div className="rounded-lg border p-8 text-center text-muted-foreground">
                            No entries yet. Edit this chronicle to add entries.
                        </div>
                    ) : (
                        chronicle.entries.map((entry) => (
                            <div key={entry.entry_id} className="rounded-lg border p-4">
                                <div className="mb-2 flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-semibold">
                                            #{entry.sequence_order + 1}
                                        </span>
                                        {formatYearRange(entry.start_year, entry.end_year) && (
                                            <Badge variant="outline" className="text-xs">
                                                {formatYearRange(entry.start_year, entry.end_year)}
                                            </Badge>
                                        )}
                                        {entry.impact_score !== null && entry.impact_score !== undefined && (
                                            <Badge variant="outline" className="text-xs">
                                                Impact {entry.impact_score}
                                            </Badge>
                                        )}
                                    </div>
                                </div>

                                <p className="mb-3 text-sm leading-relaxed">
                                    {entry.narrative_text}
                                </p>

                                {/* Primary relationship */}
                                {entry.primary_relationship && (
                                    <div className="mb-2 flex flex-wrap items-center gap-1.5 text-xs">
                                        <span className="font-semibold text-muted-foreground">Relationship:</span>
                                        <Badge variant="outline">
                                            {entry.primary_relationship.source_name ?? '?'}
                                            <span className="mx-1 opacity-70">
                                                —{entry.primary_relationship.relationship_type?.replace(/_/g, ' ') ?? 'related'}→
                                            </span>
                                            {entry.primary_relationship.target_name ?? '?'}
                                        </Badge>
                                    </div>
                                )}

                                {entry.notes && (
                                    <p className="mb-2 text-xs text-muted-foreground italic">
                                        {entry.notes}
                                    </p>
                                )}

                                {entry.source_evidence && (
                                    <p className="mb-2 text-xs text-muted-foreground">
                                        Source: {entry.source_evidence}
                                    </p>
                                )}

                                {/* Secondary Entities */}
                                {entry.secondary_entities && entry.secondary_entities.length > 0 && (
                                    <div className="mt-3 border-t pt-3">
                                        <h4 className="mb-2 text-xs font-semibold text-muted-foreground">
                                            Entities
                                        </h4>
                                        <div className="flex flex-wrap gap-2">
                                            {entry.secondary_entities.map((entity) => (
                                                <Badge key={entity.entity_id} variant="secondary">
                                                    {entity.name}
                                                    {entity.role && (
                                                        <span className="ml-1 text-xs opacity-70">
                                                            ({entity.role})
                                                        </span>
                                                    )}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Delete Confirmation Dialog */}
            <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Delete Chronicle</DialogTitle>
                        <DialogDescription>
                            Are you sure you want to delete "{chronicle.title}"? This action cannot be undone.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setConfirmDelete(false)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleDelete}
                            disabled={deleting}
                        >
                            {deleting ? 'Deleting...' : 'Delete'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </AppLayout>
    );
}

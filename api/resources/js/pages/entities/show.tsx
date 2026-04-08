import { Head, Link, router } from '@inertiajs/react';
import { ArrowLeft, Pencil, Trash2 } from 'lucide-react';
import { lazy, Suspense, useState } from 'react';
import EntityGeometryPeriodsPanel from '@/components/entity-geometry-periods-panel';
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
import { destroy, edit } from '@/routes/entities';
import type { BreadcrumbItem, EntityDetail } from '@/types';

const RelationshipPanel = lazy(() => import('@/components/relationship-panel'));
const EntityHistoryPanel = lazy(
    () => import('@/components/entity-history-panel'),
);

type Props = {
    entity: EntityDetail;
};

export default function EntityShow({ entity }: Props) {
    const [confirmDelete, setConfirmDelete] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [relationshipOpen, setRelationshipOpen] = useState(false);
    const breadcrumbs: BreadcrumbItem[] = [
        { title: 'Dashboard', href: '/dashboard' },
        { title: 'Entities', href: '/entities' },
        { title: entity.name, href: `/entities/${entity.id}` },
    ];

    function handleDelete() {
        setDeleting(true);
        router.delete(destroy(entity.id), {
            onFinish: () => setDeleting(false),
        });
    }

    const relationshipsUrl = `/entities/${entity.id}/relationships`;
    const timelineUrl = `/api/v1/entities/${entity.id}/timeline`;

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={entity.name} />

            <div className="flex flex-col gap-6 p-4">
                <div className="flex items-center gap-4">
                    <Link href="/entities">
                        <Button
                            variant="outline"
                            size="icon"
                            className="size-8"
                        >
                            <ArrowLeft className="size-4" />
                        </Button>
                    </Link>
                    <div className="flex-1">
                        <h1 className="text-2xl font-bold tracking-tight">
                            {entity.name}
                        </h1>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            {entity.entity_group && (
                                <Badge variant="outline">
                                    {entity.entity_group}
                                </Badge>
                            )}
                            {entity.entity_type && (
                                <span>
                                    {entity.entity_type
                                        .replace(/_/g, ' ')
                                        .replace(/\b\w/g, (c) =>
                                            c.toUpperCase(),
                                        )}
                                </span>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Link href={edit(entity.id)}>
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

                {/* Summary card with the data we do have */}
                {(entity.summary ||
                    entity.temporal_display_range ||
                    entity.location_name) && (
                    <div className="grid gap-4 md:grid-cols-3">
                        {entity.summary && (
                            <div className="rounded-lg border p-4 md:col-span-2">
                                <h2 className="mb-2 text-sm font-medium">
                                    Summary
                                </h2>
                                <p className="text-sm text-muted-foreground">
                                    {entity.summary}
                                </p>
                            </div>
                        )}
                        <div className="space-y-3 rounded-lg border p-4">
                            {entity.temporal_display_range && (
                                <div>
                                    <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                                        Period
                                    </h3>
                                    <p className="text-sm">
                                        {entity.temporal_display_range}
                                    </p>
                                </div>
                            )}
                            {entity.location_name && (
                                <div>
                                    <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                                        Location
                                    </h3>
                                    <p className="text-sm">
                                        {entity.location_name}
                                    </p>
                                </div>
                            )}
                            {entity.impact_score != null && (
                                <div>
                                    <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                                        Impact Score
                                    </h3>
                                    <p className="text-sm tabular-nums">
                                        {entity.impact_score}
                                    </p>
                                </div>
                            )}
                            {entity.verification_status && (
                                <div>
                                    <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                                        Status
                                    </h3>
                                    <p className="text-sm">
                                        {entity.verification_status
                                            .replace(/_/g, ' ')
                                            .replace(/\b\w/g, (c) =>
                                                c.toUpperCase(),
                                            )}
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Geometry map + timeline */}
                <div className="rounded-lg border p-4">
                    <Suspense
                        fallback={
                            <div className="flex h-24 items-center justify-center text-sm text-muted-foreground">
                                Loading map and timeline…
                            </div>
                        }
                    >
                        <EntityHistoryPanel
                            entityGeojson={entity.geojson}
                            entityTerritoryGeojson={entity.territory_geojson}
                            entityTemporalStart={entity.temporal_start}
                            entityTemporalEnd={entity.temporal_end}
                            timelineUrl={timelineUrl}
                        />
                    </Suspense>
                </div>

                <div className="rounded-lg border p-4">
                    <h2 className="mb-3 text-sm font-semibold">Geometry Periods</h2>
                    <EntityGeometryPeriodsPanel
                        listUrl={entity.geometry_periods_url ?? `/entities/${entity.id}/geometry-periods`}
                        readOnly
                    />
                </div>

                {/* Relationships — collapsible, read-only */}
                <div className="rounded-lg border">
                    <button
                        type="button"
                        onClick={() => setRelationshipOpen((v) => !v)}
                        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium"
                    >
                        <span>Relationships</span>
                        <span className="text-xs text-muted-foreground">
                            {relationshipOpen ? 'Collapse' : 'Expand'}
                        </span>
                    </button>

                    {relationshipOpen && (
                        <div className="border-t p-4">
                            <Suspense
                                fallback={
                                    <div className="flex h-24 items-center justify-center text-sm text-muted-foreground">
                                        Loading relationships…
                                    </div>
                                }
                            >
                                <RelationshipPanel
                                    entityId={entity.id}
                                    listUrl={relationshipsUrl}
                                    storeUrl={relationshipsUrl}
                                    deleteUrlFn={(relationshipId) =>
                                        `/entities/${entity.id}/relationships/${relationshipId}`
                                    }
                                    readonly
                                />
                            </Suspense>
                        </div>
                    )}
                </div>

                {/* Delete confirmation dialog */}
                <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Delete entity?</DialogTitle>
                            <DialogDescription>
                                This will permanently delete{' '}
                                <strong>{entity.name}</strong>. This action
                                cannot be undone.
                            </DialogDescription>
                        </DialogHeader>
                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => setConfirmDelete(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                variant="destructive"
                                disabled={deleting}
                                onClick={handleDelete}
                            >
                                {deleting ? 'Deleting…' : 'Delete'}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </AppLayout>
    );
}

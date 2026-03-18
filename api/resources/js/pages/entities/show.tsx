import { Head, Link } from '@inertiajs/react';
import { ArrowLeft } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import AppLayout from '@/layouts/app-layout';
import type { BreadcrumbItem } from '@/types';

type EntityDetail = {
    id: string;
    name: string;
    entity_type: string | null;
    entity_group: string | null;
    summary: string | null;
    impact_score: number | null;
    temporal_display_range: string | null;
    location_name: string | null;
    verification_status: string | null;
    confidence: string | null;
};

type Props = {
    entity: EntityDetail;
};

export default function EntityShow({ entity }: Props) {
    const breadcrumbs: BreadcrumbItem[] = [
        { title: 'Dashboard', href: '/dashboard' },
        { title: 'Entities', href: '/entities' },
        { title: entity.name, href: `/entities/${entity.id}` },
    ];

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={entity.name} />

            <div className="flex flex-col gap-6 p-4">
                <div className="flex items-center gap-4">
                    <Link href="/entities">
                        <Button variant="outline" size="icon" className="size-8">
                            <ArrowLeft className="size-4" />
                        </Button>
                    </Link>
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">{entity.name}</h1>
                        <div className="text-muted-foreground flex items-center gap-2 text-sm">
                            {entity.entity_group && (
                                <Badge variant="outline">{entity.entity_group}</Badge>
                            )}
                            {entity.entity_type && (
                                <span>
                                    {entity.entity_type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                <div className="bg-muted/50 rounded-lg border p-8 text-center">
                    <p className="text-muted-foreground text-lg">
                        Entity detail view coming soon.
                    </p>
                    <p className="text-muted-foreground mt-2 text-sm">
                        This page will show the full entity record with all fields, relationships, timeline, and geographic context.
                    </p>
                </div>

                {/* Summary card with the data we do have */}
                {(entity.summary || entity.temporal_display_range || entity.location_name) && (
                    <div className="grid gap-4 md:grid-cols-3">
                        {entity.summary && (
                            <div className="rounded-lg border p-4 md:col-span-2">
                                <h2 className="mb-2 text-sm font-medium">Summary</h2>
                                <p className="text-muted-foreground text-sm">{entity.summary}</p>
                            </div>
                        )}
                        <div className="space-y-3 rounded-lg border p-4">
                            {entity.temporal_display_range && (
                                <div>
                                    <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Period</h3>
                                    <p className="text-sm">{entity.temporal_display_range}</p>
                                </div>
                            )}
                            {entity.location_name && (
                                <div>
                                    <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Location</h3>
                                    <p className="text-sm">{entity.location_name}</p>
                                </div>
                            )}
                            {entity.impact_score != null && (
                                <div>
                                    <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Impact Score</h3>
                                    <p className="text-sm tabular-nums">{entity.impact_score}</p>
                                </div>
                            )}
                            {entity.verification_status && (
                                <div>
                                    <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Status</h3>
                                    <p className="text-sm">
                                        {entity.verification_status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </AppLayout>
    );
}

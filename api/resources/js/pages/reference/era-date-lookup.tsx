import { Head } from '@inertiajs/react';
import { RefTableLayout } from '@/components/ref-table-layout';
import { Badge } from '@/components/ui/badge';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import AppLayout from '@/layouts/app-layout';
import { index } from '@/routes/reference/era-date-lookup';
import type { BreadcrumbItem, PaginatedData } from '@/types';
import type { EraDateLookup } from '@/types/reference';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Reference', href: '#' },
    { title: 'Era Date Lookup', href: index.url() },
];

const confidenceColors: Record<string, string> = {
    high: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    low: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
};

type Filters = { search: string; per_page: number };

type Props = {
    lookups: PaginatedData<EraDateLookup>;
    filters: Filters;
};

export default function EraDateLookupIndex({ lookups, filters }: Props) {
    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Era Date Lookup" />

            <RefTableLayout
                title="Era Date Lookup"
                description="Resolved date ranges for historical era search terms"
                basePath={index.url()}
                filters={filters}
                paginated={lookups}
            >
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Search Term</TableHead>
                                <TableHead>Resolved Start</TableHead>
                                <TableHead>Resolved End</TableHead>
                                <TableHead>Geographic Scope</TableHead>
                                <TableHead>Confidence</TableHead>
                                <TableHead>Period</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {lookups.data.length === 0 ? (
                                <TableRow>
                                    <TableCell
                                        colSpan={6}
                                        className="h-24 text-center"
                                    >
                                        <div className="text-muted-foreground">
                                            No records found.
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                lookups.data.map((lookup) => (
                                    <TableRow key={lookup.lookup_id}>
                                        <TableCell className="font-medium">
                                            {lookup.search_term}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground tabular-nums">
                                            {lookup.resolved_start}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground tabular-nums">
                                            {lookup.resolved_end}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {lookup.geographic_scope ?? '—'}
                                        </TableCell>
                                        <TableCell>
                                            <Badge
                                                variant="outline"
                                                className={
                                                    confidenceColors[
                                                        lookup.confidence
                                                    ] ?? ''
                                                }
                                            >
                                                {lookup.confidence}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {lookup.period_name ?? '—'}
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>
            </RefTableLayout>
        </AppLayout>
    );
}

import { Head } from '@inertiajs/react';
import { RefTableLayout } from '@/components/ref-table-layout';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import AppLayout from '@/layouts/app-layout';
import { index } from '@/routes/reference/historical-periods';
import type { BreadcrumbItem, PaginatedData } from '@/types';
import type { HistoricalPeriod } from '@/types/reference';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Reference', href: '#' },
    { title: 'Historical Periods', href: index.url() },
];

type Filters = { search: string; per_page: number };

type Props = {
    periods: PaginatedData<HistoricalPeriod>;
    filters: Filters;
};

export default function HistoricalPeriodsIndex({ periods, filters }: Props) {
    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Historical Periods" />

            <RefTableLayout
                title="Historical Periods"
                description="Hierarchical historical periods and their time ranges"
                basePath={index.url()}
                filters={filters}
                paginated={periods}
            >
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Parent</TableHead>
                                <TableHead>Start</TableHead>
                                <TableHead>End</TableHead>
                                <TableHead>Region</TableHead>
                                <TableHead>Colour</TableHead>
                                <TableHead className="text-right">
                                    Sort
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {periods.data.length === 0 ? (
                                <TableRow>
                                    <TableCell
                                        colSpan={7}
                                        className="h-24 text-center"
                                    >
                                        <div className="text-muted-foreground">
                                            No records found.
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                periods.data.map((period) => (
                                    <TableRow key={period.period_id}>
                                        <TableCell className="font-medium">
                                            <span
                                                style={{
                                                    paddingLeft: `${period.depth_level * 1.25}rem`,
                                                }}
                                            >
                                                {period.depth_level > 0 && (
                                                    <span className="mr-1 text-muted-foreground">
                                                        ↳
                                                    </span>
                                                )}
                                                {period.name}
                                            </span>
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {period.parent_name ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground tabular-nums">
                                            {period.start_date}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground tabular-nums">
                                            {period.end_date}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {period.region_name ?? '—'}
                                        </TableCell>
                                        <TableCell>
                                            {period.color_hex ? (
                                                <span className="inline-flex items-center gap-1.5">
                                                    <span
                                                        className="inline-block size-4 rounded-sm border"
                                                        style={{
                                                            backgroundColor:
                                                                period.color_hex,
                                                        }}
                                                    />
                                                    <span className="text-xs text-muted-foreground tabular-nums">
                                                        {period.color_hex}
                                                    </span>
                                                </span>
                                            ) : (
                                                '—'
                                            )}
                                        </TableCell>
                                        <TableCell className="text-right tabular-nums">
                                            {period.sort_order ?? '—'}
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

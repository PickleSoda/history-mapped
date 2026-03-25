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
import { index } from '@/routes/reference/writing-systems';
import type { BreadcrumbItem, PaginatedData } from '@/types';
import type { WritingSystem } from '@/types/reference';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Reference', href: '#' },
    { title: 'Writing Systems', href: index.url() },
];

type Filters = { search: string; per_page: number };

type Props = {
    systems: PaginatedData<WritingSystem>;
    filters: Filters;
};

export default function WritingSystemsIndex({ systems, filters }: Props) {
    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Writing Systems" />

            <RefTableLayout
                title="Writing Systems"
                description="Historical and modern writing systems and scripts"
                basePath={index.url()}
                filters={filters}
                paginated={systems}
            >
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Code</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Direction</TableHead>
                                <TableHead>Origin Date</TableHead>
                                <TableHead>Derived From</TableHead>
                                <TableHead>Still in Use</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {systems.data.length === 0 ? (
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
                                systems.data.map((system) => (
                                    <TableRow key={system.system_id}>
                                        <TableCell className="font-medium">
                                            {system.name}
                                        </TableCell>
                                        <TableCell className="font-mono text-sm">
                                            {system.code ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {system.system_type}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {system.direction ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground tabular-nums">
                                            {system.origin_date ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {system.derived_from_name ? (
                                                <span className="inline-flex items-center gap-1">
                                                    <span className="text-muted-foreground">
                                                        ↳
                                                    </span>
                                                    {system.derived_from_name}
                                                </span>
                                            ) : (
                                                '—'
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Badge
                                                variant="outline"
                                                className={
                                                    system.still_in_use
                                                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                                        : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                                                }
                                            >
                                                {system.still_in_use
                                                    ? 'Yes'
                                                    : 'No'}
                                            </Badge>
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

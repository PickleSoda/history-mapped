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
import { index } from '@/routes/reference/historiographical-schools';
import type { BreadcrumbItem, PaginatedData } from '@/types';
import type { HistoriographicalSchool } from '@/types/reference';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Reference', href: '#' },
    { title: 'Historiographical Schools', href: index.url() },
];

type Filters = { search: string; per_page: number };

type Props = {
    schools: PaginatedData<HistoriographicalSchool>;
    filters: Filters;
};

export default function HistoriographicalSchoolsIndex({
    schools,
    filters,
}: Props) {
    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Historiographical Schools" />

            <RefTableLayout
                title="Historiographical Schools"
                description="Schools of historical thought and their interpretive frameworks"
                basePath={index.url()}
                filters={filters}
                paginated={schools}
            >
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Interpretive Framework</TableHead>
                                <TableHead>Active From</TableHead>
                                <TableHead>Active To</TableHead>
                                <TableHead>Geographic Centre</TableHead>
                                <TableHead className="text-right">
                                    Sort
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {schools.data.length === 0 ? (
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
                                schools.data.map((school) => (
                                    <TableRow key={school.school_id}>
                                        <TableCell className="font-medium">
                                            {school.name}
                                        </TableCell>
                                        <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                                            {school.interpretive_framework}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground tabular-nums">
                                            {school.active_from ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground tabular-nums">
                                            {school.active_to ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {school.geographic_center ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-right tabular-nums">
                                            {school.sort_order ?? '—'}
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

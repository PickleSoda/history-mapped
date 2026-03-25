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
import { index } from '@/routes/reference/geographic-regions';
import type { BreadcrumbItem, PaginatedData } from '@/types';
import type { GeographicRegion } from '@/types/reference';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Reference', href: '#' },
    { title: 'Geographic Regions', href: index.url() },
];

type Filters = { search: string; per_page: number };

type Props = {
    regions: PaginatedData<GeographicRegion>;
    filters: Filters;
};

export default function GeographicRegionsIndex({ regions, filters }: Props) {
    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Geographic Regions" />

            <RefTableLayout
                title="Geographic Regions"
                description="Hierarchical geographic regions and their relationships"
                basePath={index.url()}
                filters={filters}
                paginated={regions}
            >
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Parent</TableHead>
                                <TableHead>Depth</TableHead>
                                <TableHead>Modern Countries</TableHead>
                                <TableHead className="text-right">
                                    Sort Order
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {regions.data.length === 0 ? (
                                <TableRow>
                                    <TableCell
                                        colSpan={5}
                                        className="h-24 text-center"
                                    >
                                        <div className="text-muted-foreground">
                                            No records found.
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                regions.data.map((region) => (
                                    <TableRow key={region.region_id}>
                                        <TableCell className="font-medium">
                                            <span
                                                style={{
                                                    paddingLeft: `${region.depth_level * 1.25}rem`,
                                                }}
                                            >
                                                {region.depth_level > 0 && (
                                                    <span className="mr-1 text-muted-foreground">
                                                        ↳
                                                    </span>
                                                )}
                                                {region.name}
                                            </span>
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {region.parent_name ?? '—'}
                                        </TableCell>
                                        <TableCell className="tabular-nums">
                                            {region.depth_level}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {region.modern_countries?.join(
                                                ', ',
                                            ) ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-right tabular-nums">
                                            {region.sort_order ?? '—'}
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

import { Head } from '@inertiajs/react';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import { RefTableLayout } from '@/components/ref-table-layout';
import AppLayout from '@/layouts/app-layout';
import { index } from '@/routes/reference/religious-traditions';
import type { BreadcrumbItem, PaginatedData } from '@/types';
import type { ReligiousTradition } from '@/types/reference';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Reference', href: '#' },
    { title: 'Religious Traditions', href: index.url() },
];

type Filters = { search: string; per_page: number };

type Props = {
    traditions: PaginatedData<ReligiousTradition>;
    filters: Filters;
};

export default function ReligiousTraditionsIndex({ traditions, filters }: Props) {
    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Religious Traditions" />

            <RefTableLayout
                title="Religious Traditions"
                description="Hierarchical religious traditions and their sub-traditions"
                basePath={index.url()}
                filters={filters}
                paginated={traditions}
            >
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Parent</TableHead>
                                <TableHead>Depth</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Origin</TableHead>
                                <TableHead>Founder</TableHead>
                                <TableHead>Colour</TableHead>
                                <TableHead className="text-right">Sort</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {traditions.data.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={8} className="h-24 text-center">
                                        <div className="text-muted-foreground">No records found.</div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                traditions.data.map((tradition) => (
                                    <TableRow key={tradition.tradition_id}>
                                        <TableCell className="font-medium">
                                            <span
                                                style={{
                                                    paddingLeft: `${tradition.depth_level * 1.25}rem`,
                                                }}
                                            >
                                                {tradition.depth_level > 0 && (
                                                    <span className="text-muted-foreground mr-1">↳</span>
                                                )}
                                                {tradition.name}
                                            </span>
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {tradition.parent_name ?? '—'}
                                        </TableCell>
                                        <TableCell className="tabular-nums">{tradition.depth_level}</TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {tradition.tradition_type ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {[tradition.origin_date, tradition.origin_region]
                                                .filter(Boolean)
                                                .join(', ') || '—'}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {tradition.founder ?? '—'}
                                        </TableCell>
                                        <TableCell>
                                            {tradition.color_hex ? (
                                                <span className="inline-flex items-center gap-1.5">
                                                    <span
                                                        className="inline-block size-4 rounded-sm border"
                                                        style={{ backgroundColor: tradition.color_hex }}
                                                    />
                                                    <span className="text-muted-foreground text-xs tabular-nums">
                                                        {tradition.color_hex}
                                                    </span>
                                                </span>
                                            ) : (
                                                '—'
                                            )}
                                        </TableCell>
                                        <TableCell className="text-right tabular-nums">
                                            {tradition.sort_order ?? '—'}
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

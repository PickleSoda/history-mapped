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
import { index } from '@/routes/reference/language-families';
import type { BreadcrumbItem, PaginatedData } from '@/types';
import type { LanguageFamily } from '@/types/reference';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Reference', href: '#' },
    { title: 'Language Families', href: index.url() },
];

type Filters = { search: string; per_page: number };

type Props = {
    families: PaginatedData<LanguageFamily>;
    filters: Filters;
};

export default function LanguageFamiliesIndex({ families, filters }: Props) {
    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Language Families" />

            <RefTableLayout
                title="Language Families"
                description="Hierarchical language families and their proto-languages"
                basePath={index.url()}
                filters={filters}
                paginated={families}
            >
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Parent</TableHead>
                                <TableHead>Depth</TableHead>
                                <TableHead>Proto Language</TableHead>
                                <TableHead>Est. Origin</TableHead>
                                <TableHead>Homeland</TableHead>
                                <TableHead>Living Languages</TableHead>
                                <TableHead>Status</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {families.data.length === 0 ? (
                                <TableRow>
                                    <TableCell
                                        colSpan={8}
                                        className="h-24 text-center"
                                    >
                                        <div className="text-muted-foreground">
                                            No records found.
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                families.data.map((family) => (
                                    <TableRow key={family.family_id}>
                                        <TableCell className="font-medium">
                                            <span
                                                style={{
                                                    paddingLeft: `${family.depth_level * 1.25}rem`,
                                                }}
                                            >
                                                {family.depth_level > 0 && (
                                                    <span className="mr-1 text-muted-foreground">
                                                        ↳
                                                    </span>
                                                )}
                                                {family.name}
                                            </span>
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {family.parent_name ?? '—'}
                                        </TableCell>
                                        <TableCell className="tabular-nums">
                                            {family.depth_level}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {family.proto_language ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground tabular-nums">
                                            {family.estimated_origin ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {family.estimated_homeland ?? '—'}
                                        </TableCell>
                                        <TableCell className="tabular-nums">
                                            {family.living_languages ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {family.status ?? '—'}
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

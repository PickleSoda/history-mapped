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
import { index } from '@/routes/reference/source-type-definitions';
import type { BreadcrumbItem, PaginatedData } from '@/types';
import type { SourceTypeDefinition } from '@/types/reference';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Reference', href: '#' },
    { title: 'Source Type Definitions', href: index.url() },
];

const confidenceColors: Record<string, string> = {
    high: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    low: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
};

type Filters = { search: string; per_page: number };

type Props = {
    definitions: PaginatedData<SourceTypeDefinition>;
    filters: Filters;
};

export default function SourceTypeDefinitionsIndex({
    definitions,
    filters,
}: Props) {
    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Source Type Definitions" />

            <RefTableLayout
                title="Source Type Definitions"
                description="Source type enum definitions with confidence and scoring weights"
                basePath={index.url()}
                filters={filters}
                paginated={definitions}
            >
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Enum Name</TableHead>
                                <TableHead>Enum Value</TableHead>
                                <TableHead>Description</TableHead>
                                <TableHead>Default Confidence</TableHead>
                                <TableHead>Requires Corroboration</TableHead>
                                <TableHead className="text-right">
                                    Scoring Weight
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {definitions.data.length === 0 ? (
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
                                definitions.data.map((def) => (
                                    <TableRow key={def.definition_id}>
                                        <TableCell className="font-mono text-sm">
                                            {def.enum_name}
                                        </TableCell>
                                        <TableCell className="font-mono text-sm">
                                            {def.enum_value}
                                        </TableCell>
                                        <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                                            {def.description}
                                        </TableCell>
                                        <TableCell>
                                            {def.default_confidence ? (
                                                <Badge
                                                    variant="outline"
                                                    className={
                                                        confidenceColors[
                                                            def
                                                                .default_confidence
                                                        ] ?? ''
                                                    }
                                                >
                                                    {def.default_confidence}
                                                </Badge>
                                            ) : (
                                                '—'
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Badge
                                                variant="outline"
                                                className={
                                                    def.requires_corroboration
                                                        ? 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
                                                        : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                                                }
                                            >
                                                {def.requires_corroboration
                                                    ? 'Yes'
                                                    : 'No'}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-right tabular-nums">
                                            {def.weight_in_scoring ?? '—'}
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

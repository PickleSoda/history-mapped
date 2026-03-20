import { Head } from '@inertiajs/react';
import { Badge } from '@/components/ui/badge';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
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
import { router } from '@inertiajs/react';
import { index } from '@/routes/reference/measurement-units';
import type { BreadcrumbItem, PaginatedData } from '@/types';
import type { MeasurementUnit } from '@/types/reference';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Reference', href: '#' },
    { title: 'Measurement Units', href: index.url() },
];

type Filters = { search: string; per_page: number; type?: string };

type Props = {
    units: PaginatedData<MeasurementUnit>;
    filters: Filters;
    types: string[];
};

export default function MeasurementUnitsIndex({ units, filters, types }: Props) {
    const handleTypeChange = (value: string) => {
        router.get(
            index.url(),
            {
                ...(filters.search && { search: filters.search }),
                ...(value !== '__all__' && { type: value }),
            },
            { preserveState: true, preserveScroll: true },
        );
    };

    const typeFilter = (
        <Select value={filters.type ?? '__all__'} onValueChange={handleTypeChange}>
            <SelectTrigger className="w-48">
                <SelectValue placeholder="All Types" />
            </SelectTrigger>
            <SelectContent>
                <SelectItem value="__all__">All Types</SelectItem>
                {types.map((t) => (
                    <SelectItem key={t} value={t}>
                        {t}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    );

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Measurement Units" />

            <RefTableLayout
                title="Measurement Units"
                description="Historical measurement units and their SI equivalents"
                basePath={index.url()}
                filters={filters}
                paginated={units}
                extra={typeFilter}
            >
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Symbol</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>SI Equivalent</TableHead>
                                <TableHead>SI Unit</TableHead>
                                <TableHead>Region</TableHead>
                                <TableHead>Period</TableHead>
                                <TableHead>Approx.</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {units.data.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={8} className="h-24 text-center">
                                        <div className="text-muted-foreground">No records found.</div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                units.data.map((unit) => (
                                    <TableRow key={unit.unit_id}>
                                        <TableCell className="font-medium">{unit.name}</TableCell>
                                        <TableCell className="font-mono text-sm">
                                            {unit.symbol ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {unit.measurement_type}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground tabular-nums text-sm">
                                            {unit.si_equivalent ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {unit.si_unit ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {unit.used_by_region ?? '—'}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {unit.used_by_period ?? '—'}
                                        </TableCell>
                                        <TableCell>
                                            {unit.approximate ? (
                                                <Badge
                                                    variant="outline"
                                                    className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
                                                >
                                                    Yes
                                                </Badge>
                                            ) : (
                                                <span className="text-muted-foreground text-sm">No</span>
                                            )}
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

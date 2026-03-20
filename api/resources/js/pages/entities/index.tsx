import { Head, Link, router } from '@inertiajs/react';
import {
    ArrowDown,
    ArrowUp,
    ArrowUpDown,
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Search,
    X,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import AppLayout from '@/layouts/app-layout';
import type {
    BreadcrumbItem,
    EntityFilterOptions,
    EntityFilters,
    EntitySummary,
    PaginatedData,
} from '@/types';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Entities', href: '/entities' },
];

type Props = {
    entities: PaginatedData<EntitySummary>;
    filters: EntityFilters;
    filterOptions: EntityFilterOptions;
};

const groupColors: Record<string, string> = {
    POLITY: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    PLACE: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    EVENT: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    ECONOMY: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
    CULTURE: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
};

const confidenceColors: Record<string, string> = {
    high: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    low: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
    unresolved: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
};

const statusColors: Record<string, string> = {
    pipeline_draft: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
    auto_validated: 'bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-200',
    needs_review: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    in_review: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    human_verified: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    expert_verified: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200',
    flagged: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    rejected: 'bg-red-200 text-red-900 dark:bg-red-950 dark:text-red-200',
    merged: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
};

function formatEntityType(type: string | null): string {
    if (!type) return '-';
    return type
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatStatus(status: string | null): string {
    if (!status) return '-';
    return status
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function EntitiesIndex({ entities, filters, filterOptions }: Props) {
    const [search, setSearch] = useState(filters.search);
    const [dateFrom, setDateFrom] = useState(filters.date_from);
    const [dateTo, setDateTo] = useState(filters.date_to);

    const navigate = useCallback(
        (params: Record<string, string | number>) => {
            const query: Record<string, string | number> = {
                ...(filters.search && { search: filters.search }),
                ...(filters.type && { type: filters.type }),
                ...(filters.group && { group: filters.group }),
                ...(filters.status && { status: filters.status }),
                ...(filters.confidence && { confidence: filters.confidence }),
                ...(filters.date_from && { date_from: filters.date_from }),
                ...(filters.date_to && { date_to: filters.date_to }),
                ...(filters.sort !== 'impact' && { sort: filters.sort }),
                ...(filters.per_page !== 25 && { per_page: filters.per_page }),
                ...params,
            };

            // Remove empty values
            Object.keys(query).forEach((key) => {
                if (query[key] === '' || query[key] === undefined) {
                    delete query[key];
                }
            });

            // Reset to page 1 when filters change (but not when page changes)
            if (!('page' in params)) {
                delete query.page;
            }

            router.get('/entities', query, {
                preserveState: true,
                preserveScroll: true,
            });
        },
        [filters],
    );

    const handleSearch = useCallback(
        (e: React.FormEvent) => {
            e.preventDefault();
            navigate({ search });
        },
        [search, navigate],
    );

    const handleDateFilter = useCallback(
        (e: React.FormEvent) => {
            e.preventDefault();
            navigate({ date_from: dateFrom, date_to: dateTo });
        },
        [dateFrom, dateTo, navigate],
    );

    const clearFilters = useCallback(() => {
        setSearch('');
        setDateFrom('');
        setDateTo('');
        router.get('/entities', {}, { preserveState: true, preserveScroll: true });
    }, []);

    const hasActiveFilters =
        filters.search ||
        filters.type ||
        filters.group ||
        filters.status ||
        filters.confidence ||
        filters.date_from ||
        filters.date_to;

    const sortIcon = (field: string) => {
        if (filters.sort === field) return <ArrowDown className="ml-1 inline size-3" />;
        if (filters.sort === `-${field}`) return <ArrowUp className="ml-1 inline size-3" />;
        return <ArrowUpDown className="ml-1 inline size-3 opacity-30" />;
    };

    const toggleSort = (field: string) => {
        if (filters.sort === field) {
            navigate({ sort: `-${field}` });
        } else {
            navigate({ sort: field });
        }
    };

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Entities" />

            <div className="flex flex-col gap-4 p-4">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Entities</h1>
                        <p className="text-muted-foreground text-sm">
                            {entities.total} {entities.total === 1 ? 'entity' : 'entities'} found
                        </p>
                    </div>
                </div>

                {/* Filters — row 1: search + type + group + status + confidence */}
                <div className="flex flex-wrap items-end gap-3">
                    {/* Search */}
                    <form onSubmit={handleSearch} className="flex gap-2">
                        <div className="relative">
                            <Search className="text-muted-foreground pointer-events-none absolute left-2.5 top-2.5 size-4" />
                            <Input
                                type="search"
                                placeholder="Search entities..."
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="w-64 pl-9"
                            />
                        </div>
                        <Button type="submit" variant="outline" size="default">
                            Search
                        </Button>
                    </form>

                    {/* Entity Type filter */}
                    <Select
                        value={filters.type || '__all__'}
                        onValueChange={(v) => navigate({ type: v === '__all__' ? '' : v })}
                    >
                        <SelectTrigger className="w-48">
                            <SelectValue placeholder="All Types" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__all__">All Types</SelectItem>
                            {filterOptions.types.map((t) => (
                                <SelectItem key={t.value} value={t.value}>
                                    {t.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {/* Group filter */}
                    <Select
                        value={filters.group || '__all__'}
                        onValueChange={(v) => navigate({ group: v === '__all__' ? '' : v })}
                    >
                        <SelectTrigger className="w-36">
                            <SelectValue placeholder="All Groups" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__all__">All Groups</SelectItem>
                            {filterOptions.groups.map((g) => (
                                <SelectItem key={g.value} value={g.value}>
                                    {g.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {/* Status filter */}
                    <Select
                        value={filters.status || '__all__'}
                        onValueChange={(v) => navigate({ status: v === '__all__' ? '' : v })}
                    >
                        <SelectTrigger className="w-44">
                            <SelectValue placeholder="All Statuses" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__all__">All Statuses</SelectItem>
                            {filterOptions.statuses.map((s) => (
                                <SelectItem key={s.value} value={s.value}>
                                    {s.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {/* Confidence filter */}
                    <Select
                        value={filters.confidence || '__all__'}
                        onValueChange={(v) => navigate({ confidence: v === '__all__' ? '' : v })}
                    >
                        <SelectTrigger className="w-40">
                            <SelectValue placeholder="All Confidence" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__all__">All Confidence</SelectItem>
                            {filterOptions.confidences.map((c) => (
                                <SelectItem key={c.value} value={c.value}>
                                    {c.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Filters — row 2: date range + clear */}
                <div className="flex flex-wrap items-end gap-3">
                    <form onSubmit={handleDateFilter} className="flex items-end gap-2">
                        <div className="flex flex-col gap-1">
                            <label className="text-muted-foreground text-xs">From year</label>
                            <Input
                                type="number"
                                placeholder="e.g. -500"
                                value={dateFrom}
                                onChange={(e) => setDateFrom(e.target.value)}
                                className="w-32"
                            />
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-muted-foreground text-xs">To year</label>
                            <Input
                                type="number"
                                placeholder="e.g. 1500"
                                value={dateTo}
                                onChange={(e) => setDateTo(e.target.value)}
                                className="w-32"
                            />
                        </div>
                        <Button type="submit" variant="outline" size="default">
                            Apply
                        </Button>
                    </form>

                    {/* Clear filters */}
                    {hasActiveFilters && (
                        <Button variant="ghost" size="sm" onClick={clearFilters}>
                            <X className="mr-1 size-4" />
                            Clear filters
                        </Button>
                    )}
                </div>

                {/* Data Table */}
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead
                                    className="cursor-pointer select-none"
                                    onClick={() => toggleSort('name')}
                                >
                                    Name {sortIcon('name')}
                                </TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Group</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Confidence</TableHead>
                                <TableHead
                                    className="cursor-pointer select-none"
                                    onClick={() => toggleSort('impact')}
                                >
                                    Impact {sortIcon('impact')}
                                </TableHead>
                                <TableHead
                                    className="cursor-pointer select-none"
                                    onClick={() => toggleSort('chronological')}
                                >
                                    Period {sortIcon('chronological')}
                                </TableHead>
                                <TableHead>Location</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {entities.data.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={8} className="h-24 text-center">
                                        <div className="text-muted-foreground">
                                            {hasActiveFilters
                                                ? 'No entities match the current filters.'
                                                : 'No entities yet. Create your first entity to get started.'}
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                entities.data.map((entity) => (
                                    <TableRow key={entity.id}>
                                        <TableCell className="max-w-[250px]">
                                            <Link
                                                href={`/entities/${entity.id}`}
                                                className="font-medium text-foreground hover:underline"
                                            >
                                                {entity.name}
                                            </Link>
                                            {entity.summary && (
                                                <p className="text-muted-foreground mt-0.5 truncate text-xs">
                                                    {entity.summary}
                                                </p>
                                            )}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-xs">
                                            {formatEntityType(entity.entity_type)}
                                        </TableCell>
                                        <TableCell>
                                            {entity.entity_group ? (
                                                <Badge
                                                    variant="outline"
                                                    className={groupColors[entity.entity_group] ?? ''}
                                                >
                                                    {entity.entity_group}
                                                </Badge>
                                            ) : (
                                                '-'
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            {entity.verification_status ? (
                                                <Badge
                                                    variant="outline"
                                                    className={statusColors[entity.verification_status] ?? ''}
                                                >
                                                    {formatStatus(entity.verification_status)}
                                                </Badge>
                                            ) : (
                                                '-'
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            {entity.confidence ? (
                                                <Badge
                                                    variant="outline"
                                                    className={confidenceColors[entity.confidence] ?? ''}
                                                >
                                                    {entity.confidence}
                                                </Badge>
                                            ) : (
                                                '-'
                                            )}
                                        </TableCell>
                                        <TableCell className="tabular-nums">
                                            {entity.impact_score ?? '-'}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-xs">
                                            {entity.temporal_display_range ?? entity.era_label ?? '-'}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground max-w-[150px] truncate text-xs">
                                            {entity.location_name ?? '-'}
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>

                {/* Pagination */}
                {entities.last_page > 1 && (
                    <div className="flex items-center justify-between">
                        <p className="text-muted-foreground text-sm">
                            Showing {entities.from} to {entities.to} of {entities.total}
                        </p>
                        <div className="flex items-center gap-1">
                            <Button
                                variant="outline"
                                size="icon"
                                className="size-8"
                                disabled={entities.current_page <= 1}
                                onClick={() => navigate({ page: 1 })}
                            >
                                <ChevronsLeft className="size-4" />
                            </Button>
                            <Button
                                variant="outline"
                                size="icon"
                                className="size-8"
                                disabled={entities.current_page <= 1}
                                onClick={() => navigate({ page: entities.current_page - 1 })}
                            >
                                <ChevronLeft className="size-4" />
                            </Button>

                            <span className="text-muted-foreground px-3 text-sm tabular-nums">
                                Page {entities.current_page} of {entities.last_page}
                            </span>

                            <Button
                                variant="outline"
                                size="icon"
                                className="size-8"
                                disabled={entities.current_page >= entities.last_page}
                                onClick={() => navigate({ page: entities.current_page + 1 })}
                            >
                                <ChevronRight className="size-4" />
                            </Button>
                            <Button
                                variant="outline"
                                size="icon"
                                className="size-8"
                                disabled={entities.current_page >= entities.last_page}
                                onClick={() => navigate({ page: entities.last_page })}
                            >
                                <ChevronsRight className="size-4" />
                            </Button>
                        </div>
                    </div>
                )}
            </div>
        </AppLayout>
    );
}

import { Head, Link, router } from '@inertiajs/react';
import { Plus, Search, X } from 'lucide-react';
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
import AppLayout from '@/layouts/app-layout';
import type { BreadcrumbItem, PaginatedChronicles, ChronicleFilters, FilterOption } from '@/types';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Chronicles', href: '/chronicles' },
];

type Props = {
    chronicles: PaginatedChronicles;
    filters: ChronicleFilters;
    filterOptions: { statuses: FilterOption[]; sourceTypes: FilterOption[] };
};

const statusColors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
    published: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    archived: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

export default function ChroniclesIndex({ chronicles, filters, filterOptions }: Props) {
    const [search, setSearch] = useState(filters.search);
    const [statusFilter, setStatusFilter] = useState(filters.status || '__all__');

    const navigate = useCallback(
        (params: Record<string, string | number>) => {
            const query: Record<string, string | number> = {
                ...(filters.search && { search: filters.search }),
                ...(filters.status && { status: filters.status }),
                ...params,
            };

            Object.keys(query).forEach((key) => {
                if (query[key] === '' || query[key] === undefined) {
                    delete query[key];
                }
            });

            if (!('page' in params)) {
                delete query.page;
            }

            router.get('/chronicles', query, {
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

    const handleStatusFilter = useCallback(
        (value: string) => {
            setStatusFilter(value);
            navigate({ status: value === '__all__' ? '' : value });
        },
        [navigate],
    );

    const clearFilters = useCallback(() => {
        setSearch('');
        setStatusFilter('__all__');
        router.get('/chronicles', {}, { preserveState: true, preserveScroll: true });
    }, []);

    const hasActiveFilters = filters.search || filters.status;

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Chronicles" />

            <div className="flex flex-col gap-4 p-4">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">
                            Chronicles
                        </h1>
                        <p className="text-sm text-muted-foreground">
                            {chronicles.total} {chronicles.total === 1 ? 'chronicle' : 'chronicles'} found
                        </p>
                    </div>
                    <Link href="/chronicles/create">
                        <Button size="sm">
                            <Plus className="mr-1.5 size-4" />
                            New Chronicle
                        </Button>
                    </Link>
                </div>

                {/* Filters */}
                <div className="flex flex-wrap items-end gap-3">
                    {/* Search */}
                    <form onSubmit={handleSearch} className="flex gap-2">
                        <div className="relative">
                            <Search className="pointer-events-none absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
                            <Input
                                type="search"
                                placeholder="Search chronicles..."
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="w-64 pl-9"
                            />
                        </div>
                        <Button type="submit" variant="outline" size="default">
                            Search
                        </Button>
                    </form>

                    {/* Status filter */}
                    <Select value={statusFilter} onValueChange={handleStatusFilter}>
                        <SelectTrigger className="w-40">
                            <SelectValue placeholder="All statuses" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__all__">All statuses</SelectItem>
                            {filterOptions.statuses.map((s) => (
                                <SelectItem key={s.value} value={s.value}>
                                    {s.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {/* Clear filters */}
                    {hasActiveFilters && (
                        <Button variant="ghost" size="sm" onClick={clearFilters}>
                            <X className="mr-1.5 size-4" />
                            Clear
                        </Button>
                    )}
                </div>

                {/* Chronicle List */}
                <div className="grid gap-4">
                    {chronicles.data.length === 0 ? (
                        <div className="rounded-lg border p-8 text-center text-muted-foreground">
                            No chronicles found.{' '}
                            <Link href="/chronicles/create" className="text-primary underline">
                                Create one
                            </Link>
                        </div>
                    ) : (
                        chronicles.data.map((chronicle) => (
                            <Link
                                key={chronicle.chronicle_id}
                                href={`/chronicles/${chronicle.slug}`}
                                className="block"
                            >
                                <div className="rounded-lg border p-4 transition-colors hover:bg-muted/50">
                                    <div className="flex items-center justify-between">
                                        <div className="flex-1">
                                            <h2 className="text-lg font-semibold">{chronicle.title}</h2>
                                            <div className="mt-1 flex items-center gap-2">
                                                <Badge variant="outline">
                                                    {chronicle.source_type?.replace(/_/g, ' ') || '—'}
                                                </Badge>
                                                {chronicle.status && (
                                                    <Badge className={statusColors[chronicle.status] || ''}>
                                                        {chronicle.status}
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>
                                        <div className="text-sm text-muted-foreground">
                                            {chronicle.entry_count} {chronicle.entry_count === 1 ? 'entry' : 'entries'}
                                        </div>
                                    </div>
                                </div>
                            </Link>
                        ))
                    )}
                </div>

                {/* Pagination */}
                {chronicles.last_page > 1 && (
                    <div className="flex items-center justify-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={chronicles.current_page === 1}
                            onClick={() => navigate({ page: chronicles.current_page - 1 })}
                        >
                            Previous
                        </Button>
                        <span className="text-sm text-muted-foreground">
                            Page {chronicles.current_page} of {chronicles.last_page}
                        </span>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={chronicles.current_page === chronicles.last_page}
                            onClick={() => navigate({ page: chronicles.current_page + 1 })}
                        >
                            Next
                        </Button>
                    </div>
                )}
            </div>
        </AppLayout>
    );
}

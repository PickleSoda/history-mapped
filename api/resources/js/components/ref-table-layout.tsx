import { router } from '@inertiajs/react';
import {
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Search,
    X,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { PaginatedData } from '@/types';

type Props<T> = {
    title: string;
    description?: string;
    basePath: string;
    filters: { search: string; per_page: number; [key: string]: string | number };
    paginated: PaginatedData<T>;
    extra?: React.ReactNode;
    children: React.ReactNode;
};

export function RefTableLayout<T>({
    title,
    description,
    basePath,
    filters,
    paginated,
    extra,
    children,
}: Props<T>) {
    const [search, setSearch] = useState(filters.search);

    const navigate = useCallback(
        (params: Record<string, string | number>) => {
            const query: Record<string, string | number> = {
                ...(filters.search && { search: filters.search }),
                ...(filters.per_page !== 50 && { per_page: filters.per_page }),
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

            router.get(basePath, query, { preserveState: true, preserveScroll: true });
        },
        [filters, basePath],
    );

    const handleSearch = useCallback(
        (e: React.FormEvent) => {
            e.preventDefault();
            navigate({ search });
        },
        [search, navigate],
    );

    const clearSearch = useCallback(() => {
        setSearch('');
        router.get(basePath, {}, { preserveState: true, preserveScroll: true });
    }, [basePath]);

    return (
        <div className="flex flex-col gap-4 p-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
                    {description && (
                        <p className="text-muted-foreground text-sm">{description}</p>
                    )}
                    <p className="text-muted-foreground text-sm">
                        {paginated.total} {paginated.total === 1 ? 'record' : 'records'}
                    </p>
                </div>
            </div>

            {/* Search + extras */}
            <div className="flex flex-wrap items-end gap-3">
                <form onSubmit={handleSearch} className="flex gap-2">
                    <div className="relative">
                        <Search className="text-muted-foreground pointer-events-none absolute left-2.5 top-2.5 size-4" />
                        <Input
                            type="search"
                            placeholder={`Search ${title.toLowerCase()}…`}
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="w-64 pl-9"
                        />
                    </div>
                    <Button type="submit" variant="outline" size="default">
                        Search
                    </Button>
                </form>

                {extra}

                {filters.search && (
                    <Button variant="ghost" size="sm" onClick={clearSearch}>
                        <X className="mr-1 size-4" />
                        Clear
                    </Button>
                )}
            </div>

            {/* Table slot */}
            {children}

            {/* Pagination */}
            {paginated.last_page > 1 && (
                <div className="flex items-center justify-between">
                    <p className="text-muted-foreground text-sm">
                        Showing {paginated.from} to {paginated.to} of {paginated.total}
                    </p>
                    <div className="flex items-center gap-1">
                        <Button
                            variant="outline"
                            size="icon"
                            className="size-8"
                            disabled={paginated.current_page <= 1}
                            onClick={() => navigate({ page: 1 })}
                        >
                            <ChevronsLeft className="size-4" />
                        </Button>
                        <Button
                            variant="outline"
                            size="icon"
                            className="size-8"
                            disabled={paginated.current_page <= 1}
                            onClick={() => navigate({ page: paginated.current_page - 1 })}
                        >
                            <ChevronLeft className="size-4" />
                        </Button>
                        <span className="text-muted-foreground px-3 text-sm tabular-nums">
                            Page {paginated.current_page} of {paginated.last_page}
                        </span>
                        <Button
                            variant="outline"
                            size="icon"
                            className="size-8"
                            disabled={paginated.current_page >= paginated.last_page}
                            onClick={() => navigate({ page: paginated.current_page + 1 })}
                        >
                            <ChevronRight className="size-4" />
                        </Button>
                        <Button
                            variant="outline"
                            size="icon"
                            className="size-8"
                            disabled={paginated.current_page >= paginated.last_page}
                            onClick={() => navigate({ page: paginated.last_page })}
                        >
                            <ChevronsRight className="size-4" />
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}

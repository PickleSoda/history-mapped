import { Head, Link, router } from '@inertiajs/react';
import { Check, Search, ShieldCheck, X } from 'lucide-react';
import { useCallback, useState } from 'react';
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
import { formatDate, RoleBadges, roleLabel } from '@/components/user-badges';
import AppLayout from '@/layouts/app-layout';
import type { BreadcrumbItem, UsersIndexProps } from '@/types';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Users', href: '/users' },
];

const ALL = '__all__';

export default function UsersIndex({
    users,
    filters,
    roles,
    no_role_count,
}: UsersIndexProps) {
    const [search, setSearch] = useState(filters.search);
    const role = filters.role || ALL;

    const navigate = useCallback(
        (params: Record<string, string | number>) => {
            const query: Record<string, string | number> = {
                ...(filters.search && { search: filters.search }),
                ...(filters.role && { role: filters.role }),
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

            router.get('/users', query, {
                preserveState: true,
                preserveScroll: true,
            });
        },
        [filters.search, filters.role],
    );

    const clearFilters = () => {
        setSearch('');
        router.get('/users', {}, { preserveState: true, preserveScroll: true });
    };

    const hasFilters = Boolean(filters.search || filters.role);

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Users" />

            <div className="flex flex-col gap-4 p-4">
                {/* Header */}
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Users</h1>
                    <p className="text-sm text-muted-foreground">
                        {users.total}{' '}
                        {users.total === 1 ? 'account' : 'accounts'}
                        {hasFilters ? ' match these filters' : ''}
                    </p>
                </div>

                {/* Filters */}
                <div className="flex flex-wrap items-center gap-2">
                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            navigate({ search: search.trim() });
                        }}
                        className="flex items-center gap-2"
                    >
                        <div className="relative">
                            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
                            <Input
                                type="search"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="Search name or email…"
                                aria-label="Search users"
                                className="w-72 pl-8"
                            />
                        </div>
                        <Button type="submit" variant="outline">
                            Search
                        </Button>
                    </form>

                    <Select
                        value={role}
                        onValueChange={(value) =>
                            navigate({ role: value === ALL ? '' : value })
                        }
                    >
                        <SelectTrigger className="w-56" aria-label="Role">
                            <SelectValue placeholder="All roles" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={ALL}>All roles</SelectItem>
                            {roles.map((r) => (
                                <SelectItem key={r.name} value={r.name}>
                                    {roleLabel(r.name)}{' '}
                                    <span className="text-muted-foreground">
                                        ({r.users_count})
                                    </span>
                                </SelectItem>
                            ))}
                            <SelectItem value="none">
                                No role{' '}
                                <span className="text-muted-foreground">
                                    ({no_role_count})
                                </span>
                            </SelectItem>
                        </SelectContent>
                    </Select>

                    {hasFilters && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={clearFilters}
                        >
                            <X className="size-4" />
                            Clear
                        </Button>
                    )}
                </div>

                {/* Table */}
                {users.data.length === 0 ? (
                    <div className="rounded-lg border p-8 text-center text-muted-foreground">
                        No users found.
                    </div>
                ) : (
                    <div className="rounded-lg border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>User</TableHead>
                                    <TableHead>Roles</TableHead>
                                    <TableHead className="text-center">
                                        Verified
                                    </TableHead>
                                    <TableHead className="text-center">
                                        2FA
                                    </TableHead>
                                    <TableHead className="text-right">
                                        Contributions
                                    </TableHead>
                                    <TableHead>Joined</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {users.data.map((u) => (
                                    <TableRow
                                        key={u.id}
                                        className="cursor-pointer"
                                        onClick={() =>
                                            router.visit(`/users/${u.id}`)
                                        }
                                    >
                                        <TableCell className="max-w-sm">
                                            <Link
                                                href={`/users/${u.id}`}
                                                className="block truncate font-medium hover:underline"
                                                onClick={(e) =>
                                                    e.stopPropagation()
                                                }
                                            >
                                                {u.name}
                                            </Link>
                                            <div className="truncate text-xs text-muted-foreground">
                                                {u.email}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <RoleBadges roles={u.roles} />
                                        </TableCell>
                                        <TableCell className="text-center">
                                            <YesNo
                                                value={
                                                    u.email_verified_at !== null
                                                }
                                                label="Email verified"
                                            />
                                        </TableCell>
                                        <TableCell className="text-center">
                                            {u.two_factor_enabled ? (
                                                <ShieldCheck
                                                    className="mx-auto size-4 text-emerald-600 dark:text-emerald-400"
                                                    aria-label="Two-factor enabled"
                                                />
                                            ) : (
                                                <YesNo
                                                    value={false}
                                                    label="Two-factor"
                                                />
                                            )}
                                        </TableCell>
                                        <TableCell className="text-right font-mono text-sm">
                                            {u.contributions_count}
                                        </TableCell>
                                        <TableCell className="text-sm whitespace-nowrap text-muted-foreground">
                                            {formatDate(u.created_at)}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                )}

                {/* Pagination */}
                {users.last_page > 1 && (
                    <div className="flex items-center justify-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={users.current_page === 1}
                            onClick={() =>
                                navigate({ page: users.current_page - 1 })
                            }
                        >
                            Previous
                        </Button>
                        <span className="text-sm text-muted-foreground">
                            Page {users.current_page} of {users.last_page}
                        </span>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={users.current_page === users.last_page}
                            onClick={() =>
                                navigate({ page: users.current_page + 1 })
                            }
                        >
                            Next
                        </Button>
                    </div>
                )}
            </div>
        </AppLayout>
    );
}

function YesNo({ value, label }: { value: boolean; label: string }) {
    return value ? (
        <Check
            className="mx-auto size-4 text-emerald-600 dark:text-emerald-400"
            aria-label={`${label}: yes`}
        />
    ) : (
        <span className="text-muted-foreground" aria-label={`${label}: no`}>
            —
        </span>
    );
}

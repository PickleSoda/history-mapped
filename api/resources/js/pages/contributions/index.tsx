import { Head, Link, router } from '@inertiajs/react';
import { useCallback } from 'react';
import {
    CONTRIBUTION_STATUSES,
    DiffStatsText,
    formatDateTime,
    StaleBadge,
    StatusBadge,
    TARGET_TYPE_LABELS,
    TargetBadges,
} from '@/components/contribution-badges';
import { Button } from '@/components/ui/button';
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
import { cn } from '@/lib/utils';
import type {
    BreadcrumbItem,
    ContributionIndexProps,
    ContributionTargetType,
} from '@/types';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Contributions', href: '/contributions' },
];

const TABS = [...CONTRIBUTION_STATUSES, 'all'] as const;

export default function ContributionsIndex({
    contributions,
    filters,
    counts,
}: ContributionIndexProps) {
    const status = filters.status || 'pending';
    const type = filters.type || '__all__';
    const total = CONTRIBUTION_STATUSES.reduce(
        (sum, s) => sum + (counts[s] ?? 0),
        0,
    );

    const navigate = useCallback(
        (params: Record<string, string | number>) => {
            const query: Record<string, string | number> = {
                status,
                ...(filters.type && { type: filters.type }),
                ...params,
            };

            Object.keys(query).forEach((key) => {
                if (query[key] === '' || query[key] === undefined) {
                    delete query[key];
                }
            });

            router.get('/contributions', query, {
                preserveState: true,
                preserveScroll: true,
            });
        },
        [status, filters.type],
    );

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Contributions" />

            <div className="flex flex-col gap-4 p-4">
                {/* Header */}
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">
                        Contributions
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        Text corrections suggested by atlas users. Approving one
                        applies the proposed text.
                    </p>
                </div>

                {/* Status tabs + type filter */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <nav
                        aria-label="Filter by status"
                        className="flex flex-wrap gap-1 rounded-lg bg-muted p-1"
                    >
                        {TABS.map((tab) => {
                            const active = status === tab;
                            const count =
                                tab === 'all' ? total : (counts[tab] ?? 0);

                            return (
                                <button
                                    key={tab}
                                    type="button"
                                    aria-current={active ? 'page' : undefined}
                                    onClick={() => navigate({ status: tab })}
                                    className={cn(
                                        'inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-sm font-medium capitalize transition-colors',
                                        active
                                            ? 'bg-background text-foreground shadow-sm'
                                            : 'text-muted-foreground hover:text-foreground',
                                    )}
                                >
                                    {tab}
                                    <span className="rounded-full bg-muted-foreground/15 px-1.5 font-mono text-[11px]">
                                        {count}
                                    </span>
                                </button>
                            );
                        })}
                    </nav>

                    <Select
                        value={type}
                        onValueChange={(value) =>
                            navigate({ type: value === '__all__' ? '' : value })
                        }
                    >
                        <SelectTrigger
                            className="w-48"
                            aria-label="Target type"
                        >
                            <SelectValue placeholder="All types" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__all__">All types</SelectItem>
                            {(
                                Object.keys(
                                    TARGET_TYPE_LABELS,
                                ) as ContributionTargetType[]
                            ).map((t) => (
                                <SelectItem key={t} value={t}>
                                    {TARGET_TYPE_LABELS[t]}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* List */}
                {contributions.data.length === 0 ? (
                    <div className="rounded-lg border p-8 text-center text-muted-foreground">
                        {status === 'pending'
                            ? 'Nothing waiting for review.'
                            : 'No contributions found.'}
                    </div>
                ) : (
                    <div className="rounded-lg border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Target</TableHead>
                                    <TableHead>Contributor</TableHead>
                                    <TableHead>Change</TableHead>
                                    <TableHead>Submitted</TableHead>
                                    <TableHead>Status</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {contributions.data.map((c) => (
                                    <TableRow
                                        key={c.id}
                                        className="cursor-pointer"
                                        onClick={() =>
                                            router.visit(
                                                `/contributions/${c.id}`,
                                            )
                                        }
                                    >
                                        <TableCell className="max-w-md">
                                            <Link
                                                href={`/contributions/${c.id}`}
                                                className="block truncate font-medium hover:underline"
                                                onClick={(e) =>
                                                    e.stopPropagation()
                                                }
                                            >
                                                {c.target_label}
                                            </Link>
                                            <div className="mt-1 flex flex-wrap items-center gap-1.5">
                                                <TargetBadges
                                                    type={c.target_type}
                                                    field={c.field}
                                                />
                                                {c.is_stale &&
                                                    c.status === 'pending' && (
                                                        <StaleBadge />
                                                    )}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            {c.user ? (
                                                <>
                                                    <div className="text-sm">
                                                        {c.user.name}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {c.user.email}
                                                    </div>
                                                </>
                                            ) : (
                                                <span className="text-muted-foreground">
                                                    Deleted user
                                                </span>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <DiffStatsText stats={c.stats} />
                                        </TableCell>
                                        <TableCell className="text-sm whitespace-nowrap text-muted-foreground">
                                            {formatDateTime(c.created_at)}
                                        </TableCell>
                                        <TableCell>
                                            <StatusBadge status={c.status} />
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                )}

                {/* Pagination */}
                {contributions.last_page > 1 && (
                    <div className="flex items-center justify-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={contributions.current_page === 1}
                            onClick={() =>
                                navigate({
                                    page: contributions.current_page - 1,
                                })
                            }
                        >
                            Previous
                        </Button>
                        <span className="text-sm text-muted-foreground">
                            Page {contributions.current_page} of{' '}
                            {contributions.last_page}
                        </span>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={
                                contributions.current_page ===
                                contributions.last_page
                            }
                            onClick={() =>
                                navigate({
                                    page: contributions.current_page + 1,
                                })
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

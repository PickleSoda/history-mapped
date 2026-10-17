import { Head, Link } from '@inertiajs/react';
import {
    ArrowLeft,
    Check,
    Folder,
    PencilLine,
    ShieldCheck,
    Star,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import {
    CONTRIBUTION_STATUSES,
    fieldLabel,
    formatDateTime,
    StatusBadge,
    TARGET_TYPE_LABELS,
} from '@/components/contribution-badges';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { formatDate, RoleBadges } from '@/components/user-badges';
import AppLayout from '@/layouts/app-layout';
import type { BreadcrumbItem, UserShowProps } from '@/types';

function Detail({ label, children }: { label: string; children: ReactNode }) {
    return (
        <div className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium text-muted-foreground">
                {label}
            </dt>
            <dd className="text-sm">{children}</dd>
        </div>
    );
}

function StatCard({
    icon: Icon,
    label,
    value,
}: {
    icon: LucideIcon;
    label: string;
    value: number;
}) {
    return (
        <Card className="gap-2 py-4">
            <CardContent className="flex items-center gap-3 px-4">
                <Icon className="size-5 text-muted-foreground" />
                <div>
                    <div className="text-xl font-semibold tabular-nums">
                        {value}
                    </div>
                    <div className="text-xs text-muted-foreground">{label}</div>
                </div>
            </CardContent>
        </Card>
    );
}

export default function UserShow({
    user,
    direct_permissions,
    effective_permissions,
    stats,
    recent_contributions,
    is_self,
}: UserShowProps) {
    const breadcrumbs: BreadcrumbItem[] = [
        { title: 'Dashboard', href: '/dashboard' },
        { title: 'Users', href: '/users' },
        { title: user.name, href: `/users/${user.id}` },
    ];

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={user.name} />

            <div className="flex max-w-5xl flex-col gap-4 p-4">
                <Link
                    href="/users"
                    className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
                >
                    <ArrowLeft className="size-4" />
                    All users
                </Link>

                {/* Header */}
                <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex flex-col gap-1.5">
                        <h1 className="text-2xl font-bold tracking-tight">
                            {user.name}
                            {is_self && (
                                <span className="ml-2 text-base font-normal text-muted-foreground">
                                    (you)
                                </span>
                            )}
                        </h1>
                        <p className="text-sm text-muted-foreground">
                            {user.email}
                        </p>
                        <RoleBadges roles={user.roles} />
                    </div>
                    <Button asChild>
                        <Link href={`/users/${user.id}/edit`}>
                            <PencilLine className="size-4" />
                            Edit
                        </Link>
                    </Button>
                </div>

                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    {/* Profile */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Account</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <dl className="grid grid-cols-2 gap-4">
                                <Detail label="Email verified">
                                    {user.email_verified_at ? (
                                        <span className="inline-flex items-center gap-1">
                                            <Check className="size-4 text-emerald-600 dark:text-emerald-400" />
                                            {formatDate(user.email_verified_at)}
                                        </span>
                                    ) : (
                                        <span className="text-muted-foreground">
                                            Not verified
                                        </span>
                                    )}
                                </Detail>
                                <Detail label="Two-factor">
                                    {user.two_factor_enabled ? (
                                        <span className="inline-flex items-center gap-1">
                                            <ShieldCheck className="size-4 text-emerald-600 dark:text-emerald-400" />
                                            Enabled
                                        </span>
                                    ) : (
                                        <span className="text-muted-foreground">
                                            Off
                                        </span>
                                    )}
                                </Detail>
                                <Detail label="Joined">
                                    {formatDateTime(user.created_at)}
                                </Detail>
                                <Detail label="Last updated">
                                    {formatDateTime(user.updated_at)}
                                </Detail>
                            </dl>
                        </CardContent>
                    </Card>

                    {/* Access */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Access</CardTitle>
                            <CardDescription>
                                What this account can do, through its roles and
                                any directly granted permissions.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="flex flex-col gap-3">
                            {effective_permissions === 'all' ? (
                                <p className="text-sm">
                                    All permissions{' '}
                                    <span className="text-muted-foreground">
                                        (admin)
                                    </span>
                                </p>
                            ) : effective_permissions.length === 0 ? (
                                <p className="text-sm text-muted-foreground">
                                    No permissions.
                                </p>
                            ) : (
                                <div className="flex flex-wrap gap-1">
                                    {effective_permissions.map((p) => (
                                        <Badge
                                            key={p}
                                            variant="outline"
                                            className="font-mono"
                                        >
                                            {p}
                                        </Badge>
                                    ))}
                                </div>
                            )}
                            <p className="text-xs text-muted-foreground">
                                {direct_permissions.length === 0
                                    ? 'No permissions are granted directly; everything comes from roles.'
                                    : `Granted directly (not via a role): ${direct_permissions.join(', ')}.`}
                            </p>
                        </CardContent>
                    </Card>
                </div>

                {/* Activity */}
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                    <StatCard
                        icon={Star}
                        label="Starred items"
                        value={stats.stars}
                    />
                    <StatCard
                        icon={Folder}
                        label="Folders"
                        value={stats.folders}
                    />
                    {CONTRIBUTION_STATUSES.map((status) => (
                        <Link
                            key={status}
                            href={`/contributions?status=${status}`}
                            className="rounded-xl transition-colors hover:bg-muted/50"
                        >
                            <Card className="h-full gap-2 bg-transparent py-4">
                                <CardContent className="px-4">
                                    <div className="text-xl font-semibold tabular-nums">
                                        {stats.contributions[status] ?? 0}
                                    </div>
                                    <div className="mt-1">
                                        <StatusBadge status={status} />
                                    </div>
                                </CardContent>
                            </Card>
                        </Link>
                    ))}
                </div>

                {/* Recent contributions */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">
                            Recent contributions
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {recent_contributions.length === 0 ? (
                            <p className="text-sm text-muted-foreground">
                                No contributions yet.
                            </p>
                        ) : (
                            <ul className="divide-y">
                                {recent_contributions.map((c) => (
                                    <li key={c.id}>
                                        <Link
                                            href={`/contributions/${c.id}`}
                                            className="-mx-2 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md px-2 py-2.5 hover:bg-muted/50"
                                        >
                                            <span className="min-w-0 flex-1 truncate text-sm font-medium">
                                                {c.target_label}
                                            </span>
                                            <span className="text-xs text-muted-foreground">
                                                {TARGET_TYPE_LABELS[
                                                    c.target_type
                                                ] ?? c.target_type}{' '}
                                                · {fieldLabel(c.field)}
                                            </span>
                                            <StatusBadge status={c.status} />
                                            <span className="text-xs whitespace-nowrap text-muted-foreground">
                                                {formatDateTime(c.created_at)}
                                            </span>
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </CardContent>
                </Card>
            </div>
        </AppLayout>
    );
}

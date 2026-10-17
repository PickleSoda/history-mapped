import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

/** `history_moderator` → "History moderator". */
export function roleLabel(role: string): string {
    const words = role.replace(/[_.]/g, ' ').trim();

    return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Sort roles so `admin` leads, then alphabetical. */
export function sortRoles(roles: string[]): string[] {
    return [...roles].sort((a, b) =>
        a === 'admin' ? -1 : b === 'admin' ? 1 : a.localeCompare(b),
    );
}

export function RoleBadge({ role }: { role: string }) {
    if (role === 'admin') {
        return (
            <Badge className="bg-violet-600 text-white dark:bg-violet-500">
                {roleLabel(role)}
            </Badge>
        );
    }

    return (
        <Badge
            variant={role === 'user' ? 'outline' : 'secondary'}
            className={cn(role === 'user' && 'text-muted-foreground')}
        >
            {roleLabel(role)}
        </Badge>
    );
}

export function RoleBadges({ roles }: { roles: string[] }) {
    if (roles.length === 0) {
        return <span className="text-xs text-muted-foreground">No role</span>;
    }

    return (
        <div className="flex flex-wrap gap-1">
            {sortRoles(roles).map((role) => (
                <RoleBadge key={role} role={role} />
            ))}
        </div>
    );
}

export function formatDate(value: string | null): string {
    if (!value) {
        return '—';
    }

    const date = new Date(value);

    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

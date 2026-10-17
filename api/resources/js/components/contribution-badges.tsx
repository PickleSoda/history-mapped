import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type {
    ContributionStatus,
    ContributionTargetType,
    DiffStats,
} from '@/types';

export const CONTRIBUTION_STATUSES: ContributionStatus[] = [
    'pending',
    'approved',
    'rejected',
    'withdrawn',
];

export const TARGET_TYPE_LABELS: Record<ContributionTargetType, string> = {
    entity: 'Entity',
    relationship: 'Relationship',
    chronicle: 'Chronicle',
    chronicle_entry: 'Chronicle step',
};

const FIELD_LABELS: Record<string, string> = {
    name: 'Name',
    summary: 'Summary',
    significance: 'Significance',
    description: 'Description',
    title: 'Title',
    narrative_text: 'Narrative',
    aliases: 'Aliases',
};

const statusColors: Record<ContributionStatus, string> = {
    pending:
        'bg-amber-100 text-amber-900 dark:bg-amber-900/60 dark:text-amber-100',
    approved:
        'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    rejected: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    withdrawn: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
};

export function fieldLabel(field: string): string {
    return FIELD_LABELS[field] ?? field.replace(/_/g, ' ');
}

export function formatDateTime(value: string | null): string {
    if (!value) {
        return '—';
    }

    const date = new Date(value);

    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function StatusBadge({ status }: { status: ContributionStatus }) {
    return (
        <Badge className={cn('capitalize', statusColors[status])}>
            {status}
        </Badge>
    );
}

export function TargetBadges({
    type,
    field,
}: {
    type: ContributionTargetType;
    field: string;
}) {
    return (
        <>
            <Badge variant="outline">{TARGET_TYPE_LABELS[type] ?? type}</Badge>
            <Badge variant="secondary">{fieldLabel(field)}</Badge>
        </>
    );
}

export function StaleBadge() {
    return (
        <Badge
            variant="outline"
            className="border-amber-400 text-amber-700 dark:border-amber-500/60 dark:text-amber-300"
            title="The text has changed since this was submitted"
        >
            Stale
        </Badge>
    );
}

export function DiffStatsText({ stats }: { stats: DiffStats }) {
    return (
        <span className="font-mono text-xs whitespace-nowrap">
            <span className="text-emerald-700 dark:text-emerald-400">
                +{stats.added}
            </span>{' '}
            <span className="text-red-700 dark:text-red-400">
                −{stats.removed}
            </span>
        </span>
    );
}

import { Badge } from '@/components/ui/badge';

export type TimelineItem = {
    id: string;
    kind: 'timeline';
    startYear: number | null;
    endYear: number | null;
    title: string;
    subtitle?: string;
    badgeLabel?: string;
    relatedEntityId?: string | null;
};

export type SelectedTimelineItem = { kind: 'timeline'; id: string } | null;

export type EntityHistoryTimelineProps = {
    items: TimelineItem[];
    loading: boolean;
    loadError: string | null;
    selectedItem: SelectedTimelineItem;
    onSelect: (item: SelectedTimelineItem) => void;
    onHover?: (item: SelectedTimelineItem) => void;
};

export default function EntityHistoryTimeline({
    items,
    loading,
    loadError,
    selectedItem,
    onSelect,
    onHover,
}: EntityHistoryTimelineProps) {
    return (
        <div className="h-full space-y-2 overflow-y-auto p-3">
            {loading && (
                <p className="text-sm text-muted-foreground">
                    Loading timeline…
                </p>
            )}
            {!loading && loadError && (
                <p className="text-sm text-destructive">{loadError}</p>
            )}
            {!loading && !loadError && items.length === 0 && (
                <p className="text-sm text-muted-foreground">
                    No relationships with timeline data.
                </p>
            )}

            {!loading &&
                !loadError &&
                items.map((item) => {
                    const selected =
                        selectedItem?.kind === item.kind &&
                        item.id === selectedItem.id;

                    // Ref for scrolling/focusing
                    const ref = (el: HTMLDivElement | null) => {
                        if (el && selected) {
                            // Scroll into view and focus
                            el.scrollIntoView({
                                block: 'nearest',
                                behavior: 'smooth',
                            });
                            el.querySelector('button')?.focus();
                        }
                    };

                    return (
                        <div
                            key={item.id}
                            className="group relative"
                            ref={ref}
                            onMouseEnter={() => {
                                const hovered = item.id
                                    ? {
                                          kind: 'timeline' as const,
                                          id: item.id,
                                      }
                                    : null;

                                onHover?.(hovered);
                            }}
                            onMouseLeave={() => {
                                onHover?.(null);
                            }}
                        >
                            <button
                                type="button"
                                onClick={() => {
                                    const nextSelection = item.id
                                        ? {
                                              kind: 'timeline' as const,
                                              id: item.id,
                                          }
                                        : null;

                                    if (!nextSelection) {
                                        return;
                                    }

                                    onSelect(
                                        selected && selectedItem
                                            ? null
                                            : nextSelection,
                                    );
                                }}
                                className={[
                                    'w-full rounded-md border px-3 py-2 text-left',
                                    selected
                                        ? 'border-amber-500 bg-amber-500/5'
                                        : 'hover:bg-muted/50',
                                ].join(' ')}
                            >
                                <div className="mb-1 flex items-center justify-between gap-2">
                                    <Badge variant="outline">
                                        {item.badgeLabel ?? item.kind}
                                    </Badge>
                                    <span className="text-xs text-muted-foreground tabular-nums">
                                        {formatYearRange(
                                            item.startYear,
                                            item.endYear,
                                        )}
                                    </span>
                                </div>
                                <p className="text-sm leading-tight font-medium">
                                    {item.title}
                                </p>
                                {item.subtitle && (
                                    <p className="mt-1 text-xs leading-snug text-muted-foreground">
                                        {item.subtitle}
                                    </p>
                                )}
                            </button>
                            {item.relatedEntityId && (
                                <a
                                    href={`/entities/${item.relatedEntityId}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="absolute top-2 right-2 text-xs text-blue-600 underline opacity-0 transition-opacity group-hover:opacity-100"
                                    title="Open related entity in new tab"
                                    onClick={(e) => e.stopPropagation()}
                                >
                                    ↗
                                </a>
                            )}
                        </div>
                    );
                })}
        </div>
    );
}

function formatYear(year: number | null): string {
    if (year == null) {
        return 'Unknown';
    }

    return year < 0 ? `${Math.abs(year)} BCE` : `${year} CE`;
}

function formatYearRange(start: number | null, end: number | null): string {
    if (start == null && end == null) {
        return 'Undated';
    }

    if (start != null && end != null) {
        return `${formatYear(start)} – ${formatYear(end)}`;
    }

    if (start != null) {
        return `From ${formatYear(start)}`;
    }

    return `Until ${formatYear(end)}`;
}

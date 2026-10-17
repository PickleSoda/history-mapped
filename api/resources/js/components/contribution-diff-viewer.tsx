import { Columns2, Rows3 } from 'lucide-react';
import { useState } from 'react';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { cn } from '@/lib/utils';
import type { Diff, DiffOp, DiffStats } from '@/types';

export type DiffMode = 'inline' | 'split';

const WORD = /[\p{L}\p{N}\p{M}_]+/gu;

/** Changed word counts, matching the server's `stats` (word tokens only). */
export function diffStats(diff: Diff): DiffStats {
    let added = 0;
    let removed = 0;

    for (const [op, text] of diff) {
        const words = text.match(WORD)?.length ?? 0;

        if (op === '+') {
            added += words;
        } else if (op === '-') {
            removed += words;
        }
    }

    return { added, removed };
}

/** Rebuild both sides of a diff: `=`/`-` is the base, `=`/`+` the proposal. */
export function diffSides(diff: Diff): { base: string; proposed: string } {
    let base = '';
    let proposed = '';

    for (const [op, text] of diff) {
        if (op !== '+') {
            base += text;
        }

        if (op !== '-') {
            proposed += text;
        }
    }

    return { base, proposed };
}

const REMOVED =
    'rounded-sm bg-red-100 text-red-900 line-through decoration-red-500/70 dark:bg-red-950/70 dark:text-red-200 dark:decoration-red-400/70';
const ADDED =
    'rounded-sm bg-emerald-100 text-emerald-900 no-underline dark:bg-emerald-950/70 dark:text-emerald-200';

/** A changed run that is only whitespace would be invisible — mark it. */
function ChangedText({ text }: { text: string }) {
    if (!/^\s+$/.test(text)) {
        return <>{text}</>;
    }

    return (
        <>
            <span aria-hidden className="px-0.5 text-[0.85em] opacity-70">
                {text.includes('\n') ? '↵' : '·'}
            </span>
            {text}
        </>
    );
}

function DiffSegment({ op, text }: { op: DiffOp[0]; text: string }) {
    if (op === '-') {
        return (
            <del className={REMOVED}>
                <span className="sr-only">[removed: </span>
                <ChangedText text={text} />
                <span className="sr-only">]</span>
            </del>
        );
    }

    if (op === '+') {
        return (
            <ins className={ADDED}>
                <span className="sr-only">[added: </span>
                <ChangedText text={text} />
                <span className="sr-only">]</span>
            </ins>
        );
    }

    return <span>{text}</span>;
}

function DiffText({
    diff,
    show,
    label,
    className,
}: {
    diff: Diff;
    /** Which ops to render: both (inline), or one side of a split view. */
    show: 'both' | 'base' | 'proposed';
    label: string;
    className?: string;
}) {
    const visible = diff.filter(
        ([op]) =>
            !(show === 'base' && op === '+') &&
            !(show === 'proposed' && op === '-'),
    );
    // A suggestion for a missing field has no base (and clearing a field no
    // proposal): say so instead of rendering an empty box.
    const empty = visible.every(([, text]) => text === '');

    return (
        <div
            role="region"
            aria-label={label}
            className={cn(
                'rounded-md border bg-muted/30 p-3 text-sm leading-relaxed break-words whitespace-pre-wrap',
                className,
            )}
        >
            {empty ? (
                <span className="text-muted-foreground italic">(empty)</span>
            ) : (
                visible.map(([op, text], i) => (
                    <DiffSegment key={i} op={op} text={text} />
                ))
            )}
        </div>
    );
}

/**
 * Renders a stored contribution diff (`[op, text]` tuples) either inline — one
 * flow with removals struck through and additions highlighted — or side by
 * side, base on the left and proposal on the right. Pure: ops in, markup out.
 */
export function ContributionDiffViewer({
    diff,
    stats,
    baseLabel = 'Original text',
    proposedLabel = 'Proposed text',
    defaultMode = 'inline',
}: {
    diff: Diff;
    stats?: DiffStats;
    baseLabel?: string;
    proposedLabel?: string;
    defaultMode?: DiffMode;
}) {
    const [mode, setMode] = useState<DiffMode>(defaultMode);
    const { added, removed } = stats ?? diffStats(diff);
    const changed = diff.some(([op]) => op !== '=');

    return (
        <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <ToggleGroup
                    type="single"
                    variant="outline"
                    size="sm"
                    value={mode}
                    onValueChange={(v) => v && setMode(v as DiffMode)}
                    aria-label="Diff layout"
                >
                    <ToggleGroupItem value="inline" className="gap-1.5 px-2.5">
                        <Rows3 className="size-3.5" />
                        Inline
                    </ToggleGroupItem>
                    <ToggleGroupItem value="split" className="gap-1.5 px-2.5">
                        <Columns2 className="size-3.5" />
                        Side by side
                    </ToggleGroupItem>
                </ToggleGroup>

                <span className="flex items-center gap-1.5">
                    <span aria-hidden className={cn(REMOVED, 'px-1')}>
                        abc
                    </span>
                    Removed
                </span>
                <span className="flex items-center gap-1.5">
                    <span aria-hidden className={cn(ADDED, 'px-1')}>
                        abc
                    </span>
                    Added
                </span>

                <span className="ml-auto font-mono">
                    <span className="text-emerald-700 dark:text-emerald-400">
                        +{added}
                    </span>{' '}
                    /{' '}
                    <span className="text-red-700 dark:text-red-400">
                        −{removed}
                    </span>{' '}
                    words
                </span>
            </div>

            {!changed ? (
                <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                    No changes.
                </p>
            ) : mode === 'inline' ? (
                <DiffText
                    diff={diff}
                    show="both"
                    label={`Changes from ${baseLabel.toLowerCase()} to ${proposedLabel.toLowerCase()}`}
                />
            ) : (
                <div className="grid gap-3 md:grid-cols-2">
                    <div className="flex min-w-0 flex-col gap-1.5">
                        <span className="text-xs font-medium text-muted-foreground">
                            {baseLabel}
                        </span>
                        <DiffText diff={diff} show="base" label={baseLabel} />
                    </div>
                    <div className="flex min-w-0 flex-col gap-1.5">
                        <span className="text-xs font-medium text-muted-foreground">
                            {proposedLabel}
                        </span>
                        <DiffText
                            diff={diff}
                            show="proposed"
                            label={proposedLabel}
                        />
                    </div>
                </div>
            )}
        </div>
    );
}

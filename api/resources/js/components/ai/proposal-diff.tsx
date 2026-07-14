import { useState } from 'react';
import { normalizeHumanDiff } from '@/lib/human-diff';

/**
 * Expandable before→after diff for a single proposal part. Renders nothing when
 * the part's human_diff has no structured rows (summary-only tools), so the card
 * gracefully shows just its summary line.
 */
export function ProposalDiff({
    tool,
    humanDiff,
}: {
    tool?: string;
    humanDiff: unknown;
}) {
    const [open, setOpen] = useState(false);
    const rows = normalizeHumanDiff(tool ?? '', humanDiff);

    if (rows.length === 0) {
        return null;
    }

    return (
        <div className="mt-1">
            <button
                type="button"
                aria-expanded={open}
                onClick={() => setOpen((o) => !o)}
                className="text-xs text-amber-700 hover:underline dark:text-amber-300"
            >
                {open ? '▾ Hide changes' : '▸ Show changes'}
            </button>
            {open && (
                <dl className="mt-1 space-y-1">
                    {rows.map((row, idx) => (
                        <div key={idx} className="text-xs">
                            <dt className="text-muted-foreground">
                                {row.label}
                            </dt>
                            <dd className="font-mono break-words whitespace-pre-wrap">
                                {row.kind === 'create' ? (
                                    <span className="text-green-600 dark:text-green-400">
                                        + {row.to}
                                    </span>
                                ) : row.kind === 'merge' ? (
                                    <span>
                                        {row.from} → {row.to}
                                    </span>
                                ) : (
                                    <>
                                        <span className="block text-red-600 line-through dark:text-red-400">
                                            − {row.from}
                                        </span>
                                        <span className="block text-green-600 dark:text-green-400">
                                            + {row.to}
                                        </span>
                                    </>
                                )}
                            </dd>
                        </div>
                    ))}
                </dl>
            )}
        </div>
    );
}

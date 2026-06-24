import { router } from '@inertiajs/react';
import { CheckCircle, XCircle } from 'lucide-react';
import { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export type ProposalPart = {
    key: string;
    human_diff: { summary: string };
};

export type Proposal = {
    proposal_id: string;
    parts: ProposalPart[];
    note?: string;
};

type PartStatus = 'applied' | 'discarded' | 'error' | 'loading';

/**
 * Renders a proposal card for an AI staging result.
 *
 * The AI agent returns a JSON payload `{proposal_id, parts:[{key, human_diff:{summary}}], note}`
 * when a staging tool is called. This component lets the user apply or discard
 * each change part individually.
 *
 * On apply: POSTs to `/ai/proposals/{proposal_id}/parts/{key}/apply`, then
 * calls `router.reload()` so the page's Inertia props refresh.
 * On discard: POSTs to `/ai/proposals/{proposal_id}/parts/{key}/discard`.
 */
export function ProposalCard({ proposal }: { proposal: Proposal }) {
    const [partStatus, setPartStatus] = useState<Record<string, PartStatus>>(
        {},
    );
    const csrfRef = useRef<string>('');

    // Lazily read the CSRF token the first time we need it (same pattern as
    // relationship-panel and entity-geo-ref-editor).
    function getCsrf(): string {
        if (!csrfRef.current) {
            const meta = document.querySelector<HTMLMetaElement>(
                'meta[name="csrf-token"]',
            );
            csrfRef.current = meta?.content ?? '';
        }

        return csrfRef.current;
    }

    async function act(key: string, verb: 'apply' | 'discard') {
        // Guard against concurrent or double calls (e.g. double-click).
        const currentStatus = partStatus[key];

        if (
            currentStatus === 'loading' ||
            currentStatus === 'applied' ||
            currentStatus === 'discarded'
        ) {
            return;
        }

        setPartStatus((s) => ({ ...s, [key]: 'loading' }));

        try {
            const res = await fetch(
                `/ai/proposals/${proposal.proposal_id}/parts/${encodeURIComponent(key)}/${verb}`,
                {
                    method: 'POST',
                    headers: {
                        Accept: 'application/json',
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-TOKEN': getCsrf(),
                    },
                },
            );

            if (!res.ok) {
                setPartStatus((s) => ({ ...s, [key]: 'error' }));

                return;
            }

            const json = (await res.json()) as { status: string };
            const status =
                json.status === 'applied'
                    ? 'applied'
                    : json.status === 'discarded'
                      ? 'discarded'
                      : 'error';
            setPartStatus((s) => ({ ...s, [key]: status }));

            if (status === 'applied') {
                // Refresh Inertia page props so the entity data reflects the
                // applied change without a full navigation.
                router.reload();
            }
        } catch {
            setPartStatus((s) => ({ ...s, [key]: 'error' }));
        }
    }

    return (
        <Card className="my-2 border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30">
            <CardHeader className="pt-3 pb-2">
                <CardTitle className="text-sm font-medium text-amber-900 dark:text-amber-200">
                    Proposed changes
                    {proposal.note ? (
                        <span className="ml-2 font-normal text-amber-700 dark:text-amber-300">
                            — {proposal.note}
                        </span>
                    ) : null}
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 pb-3">
                {proposal.parts.map((part) => {
                    const status = partStatus[part.key];

                    return (
                        <div
                            key={part.key}
                            className="flex items-center justify-between gap-2"
                        >
                            <span className="min-w-0 flex-1 text-sm text-foreground">
                                {part.human_diff.summary}
                            </span>
                            {status === 'loading' ? (
                                <span className="text-xs text-muted-foreground">
                                    Saving…
                                </span>
                            ) : status === 'applied' ? (
                                <span className="flex items-center gap-1 text-xs text-green-600">
                                    <CheckCircle className="size-3.5" />
                                    Applied
                                </span>
                            ) : status === 'discarded' ? (
                                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <XCircle className="size-3.5" />
                                    Discarded
                                </span>
                            ) : status === 'error' ? (
                                <span className="text-xs text-red-600">
                                    Error — try again
                                </span>
                            ) : (
                                <span className="flex shrink-0 gap-1">
                                    <Button
                                        size="sm"
                                        variant="default"
                                        className="h-7 px-2 text-xs"
                                        onClick={() =>
                                            void act(part.key, 'apply')
                                        }
                                    >
                                        Apply
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-7 px-2 text-xs"
                                        onClick={() =>
                                            void act(part.key, 'discard')
                                        }
                                    >
                                        Discard
                                    </Button>
                                </span>
                            )}
                        </div>
                    );
                })}
            </CardContent>
        </Card>
    );
}

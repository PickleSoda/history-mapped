import { History, RotateCcw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from '@/components/ui/sheet';
import {
    index as revisionsIndex,
    restore as revisionsRestore,
    show as revisionsShow,
} from '@/routes/map-stories/revisions';
import { storyRequest } from './request';
import type { SaveResponse } from './request';

type Revision = {
    id: number;
    source: string;
    user: string | null;
    note: string | null;
    created_at: string | null;
};

const when = (iso: string | null) =>
    iso ? new Date(iso).toLocaleString() : '—';

/**
 * The story's saved versions, newest first (the last 50): look at one, load it
 * into the editor as a draft, or restore it (saved at once as a new version).
 */
export function RevisionsSheet({
    slug,
    open,
    onOpenChange,
    canEdit,
    dirty,
    onLoad,
    onRestored,
}: {
    slug: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    canEdit: boolean;
    dirty: boolean;
    onLoad: (documentJson: string) => void;
    onRestored: (response: SaveResponse) => void;
}) {
    const [revisions, setRevisions] = useState<Revision[] | null>(null);
    const [picked, setPicked] = useState<{ id: number; json: string } | null>(
        null,
    );
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!open) {
            return;
        }

        storyRequest<{ data: Revision[] }>(
            revisionsIndex.url(slug),
            'GET',
        ).then((r) => setRevisions(r.ok ? r.data.data : []));
    }, [open, slug]);

    // Closing clears what was looked at, so the next opening starts fresh.
    const change = (next: boolean) => {
        if (!next) {
            setPicked(null);
            setError(null);
            setRevisions(null);
        }

        onOpenChange(next);
    };

    const view = async (id: number) => {
        const r = await storyRequest<{ data: { document_json: string } }>(
            revisionsShow.url({ slug, revision: id }),
            'GET',
        );

        if (r.ok) {
            setPicked({ id, json: r.data.data.document_json });
        }
    };

    const restore = async (id: number) => {
        if (
            dirty &&
            !window.confirm('Restoring discards your unsaved edits. Go on?')
        ) {
            return;
        }

        setBusy(true);
        setError(null);
        const r = await storyRequest<SaveResponse>(
            revisionsRestore.url({ slug, revision: id }),
            'POST',
            {},
        );
        setBusy(false);

        if (!r.ok) {
            setError(
                (
                    r.data?.errors ?? [
                        r.data?.message ?? `Failed (${r.status})`,
                    ]
                ).join(' · '),
            );

            return;
        }

        onRestored(r.data);
        change(false);
    };

    return (
        <Sheet open={open} onOpenChange={change}>
            <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
                <SheetHeader>
                    <SheetTitle className="flex items-center gap-2">
                        <History className="size-4" /> History
                    </SheetTitle>
                    <SheetDescription>
                        Every save, sync, AI edit and restore keeps a version
                        (the last 50).
                    </SheetDescription>
                </SheetHeader>
                <div className="space-y-2 px-4 pb-4">
                    {error && (
                        <p className="text-sm text-destructive">{error}</p>
                    )}
                    {revisions === null && (
                        <p className="text-sm text-muted-foreground">
                            Loading…
                        </p>
                    )}
                    {revisions?.length === 0 && (
                        <p className="text-sm text-muted-foreground">
                            No versions yet.
                        </p>
                    )}
                    {revisions?.map((r, i) => (
                        <div
                            key={r.id}
                            className={`rounded-md border p-2 text-sm ${picked?.id === r.id ? 'border-primary' : ''}`}
                        >
                            <div className="flex items-center gap-2">
                                <Badge variant="outline">{r.source}</Badge>
                                <span className="text-xs text-muted-foreground">
                                    {when(r.created_at)}
                                </span>
                                {r.user && (
                                    <span className="text-xs">{r.user}</span>
                                )}
                                {i === 0 && (
                                    <Badge variant="secondary">current</Badge>
                                )}
                                <span className="ml-auto flex gap-1">
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={() => view(r.id)}
                                    >
                                        View
                                    </Button>
                                    {canEdit && i > 0 && (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            disabled={busy}
                                            onClick={() => restore(r.id)}
                                        >
                                            <RotateCcw className="size-3.5" />{' '}
                                            Restore
                                        </Button>
                                    )}
                                </span>
                            </div>
                            {r.note && (
                                <p className="mt-1 text-xs text-muted-foreground">
                                    {r.note}
                                </p>
                            )}
                            {picked?.id === r.id && (
                                <div className="mt-2 space-y-1">
                                    <pre className="max-h-72 overflow-auto rounded bg-muted p-2 text-[11px] leading-snug">
                                        {JSON.stringify(
                                            JSON.parse(picked.json),
                                            null,
                                            2,
                                        )}
                                    </pre>
                                    <Button
                                        size="sm"
                                        variant="secondary"
                                        onClick={() => {
                                            onLoad(picked.json);
                                            change(false);
                                        }}
                                    >
                                        Load into the editor (unsaved)
                                    </Button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </SheetContent>
        </Sheet>
    );
}

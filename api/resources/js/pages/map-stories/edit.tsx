import { Head, Link, router } from '@inertiajs/react';
import {
    AlertTriangle,
    ExternalLink,
    History,
    Loader2,
    Save,
    Trash2,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { StoryEditorContext } from '@/components/map-story/editor-context';
import type {
    ChronicleEntry,
    StoryEditor,
} from '@/components/map-story/editor-context';
import { FeaturesTab } from '@/components/map-story/features-tab';
import { JsonTab } from '@/components/map-story/json-tab';
import { OverviewTab } from '@/components/map-story/overview-tab';
import { storyRequest } from '@/components/map-story/request';
import type { SaveResponse } from '@/components/map-story/request';
import { RevisionsSheet } from '@/components/map-story/revisions-sheet';
import { SidesTab } from '@/components/map-story/sides-tab';
import { StepsTab } from '@/components/map-story/steps-tab';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import AppLayout from '@/layouts/app-layout';
import { issueTarget, moveUnitTo } from '@/lib/map-story-doc';
import type {
    LinkedEntity,
    LngLat,
    StoryDoc,
    StorySummary,
    StoryVocabulary,
} from '@/lib/map-story-doc';
import { cn } from '@/lib/utils';
import {
    destroy,
    index as storiesIndex,
    update,
    validate,
} from '@/routes/map-stories';
import type { BreadcrumbItem } from '@/types';

type Props = {
    story: StorySummary;
    document_json: string;
    warnings: string[];
    entries: ChronicleEntry[];
    linked: Record<string, LinkedEntity>;
    vocabulary: StoryVocabulary;
    preview_url: string | null;
    can_edit: boolean;
};

type Tab = 'overview' | 'sides' | 'features' | 'steps' | 'json';

const TABS: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'sides', label: 'Sides & units' },
    { id: 'features', label: 'Features' },
    { id: 'steps', label: 'Steps' },
    { id: 'json', label: 'JSON' },
];

/** A stable comparison form of a document (key order kept, as saved). */
const canon = (doc: unknown) => JSON.stringify(doc);

export default function MapStoryEdit({
    story: initialStory,
    document_json,
    warnings: initialWarnings,
    entries,
    linked: initialLinked,
    vocabulary,
    preview_url,
    can_edit,
}: Props) {
    const [story, setStory] = useState(initialStory);
    const [baseline, setBaseline] = useState(document_json);
    const [doc, setDoc] = useState<StoryDoc>(() => JSON.parse(document_json));
    const [errors, setErrors] = useState<string[]>([]);
    const [warnings, setWarnings] = useState<string[]>(initialWarnings);
    const [linked, setLinked] = useState(initialLinked);
    const [tab, setTab] = useState<Tab>('overview');
    const [step, setStepState] = useState(0);
    const [jsonError, setJsonError] = useState<string | null>(null);
    const [note, setNote] = useState('');
    const [saving, setSaving] = useState(false);
    const [checking, setChecking] = useState(false);
    const [flash, setFlash] = useState<{
        kind: 'ok' | 'error';
        text: string;
    } | null>(null);
    const [historyOpen, setHistoryOpen] = useState(false);
    const [showWarnings, setShowWarnings] = useState(false);
    const [picking, setPicking] = useState<'point' | 'path' | null>(null);
    const [previewReady, setPreviewReady] = useState(false);
    const [previewIssues, setPreviewIssues] = useState<string[]>([]);
    const [serverChanged, setServerChanged] = useState(false);

    const baselineDoc = useMemo(() => canon(JSON.parse(baseline)), [baseline]);
    const dirty = canon(doc) !== baselineDoc;

    // ── The preview iframe ──────────────────────────────────────────────────
    const frame = useRef<HTMLIFrameElement>(null);
    const previewSrc = useMemo(() => {
        if (!preview_url) {
            return null;
        }

        const url = new URL(preview_url);
        url.searchParams.set('story', initialStory.slug);
        url.searchParams.set('sstep', '0');
        url.searchParams.set('preview', '1');

        return url.toString();
    }, [preview_url, initialStory.slug]);
    const previewOrigin = previewSrc ? new URL(previewSrc).origin : null;
    const send = useCallback(
        (message: Record<string, unknown>) => {
            if (previewOrigin && frame.current?.contentWindow) {
                frame.current.contentWindow.postMessage(message, previewOrigin);
            }
        },
        [previewOrigin],
    );

    const docRef = useRef(doc);
    const stepRef = useRef(step);
    const pickDone = useRef<((value: LngLat | LngLat[]) => void) | null>(null);
    const cameraDone = useRef<
        ((c: { center: LngLat; zoom: number; bearing: number }) => void) | null
    >(null);
    useEffect(() => {
        docRef.current = doc;
        stepRef.current = step;
    });

    const setStep = useCallback(
        (index: number) => {
            setStepState(index);
            send({ type: 'map-story:step', index });
        },
        [send],
    );

    // Messages from the preview.
    useEffect(() => {
        const onMessage = (e: MessageEvent) => {
            if (
                e.origin !== previewOrigin ||
                e.source !== frame.current?.contentWindow
            ) {
                return;
            }

            const m = e.data as Record<string, any>;

            switch (m?.type) {
                case 'map-story:ready':
                    setPreviewReady(true);
                    send({
                        type: 'map-story:document',
                        document: docRef.current,
                    });
                    send({ type: 'map-story:step', index: stepRef.current });
                    break;
                case 'map-story:step-changed':
                    if (typeof m.index === 'number') {
                        setStepState(m.index);
                    }

                    break;
                case 'map-story:picked':
                    setPicking(null);
                    pickDone.current?.(m.at ?? m.path);
                    pickDone.current = null;
                    break;
                case 'map-story:pick-cancelled':
                    setPicking(null);
                    pickDone.current = null;
                    break;
                case 'map-story:unit-dragged':
                    if (
                        typeof m.unit === 'string' &&
                        Array.isArray(m.at) &&
                        typeof m.step === 'number' &&
                        can_edit
                    ) {
                        setDoc(
                            moveUnitTo(
                                docRef.current,
                                m.step,
                                m.unit,
                                m.at as LngLat,
                            ),
                        );
                    }

                    break;
                case 'map-story:camera':
                    cameraDone.current?.({
                        center: m.center,
                        zoom: m.zoom,
                        bearing: m.bearing,
                    });
                    cameraDone.current = null;
                    break;
                case 'map-story:document-rejected':
                    setPreviewIssues(Array.isArray(m.issues) ? m.issues : []);
                    break;
            }
        };
        window.addEventListener('message', onMessage);

        return () => window.removeEventListener('message', onMessage);
    }, [previewOrigin, send, can_edit]);

    // The draft goes to the preview as you edit (debounced).
    useEffect(() => {
        if (!previewReady) {
            return;
        }

        const t = setTimeout(() => {
            setPreviewIssues([]);
            send({ type: 'map-story:document', document: doc });
        }, 250);

        return () => clearTimeout(t);
    }, [doc, previewReady, send]);

    // …and to the server for errors and warnings (debounced dry run).
    const firstCheck = useRef(true);
    useEffect(() => {
        if (firstCheck.current) {
            firstCheck.current = false;

            return;
        }

        if (jsonError) {
            return;
        }

        const controller = new AbortController();
        const t = setTimeout(async () => {
            setChecking(true);

            try {
                const r = await storyRequest<SaveResponse>(
                    validate.url(initialStory.slug),
                    'POST',
                    { document: JSON.stringify(doc) },
                    controller.signal,
                );

                if (r.ok) {
                    setErrors(r.data.errors ?? []);
                    setWarnings(r.data.warnings ?? []);
                }
            } catch {
                // aborted or offline: the next edit tries again
            } finally {
                setChecking(false);
            }
        }, 700);

        return () => {
            clearTimeout(t);
            controller.abort();
        };
    }, [doc, jsonError, initialStory.slug]);

    // An approved AI edit reloads the page props: take the new document unless there are unsaved edits.
    const lastProp = useRef(document_json);
    useEffect(() => {
        if (document_json === lastProp.current) {
            return;
        }

        lastProp.current = document_json;

        if (dirty) {
            setServerChanged(true);
        } else {
            setBaseline(document_json);
            setDoc(JSON.parse(document_json));
            setStory(initialStory);
            setLinked(initialLinked);
            setWarnings(initialWarnings);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [document_json]);

    // Leaving with unsaved edits asks first.
    useEffect(() => {
        if (!dirty) {
            return;
        }

        const onBeforeUnload = (e: BeforeUnloadEvent) => e.preventDefault();
        window.addEventListener('beforeunload', onBeforeUnload);
        const off = router.on('before', (e) => {
            const visit = e.detail.visit;

            const reload = visit.url.pathname === window.location.pathname;

            if (
                visit.method === 'get' &&
                !reload &&
                !window.confirm('Leave with unsaved changes?')
            ) {
                e.preventDefault();
            }
        });

        return () => {
            window.removeEventListener('beforeunload', onBeforeUnload);
            off();
        };
    }, [dirty]);

    const edit = useCallback((fn: (draft: StoryDoc) => void) => {
        setDoc((current) => {
            const draft = JSON.parse(JSON.stringify(current));
            fn(draft);

            return draft;
        });
    }, []);

    const pick = useCallback(
        (mode: 'point' | 'path', done: (value: LngLat | LngLat[]) => void) => {
            if (!previewReady) {
                setFlash({
                    kind: 'error',
                    text: 'The preview is not ready: wait for the map to load (or set FRONTEND_URL).',
                });

                return;
            }

            pickDone.current = done;
            setPicking(mode);
            send({ type: 'map-story:pick', mode });
        },
        [previewReady, send],
    );

    const requestCamera = useCallback(
        (
            done: (c: {
                center: LngLat;
                zoom: number;
                bearing: number;
            }) => void,
        ) => {
            cameraDone.current = done;
            send({ type: 'map-story:get-camera' });
        },
        [send],
    );

    const applySaved = (data: SaveResponse) => {
        if (data.story) {
            setStory(data.story);
        }

        if (data.document_json) {
            setBaseline(data.document_json);
            setDoc(JSON.parse(data.document_json));
        }

        setErrors([]);
        setWarnings(data.warnings ?? []);
        setServerChanged(false);
    };

    const save = async () => {
        setSaving(true);
        setFlash(null);
        const r = await storyRequest<SaveResponse>(
            update.url(initialStory.slug),
            'PUT',
            { document: JSON.stringify(doc), note: note || null },
        );
        setSaving(false);

        if (!r.ok) {
            const errs = r.data?.errors ?? [
                r.data?.message ?? `Save failed (${r.status})`,
            ];
            setErrors(
                Array.isArray(errs)
                    ? errs
                    : Object.values(errs).flat().map(String),
            );
            setFlash({
                kind: 'error',
                text: `Not saved: ${Array.isArray(errs) ? errs.length : 1} error(s) — see the marked tabs.`,
            });

            return;
        }

        applySaved(r.data);
        setNote('');
        setFlash({
            kind: 'ok',
            text: r.data.warnings.length
                ? `Saved, with ${r.data.warnings.length} warning(s).`
                : 'Saved.',
        });
    };

    const remove = () => {
        const file = story.source_path
            ? `\n\nIts file (${story.source_path}) will re-create it on the next map-stories:sync unless the file is deleted too.`
            : '';

        if (window.confirm(`Delete “${story.title}” and its history?${file}`)) {
            router.delete(destroy.url(initialStory.slug));
        }
    };

    const errorsByTab = useMemo(() => {
        const counts: Partial<Record<Tab, number>> = {};

        for (const m of errors) {
            const t = issueTarget(m).tab;
            counts[t] = (counts[t] ?? 0) + 1;
        }

        return counts;
    }, [errors]);

    const context: StoryEditor = {
        doc,
        edit,
        replace: setDoc,
        vocab: vocabulary,
        errors,
        warnings,
        linked,
        addLinked: (qid: string, entity: LinkedEntity) =>
            setLinked((l) => ({ ...l, [qid]: entity })),
        entries,
        step,
        setStep,
        pick,
        requestCamera,
    };

    const breadcrumbs: BreadcrumbItem[] = [
        { title: 'Dashboard', href: '/dashboard' },
        { title: 'Map stories', href: storiesIndex.url() },
        { title: story.title, href: '#' },
    ];

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={`Edit ${story.title}`} />
            <StoryEditorContext value={context}>
                <div className="flex h-[calc(100vh-4rem)] min-h-0 flex-col">
                    {/* Toolbar */}
                    <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2">
                        <div className="min-w-0">
                            <h1 className="truncate text-lg font-semibold">
                                {story.title}
                            </h1>
                            <p className="text-xs text-muted-foreground">
                                {story.kind.replace(/_/g, ' ')} · {story.slug}
                                {story.entity && (
                                    <>
                                        {' · '}
                                        <Link
                                            href={`/entities/${story.entity.id}/edit`}
                                            className="underline"
                                        >
                                            {story.entity.name}
                                        </Link>
                                    </>
                                )}
                                {story.chronicle && (
                                    <> · chronicle “{story.chronicle.title}”</>
                                )}
                                {story.edited
                                    ? ` · edited here${story.edited_by ? ` by ${story.edited_by}` : ''} — not yet exported to its file`
                                    : story.source_path
                                      ? ' · matches its file'
                                      : ''}
                            </p>
                        </div>
                        <div className="ml-auto flex items-center gap-2">
                            {checking && (
                                <Loader2 className="size-4 animate-spin text-muted-foreground" />
                            )}
                            {dirty && <Badge variant="outline">unsaved</Badge>}
                            {errors.length > 0 && (
                                <Badge variant="destructive">
                                    {errors.length} error(s)
                                </Badge>
                            )}
                            {warnings.length > 0 && (
                                <button
                                    type="button"
                                    onClick={() => setShowWarnings((s) => !s)}
                                >
                                    <Badge className="bg-amber-100 text-amber-900 dark:bg-amber-900 dark:text-amber-100">
                                        {warnings.length} warning(s)
                                    </Badge>
                                </button>
                            )}
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setHistoryOpen(true)}
                            >
                                <History className="size-4" /> History
                            </Button>
                            {can_edit && (
                                <>
                                    <input
                                        className="h-8 w-48 rounded-md border bg-background px-2 text-sm"
                                        placeholder="What changed (optional)"
                                        value={note}
                                        maxLength={500}
                                        onChange={(e) =>
                                            setNote(e.target.value)
                                        }
                                    />
                                    <Button
                                        size="sm"
                                        disabled={
                                            !dirty ||
                                            saving ||
                                            jsonError !== null
                                        }
                                        onClick={save}
                                    >
                                        {saving ? (
                                            <Loader2 className="size-4 animate-spin" />
                                        ) : (
                                            <Save className="size-4" />
                                        )}{' '}
                                        Save
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        title="Delete this story"
                                        onClick={remove}
                                    >
                                        <Trash2 className="size-4 text-destructive" />
                                    </Button>
                                </>
                            )}
                        </div>
                        {flash && (
                            <p
                                className={cn(
                                    'w-full text-sm',
                                    flash.kind === 'ok'
                                        ? 'text-emerald-700'
                                        : 'text-destructive',
                                )}
                            >
                                {flash.text}
                            </p>
                        )}
                        {serverChanged && (
                            <p className="flex w-full items-center gap-2 text-sm text-amber-700">
                                <AlertTriangle className="size-4" /> The stored
                                story changed (an approved AI edit?) while you
                                have unsaved edits.
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() =>
                                        applySaved({
                                            document_json,
                                            story: initialStory,
                                            errors: [],
                                            warnings: initialWarnings,
                                        })
                                    }
                                >
                                    Take the stored version
                                </Button>
                            </p>
                        )}
                        {showWarnings && warnings.length > 0 && (
                            <ul className="max-h-40 w-full list-disc overflow-y-auto pl-5 text-xs text-amber-700">
                                {warnings.map((w) => (
                                    <li key={w}>{w}</li>
                                ))}
                            </ul>
                        )}
                        {errors.length > 0 && (
                            <details className="w-full text-xs text-destructive">
                                <summary className="cursor-pointer">
                                    Errors (saving is blocked until they are
                                    fixed)
                                </summary>
                                <ul className="max-h-40 list-disc overflow-y-auto pl-5">
                                    {errors.map((m) => (
                                        <li key={m}>{m}</li>
                                    ))}
                                </ul>
                            </details>
                        )}
                    </div>

                    {/* Split: form | preview */}
                    <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(26rem,38%)_1fr]">
                        <div className="flex min-h-0 flex-col border-r">
                            <nav className="flex gap-1 border-b px-2 pt-2">
                                {TABS.map((t) => (
                                    <button
                                        key={t.id}
                                        type="button"
                                        disabled={
                                            jsonError !== null &&
                                            t.id !== 'json'
                                        }
                                        title={
                                            jsonError !== null &&
                                            t.id !== 'json'
                                                ? 'Fix the JSON first'
                                                : undefined
                                        }
                                        onClick={() => setTab(t.id)}
                                        className={cn(
                                            '-mb-px rounded-t-md border border-b-0 px-3 py-1.5 text-sm disabled:opacity-40',
                                            tab === t.id
                                                ? 'bg-background font-medium'
                                                : 'border-transparent text-muted-foreground hover:text-foreground',
                                        )}
                                    >
                                        {t.label}
                                        {errorsByTab[
                                            t.id as Exclude<Tab, 'json'>
                                        ] ? (
                                            <span className="ml-1 rounded-full bg-destructive px-1.5 text-[10px] text-white">
                                                {
                                                    errorsByTab[
                                                        t.id as Exclude<
                                                            Tab,
                                                            'json'
                                                        >
                                                    ]
                                                }
                                            </span>
                                        ) : null}
                                    </button>
                                ))}
                            </nav>
                            <fieldset
                                disabled={!can_edit}
                                className="min-h-0 flex-1 overflow-y-auto p-3"
                            >
                                {tab === 'overview' && <OverviewTab />}
                                {tab === 'sides' && <SidesTab />}
                                {tab === 'features' && <FeaturesTab />}
                                {tab === 'steps' && <StepsTab />}
                                {tab === 'json' && (
                                    <JsonTab onParseError={setJsonError} />
                                )}
                            </fieldset>
                        </div>
                        <div className="relative min-h-[28rem] bg-muted">
                            {previewSrc ? (
                                <>
                                    <iframe
                                        ref={frame}
                                        src={previewSrc}
                                        title="Atlas preview"
                                        className="absolute inset-0 size-full border-0"
                                    />
                                    <div className="pointer-events-none absolute top-2 left-2 flex flex-col gap-1">
                                        {picking && (
                                            <span className="pointer-events-auto rounded bg-pink-600 px-2 py-1 text-xs text-white shadow">
                                                {picking === 'point'
                                                    ? 'Click the map to pick a point'
                                                    : 'Click points; double-click or Enter to finish'}{' '}
                                                · Esc cancels{' '}
                                                <button
                                                    type="button"
                                                    className="ml-1 underline"
                                                    onClick={() => {
                                                        send({
                                                            type: 'map-story:pick-cancel',
                                                        });
                                                        setPicking(null);
                                                        pickDone.current = null;
                                                    }}
                                                >
                                                    cancel
                                                </button>
                                            </span>
                                        )}
                                        {previewIssues.length > 0 && (
                                            <span
                                                className="max-w-md rounded bg-amber-100 px-2 py-1 text-xs text-amber-900 shadow"
                                                title={previewIssues.join('\n')}
                                            >
                                                The preview can't draw this
                                                draft yet (showing the last one
                                                it could): {previewIssues[0]}
                                            </span>
                                        )}
                                    </div>
                                    <a
                                        href={previewSrc.replace(
                                            /&?preview=1/,
                                            '',
                                        )}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="absolute right-2 bottom-2 inline-flex items-center gap-1 rounded bg-background/90 px-2 py-1 text-xs shadow"
                                    >
                                        Open the saved story in the atlas{' '}
                                        <ExternalLink className="size-3" />
                                    </a>
                                </>
                            ) : (
                                <p className="p-6 text-sm text-muted-foreground">
                                    No preview: set FRONTEND_URL to the public
                                    atlas.
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            </StoryEditorContext>
            <RevisionsSheet
                slug={initialStory.slug}
                open={historyOpen}
                onOpenChange={setHistoryOpen}
                canEdit={can_edit}
                dirty={dirty}
                onLoad={(json) => setDoc(JSON.parse(json))}
                onRestored={(data) => {
                    applySaved(data);
                    setFlash({
                        kind: 'ok',
                        text: 'Restored (saved as a new version).',
                    });
                }}
            />
        </AppLayout>
    );
}

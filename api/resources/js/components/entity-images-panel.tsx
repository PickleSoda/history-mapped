import { ArrowDown, ArrowUp, ExternalLink, ImageOff, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

/** One `media_refs` item: a link to an image plus its credit. */
export type MediaRef = {
    type: 'image';
    kind: string;
    url: string;
    original_url?: string;
    page_url?: string;
    file?: string;
    caption?: string;
    author?: string;
    license?: string;
    license_url?: string;
    attribution_required?: boolean;
    width?: number;
    height?: number;
    source?: string;
    property?: string;
    found_on?: string;
};

type Source = 'wikidata' | 'wikipedia' | 'commons' | 'url';

const SOURCES: { key: Source; label: string; hint: string }[] = [
    {
        key: 'wikidata',
        label: 'Wikidata',
        hint: 'QID (defaults to this entity’s)',
    },
    {
        key: 'wikipedia',
        label: 'Wikipedia',
        hint: 'Article search (defaults to the name)',
    },
    {
        key: 'commons',
        label: 'Commons',
        hint: 'File search (defaults to the name)',
    },
    {
        key: 'url',
        label: 'Paste URL',
        hint: 'https://commons.wikimedia.org/wiki/File:… or any image URL',
    },
];

const KINDS = ['image', 'flag', 'coat_of_arms', 'seal', 'logo', 'map', 'plan'];

function kindLabel(kind: string): string {
    return kind.replace(/_/g, ' ');
}

function Credit({ item }: { item: MediaRef }) {
    return (
        <p className="text-xs text-muted-foreground">
            {item.author ?? 'Unknown author'}
            {' · '}
            {item.license_url ? (
                <a
                    href={item.license_url}
                    target="_blank"
                    rel="noreferrer"
                    className="underline-offset-2 hover:underline"
                >
                    {item.license ?? 'license'}
                </a>
            ) : (
                (item.license ?? 'no license given')
            )}
            {item.page_url && (
                <>
                    {' · '}
                    <a
                        href={item.page_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-0.5 underline-offset-2 hover:underline"
                    >
                        source <ExternalLink className="size-3" />
                    </a>
                </>
            )}
        </p>
    );
}

function Thumb({ item }: { item: MediaRef }) {
    return (
        <img
            src={item.url}
            alt={item.caption ?? item.file ?? ''}
            loading="lazy"
            referrerPolicy="no-referrer"
            className="h-20 w-28 flex-none rounded border bg-muted object-contain"
        />
    );
}

type Props = {
    entityId: string;
    readOnly?: boolean;
};

/**
 * The entity's linked images (first = primary) and a picker that searches
 * Wikidata, Wikipedia or Commons, or takes a pasted URL. Images are linked,
 * never copied; Commons credits are re-read from Commons on save.
 */
export default function EntityImagesPanel({
    entityId,
    readOnly = false,
}: Props) {
    const baseUrl = `/entities/${entityId}/images`;
    const csrfRef = useRef<string>('');
    const [items, setItems] = useState<MediaRef[]>([]);
    const [curatedAt, setCuratedAt] = useState<string | null>(null);
    const [hasQid, setHasQid] = useState(false);
    const [dirty, setDirty] = useState(false);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    const [source, setSource] = useState<Source>('wikidata');
    const [query, setQuery] = useState('');
    const [searching, setSearching] = useState(false);
    const [results, setResults] = useState<MediaRef[] | null>(null);

    useEffect(() => {
        csrfRef.current =
            document
                .querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
                ?.getAttribute('content') ?? '';
    }, []);

    function applyPayload(payload: {
        data: MediaRef[];
        curated_at: string | null;
        wikidata_id: string | null;
    }) {
        setItems(payload.data ?? []);
        setCuratedAt(payload.curated_at);
        setHasQid(Boolean(payload.wikidata_id));
        setDirty(false);
    }

    async function errorMessage(response: Response): Promise<string> {
        try {
            const body = (await response.json()) as {
                message?: string;
                errors?: Record<string, string[]>;
            };
            const first = body.errors
                ? Object.values(body.errors)[0]?.[0]
                : null;

            return first ?? body.message ?? `HTTP ${response.status}`;
        } catch {
            return `HTTP ${response.status}`;
        }
    }

    useEffect(() => {
        let cancelled = false;

        async function load() {
            setLoading(true);

            try {
                const response = await fetch(baseUrl, {
                    headers: { Accept: 'application/json' },
                });

                if (!response.ok) {
                    throw new Error(await errorMessage(response));
                }

                const payload = await response.json();

                if (!cancelled) {
                    applyPayload(payload);
                    setSource(payload.wikidata_id ? 'wikidata' : 'wikipedia');
                }
            } catch (e) {
                if (!cancelled) {
                    setError(`Failed to load images: ${(e as Error).message}`);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        void load();

        return () => {
            cancelled = true;
        };
    }, [baseUrl]);

    async function search(e?: React.FormEvent) {
        e?.preventDefault();
        setSearching(true);
        setError(null);
        setResults(null);

        try {
            const params = new URLSearchParams({ source, q: query.trim() });
            const response = await fetch(`${baseUrl}/candidates?${params}`, {
                headers: { Accept: 'application/json' },
            });

            if (!response.ok) {
                throw new Error(await errorMessage(response));
            }

            const payload = (await response.json()) as { data: MediaRef[] };
            setResults(payload.data ?? []);
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setSearching(false);
        }
    }

    function update(next: MediaRef[]) {
        setItems(next);
        setDirty(true);
        setNotice(null);
    }

    function move(index: number, by: number) {
        const next = [...items];
        const [item] = next.splice(index, 1);
        next.splice(index + by, 0, item);
        update(next);
    }

    function add(candidate: MediaRef, primary: boolean) {
        const rest = items.filter((i) => i.url !== candidate.url);
        update(primary ? [candidate, ...rest] : [...rest, candidate]);
    }

    function patch(index: number, fields: Partial<MediaRef>) {
        update(items.map((i, n) => (n === index ? { ...i, ...fields } : i)));
    }

    async function save() {
        setSaving(true);
        setError(null);

        try {
            const response = await fetch(baseUrl, {
                method: 'PUT',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
                body: JSON.stringify({
                    images: items.map((i) =>
                        i.source === 'external'
                            ? {
                                  url: i.url,
                                  kind: i.kind,
                                  caption: i.caption || null,
                                  author: i.author || null,
                                  license: i.license || null,
                                  license_url: i.license_url || null,
                                  page_url: i.page_url || null,
                              }
                            : {
                                  file: i.file,
                                  kind: i.kind,
                                  source: i.source ?? 'commons',
                                  property: i.property ?? null,
                                  caption: i.caption || null,
                              },
                    ),
                }),
            });

            if (!response.ok) {
                throw new Error(await errorMessage(response));
            }

            applyPayload(await response.json());
            setNotice(
                'Images saved. The automatic fetcher will leave this entity alone from now on.',
            );
        } catch (e) {
            setError(`Not saved: ${(e as Error).message}`);
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return <p className="text-sm text-muted-foreground">Loading images…</p>;
    }

    const hint = SOURCES.find((s) => s.key === source)?.hint ?? '';

    return (
        <div className="space-y-5">
            {/* Current images */}
            <div className="space-y-2">
                {items.length === 0 ? (
                    <div className="flex items-center gap-2 rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                        <ImageOff className="size-4" />
                        No image linked.{' '}
                        {hasQid
                            ? 'Nothing was found on its Wikidata item; try Wikipedia or Commons below.'
                            : 'It has no Wikidata id; search Wikipedia or Commons, or paste a URL below.'}
                    </div>
                ) : (
                    items.map((item, index) => (
                        <div
                            key={item.url}
                            className="flex gap-3 rounded-md border p-2"
                        >
                            <Thumb item={item} />
                            <div className="min-w-0 flex-1 space-y-1">
                                <div className="flex flex-wrap items-center gap-2 text-sm">
                                    {index === 0 && (
                                        <span className="rounded bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground uppercase">
                                            Primary
                                        </span>
                                    )}
                                    <select
                                        value={item.kind}
                                        disabled={readOnly}
                                        onChange={(e) =>
                                            patch(index, {
                                                kind: e.target.value,
                                            })
                                        }
                                        className="h-7 rounded border bg-background px-1 text-xs"
                                        aria-label="Kind"
                                    >
                                        {KINDS.map((k) => (
                                            <option key={k} value={k}>
                                                {kindLabel(k)}
                                            </option>
                                        ))}
                                    </select>
                                    <span className="truncate text-xs text-muted-foreground">
                                        {item.file ?? item.url}
                                        {item.source && ` · via ${item.source}`}
                                        {item.property && ` ${item.property}`}
                                    </span>
                                </div>
                                {item.source === 'external' ? (
                                    <div className="grid gap-1.5 sm:grid-cols-2">
                                        <Input
                                            value={item.author ?? ''}
                                            onChange={(e) =>
                                                patch(index, {
                                                    author: e.target.value,
                                                })
                                            }
                                            placeholder="Author / credit"
                                            className="h-8 text-xs"
                                        />
                                        <Input
                                            value={item.license ?? ''}
                                            onChange={(e) =>
                                                patch(index, {
                                                    license: e.target.value,
                                                })
                                            }
                                            placeholder="License (required), e.g. CC BY 4.0"
                                            className="h-8 text-xs"
                                        />
                                        <Input
                                            value={item.license_url ?? ''}
                                            onChange={(e) =>
                                                patch(index, {
                                                    license_url: e.target.value,
                                                })
                                            }
                                            placeholder="License URL"
                                            className="h-8 text-xs"
                                        />
                                        <Input
                                            value={item.page_url ?? ''}
                                            onChange={(e) =>
                                                patch(index, {
                                                    page_url: e.target.value,
                                                })
                                            }
                                            placeholder="Source page URL"
                                            className="h-8 text-xs"
                                        />
                                    </div>
                                ) : (
                                    <Credit item={item} />
                                )}
                                <Input
                                    value={item.caption ?? ''}
                                    disabled={readOnly}
                                    onChange={(e) =>
                                        patch(index, {
                                            caption: e.target.value,
                                        })
                                    }
                                    placeholder="Caption"
                                    className="h-8 text-xs"
                                />
                            </div>
                            {!readOnly && (
                                <div className="flex flex-col gap-1">
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className="size-7"
                                        disabled={index === 0}
                                        onClick={() => move(index, -1)}
                                        aria-label="Move up"
                                    >
                                        <ArrowUp className="size-4" />
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className="size-7"
                                        disabled={index === items.length - 1}
                                        onClick={() => move(index, 1)}
                                        aria-label="Move down"
                                    >
                                        <ArrowDown className="size-4" />
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className="size-7"
                                        onClick={() =>
                                            update(
                                                items.filter(
                                                    (_, n) => n !== index,
                                                ),
                                            )
                                        }
                                        aria-label="Remove"
                                    >
                                        <X className="size-4" />
                                    </Button>
                                </div>
                            )}
                        </div>
                    ))
                )}

                <div className="flex flex-wrap items-center gap-3">
                    {!readOnly && (
                        <Button
                            type="button"
                            size="sm"
                            disabled={!dirty || saving}
                            onClick={() => void save()}
                        >
                            {saving ? 'Saving…' : 'Save images'}
                        </Button>
                    )}
                    <span className="text-xs text-muted-foreground">
                        {curatedAt
                            ? `Picked by an admin (${new Date(curatedAt).toLocaleDateString()}).`
                            : items.length > 0
                              ? 'Found automatically on Wikimedia.'
                              : null}
                    </span>
                    {notice && (
                        <span className="text-xs text-green-700 dark:text-green-400">
                            {notice}
                        </span>
                    )}
                </div>
            </div>

            {/* Find images */}
            {!readOnly && (
                <div className="space-y-3 border-t pt-4">
                    <p className="text-sm font-medium">Find an image</p>
                    <div className="flex flex-wrap gap-1">
                        {SOURCES.map((s) => (
                            <Button
                                key={s.key}
                                type="button"
                                size="sm"
                                variant={
                                    source === s.key ? 'default' : 'outline'
                                }
                                onClick={() => {
                                    setSource(s.key);
                                    setResults(null);
                                }}
                            >
                                {s.label}
                            </Button>
                        ))}
                    </div>
                    <form
                        onSubmit={(e) => void search(e)}
                        className="flex gap-2"
                    >
                        <Input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder={hint}
                            className="h-9"
                        />
                        <Button
                            type="submit"
                            size="sm"
                            variant="secondary"
                            disabled={
                                searching ||
                                (source === 'url' && query.trim() === '')
                            }
                        >
                            {searching
                                ? 'Searching…'
                                : source === 'url'
                                  ? 'Use'
                                  : 'Search'}
                        </Button>
                    </form>
                    <p className="text-xs text-muted-foreground">
                        Only links are stored; images stay where they are
                        hosted. Wikimedia results show their license. For other
                        URLs, enter the author and license before saving.
                    </p>

                    {error && (
                        <p className="text-sm text-destructive">{error}</p>
                    )}

                    {results !== null && results.length === 0 && (
                        <p className="text-sm text-muted-foreground">
                            Nothing found
                            {source === 'wikidata' && !hasQid && !query
                                ? ' (this entity has no Wikidata id; enter a QID)'
                                : ''}
                            .
                        </p>
                    )}

                    {results !== null && results.length > 0 && (
                        <div className="grid gap-2 sm:grid-cols-2">
                            {results.map((r) => {
                                const linked = items.some(
                                    (i) => i.url === r.url,
                                );

                                return (
                                    <div
                                        key={r.url}
                                        className="flex gap-2 rounded-md border p-2"
                                    >
                                        <Thumb item={r} />
                                        <div className="min-w-0 flex-1 space-y-1">
                                            <p className="truncate text-xs font-medium">
                                                {r.found_on
                                                    ? `Wikipedia: ${r.found_on}`
                                                    : (r.file ?? r.url)}
                                            </p>
                                            <p className="text-[11px] text-muted-foreground">
                                                {kindLabel(r.kind)}
                                                {r.property &&
                                                    ` · ${r.property}`}
                                                {r.width && r.height
                                                    ? ` · ${r.width}×${r.height}`
                                                    : ''}
                                            </p>
                                            {r.source !== 'external' && (
                                                <Credit item={r} />
                                            )}
                                            <div className="flex gap-1 pt-1">
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="outline"
                                                    className="h-7 text-xs"
                                                    onClick={() => add(r, true)}
                                                >
                                                    Make primary
                                                </Button>
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="ghost"
                                                    className="h-7 text-xs"
                                                    disabled={linked}
                                                    onClick={() =>
                                                        add(r, false)
                                                    }
                                                >
                                                    {linked ? 'Linked' : 'Add'}
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}
            {readOnly && error && (
                <p className="text-sm text-destructive">{error}</p>
            )}
        </div>
    );
}

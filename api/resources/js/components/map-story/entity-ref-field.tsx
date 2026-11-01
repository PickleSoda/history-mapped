import { CheckCircle2, CircleAlert, Search } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { entities as entitiesRoute } from '@/routes/map-stories';
import { useStoryEditor } from './editor-context';
import { Field, IconButton, inputCls } from './fields';

type Ref = {
    name?: string;
    wikidata?: string;
    entity_id?: string;
    [key: string]: unknown;
};

type Hit = {
    id: string;
    name: string;
    wikidata: string | null;
    type: string | null;
    start_year: number | null;
    end_year: number | null;
};

const years = (h: Hit) =>
    h.start_year == null && h.end_year == null
        ? ''
        : ` · ${h.start_year ?? '?'}–${h.end_year ?? '?'}`;

/**
 * A linked entity reference — {name, wikidata?} (or, without a name, an
 * `area_from_entity` {wikidata} / {entity_id}) — with a search over the atlas
 * that fills the Q-id, and a check of what the Q-id resolves to.
 */
export function EntityRefField({
    label,
    value,
    onChange,
    needsName = true,
    className,
}: {
    label: string;
    value: Ref | null | undefined;
    onChange: (value: Ref | undefined) => void;
    needsName?: boolean;
    className?: string;
}) {
    const { linked, addLinked } = useStoryEditor();
    const [query, setQuery] = useState<string | null>(null);
    const [hits, setHits] = useState<Hit[]>([]);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        if (query === null || query.trim().length < 2) {
            return;
        }

        if (timer.current) {
            clearTimeout(timer.current);
        }

        const controller = new AbortController();
        timer.current = setTimeout(() => {
            fetch(entitiesRoute.url({ query: { q: query } }), {
                headers: { Accept: 'application/json' },
                signal: controller.signal,
            })
                .then((r) => r.json())
                .then((body) => setHits(body.data ?? []))
                .catch(() => {});
        }, 250);

        return () => controller.abort();
    }, [query]);

    const ref = value ?? {};
    const set = (patch: Partial<Ref>) => {
        const next: Ref = { ...ref, ...patch };

        for (const k of Object.keys(next)) {
            if (next[k] === undefined || next[k] === '') {
                delete next[k];
            }
        }

        onChange(Object.keys(next).length === 0 ? undefined : next);
    };
    const atlas =
        typeof ref.wikidata === 'string' ? linked[ref.wikidata] : undefined;
    const status = !ref.wikidata ? null : !atlas ? (
        <span
            className="inline-flex items-center gap-1 text-amber-600"
            title="No atlas entity has this Q-id: the link won't resolve"
        >
            <CircleAlert className="size-3" /> not in the atlas
        </span>
    ) : ref.name && atlas.name !== ref.name ? (
        <span
            className="inline-flex items-center gap-1 text-amber-600"
            title="The atlas names this Q-id differently — check it is the same"
        >
            <CircleAlert className="size-3" /> atlas: {atlas.name}
        </span>
    ) : (
        <span
            className="inline-flex items-center gap-1 text-emerald-600"
            title={`Resolves to ${atlas.name}`}
        >
            <CheckCircle2 className="size-3" /> linked
        </span>
    );

    return (
        <Field
            label={label}
            className={className}
            hint={<span className="text-[10px]">{status}</span>}
        >
            <span className="relative flex gap-1">
                {needsName && (
                    <input
                        className={inputCls}
                        placeholder="name"
                        value={ref.name ?? ''}
                        onChange={(e) => set({ name: e.target.value })}
                    />
                )}
                <input
                    className={`${inputCls} max-w-[7.5rem] font-mono`}
                    placeholder="Q-id"
                    value={ref.wikidata ?? ''}
                    onChange={(e) =>
                        set({
                            wikidata:
                                e.target.value.trim().toUpperCase() ||
                                undefined,
                        })
                    }
                />
                <IconButton
                    title="Search the atlas"
                    onClick={() =>
                        setQuery(query === null ? (ref.name ?? '') : null)
                    }
                >
                    <Search className="size-3.5" />
                </IconButton>
                {query !== null && (
                    <div className="absolute top-9 right-0 z-30 w-80 rounded-md border bg-popover p-2 shadow-lg">
                        <input
                            autoFocus
                            className={inputCls}
                            placeholder="Search entities by name or Q-id"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) =>
                                e.key === 'Escape' && setQuery(null)
                            }
                        />
                        <ul className="mt-1 max-h-60 overflow-y-auto text-sm">
                            {hits.map((h) => (
                                <li key={h.id}>
                                    <button
                                        type="button"
                                        className="w-full rounded px-2 py-1 text-left hover:bg-muted"
                                        onClick={() => {
                                            if (h.wikidata) {
                                                addLinked(h.wikidata, {
                                                    id: h.id,
                                                    name: h.name,
                                                    type: h.type,
                                                });
                                                set({
                                                    name: needsName
                                                        ? h.name
                                                        : ref.name,
                                                    wikidata: h.wikidata,
                                                    entity_id: undefined,
                                                });
                                            } else {
                                                set({
                                                    name: needsName
                                                        ? h.name
                                                        : ref.name,
                                                    entity_id: h.id,
                                                    wikidata: undefined,
                                                });
                                            }

                                            setQuery(null);
                                        }}
                                    >
                                        <span className="font-medium">
                                            {h.name}
                                        </span>
                                        <span className="block text-xs text-muted-foreground">
                                            {(h.type ?? '').replace(/_/g, ' ')}
                                            {years(h)} ·{' '}
                                            {h.wikidata ??
                                                'no Q-id (links by id)'}
                                        </span>
                                    </button>
                                </li>
                            ))}
                            {hits.length === 0 && (query ?? '').length >= 2 && (
                                <li className="px-2 py-1 text-xs text-muted-foreground">
                                    No match yet…
                                </li>
                            )}
                        </ul>
                    </div>
                )}
            </span>
        </Field>
    );
}

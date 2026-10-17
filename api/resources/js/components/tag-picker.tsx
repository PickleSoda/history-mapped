import { Plus, X } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import type { TagFacet, TagOption } from '@/types';

const FACET_LABELS: Record<TagFacet, string> = {
    era: 'Era',
    region: 'Region',
    theme: 'Theme',
    type: 'Type',
    topic: 'Topic',
};

const FACET_STYLES: Record<TagFacet, string> = {
    era: 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200',
    region: 'border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-200',
    theme: 'border-violet-300 bg-violet-50 text-violet-900 dark:border-violet-800 dark:bg-violet-950 dark:text-violet-200',
    type: 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200',
    topic: 'border-border bg-muted text-foreground',
};

/** Slug → option lookup; unknown slugs render as topic tags named by slug. */
function useTagIndex(options: TagOption[]) {
    return useMemo(
        () => new Map(options.map((o) => [o.slug, o] as const)),
        [options],
    );
}

function TagBadge({
    tag,
    onRemove,
}: {
    tag: TagOption;
    onRemove?: () => void;
}) {
    return (
        <Badge
            variant="outline"
            className={cn('gap-1 font-normal', FACET_STYLES[tag.facet])}
            title={FACET_LABELS[tag.facet]}
        >
            {tag.name}
            {onRemove && (
                <button
                    type="button"
                    onClick={onRemove}
                    className="-mr-1 rounded-sm opacity-60 hover:opacity-100"
                    aria-label={`Remove ${tag.name}`}
                >
                    <X className="size-3" />
                </button>
            )}
        </Badge>
    );
}

/** Read-only tag list, ordered by facet as given in `options`. */
export function TagBadges({
    slugs,
    options,
    className,
}: {
    slugs: string[];
    options: TagOption[];
    className?: string;
}) {
    const index = useTagIndex(options);
    const order = useMemo(
        () => new Map(options.map((o, i) => [o.slug, i] as const)),
        [options],
    );
    const tags = slugs
        .map(
            (s) =>
                index.get(s) ??
                ({
                    slug: s,
                    name: s,
                    facet: 'topic',
                    parent: null,
                    chronicle_count: 0,
                } satisfies TagOption),
        )
        .sort(
            (a, b) =>
                (order.get(a.slug) ?? Infinity) -
                (order.get(b.slug) ?? Infinity),
        );

    if (tags.length === 0) {
        return null;
    }

    return (
        <div className={cn('flex flex-wrap gap-1', className)}>
            {tags.map((t) => (
                <TagBadge key={t.slug} tag={t} />
            ))}
        </div>
    );
}

/**
 * Multi-select tag input: type to search the vocabulary (grouped by facet),
 * Enter picks the first match. With `allowCreate`, an unmatched term is added
 * as-is and becomes a new topic tag on save.
 */
export function TagPicker({
    value,
    onChange,
    options,
    allowCreate = false,
    placeholder = 'Add tags…',
    id,
}: {
    value: string[];
    onChange: (slugs: string[]) => void;
    options: TagOption[];
    allowCreate?: boolean;
    placeholder?: string;
    id?: string;
}) {
    const index = useTagIndex(options);
    const [query, setQuery] = useState('');
    const [open, setOpen] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    const matches = useMemo(() => {
        const q = query.trim().toLowerCase();

        return options
            .filter(
                (o) =>
                    !value.includes(o.slug) &&
                    (q === '' ||
                        o.name.toLowerCase().includes(q) ||
                        o.slug.includes(q)),
            )
            .slice(0, 40);
    }, [options, query, value]);

    const grouped = useMemo(() => {
        const groups = new Map<TagFacet, TagOption[]>();

        for (const m of matches) {
            groups.set(m.facet, [...(groups.get(m.facet) ?? []), m]);
        }

        return [...groups.entries()];
    }, [matches]);

    const term = query.trim();
    const canCreate =
        allowCreate &&
        term !== '' &&
        !options.some((o) => o.name.toLowerCase() === term.toLowerCase()) &&
        !value.includes(term);

    function add(slug: string) {
        onChange([...value, slug]);
        setQuery('');
        inputRef.current?.focus();
    }

    function remove(slug: string) {
        onChange(value.filter((s) => s !== slug));
    }

    return (
        <div className="space-y-2">
            {value.length > 0 && (
                <div className="flex flex-wrap gap-1">
                    {value.map((slug) => (
                        <TagBadge
                            key={slug}
                            tag={
                                index.get(slug) ?? {
                                    slug,
                                    name: slug,
                                    facet: 'topic',
                                    parent: null,
                                    chronicle_count: 0,
                                }
                            }
                            onRemove={() => remove(slug)}
                        />
                    ))}
                </div>
            )}
            <div className="relative">
                <Plus className="pointer-events-none absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
                <Input
                    id={id}
                    ref={inputRef}
                    value={query}
                    placeholder={placeholder}
                    className="pl-9"
                    onChange={(e) => {
                        setQuery(e.target.value);
                        setOpen(true);
                    }}
                    onFocus={() => setOpen(true)}
                    onBlur={() => setTimeout(() => setOpen(false), 150)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                            e.preventDefault();

                            if (matches[0]) {
                                add(matches[0].slug);
                            } else if (canCreate) {
                                add(term);
                            }
                        } else if (
                            e.key === 'Backspace' &&
                            query === '' &&
                            value.length > 0
                        ) {
                            remove(value[value.length - 1]);
                        } else if (e.key === 'Escape') {
                            setOpen(false);
                        }
                    }}
                />
                {open && (grouped.length > 0 || canCreate) && (
                    <div className="absolute z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
                        {grouped.map(([facet, tags]) => (
                            <div key={facet} className="py-1">
                                <div className="px-2 pb-1 text-xs font-medium text-muted-foreground">
                                    {FACET_LABELS[facet]}
                                </div>
                                {tags.map((t) => (
                                    <button
                                        key={t.slug}
                                        type="button"
                                        onMouseDown={(e) => e.preventDefault()}
                                        onClick={() => add(t.slug)}
                                        className="flex w-full items-center justify-between rounded-sm px-2 py-1 text-left text-sm hover:bg-accent"
                                    >
                                        <span>{t.name}</span>
                                        <span className="text-xs text-muted-foreground tabular-nums">
                                            {t.chronicle_count}
                                        </span>
                                    </button>
                                ))}
                            </div>
                        ))}
                        {canCreate && (
                            <button
                                type="button"
                                onMouseDown={(e) => e.preventDefault()}
                                onClick={() => add(term)}
                                className="w-full rounded-sm px-2 py-1 text-left text-sm hover:bg-accent"
                            >
                                Create topic “{term}”
                            </button>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

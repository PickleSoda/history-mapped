import { ChevronLeft, ScrollText, Search, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useChronicleList, useChronicleNav, useChronicleTags, useTags } from '@/hooks';
import { formatYear } from '@/lib/format';
import type { ChronicleSummary } from '@/lib/schemas/chronicle';
import type { TagFacet } from '@/lib/schemas/tag';
import { FACETS, ancestorsOf, childrenOf, displayTags, toggleTag } from '@/lib/tags';
import type { IndexedTag, TagIndex } from '@/lib/tags';
import { cn } from '@/lib/utils';

const BROWSE_FACETS: TagFacet[] = ['era', 'region', 'theme', 'type'];

function rangeLabel(c: ChronicleSummary): string | null {
  const s = c.start_year != null ? formatYear(c.start_year) : null;
  const e = c.end_year != null ? formatYear(c.end_year) : null;
  if (s && e) return `${s} – ${e}`;
  return s ?? e ?? null;
}

/** `value`, settled for `ms` — so typing doesn't fire a request per keystroke. */
function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

function TagChip({
  tag,
  active = false,
  count,
  onClick,
  removable = false,
}: {
  tag: IndexedTag;
  active?: boolean;
  count?: number;
  onClick: () => void;
  removable?: boolean;
}) {
  const color = FACETS[tag.facet].color;
  return (
    <button
      type="button"
      onClick={onClick}
      title={tag.description ?? FACETS[tag.facet].label}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors',
        active ? 'border-transparent font-medium' : 'text-muted-foreground hover:bg-muted/60',
      )}
      style={active ? { background: `color-mix(in oklab, ${color} 16%, transparent)`, color } : undefined}
    >
      <span className="size-[7px] flex-none rounded-full" style={{ background: color }} />
      {tag.name}
      {count != null && <span className="font-mono text-[10px] opacity-60">{count}</span>}
      {removable && <X size={12} className="-mr-0.5 opacity-70" />}
    </button>
  );
}

/** Chips for one facet. Regions drill down: picking Asia shows its subregions. */
function FacetBrowser({
  facet,
  tags,
  index,
  selected,
  onToggle,
}: {
  facet: TagFacet;
  tags: IndexedTag[];
  index: TagIndex;
  selected: string[];
  onToggle: (slug: string) => void;
}) {
  const [drilled, setRoot] = useState<IndexedTag | null>(null);
  // Back to the top once nothing under the drilled region is selected (Clear).
  const root =
    drilled && selected.some((s) => s === drilled.slug || ancestorsOf(s, index).includes(drilled.slug))
      ? drilled
      : null;
  const level = facet === 'region' ? childrenOf(root?.slug ?? null, facet, tags) : tags.filter((t) => t.facet === facet);
  const shown = level.filter((t) => t.chronicle_count > 0);

  return (
    <div className="flex flex-wrap gap-1.5">
      {root && (
        <button
          type="button"
          onClick={() => setRoot(tags.find((t) => t.slug === root.parent) ?? null)}
          className="inline-flex items-center gap-0.5 rounded-full px-1.5 py-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft size={13} /> {root.parent ? tags.find((t) => t.slug === root.parent)?.name : 'All regions'}
        </button>
      )}
      {shown.map((t) => (
        <TagChip
          key={t.slug}
          tag={t}
          count={t.chronicle_count}
          active={selected.includes(t.slug)}
          onClick={() => {
            onToggle(t.slug);
            if (facet === 'region' && childrenOf(t.slug, facet, tags).some((c) => c.chronicle_count > 0)) {
              setRoot(t);
            }
          }}
        />
      ))}
    </div>
  );
}

function ChronicleRow({
  c,
  index,
  selected,
  onToggle,
}: {
  c: ChronicleSummary;
  index: TagIndex;
  selected: string[];
  onToggle: (slug: string) => void;
}) {
  const { enter } = useChronicleNav();
  const shown = displayTags(c.tags, index);
  const type = shown.find((t) => t.facet === 'type');
  const pills = shown.filter((t) => t.facet !== 'type' && t.facet !== 'topic').slice(0, 5);
  const range = rangeLabel(c);

  return (
    <div className="rounded-lg border bg-card transition-colors hover:bg-muted/40">
      <button type="button" onClick={() => enter(c.slug)} className="w-full px-3 pt-2.5 text-left">
        <div className="flex items-start gap-2">
          <ScrollText size={15} className="mt-0.5 flex-none text-muted-foreground" />
          <div className="min-w-0 flex-1">
            <p className="line-clamp-2 text-sm font-medium">{c.title}</p>
            <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] text-muted-foreground">
              {range && <span className="font-mono">{range}</span>}
              {c.entry_count != null && <span>{c.entry_count} steps</span>}
              {type && <span>{type.name}</span>}
            </div>
          </div>
        </div>
      </button>
      {pills.length > 0 && (
        <div className="flex flex-wrap gap-1 px-3 pt-1.5 pb-2.5 pl-[33px]">
          {pills.map((t) => (
            <button
              key={t.slug}
              type="button"
              onClick={() => onToggle(t.slug)}
              title={`${selected.includes(t.slug) ? 'Remove' : 'Filter by'} ${t.name}`}
              className={cn(
                'inline-flex items-center gap-1 rounded-full border px-1.5 py-px text-[10.5px] text-muted-foreground hover:text-foreground',
                selected.includes(t.slug) && 'border-foreground/40 text-foreground',
              )}
            >
              <span className="size-[5px] rounded-full" style={{ background: FACETS[t.facet].color }} />
              {t.name}
            </button>
          ))}
        </div>
      )}
      {pills.length === 0 && <div className="pb-2.5" />}
    </div>
  );
}

/** Chronicles tab: search (titles and tag names), tag filters by facet, and
 *  the matching chronicles in chronological order. Tags live in the URL (`ct`). */
export function ChronicleList() {
  const { tags: selected, setTags } = useChronicleTags();
  const { tags, index } = useTags();
  const [query, setQuery] = useState('');
  const [facet, setFacet] = useState<TagFacet>('era');
  const search = useDebounced(query.trim(), 250);

  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } = useChronicleList({
    search: search || undefined,
    tags: selected,
    sort: 'chronological',
  });
  const rows = data?.pages.flatMap((p) => p.data) ?? [];
  const total = data?.pages[0]?.meta.total;

  const toggle = (slug: string) => void setTags(toggleTag(selected, slug, index));

  // Tags whose name matches the search box, offered as one-click filters.
  const suggestions = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    return tags
      .filter((t) => t.chronicle_count > 0 && !selected.includes(t.slug) && t.name.toLowerCase().includes(q))
      .slice(0, 6);
  }, [query, tags, selected]);

  const active = selected.map((s) => index.get(s)).filter((t): t is IndexedTag => t != null);

  return (
    <div className="flex flex-col p-3">
      <div className="flex items-center justify-between px-1 pb-2">
        <span className="text-xs font-medium text-muted-foreground">Chronicles</span>
        {total != null && <span className="font-mono text-[11px] text-muted-foreground">{total}</span>}
      </div>

      <div className="relative">
        <Search
          size={14}
          className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground"
        />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search chronicles or tags…"
          aria-label="Search chronicles or tags"
          className="h-9 w-full rounded-lg border bg-card pr-3 pl-8 text-[13px] outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
        />
      </div>

      {suggestions.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground">Tags:</span>
          {suggestions.map((t) => (
            <TagChip
              key={t.slug}
              tag={t}
              count={t.chronicle_count}
              onClick={() => {
                toggle(t.slug);
                setQuery('');
              }}
            />
          ))}
        </div>
      )}

      {active.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {active.map((t) => (
            <TagChip key={t.slug} tag={t} active removable onClick={() => toggle(t.slug)} />
          ))}
          <button
            type="button"
            onClick={() => void setTags([])}
            className="px-1 text-[11px] text-muted-foreground underline-offset-2 hover:underline"
          >
            Clear
          </button>
        </div>
      )}

      {tags.length > 0 && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-0.5 rounded-lg bg-muted p-0.5" role="tablist" aria-label="Browse by">
            {BROWSE_FACETS.map((f) => (
              <button
                key={f}
                type="button"
                role="tab"
                aria-selected={facet === f}
                onClick={() => setFacet(f)}
                className={cn(
                  'flex-1 rounded-md py-1 text-[11px] font-medium transition-colors',
                  facet === f ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground',
                )}
              >
                {FACETS[f].label}
              </button>
            ))}
          </div>
          <FacetBrowser
            key={facet}
            facet={facet}
            tags={tags}
            index={index}
            selected={selected}
            onToggle={toggle}
          />
        </div>
      )}

      <div className="my-3 h-px bg-border" />

      {isLoading && <p className="px-1 py-2 text-sm text-muted-foreground">Loading…</p>}
      {isError && <p className="px-1 py-2 text-sm text-destructive">Could not load chronicles.</p>}
      {data && rows.length === 0 && (
        <p className="px-1 py-2 text-sm text-muted-foreground">
          {selected.length > 0 || search ? 'No chronicles match these filters.' : 'No chronicles yet.'}
        </p>
      )}

      <div className="space-y-1.5">
        {rows.map((c) => (
          <ChronicleRow key={c.chronicle_id} c={c} index={index} selected={selected} onToggle={toggle} />
        ))}
      </div>

      {hasNextPage && (
        <button
          type="button"
          onClick={() => void fetchNextPage()}
          disabled={isFetchingNextPage}
          className="mt-2 rounded-lg border py-2 text-xs text-muted-foreground hover:bg-muted/50 disabled:opacity-50"
        >
          {isFetchingNextPage ? 'Loading…' : `Load more (${rows.length} of ${total})`}
        </button>
      )}
    </div>
  );
}

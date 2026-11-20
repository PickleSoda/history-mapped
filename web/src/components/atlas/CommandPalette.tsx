import { CornerDownLeft, Filter, MapPin, Search, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type {KeyboardEvent as ReactKeyboardEvent} from 'react';
import { GroupBadge, GroupDot } from '@/components/atlas/GroupBadge';
import {
  SEARCH_FILTER_MIN,
  useCommandPalette,
  useEntitySearch,
  useSearchFilter,
  useSelection,
} from '@/hooks';
import { formatYear } from '@/lib/format';
import { GROUPS, GROUP_ORDER } from '@/lib/groups';
import type { EntitySummary } from '@/lib/schemas/entity';
import { cn } from '@/lib/utils';
import type { EntityGroup } from '@/types/atlas';

/** Debounce a value by `ms`. */
function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="rounded border border-b-2 bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
      {children}
    </kbd>
  );
}

function spanLabel(e: EntitySummary): string | null {
  if (e.temporal_display_range) return e.temporal_display_range;
  if (e.era_label) return e.era_label;
  const fmt = (v: number | string | null) =>
    v == null ? null : typeof v === 'number' ? formatYear(v) : v;
  const s = fmt(e.temporal_start);
  const end = fmt(e.temporal_end);
  if (s && end) return `${s} – ${end}`;
  return s ?? end ?? null;
}

function ResultRow({
  e,
  active,
  onPick,
  onHover,
}: {
  e: EntitySummary;
  active: boolean;
  onPick: () => void;
  onHover: () => void;
}) {
  const span = spanLabel(e);
  return (
    <button
      type="button"
      onClick={onPick}
      onMouseMove={onHover}
      className={cn(
        'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left',
        active ? 'bg-muted' : 'hover:bg-muted/50',
      )}
    >
      <GroupDot group={e.entity_group} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{e.name}</span>
        {e.location_name && (
          <span className="flex items-center gap-1 truncate text-[11px] text-muted-foreground">
            <MapPin size={11} /> {e.location_name}
          </span>
        )}
      </span>
      {span && (
        <span className="font-mono text-[11px] text-muted-foreground">{span}</span>
      )}
      <GroupBadge group={e.entity_group} />
    </button>
  );
}

/** The row above the results: keep the typed word as a filter. */
const FILTER_ROW = -1;

/**
 * Command palette (⌘K). A comprehensive, global entity search — independent of
 * the map viewport and the sidebar's filters — with group facets and full
 * keyboard navigation. Enter keeps the typed word as a filter on the map and
 * the list (until cleared); picking a result opens that entity.
 */
export function CommandPalette() {
  const { open, setOpen } = useCommandPalette();
  const { select, clear: clearSelection } = useSelection();
  const { q: filter, setFilter } = useSearchFilter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState('');
  const [groups, setGroups] = useState<EntityGroup[]>([]); // empty = all
  const [active, setActive] = useState(FILTER_ROW);

  const debounced = useDebounced(query.trim(), 200);
  const { data, isFetching } = useEntitySearch(debounced, groups);
  const results = data?.data ?? [];

  // Global ⌘K toggle + Esc close.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen(!open);
      } else if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, setOpen]);

  // Reset transient state + focus on open.
  useEffect(() => {
    if (open) {
      setActive(FILTER_ROW);
      // Reopened over a kept filter: start from its word, ready to change.
      if (filter) setQuery(filter);
      const id = requestAnimationFrame(() => inputRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
    setQuery('');
    // Only on open / close; a filter set meanwhile must not retype the box.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => setActive(FILTER_ROW), [debounced, groups]);

  // On phones the palette sits beside the bottom sheet, whose drawer library
  // traps focus: its document listeners saw focus leave the sheet for the
  // search box and pulled it back, so nothing could be typed. While the
  // palette is open, focus moves into or out of it stop at the document,
  // before those listeners run.
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const stop = (e: FocusEvent) => {
      const root = rootRef.current;
      if (!root) return;
      const inPalette = (t: EventTarget | null) => t instanceof Node && root.contains(t);
      if (inPalette(e.target) || inPalette(e.relatedTarget)) e.stopPropagation();
    };
    document.addEventListener('focusin', stop, true);
    document.addEventListener('focusout', stop, true);
    return () => {
      document.removeEventListener('focusin', stop, true);
      document.removeEventListener('focusout', stop, true);
    };
  }, [open]);

  if (!open) return null;

  const close = () => setOpen(false);
  const pick = (e: EntitySummary) => {
    select(e.id);
    close();
  };

  const word = query.trim();
  const canFilter = word.length >= SEARCH_FILTER_MIN;
  /** Keep the word as a filter. An open entity would hold the map on its own
   *  relations, so it is closed. */
  const applyFilter = () => {
    if (!canFilter) return;
    void clearSelection();
    void setFilter(word);
    close();
  };

  const toggleGroup = (g: EntityGroup) =>
    setGroups((prev) =>
      prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g],
    );

  const onInputKey = (e: ReactKeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, FILTER_ROW));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (active !== FILTER_ROW && results[active]) pick(results[active]);
      else applyFilter();
    }
  };

  return (
    <div
      ref={rootRef}
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 pt-3 backdrop-blur-sm md:pt-[12vh]"
      onClick={close}
    >
      <div
        className="mx-4 w-full max-w-xl overflow-hidden rounded-xl border bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Input */}
        <div className="flex items-center gap-2.5 border-b px-3.5">
          <Search size={17} className="flex-none text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKey}
            placeholder="Search places, polities, events…"
            // Focused in the tap's own render, so phones raise the keyboard;
            // 16px on phones, or iOS zooms the page on focus.
            autoFocus
            enterKeyHint="search"
            className="h-12 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground md:text-sm"
          />
          <button
            type="button"
            onClick={close}
            className="grid size-6 flex-none place-items-center rounded text-muted-foreground hover:bg-muted"
            aria-label="Close"
          >
            <X size={15} />
          </button>
        </div>

        {/* Group facets */}
        <div className="flex flex-wrap gap-1.5 border-b px-3 py-2">
          <button
            type="button"
            onClick={() => setGroups([])}
            className={cn(
              'rounded-full border px-2.5 py-1 text-xs font-medium',
              groups.length === 0
                ? 'border-transparent bg-foreground text-background'
                : 'text-muted-foreground',
            )}
          >
            All
          </button>
          {GROUP_ORDER.map((g) => {
            const on = groups.includes(g);
            const m = GROUPS[g];
            return (
              <button
                key={g}
                type="button"
                onClick={() => toggleGroup(g)}
                className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium"
                style={
                  on
                    ? { background: m.soft, color: m.color, borderColor: 'transparent' }
                    : { color: 'var(--muted-foreground)' }
                }
              >
                <span className="size-[7px] rounded-full" style={{ background: m.color }} />
                {m.label}
              </button>
            );
          })}
        </div>

        {/* Results — fixed height so the modal doesn't resize once results load */}
        <div className="h-[40dvh] overflow-y-auto p-1.5 md:h-[50vh]">
          {debounced.length === 0 ? (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              Type to search History Mapped…
            </p>
          ) : results.length === 0 && !isFetching ? (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">
              No results for “{debounced}”.
            </p>
          ) : null}
          {canFilter && (
            <button
              type="button"
              onClick={applyFilter}
              onMouseMove={() => setActive(FILTER_ROW)}
              className={cn(
                'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm',
                active === FILTER_ROW ? 'bg-muted' : 'hover:bg-muted/50',
              )}
            >
              <Filter size={15} className="flex-none text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate">
                Show everything matching <b className="font-medium">“{word}”</b> on the map
              </span>
              <Kbd>↵</Kbd>
            </button>
          )}
          {debounced.length > 0 &&
            results.map((e, i) => (
              <ResultRow
                key={e.id}
                e={e}
                active={i === active}
                onPick={() => pick(e)}
                onHover={() => setActive(i)}
              />
            ))}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 border-t px-3.5 py-2 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <Kbd>↑</Kbd>
            <Kbd>↓</Kbd> navigate
          </span>
          <span className="flex items-center gap-1">
            <CornerDownLeft size={12} /> filter / open
          </span>
          <span className="flex items-center gap-1">
            <Kbd>esc</Kbd> close
          </span>
          {data && (
            <span className="ml-auto font-mono">
              {data.meta.total.toLocaleString()}
              {data.meta.total_capped ? '+' : ''} matches
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

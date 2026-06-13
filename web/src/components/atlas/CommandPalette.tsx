import { CornerDownLeft, MapPin, Search, X } from 'lucide-react';
import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { GroupBadge, GroupDot } from '@/components/atlas/GroupBadge';
import { useCommandPalette, useEntitySearch, useSelection } from '@/hooks';
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

/**
 * Command palette (⌘K). A comprehensive, global entity search — independent of
 * the map viewport and the sidebar's filters — with group facets and full
 * keyboard navigation.
 */
export function CommandPalette() {
  const { open, setOpen } = useCommandPalette();
  const { select } = useSelection();
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState('');
  const [groups, setGroups] = useState<EntityGroup[]>([]); // empty = all
  const [active, setActive] = useState(0);

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
      setActive(0);
      const id = requestAnimationFrame(() => inputRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
    setQuery('');
  }, [open]);

  useEffect(() => setActive(0), [debounced, groups]);

  if (!open) return null;

  const close = () => setOpen(false);
  const pick = (e: EntitySummary) => {
    select(e.id);
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
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === 'Enter' && results[active]) {
      e.preventDefault();
      pick(results[active]);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 pt-[12vh] backdrop-blur-sm"
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
            className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
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

        {/* Results */}
        <div className="max-h-[50vh] overflow-y-auto p-1.5">
          {debounced.length === 0 ? (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              Type to search the atlas…
            </p>
          ) : results.length === 0 && !isFetching ? (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              No results for “{debounced}”.
            </p>
          ) : (
            results.map((e, i) => (
              <ResultRow
                key={e.id}
                e={e}
                active={i === active}
                onPick={() => pick(e)}
                onHover={() => setActive(i)}
              />
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 border-t px-3.5 py-2 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <Kbd>↑</Kbd>
            <Kbd>↓</Kbd> navigate
          </span>
          <span className="flex items-center gap-1">
            <CornerDownLeft size={12} /> open
          </span>
          <span className="flex items-center gap-1">
            <Kbd>esc</Kbd> close
          </span>
          {data && (
            <span className="ml-auto font-mono">{data.meta.total} matches</span>
          )}
        </div>
      </div>
    </div>
  );
}

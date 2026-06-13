import { Clock, MapPin, Search, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { GroupBadge, GroupDot } from '@/components/atlas/GroupBadge';
import {
  useEntityList,
  useFilters,
  usePrefetchEntity,
  useSelection,
  useTimeState,
} from '@/hooks';
import { formatTime, formatYear } from '@/lib/format';
import { GROUPS, GROUP_ORDER } from '@/lib/groups';
import type { EntitySummary } from '@/lib/schemas/entity';

/** Group filter chips — wired to the URL `g` param via useFilters. */
function FilterChips() {
  const { isActive, toggle } = useFilters();
  return (
    <div className="flex flex-wrap gap-1.5">
      {GROUP_ORDER.map((g) => {
        const on = isActive(g);
        const m = GROUPS[g];
        return (
          <button
            key={g}
            type="button"
            onClick={() => toggle(g)}
            className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
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
  );
}

/** Three-bar prominence indicator from an impact score (0–100). */
function Prominence({ score }: { score: number | null }) {
  const tier = score == null ? 0 : score < 34 ? 1 : score < 67 ? 2 : 3;
  return (
    <span className="flex items-end gap-0.5" title="Prominence in this period & scope">
      {[0, 1, 2].map((i) => (
        <i
          key={i}
          className="w-[3px] rounded-sm"
          style={{
            height: 4 + i * 3,
            background: i < tier ? 'var(--foreground)' : 'var(--border)',
          }}
        />
      ))}
    </span>
  );
}

/** Number → "490 BCE"; date string → returned as-is; null → null. */
function yearText(v: number | string | null): string | null {
  if (v == null) return null;
  return typeof v === 'number' ? formatYear(v) : v;
}

function spanLabel(e: EntitySummary): string {
  if (e.temporal_display_range) return e.temporal_display_range;
  if (e.era_label) return e.era_label;
  const s = yearText(e.temporal_start);
  const end = yearText(e.temporal_end);
  if (s && end) return `${s} – ${end}`;
  return s ?? end ?? '—';
}

function ListRow({ e }: { e: EntitySummary }) {
  const { sel, select } = useSelection();
  const prefetch = usePrefetchEntity();
  return (
    <button
      type="button"
      onClick={() => select(e.id)}
      onMouseEnter={() => prefetch(e.id)}
      className={`flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left transition-colors ${
        sel === e.id ? 'bg-muted' : 'hover:bg-muted/60'
      }`}
    >
      <GroupDot group={e.entity_group} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{e.name}</span>
        <span className="mt-1 flex items-center gap-2">
          <GroupBadge group={e.entity_group} />
          <span className="truncate font-mono text-[11px] text-muted-foreground">
            {spanLabel(e)}
          </span>
        </span>
      </span>
      <Prominence score={e.impact_score} />
    </button>
  );
}

/** "Notable here" entities tab — ranked list with filter chips and scope note. */
export function BrowseTab() {
  const { data, isLoading, isError } = useEntityList({ sort: 'impact' });
  const { time } = useTimeState();
  const [filter, setFilter] = useState('');

  const items = (data?.data ?? []).filter((e) =>
    e.name.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="flex flex-col">
      <div className="space-y-3 p-4">
        <div className="relative">
          <Search
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter within view…"
            className="h-9 w-full rounded-lg border bg-card pl-8 pr-3 text-[13px] outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
          />
        </div>
        <FilterChips />
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <Clock size={12} /> {formatTime(time)}
          <span className="opacity-50">·</span>
          <MapPin size={12} /> current view
        </div>
      </div>

      <div className="h-px bg-border" />

      <div className="flex items-center justify-between px-4 py-2.5">
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Sparkles size={13} /> Notable here
        </span>
        {data && (
          <span className="font-mono text-[11px] text-muted-foreground">
            top {Math.min(items.length, data.meta.per_page)}
          </span>
        )}
      </div>

      {isLoading && <p className="px-4 py-2 text-sm text-muted-foreground">Loading…</p>}
      {isError && (
        <p className="px-4 py-2 text-sm text-destructive">Could not load entities.</p>
      )}

      <div className="space-y-0.5 px-2 pb-3">
        {items.map((e) => (
          <ListRow key={e.id} e={e} />
        ))}
      </div>
    </div>
  );
}

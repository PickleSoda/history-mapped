import { useState } from 'react';
import type { ReactNode } from 'react';
import { formatYear } from '@/lib/format';
import { toggled } from '@/lib/graph';
import type { Facet, GraphFilter, YearRange } from '@/lib/graph';
import { GROUPS } from '@/lib/groups';
import { cn } from '@/lib/utils';
import type { EntityGroup } from '@/types/atlas';

/** Relationship type → chip label. */
export const relLabel = (t: string | null) => (t ?? 'untyped').replace(/_/g, ' ');

/** How many type chips show before "+N more". */
const TYPE_CHIPS = 8;

/** A toggle chip. `on` = the facet is shown (aria-pressed). */
function Chip({
  on,
  onClick,
  count,
  dot,
  children,
}: {
  on: boolean;
  onClick: () => void;
  count?: number;
  dot?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'inline-flex h-6 flex-none items-center gap-1.5 rounded-full border px-2 text-[11px] capitalize transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring',
        on
          ? 'border-transparent bg-muted text-foreground hover:bg-accent'
          : 'border-dashed text-muted-foreground/70 line-through decoration-muted-foreground/40 hover:text-foreground',
      )}
    >
      {dot && (
        <span
          className={cn('size-[7px] flex-none rounded-full', !on && 'opacity-40')}
          style={{ background: dot }}
        />
      )}
      {children}
      {count != null && (
        <span className="font-mono text-[10px] text-muted-foreground no-underline">{count}</span>
      )}
    </button>
  );
}

/** Two thumbs on one track (two overlaid native range inputs, so both stay
 *  keyboard-operable). `value` null = the whole extent. */
function YearRangeControl({
  extent,
  value,
  onChange,
}: {
  extent: YearRange;
  value: YearRange | null;
  onChange: (next: YearRange | null) => void;
}) {
  const v = value ?? extent;
  const span = Math.max(1, extent.to - extent.from);
  const pct = (y: number) => ((y - extent.from) / span) * 100;
  const commit = (from: number, to: number) =>
    onChange(from <= extent.from && to >= extent.to ? null : { from, to });
  const thumb =
    'pointer-events-none absolute inset-0 h-full w-full appearance-none bg-transparent ' +
    '[&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:size-3.5 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-card [&::-webkit-slider-thumb]:bg-foreground [&::-webkit-slider-thumb]:shadow ' +
    '[&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:size-3 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-card [&::-moz-range-thumb]:bg-foreground ' +
    'focus-visible:outline-none [&:focus-visible::-webkit-slider-thumb]:ring-2 [&:focus-visible::-webkit-slider-thumb]:ring-ring';
  return (
    <div className="flex min-w-[220px] flex-1 items-center gap-2.5">
      <span className="w-[68px] flex-none text-right font-mono text-[10px] text-muted-foreground">
        {formatYear(v.from)}
      </span>
      <div className="relative h-4 flex-1">
        <span className="absolute inset-x-0 top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-border" />
        <span
          className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-foreground/70"
          style={{ left: `${pct(v.from)}%`, right: `${100 - pct(v.to)}%` }}
        />
        <input
          type="range"
          aria-label="Relations from year"
          aria-valuetext={formatYear(v.from)}
          min={extent.from}
          max={extent.to}
          value={v.from}
          onChange={(e) => commit(Math.min(Number(e.target.value), v.to), v.to)}
          className={thumb}
        />
        <input
          type="range"
          aria-label="Relations to year"
          aria-valuetext={formatYear(v.to)}
          min={extent.from}
          max={extent.to}
          value={v.to}
          onChange={(e) => commit(v.from, Math.max(Number(e.target.value), v.from))}
          className={thumb}
        />
      </div>
      <span className="w-[68px] flex-none font-mono text-[10px] text-muted-foreground">
        {formatYear(v.to)}
      </span>
    </div>
  );
}

/** The graph's filter controls: relationship-type chips, entity-group chips,
 *  the year window and (chronicles) the external toggle. Pure view over a
 *  `GraphFilter` — it never refetches. */
export function GraphFilterBar({
  filter,
  onChange,
  types,
  groups,
  extent,
  externalToggle,
}: {
  filter: GraphFilter;
  onChange: (next: GraphFilter) => void;
  types: Facet[];
  groups: Facet<EntityGroup>[];
  extent: YearRange | null;
  externalToggle?: boolean;
}) {
  const [allTypes, setAllTypes] = useState(false);
  // Keep a hidden type visible as a chip even when it's past the cut-off.
  const shownTypes = allTypes
    ? types
    : types.filter((t, i) => i < TYPE_CHIPS || filter.hiddenTypes.has(t.key));
  const more = types.length - shownTypes.length;

  return (
    <div className="space-y-2" role="group" aria-label="Graph filters">
      {types.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Relations
          </span>
          {shownTypes.map((t) => (
            <Chip
              key={t.key}
              on={!filter.hiddenTypes.has(t.key)}
              count={t.count}
              onClick={() => onChange({ ...filter, hiddenTypes: toggled(filter.hiddenTypes, t.key) })}
            >
              {relLabel(t.key)}
            </Chip>
          ))}
          {(more > 0 || allTypes) && types.length > TYPE_CHIPS && (
            <button
              type="button"
              onClick={() => setAllTypes((v) => !v)}
              className="h-6 rounded-full px-2 text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              {allTypes ? 'Fewer' : `+${more} more`}
            </button>
          )}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {groups.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Kinds
            </span>
            {groups.map((g) => (
              <Chip
                key={g.key}
                on={!filter.hiddenGroups.has(g.key)}
                count={g.count}
                dot={GROUPS[g.key].color}
                onClick={() =>
                  onChange({ ...filter, hiddenGroups: toggled(filter.hiddenGroups, g.key) })
                }
              >
                {GROUPS[g.key].label}
              </Chip>
            ))}
            {externalToggle && (
              <Chip on={filter.external} onClick={() => onChange({ ...filter, external: !filter.external })}>
                Outside the chronicle
              </Chip>
            )}
          </div>
        )}
        {extent && extent.to > extent.from && (
          <YearRangeControl
            extent={extent}
            value={filter.years}
            onChange={(years) => onChange({ ...filter, years })}
          />
        )}
      </div>
    </div>
  );
}

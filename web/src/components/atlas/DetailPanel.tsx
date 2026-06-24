import { Clock, FileText, MapPin, ScrollText, Sparkles, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useEffect, useMemo, useRef } from 'react';
import type { ReactNode } from 'react';
import { GroupDot, TypeBadge } from '@/components/atlas/GroupBadge';
import {
  useChronicleNav,
  useEntity,
  useEntityChronicles,
  useEntityConnections,
  useMapFocus,
  useSelection,
  useTimeState,
} from '@/hooks';
import { formatYear } from '@/lib/format';
import { GROUPS } from '@/lib/groups';
import type { EntityDetail, Relationship } from '@/lib/schemas/entity';
import { cn } from '@/lib/utils';

/** A compact icon pill; a button when `onClick` is given, else static text. */
function Pill({
  icon: Icon,
  className,
  onClick,
  title,
  children,
}: {
  icon: LucideIcon;
  className: string;
  onClick?: () => void;
  title?: string;
  children: ReactNode;
}) {
  const cls = cn(
    'inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px]',
    onClick && 'transition-opacity hover:opacity-80',
    className,
  );
  if (onClick) {
    return (
      <button type="button" onClick={onClick} title={title} className={cls}>
        <Icon size={13} /> {children}
      </button>
    );
  }
  return (
    <span className={cls} title={title}>
      <Icon size={13} /> {children}
    </span>
  );
}

/** A year (number) or raw date string → display text. */
function yearText(v: number | string | null): string | null {
  if (v == null) return null;
  return typeof v === 'number' ? formatYear(v) : v;
}

/** Extract a numeric year from a year number or a date string (null if none). */
function numericYear(v: number | string | null): number | null {
  if (typeof v === 'number') return v;
  if (typeof v === 'string') {
    const m = v.match(/-?\d{1,6}/);
    if (m) return parseInt(m[0], 10);
  }
  return null;
}

/** Numeric sort key for a relationship's start (unknown → sorts last). */
function relStart(rel: Relationship): number {
  const v = rel.temporal_start;
  if (typeof v === 'number') return v;
  if (typeof v === 'string') {
    const m = v.match(/-?\d{1,6}/);
    if (m) return parseInt(m[0], 10);
  }
  return Number.POSITIVE_INFINITY;
}

function temporalText(d: EntityDetail): string | null {
  if (d.temporal_display_range) return d.temporal_display_range;
  const s = yearText(d.temporal_start);
  const e = yearText(d.temporal_end);
  if (s && e) return `${s} – ${e}`;
  return s ?? e ?? d.era_label ?? null;
}

/** Pick the entity on the far side of a relationship from the selected one. */
function otherSide(rel: Relationship, selfId: string) {
  return rel.source_entity_id === selfId ? rel.target_entity : rel.source_entity;
}

/** Vertical timeline of the entity's relationships, ordered by start year. Rows
 *  carry a chronicle badge when the relationship is part of a chronicle. */
function RelationshipTimeline({
  rels,
  selfId,
  relChronicle,
}: {
  rels: Relationship[];
  selfId: string;
  relChronicle: Map<string, { title: string; slug: string }>;
}) {
  const { select } = useSelection();
  const { enter } = useChronicleNav();
  const sorted = useMemo(
    () => [...rels].sort((a, b) => relStart(a) - relStart(b)),
    [rels],
  );

  return (
    <div className="relative pl-5">
      <span className="absolute bottom-2 left-2 top-2 w-px bg-border" />
      <div className="space-y-3">
        {sorted.map((rel) => {
          const other = otherSide(rel, selfId);
          const year = yearText(rel.temporal_start);
          const chronicle = relChronicle.get(rel.id);
          return (
            <div key={rel.id} className="relative">
              <span
                className="absolute -left-[15px] top-1.5 size-2.5 rounded-full border-2 border-card"
                style={{
                  background: other ? GROUPS[other.entity_group].color : 'var(--border)',
                }}
              />
              <div className="flex items-center gap-2">
                {year && (
                  <span className="font-mono text-[10px] text-muted-foreground">{year}</span>
                )}
                {rel.relationship_type && (
                  <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                    {rel.relationship_type.replace(/_/g, ' ')}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => other && select(other.id)}
                disabled={!other}
                className="mt-0.5 flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left hover:bg-muted/60 disabled:cursor-default"
              >
                {other ? (
                  <GroupDot group={other.entity_group} />
                ) : (
                  <span className="size-[7px]" />
                )}
                <span className="min-w-0 flex-1 truncate text-[13px]">
                  {other?.name ?? '—'}
                </span>
                {other && (
                  <TypeBadge group={other.entity_group} type={other.entity_type} />
                )}
              </button>
              {rel.description && (
                <p className="ml-1.5 mt-1 text-[12px] leading-snug text-foreground/70">
                  {rel.description}
                </p>
              )}
              {chronicle && (
                <button
                  type="button"
                  onClick={() => enter(chronicle.slug)}
                  className="ml-1.5 mt-1 inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
                  title="Open chronicle"
                >
                  <ScrollText size={11} /> {chronicle.title}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Chrome-less detail body — shared by the desktop aside and the mobile sheet.
 *  Reads the selection itself; renders nothing when nothing is selected. */
export function DetailPanelContent() {
  const { sel } = useSelection();
  const { enter } = useChronicleNav();
  const { data: entity, isLoading, isError } = useEntity(sel);
  const { data: connections } = useEntityConnections(sel);
  const { data: chronicles } = useEntityChronicles(sel);
  const { focusGeometries } = useMapFocus();
  const { setInstant } = useTimeState();

  // Frame the entity on the map the first time its detail opens (once per
  // selection — re-renders or a re-fetch must not yank the camera back).
  const focusedRef = useRef<string | null>(null);
  useEffect(() => {
    if (entity?.id && entity.geom != null && focusedRef.current !== entity.id) {
      focusedRef.current = entity.id;
      focusGeometries([entity.geom]);
    }
  }, [entity?.id, entity?.geom, focusGeometries]);

  // relationship id → chronicle (first match wins).
  const relChronicle = useMemo(() => {
    const m = new Map<string, { title: string; slug: string }>();
    chronicles?.data.forEach((c) =>
      c.relationship_ids.forEach((rid) => {
        if (!m.has(rid)) m.set(rid, { title: c.title, slug: c.slug });
      }),
    );
    return m;
  }, [chronicles]);

  if (!sel) return null;

  // The year the date pill jumps the timeline to (entity's start, else end).
  const startYear = entity
    ? (numericYear(entity.temporal_start) ?? numericYear(entity.temporal_end))
    : null;

  return (
    <>
      {isLoading && <p className="px-4 py-3 text-sm text-muted-foreground">Loading…</p>}
      {isError && (
        <p className="px-4 py-3 text-sm text-destructive">Could not load entity.</p>
      )}

      {entity && (
        <>
          {/* Title block */}
          <div className="px-4 pb-4">
            <TypeBadge group={entity.entity_group} type={entity.entity_type} />
            <h2 className="mt-3 text-lg font-semibold leading-tight">{entity.name}</h2>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {temporalText(entity) && (
                <Pill
                  icon={Clock}
                  className="bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300"
                  onClick={startYear != null ? () => setInstant(startYear) : undefined}
                  title={startYear != null ? 'Jump the timeline to this date' : undefined}
                >
                  <span className="font-mono">{temporalText(entity)}</span>
                </Pill>
              )}
              {entity.geom != null ? (
                <Pill
                  icon={MapPin}
                  className="bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  onClick={() => focusGeometries([entity.geom])}
                  title="Focus on map"
                >
                  {entity.location_name ?? 'Show on map'}
                </Pill>
              ) : (
                <Pill
                  icon={MapPin}
                  className="bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                >
                  Not placed on map
                </Pill>
              )}
              {entity.impact_score != null && (
                <Pill
                  icon={Sparkles}
                  className="bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300"
                  title="Impact score"
                >
                  Impact {entity.impact_score}
                </Pill>
              )}
            </div>

            {/* Chronicle membership */}
            {chronicles && chronicles.data.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {chronicles.data.map((c) => (
                  <button
                    key={c.chronicle_id}
                    type="button"
                    onClick={() => enter(c.slug)}
                    className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-[11px] hover:bg-muted/70"
                    title="Open this chronicle"
                  >
                    <ScrollText size={12} /> {c.title}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Summary */}
          {(entity.summary || entity.significance) && (
            <>
              <div className="h-px bg-border" />
              <div className="px-4 py-4">
                <h4 className="mb-2 text-xs font-semibold text-muted-foreground">
                  Summary
                </h4>
                <p className="text-[13px] leading-relaxed text-foreground/90">
                  {entity.summary ?? entity.significance}
                </p>
              </div>
            </>
          )}

          {/* Relationships timeline */}
          {connections && connections.data.length > 0 && (
            <>
              <div className="h-px bg-border" />
              <div className="px-4 py-4">
                <h4 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                  Relationships
                  <span className="rounded-full bg-muted px-1.5 py-0.5 font-mono text-[10px]">
                    {connections.data.length}
                  </span>
                </h4>
                <RelationshipTimeline
                  rels={connections.data}
                  selfId={entity.id}
                  relChronicle={relChronicle}
                />
              </div>
            </>
          )}

          <div className="mt-auto flex items-center gap-1.5 border-t px-4 py-3 text-[11px] text-muted-foreground">
            <FileText size={13} /> sources
          </div>
        </>
      )}
    </>
  );
}

/** Desktop right aside: chrome + the shared content. */
export function DetailPanel() {
  const { sel, clear } = useSelection();
  if (!sel) return null;
  return (
    <aside className="flex h-full w-[380px] max-w-[90vw] flex-none flex-col overflow-y-auto border-l bg-card">
      <div className="flex items-center justify-between px-3 py-2.5">
        <span className="px-1.5 text-xs font-medium text-muted-foreground">Detail</span>
        <button
          type="button"
          onClick={clear}
          className="grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-muted"
          aria-label="Close detail"
        >
          <X size={16} />
        </button>
      </div>
      <DetailPanelContent />
    </aside>
  );
}

import { Clock, FileText, Maximize2, MapPin, ScrollText, Sparkles, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useEffect, useMemo, useRef } from 'react';
import type { ReactNode } from 'react';
import { preloadEntityPage } from '@/components/atlas/FullPage';
import { TypeBadge } from '@/components/atlas/GroupBadge';
import {
  chronicleByRelationship,
  RelationshipTimeline,
} from '@/components/atlas/RelationshipTimeline';
import {
  useChronicleNav,
  useEntity,
  useEntityChronicles,
  useEntityConnections,
  useFullPage,
  useMapFocus,
  useSelection,
  useTimeState,
} from '@/hooks';
import { numericYear, temporalText } from '@/lib/entity-format';
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
  const relChronicle = useMemo(() => chronicleByRelationship(chronicles?.data), [chronicles]);

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
            <h2 className="mt-3 font-heading text-xl font-semibold leading-tight">
              {entity.name}
            </h2>
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
                <h4 className="mb-2 text-xs font-semibold font-heading text-muted-foreground">
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
                <h4 className="mb-3 flex items-center gap-1.5 text-xs font-semibold font-heading text-muted-foreground">
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
  const { expand } = useFullPage();
  if (!sel) return null;
  return (
    <aside className="flex h-full w-[380px] max-w-[90vw] flex-none flex-col overflow-y-auto border-l bg-card">
      <div className="flex items-center justify-between px-3 py-2.5">
        <span className="px-1.5 text-xs font-medium text-muted-foreground">Detail</span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={expand}
            onPointerEnter={preloadEntityPage}
            onFocus={preloadEntityPage}
            className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            title="Open the full page"
          >
            <Maximize2 size={14} /> Expand
          </button>
          <button
            type="button"
            onClick={clear}
            className="grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-muted"
            aria-label="Close detail"
          >
            <X size={16} />
          </button>
        </div>
      </div>
      <DetailPanelContent />
    </aside>
  );
}

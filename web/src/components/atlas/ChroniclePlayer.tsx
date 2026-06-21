import { ChevronLeft, MoveRight, Route } from 'lucide-react';
import { useEffect } from 'react';
import { GroupDot } from '@/components/atlas/GroupBadge';
import { useChronicle, useChronicleNav, useSelection, useTimeState } from '@/hooks';
import { formatYear } from '@/lib/format';
import type { ChronicleEntry } from '@/lib/schemas/chronicle';
import type { Relationship } from '@/lib/schemas/entity';
import { cn } from '@/lib/utils';

type SecondaryEntity = NonNullable<ChronicleEntry['secondary_entities']>[number];

/** Entities attached to the step (chronicle entry's secondary entities). */
function StepEntities({ entities }: { entities: SecondaryEntity[] }) {
  const { select } = useSelection();
  return (
    <div className="mt-4">
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        Entities in this step
      </h4>
      <div className="space-y-0.5">
        {entities.map((e) => (
          <button
            key={e.entity_id}
            type="button"
            onClick={() => select(e.entity_id)}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-muted/60"
          >
            <span className="size-1.5 flex-none rounded-full bg-muted-foreground/60" />
            <span className="min-w-0 flex-1 truncate">{e.name}</span>
            {e.role && (
              <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                {e.role.replace(/_/g, ' ')}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

/** "What changed here" — the step's primary relationship, source → target. */
function WhatChanged({ rel }: { rel: Relationship }) {
  const { select } = useSelection();
  const src = rel.source_entity;
  const tgt = rel.target_entity;
  if (!src && !tgt) return null;
  return (
    <div className="mt-4 rounded-lg border bg-muted/40 p-3">
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        What changed
      </h4>
      <div className="flex items-center gap-2 text-[13px]">
        {src && (
          <button
            type="button"
            onClick={() => select(src.id)}
            className="inline-flex min-w-0 items-center gap-1.5 hover:underline"
          >
            <GroupDot group={src.entity_group} />
            <span className="truncate">{src.name}</span>
          </button>
        )}
        <span className="flex flex-none items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          {rel.relationship_type && (
            <span>{rel.relationship_type.replace(/_/g, ' ')}</span>
          )}
          <MoveRight size={12} />
        </span>
        {tgt && (
          <button
            type="button"
            onClick={() => select(tgt.id)}
            className="inline-flex min-w-0 items-center gap-1.5 hover:underline"
          >
            <GroupDot group={tgt.entity_group} />
            <span className="truncate">{tgt.name}</span>
          </button>
        )}
      </div>
      {rel.description && (
        <p className="mt-2 text-[12px] leading-relaxed text-foreground/80">
          {rel.description}
        </p>
      )}
    </div>
  );
}

/** Chrome-less chronicle body — shared by the desktop aside and the mobile sheet. */
export function ChroniclePlayerContent() {
  const { chron, step, next, prev, goto } = useChronicleNav();
  const { data, isLoading, isError } = useChronicle(chron);
  const { setInstant } = useTimeState();

  const entries = data?.entries ?? [];
  const total = entries.length;
  const current = entries[step];

  useEffect(() => {
    if (current?.start_year != null) setInstant(current.start_year);
  }, [current?.entry_id, current?.start_year, setInstant]);

  return (
    <div className="flex h-full flex-col">
      {isLoading && <p className="p-4 text-sm text-muted-foreground">Loading…</p>}
      {isError && (
        <p className="p-4 text-sm text-destructive">Could not load chronicle.</p>
      )}

      {data && (
        <>
          <div className="px-4 pt-4">
            <h2 className="text-base font-semibold leading-tight">{data.title}</h2>
            <div className="mt-2 flex items-center gap-2">
              <span className="font-mono text-[11px] text-muted-foreground">
                Step {Math.min(step + 1, total)} / {total}
              </span>
              <div className="flex flex-1 flex-wrap gap-1">
                {entries.map((e, i) => (
                  <button
                    key={e.entry_id}
                    type="button"
                    onClick={() => goto(i)}
                    aria-label={`Step ${i + 1}`}
                    className={cn(
                      'h-1.5 rounded-full transition-all',
                      i === step
                        ? 'w-4 bg-foreground'
                        : i < step
                          ? 'w-1.5 bg-foreground/50'
                          : 'w-1.5 bg-border',
                    )}
                  />
                ))}
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            {current?.start_year != null && (
              <p className="mb-2 font-mono text-[11px] text-muted-foreground">
                {formatYear(current.start_year)}
              </p>
            )}
            <p className="whitespace-pre-line text-[13px] leading-relaxed text-foreground/90">
              {current?.narrative_text ?? 'No narrative for this step.'}
            </p>
            {current?.primary_relationship && (
              <WhatChanged rel={current.primary_relationship} />
            )}
            {current?.secondary_entities && current.secondary_entities.length > 0 && (
              <StepEntities entities={current.secondary_entities} />
            )}
          </div>

          <div className="flex gap-2 border-t p-3">
            <button
              type="button"
              onClick={prev}
              disabled={step <= 0}
              className="inline-flex items-center gap-1 rounded-lg border bg-card px-3 py-2 text-[13px] font-medium hover:bg-muted disabled:opacity-40"
            >
              <ChevronLeft size={15} /> Prev
            </button>
            <button
              type="button"
              onClick={next}
              disabled={step >= total - 1}
              className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg bg-primary px-3 py-2 text-[13px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-40"
            >
              Next step
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Chronicle tour player. Takes over the left sidebar while a chronicle is
 * active (?chron=). Stepping bumps ?step= (back-button walks steps) and drives
 * the timeline year. (Map camera following is deferred with map integration.)
 */
export function ChroniclePlayer() {
  const { exit } = useChronicleNav();
  return (
    <aside className="flex h-full w-[380px] max-w-[90vw] flex-none flex-col border-l bg-card">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <button
          type="button"
          onClick={exit}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[13px] text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ChevronLeft size={15} /> Exit tour
        </button>
        <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">
          <Route size={12} /> Chronicle
        </span>
      </div>
      <ChroniclePlayerContent />
    </aside>
  );
}

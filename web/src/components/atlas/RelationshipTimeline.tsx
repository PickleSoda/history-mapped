import { ScrollText } from 'lucide-react';
import { useMemo } from 'react';
import { StarButton } from '@/components/account/SaveControls';
import { SuggestEditButton } from '@/components/account/SuggestEdit';
import { GroupDot, TypeBadge } from '@/components/atlas/GroupBadge';
import { useChronicleNav, useSelection, useStarState } from '@/hooks';
import { yearText } from '@/lib/entity-format';
import { GROUPS } from '@/lib/groups';
import type { EntityChronicleRef } from '@/lib/schemas/chronicle';
import type { Relationship } from '@/lib/schemas/entity';
import { cn } from '@/lib/utils';

/** relationship id → the chronicle it appears in (first match wins). */
export function chronicleByRelationship(
  chronicles: EntityChronicleRef[] | undefined,
): Map<string, { title: string; slug: string }> {
  const m = new Map<string, { title: string; slug: string }>();
  chronicles?.forEach((c) =>
    c.relationship_ids.forEach((rid) => {
      if (!m.has(rid)) m.set(rid, { title: c.title, slug: c.slug });
    }),
  );
  return m;
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

/** Pick the entity on the far side of a relationship from the selected one. */
function otherSide(rel: Relationship, selfId: string) {
  return rel.source_entity_id === selfId ? rel.target_entity : rel.source_entity;
}

/** A row's star + suggest-edit controls. On hover devices they stay hidden
 *  until the row is hovered or focused — unless the row is starred. */
function RowActions({ rel }: { rel: Relationship }) {
  const { starred } = useStarState('relationship', rel.id);
  const label = `${rel.source_entity?.name ?? '—'} → ${rel.target_entity?.name ?? '—'}`;
  return (
    <span
      className={cn(
        'ml-auto flex items-center',
        !starred &&
          '[@media(hover:hover)]:opacity-0 group-focus-within:opacity-100 group-hover:opacity-100',
      )}
    >
      <SuggestEditButton
        compact
        targetType="relationship"
        targetId={rel.id}
        field="description"
        fieldLabel="Description"
        targetLabel={label}
        currentText={rel.description ?? ''}
        label={rel.description ? undefined : 'Suggest a description'}
      />
      <StarButton dense type="relationship" id={rel.id} />
    </span>
  );
}

/** Vertical timeline of the entity's relationships, ordered by start year. Rows
 *  carry a chronicle badge when the relationship is part of a chronicle. */
export function RelationshipTimeline({
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
            <div key={rel.id} className="group relative">
              <span
                className="absolute -left-[15px] top-1.5 size-2.5 rounded-full border-2 border-card"
                style={{
                  background: other ? GROUPS[other.entity_group].color : 'var(--border)',
                }}
              />
              <div className="flex min-h-6 items-center gap-2">
                {year && (
                  <span className="font-mono text-[10px] text-muted-foreground">{year}</span>
                )}
                {rel.relationship_type && (
                  <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                    {rel.relationship_type.replace(/_/g, ' ')}
                  </span>
                )}
                <RowActions rel={rel} />
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

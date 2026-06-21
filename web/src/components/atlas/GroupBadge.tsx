import { GROUPS } from '@/lib/groups';
import { cn } from '@/lib/utils';
import type { EntityGroup } from '@/types/atlas';

/** Small colored dot for an entity group. */
export function GroupDot({
  group,
  className,
}: {
  group: EntityGroup;
  className?: string;
}) {
  return (
    <span
      className={cn('inline-block size-[7px] flex-none rounded-full', className)}
      style={{ background: GROUPS[group].color }}
    />
  );
}

/** Pill badge: dot + label, in the group's accent color on a soft background. */
export function GroupBadge({
  group,
  className,
}: {
  group: EntityGroup;
  className?: string;
}) {
  const g = GROUPS[group];
  return (
    <span
      className={cn(
        'inline-flex h-[21px] items-center gap-1.5 rounded-full px-2 text-[11px] font-medium whitespace-nowrap',
        className,
      )}
      style={{ background: g.soft, color: g.color }}
    >
      <span className="size-[7px] rounded-full" style={{ background: g.color }} />
      {g.label}
    </span>
  );
}

/** Pill badge labelled with the entity's specific type, coloured by its group —
 *  the colour carries the group, the text carries the type. Falls back to the
 *  group label when an entity has no type. */
export function TypeBadge({
  group,
  type,
  className,
}: {
  group: EntityGroup;
  type?: string | null;
  className?: string;
}) {
  const g = GROUPS[group];
  return (
    <span
      className={cn(
        'inline-flex h-[21px] items-center rounded-full px-2 text-[11px] font-medium whitespace-nowrap capitalize',
        className,
      )}
      style={{ background: g.soft, color: g.color }}
    >
      {type ? type.replace(/_/g, ' ') : g.label}
    </span>
  );
}

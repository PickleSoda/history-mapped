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

import { MoveRight } from 'lucide-react';
import { GROUP_ORDER, GROUPS } from '@/lib/groups';

/** Key to the graph's visual encoding. */
export function GraphLegend({ dimmed }: { dimmed?: boolean }) {
  const row = 'flex items-center gap-2';
  return (
    <div
      role="note"
      aria-label="Graph legend"
      className="pointer-events-auto w-[200px] rounded-xl border bg-popover/95 p-3 text-[11px] text-popover-foreground shadow-lg backdrop-blur"
    >
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Legend
      </p>
      <ul className="space-y-1">
        {GROUP_ORDER.map((g) => (
          <li key={g} className={row}>
            <span className="size-2.5 rounded-full" style={{ background: GROUPS[g].color }} />
            {GROUPS[g].label}
          </li>
        ))}
      </ul>
      <ul className="mt-2.5 space-y-1.5 border-t pt-2.5 text-muted-foreground">
        <li className={row}>
          <span className="flex w-6 items-end justify-center gap-0.5">
            <span className="size-1.5 rounded-full bg-muted-foreground" />
            <span className="size-3 rounded-full bg-muted-foreground" />
          </span>
          Size = impact
        </li>
        <li className={row}>
          <span className="flex w-6 justify-center">
            <MoveRight size={14} />
          </span>
          Direction of the relation
        </li>
        <li className={row}>
          <span className="flex w-6 justify-center">
            <span className="size-3 rounded-full border-2 border-foreground bg-muted-foreground" />
          </span>
          Centre of the graph
        </li>
        <li className={row}>
          <span className="flex w-6 justify-center">
            <span className="size-3 rounded-full border-[3px] border-double border-foreground bg-muted-foreground" />
          </span>
          Expanded
        </li>
        {dimmed && (
          <li className={row}>
            <span className="flex w-6 justify-center">
              <span className="size-3 rounded-full bg-muted-foreground opacity-40" />
            </span>
            Outside the chronicle
          </li>
        )}
      </ul>
      <p className="mt-2.5 border-t pt-2 text-muted-foreground">
        Ctrl/⌘ + scroll or pinch to zoom · drag to pan.
      </p>
    </div>
  );
}

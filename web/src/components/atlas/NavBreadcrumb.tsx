import { ChevronRight, Route } from 'lucide-react';
import { Fragment } from 'react';
import { useNavTrail } from '@/hooks';
import { GROUPS } from '@/lib/groups';
import { cn } from '@/lib/utils';
import type { EntityGroup } from '@/types/atlas';

/**
 * The navigation trail: where you've been across tours and entities, newest on
 * the right. Click any crumb to jump back to exactly that state (tour step and
 * all). Renders nothing until there's somewhere to go back to (≥2 crumbs).
 *
 * `variant`: a `bar` sits flush at the top of a panel (desktop sidebar / tour);
 * a `pill` floats with its own border + shadow (the mobile sheet).
 */
export function NavBreadcrumb({
  className,
  variant = 'bar',
}: {
  className?: string;
  variant?: 'bar' | 'pill';
}) {
  const { trail, goTo } = useNavTrail();
  if (trail.length < 2) return null;

  return (
    <nav
      aria-label="Navigation trail"
      className={cn(
        'flex max-w-full items-center gap-0.5 overflow-x-auto text-[12px]',
        variant === 'pill'
          ? 'rounded-lg border bg-card/95 px-1.5 py-1 shadow-sm backdrop-blur'
          : 'border-b px-2 py-1.5',
        className,
      )}
    >
      {trail.map((c, i) => {
        const isLast = i === trail.length - 1;
        const color = c.group ? GROUPS[c.group as EntityGroup]?.color : undefined;
        return (
          <Fragment key={c.key}>
            {i > 0 && (
              <ChevronRight size={13} className="flex-none text-muted-foreground/60" />
            )}
            <button
              type="button"
              onClick={() => goTo(i)}
              disabled={isLast}
              title={c.label}
              className={cn(
                'inline-flex max-w-[160px] flex-none items-center gap-1 rounded-md px-1.5 py-0.5 transition-colors',
                isLast
                  ? 'font-medium text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              {c.kind === 'chronicle' ? (
                <Route size={12} className="flex-none" />
              ) : (
                <span
                  className="size-[7px] flex-none rounded-full"
                  style={{ background: color ?? 'var(--muted-foreground)' }}
                />
              )}
              <span className="truncate">{c.label}</span>
            </button>
          </Fragment>
        );
      })}
    </nav>
  );
}

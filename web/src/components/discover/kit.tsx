/**
 * Shared pieces of the Discover cards (on this day, meanwhile, the daily
 * expedition, for you). Every card comes in two variants: `panel` in the
 * atlas sidebar and sheet (dense; actions drive the map in place) and `page`
 * on the browse page (roomier; actions are links into the atlas).
 */
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAtlasGo } from '@/hooks';
import type { AtlasGoTarget } from '@/hooks/useAtlasGo';
import { atlasHref } from '@/lib/site-links';
import { cn } from '@/lib/utils';

export type DiscoverVariant = 'panel' | 'page';

/** A titled card: icon, title, an optional note beside it and an optional footer. */
export function DiscoverCard({
  variant,
  icon: Icon,
  title,
  aside,
  footer,
  className,
  children,
}: {
  variant: DiscoverVariant;
  icon: LucideIcon;
  title: ReactNode;
  /** Small text at the right of the title (a date, a count, a streak). */
  aside?: ReactNode;
  footer?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={cn(
        'flex min-w-0 flex-col rounded-xl border bg-card',
        variant === 'panel' ? 'p-3' : 'p-4 shadow-xs',
        className,
      )}
    >
      <header className="mb-2 flex items-center gap-2">
        <Icon size={variant === 'panel' ? 14 : 16} className="flex-none text-muted-foreground" aria-hidden />
        <h3
          className={cn(
            'min-w-0 flex-1 truncate font-semibold',
            variant === 'panel' ? 'text-[13px]' : 'font-heading text-lg tracking-tight',
          )}
        >
          {title}
        </h3>
        {aside && <span className="flex-none font-mono text-[11px] text-muted-foreground">{aside}</span>}
      </header>
      <div className="min-w-0 flex-1">{children}</div>
      {footer && <footer className="mt-3 text-[12px] text-muted-foreground">{footer}</footer>}
    </section>
  );
}

/**
 * "Go there": in the atlas (`panel`) a button that moves the timeline, opens
 * the entity or flies to the point in place; on a site page (`page`) a link
 * into the atlas with the same entity and year.
 */
export function GoTo({ variant, ...rest }: GoToProps & { variant: DiscoverVariant }) {
  return variant === 'page' ? <GoLink {...rest} /> : <GoButton {...rest} />;
}

interface GoToProps {
  target: AtlasGoTarget;
  className?: string;
  title?: string;
  children: ReactNode;
}

/** On a site page: a link, so the atlas's own hooks are not needed there. */
function GoLink({ target, className, title, children }: GoToProps) {
  return (
    <Link to={atlasHref({ sel: target.id ?? null, year: target.year ?? null })} className={className} title={title}>
      {children}
    </Link>
  );
}

/** In the atlas: act on the map and the timeline in place. */
function GoButton({ target, className, title, children }: GoToProps) {
  const go = useAtlasGo();
  return (
    <button type="button" onClick={() => go(target)} className={cn('text-left', className)} title={title}>
      {children}
    </button>
  );
}

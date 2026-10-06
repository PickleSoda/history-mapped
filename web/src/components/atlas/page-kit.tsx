/**
 * Shared building blocks for the full pages (entity, chronicle): the scroll
 * frame with its sticky header, titled sections, and the stats-ledger cells.
 * Imported only by the lazy page chunks, so it ships with them.
 */
import { ChevronDown, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { createContext, useContext, useEffect, useId, useState } from 'react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export type PageVariant = 'page' | 'sheet';

interface FrameContext {
  /** The page's scroll container — the root for IntersectionObservers. */
  scrollRoot: HTMLElement | null;
  /** Register the hero title so the sticky header can name the page once it
   *  scrolls away. */
  setTitle: (el: HTMLElement | null) => void;
  variant: PageVariant;
}

const PageFrameContext = createContext<FrameContext>({
  scrollRoot: null,
  setTitle: () => {},
  variant: 'page',
});

/** The enclosing page's scroll container (null outside a page / pre-mount). */
export function useScrollRoot(): HTMLElement | null {
  return useContext(PageFrameContext).scrollRoot;
}

export function usePageVariant(): PageVariant {
  return useContext(PageFrameContext).variant;
}

/** The page's display title (h1); the frame watches it for the sticky header. */
export function PageTitle({ className, children }: { className?: string; children: ReactNode }) {
  const { setTitle } = useContext(PageFrameContext);
  return (
    <h1
      ref={setTitle}
      className={cn(
        'mt-4 text-balance font-heading text-[34px] font-semibold leading-[1.05] tracking-tight md:text-[46px]',
        className,
      )}
    >
      {children}
    </h1>
  );
}

/** Header action button. `compact` = icon only (label as aria-label). */
export function HeaderButton({
  icon: Icon,
  label,
  onClick,
  compact,
}: {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={compact ? label : undefined}
      title={label}
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-lg text-[12px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
        compact ? 'w-8 justify-center' : 'px-2.5',
      )}
    >
      <Icon size={15} />
      {!compact && label}
    </button>
  );
}

/**
 * Scrollable page with a sticky header (Collapse / Close) that names the page
 * once its title has scrolled out of view, over an optional colour wash.
 * `resetKey` scrolls back to the top when it changes (a new entity / chronicle).
 */
export function PageFrame({
  variant,
  name,
  accent,
  wash,
  resetKey,
  onCollapse,
  onClose,
  closeLabel = 'Close',
  children,
}: {
  variant: PageVariant;
  /** Shown in the sticky header after the title scrolls away. */
  name: string | null;
  /** Small dot colour next to the sticky name. */
  accent?: string | null;
  /** Soft colour washed down from the top of the page. */
  wash?: string | null;
  resetKey: string;
  onCollapse: () => void;
  onClose: () => void;
  closeLabel?: string;
  children: ReactNode;
}) {
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const [title, setTitle] = useState<HTMLElement | null>(null);
  const [titleHidden, setTitleHidden] = useState(false);
  const sheet = variant === 'sheet';

  useEffect(() => {
    scrollRoot?.scrollTo({ top: 0 });
  }, [resetKey, scrollRoot]);
  useEffect(() => {
    if (!scrollRoot || !title) return;
    const io = new IntersectionObserver(([e]) => setTitleHidden(!e.isIntersecting), {
      root: scrollRoot,
      rootMargin: '-56px 0px 0px 0px',
    });
    io.observe(title);
    return () => io.disconnect();
  }, [scrollRoot, title]);

  return (
    <PageFrameContext.Provider value={{ scrollRoot, setTitle, variant }}>
      <div className="flex h-full min-h-0 flex-col">
        <div ref={setScrollRoot} className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain">
          {wash && (
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 top-0 h-72"
              style={{ background: `linear-gradient(to bottom, ${wash}, transparent)` }}
            />
          )}

          <div
            className={cn(
              'sticky top-0 z-20 flex items-center gap-2 border-b bg-background/95 backdrop-blur',
              sheet ? 'h-12 px-3' : 'h-14 px-5 md:px-8',
              !titleHidden && 'border-transparent bg-transparent backdrop-blur-none',
            )}
          >
            <div
              className={cn(
                'flex min-w-0 flex-1 items-center gap-2 transition-opacity duration-200 motion-reduce:transition-none',
                titleHidden ? 'opacity-100' : 'opacity-0',
              )}
              aria-hidden={!titleHidden}
            >
              {name && (
                <>
                  {accent && <span className="size-2 flex-none rounded-full" style={{ background: accent }} />}
                  <span className="truncate font-heading text-[15px] font-semibold">{name}</span>
                </>
              )}
            </div>
            <HeaderButton icon={ChevronDown} label="Collapse" onClick={onCollapse} compact={sheet} />
            <HeaderButton icon={X} label={closeLabel} onClick={onClose} compact />
          </div>

          <article className={cn('relative mx-auto max-w-[1120px] pb-20', sheet ? 'px-4' : 'px-5 md:px-10')}>
            {children}
          </article>
        </div>
      </div>
    </PageFrameContext.Provider>
  );
}

/** Loading skeleton for a page's hero. */
export function PageSkeleton() {
  return (
    <div className="animate-pulse pt-8 motion-reduce:animate-none" aria-label="Loading">
      <div className="h-5 w-24 rounded-full bg-muted" />
      <div className="mt-5 h-10 w-2/3 rounded-lg bg-muted" />
      <div className="mt-6 h-20 rounded-xl bg-muted" />
    </div>
  );
}

/** A titled page section with a hairline rule running out to the right. */
export function Section({
  title,
  count,
  aside,
  className,
  children,
}: {
  title: string;
  count?: number;
  aside?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section aria-labelledby={id} className={cn('mt-12 first:mt-0', className)}>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h2 id={id} className="font-heading text-[17px] font-semibold tracking-tight">
          {title}
        </h2>
        {count != null && (
          <span className="rounded-full bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {count}
          </span>
        )}
        <span aria-hidden className="h-px min-w-6 flex-1 bg-border" />
        {aside}
      </div>
      {children}
    </section>
  );
}

/** The stats ledger: a hairline grid of `Stat` cells. */
export function StatGrid({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <dl
      className={cn(
        'mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-3 lg:grid-cols-6',
        className,
      )}
    >
      {children}
    </dl>
  );
}

/** One cell of the stats block: small-caps label over a value. */
export function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0 bg-card px-3.5 py-3">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 truncate text-[13px] font-medium">{children}</dd>
    </div>
  );
}

/** Impact 1–100 as a filled bar in an accent colour. */
export function ImpactMeter({ value, color }: { value: number; color: string }) {
  return (
    <span className="flex items-center gap-2" title={`Impact ${value} of 100`}>
      <span className="font-mono">{value}</span>
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <span
          className="block h-full rounded-full"
          style={{ width: `${Math.max(2, Math.min(100, value))}%`, background: color }}
        />
      </span>
    </span>
  );
}

/**
 * Layout pieces shared by the browse pages: the page shell, breadcrumbs,
 * section headers, calm empty / error notices, skeletons, "load more", tag
 * chips, the "Open on the globe" link and the paragraphs-and-links markdown.
 */
import { ChevronRight, Globe, Hash } from 'lucide-react';
import { Fragment } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { errorStatus } from '@/lib/api/errors';
import type { TagFacet } from '@/lib/schemas/tag';
import { FACETS } from '@/lib/tags';
import type { IndexedTag } from '@/lib/tags';
import { cn } from '@/lib/utils';
import { markdownParagraphs } from './browse-model';
import { browsePath, facetPath } from './links';

const TEXT_LINK = 'underline decoration-foreground/30 underline-offset-2 hover:decoration-foreground';

/** The page column: mobile-first gutter, a readable max width. */
export function BrowseShell({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn('mx-auto w-full max-w-5xl px-4 pt-6 pb-16 sm:pt-10', className)}>{children}</div>;
}

export interface Crumb {
  label: string;
  to?: string;
}

/** Browse › Region › Asia. The last crumb is the current page. */
export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-5 text-xs text-muted-foreground">
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((c, i) => (
          <li key={`${i}-${c.label}`} className="flex items-center gap-1">
            {i > 0 && <ChevronRight size={12} aria-hidden className="opacity-60" />}
            {c.to ? (
              <Link to={c.to} className="underline-offset-2 hover:text-foreground hover:underline">
                {c.label}
              </Link>
            ) : (
              <span aria-current="page" className="text-foreground/80">
                {c.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

/** Small uppercase label above a title ("Curated set", "Region"). */
export function Eyebrow({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <p
      className={cn(
        'flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase',
        className,
      )}
    >
      {children}
    </p>
  );
}

/** A page section with a Fraunces heading, an optional count, lede and action. */
export function BrowseSection({
  id,
  title,
  count,
  lede,
  action,
  className,
  children,
}: {
  id: string;
  title: string;
  count?: number | null;
  lede?: ReactNode;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className={cn('scroll-mt-20 border-t py-8 first:border-t-0', className)}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h2 id={id} className="font-heading text-2xl font-semibold tracking-tight">
            {title}
            {count != null && count > 0 && (
              <span className="ml-2 align-middle font-mono text-xs font-normal text-muted-foreground">
                {count.toLocaleString('en-US')}
              </span>
            )}
          </h2>
          {lede && <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{lede}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** A calm, dashed box for "nothing here" and "could not load". */
export function Notice({ title, children, action }: { title?: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div role="status" className="rounded-xl border border-dashed bg-muted/30 px-4 py-6 text-sm text-muted-foreground">
      {title && <p className="font-medium text-foreground">{title}</p>}
      {children && <div className={cn(title && 'mt-1')}>{children}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

/**
 * The notice for a failed query: a 404 reads as "nothing here yet" (the
 * endpoint may not be deployed yet; `missing` says more), anything else
 * offers a retry.
 */
export function QueryNotice({
  error,
  what,
  missing = 'Check back soon.',
  onRetry,
}: {
  error: unknown;
  what: string;
  missing?: string;
  onRetry?: () => void;
}) {
  const status = errorStatus(error);
  if (status === 404) return <Notice title="Nothing to show here yet.">{missing}</Notice>;
  return (
    <Notice
      title={`Could not load ${what}.`}
      action={
        onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        )
      }
    >
      {status === null ? 'Check your connection, or try again in a moment.' : 'Try again in a moment.'}
    </Notice>
  );
}

/** Placeholder cards while a list loads. */
export function CardSkeletons({
  count = 3,
  className,
  itemClassName,
}: {
  count?: number;
  className?: string;
  itemClassName?: string;
}) {
  return (
    <div className={cn('grid gap-3 sm:grid-cols-2 lg:grid-cols-3', className)} aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={cn('h-36 animate-pulse rounded-xl bg-muted/60', itemClassName)} />
      ))}
    </div>
  );
}

/** "Load more (24 of 1,259)". */
export function LoadMore({
  onClick,
  loading,
  shown,
  total,
}: {
  onClick: () => void;
  loading: boolean;
  shown: number;
  total?: number;
}) {
  return (
    <div className="mt-4 flex justify-center">
      <Button variant="outline" onClick={onClick} disabled={loading}>
        {loading
          ? 'Loading…'
          : total != null
            ? `Load more (${shown.toLocaleString('en-US')} of ${total.toLocaleString('en-US')})`
            : 'Load more'}
      </Button>
    </div>
  );
}

/** The facet's colour dot (a hash for open-ended topics). */
export function FacetMark({ facet, size = 7 }: { facet: TagFacet; size?: number }) {
  if (facet === 'topic') return <Hash size={size + 4} aria-hidden />;
  return (
    <span
      aria-hidden
      className="flex-none rounded-full"
      style={{ width: size, height: size, background: FACETS[facet].color }}
    />
  );
}

/** A tag as a chip linking to its browse page. */
export function TagChipLink({ tag, count, className }: { tag: IndexedTag; count?: number; className?: string }) {
  return (
    <Link
      to={facetPath(tag.facet, tag.slug)}
      title={tag.description ?? `${FACETS[tag.facet].label}: ${tag.name}`}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
        className,
      )}
    >
      <FacetMark facet={tag.facet} />
      {tag.name}
      {count != null && count > 0 && (
        <span className="font-mono text-[10px] opacity-60">{count.toLocaleString('en-US')}</span>
      )}
    </Link>
  );
}

/** Secondary "Open on the globe" link (the atlas at `/app`). */
export function GlobeLink({
  to,
  label = 'Open on the globe',
  className,
}: {
  to: string;
  label?: string;
  className?: string;
}) {
  return (
    <Link
      to={to}
      className={cn(
        'relative z-10 inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline',
        className,
      )}
    >
      <Globe size={13} aria-hidden />
      {label}
    </Link>
  );
}

/** A set description: paragraphs and links only (in-app links route, others
 *  open in a new tab; unsafe targets render as text). */
export function Markdown({ text, className }: { text: string | null | undefined; className?: string }) {
  const paragraphs = markdownParagraphs(text);
  if (paragraphs.length === 0) return null;
  return (
    <div className={cn('space-y-3', className)}>
      {paragraphs.map((segments, i) => (
        <p key={i}>
          {segments.map((s, j) =>
            s.type === 'text' ? (
              <Fragment key={j}>{s.text}</Fragment>
            ) : s.external ? (
              <a key={j} href={s.to} target="_blank" rel="noopener noreferrer" className={TEXT_LINK}>
                {s.text}
              </a>
            ) : (
              <Link key={j} to={s.to} className={TEXT_LINK}>
                {s.text}
              </Link>
            ),
          )}
        </p>
      ))}
    </div>
  );
}

/** The not-found state for an unknown tag or set, inside the site frame. */
export function BrowseNotFound({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <BrowseShell className="max-w-3xl">
      <Breadcrumbs items={[{ label: 'Browse', to: browsePath() }, { label: 'Not found' }]} />
      <h1 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
      {children && <div className="mt-3 text-muted-foreground">{children}</div>}
      <p className="mt-6">
        <Link to={browsePath()} className={cn('text-sm', TEXT_LINK)}>
          Back to Browse
        </Link>
      </p>
    </BrowseShell>
  );
}

/** Segmented control (sort orders, small filters). */
export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex items-center gap-0.5 rounded-lg bg-muted p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
            value === o.value ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** A row of toggle chips (kind filters). `null` is "All". */
export function FilterChips<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T | null;
  options: { value: T | null; label: string; count?: number }[];
  onChange: (v: T | null) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const active = value === o.value;
        return (
          <button
            key={o.value ?? '∅'}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors',
              active
                ? 'border-foreground/70 bg-foreground text-background'
                : 'bg-card text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            {o.label}
            {o.count != null && <span className="font-mono text-[10px] opacity-70">{o.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

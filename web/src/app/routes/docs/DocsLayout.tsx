import { Suspense } from 'react';
import { Link, Outlet, useMatch, useNavigate } from 'react-router-dom';
import { DOCS_INDEX_SLUG } from '@/content/docs/manifest';
import { docPath, docSections, findDoc } from '@/lib/docs/docs';
import { cn } from '@/lib/utils';
import { DocSkeleton } from './DocSkeleton';

/** The current doc's slug from the URL (`/docs` = the index). */
function useCurrentSlug(): string {
  const match = useMatch('/docs/:slug');
  return match?.params.slug ?? DOCS_INDEX_SLUG;
}

function DocsSidebar({ current }: { current: string }) {
  return (
    <nav aria-label="Documentation" className="space-y-6 text-sm">
      {docSections().map(({ section, pages }) => (
        <div key={section.id}>
          <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{section.title}</p>
          <ul className="space-y-0.5">
            {pages.map((page) => (
              <li key={page.slug}>
                <Link
                  to={docPath(page.slug)}
                  aria-current={page.slug === current ? 'page' : undefined}
                  className={cn(
                    'block rounded-md px-2.5 py-1.5 transition-colors',
                    page.slug === current
                      ? 'bg-muted font-medium text-foreground'
                      : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                  )}
                >
                  {page.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

/** Phones: the same list as a native select. */
function DocsPicker({ current }: { current: string }) {
  const navigate = useNavigate();
  return (
    <label className="block">
      <span className="sr-only">Documentation page</span>
      <select
        value={current}
        onChange={(event) => navigate(docPath(event.target.value))}
        className="h-10 w-full rounded-lg border bg-card px-3 text-sm"
      >
        {!findDoc(current) && (
          <option value={current} disabled>
            Choose a page
          </option>
        )}
        {docSections().map(({ section, pages }) => (
          <optgroup key={section.id} label={section.title}>
            {pages.map((page) => (
              <option key={page.slug} value={page.slug}>
                {page.title}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}

/**
 * `/docs` frame (spec 2026-11-01 public site, D5): the sections sidebar on
 * desktop, a page picker on phones, and the routed page.
 */
export function DocsLayout() {
  const current = useCurrentSlug();
  return (
    <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
      <div className="md:grid md:grid-cols-[13rem_minmax(0,1fr)] md:gap-10 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="hidden md:block">
          <div className="sticky top-[var(--site-header-height,0px)] max-h-[calc(100dvh-var(--site-header-height,0px))] overflow-y-auto py-8 pr-2">
            <DocsSidebar current={current} />
          </div>
        </aside>
        <div className="min-w-0 py-6 md:py-8">
          <div className="mb-6 md:hidden">
            <DocsPicker current={current} />
          </div>
          <Suspense fallback={<DocSkeleton />}>
            <Outlet />
          </Suspense>
        </div>
      </div>
    </div>
  );
}

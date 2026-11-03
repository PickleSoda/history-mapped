import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ArrowRight, SquarePen } from 'lucide-react';
import { useEffect } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { DOC_SECTIONS, DOCS_INDEX_SLUG } from '@/content/docs/manifest';
import type { DocEntry } from '@/content/docs/manifest';
import { docNeighbours, docPath, findDoc, githubEditUrl } from '@/lib/docs/docs';
import { useDocumentMeta } from '@/lib/docs/document-meta';
import { loadDoc } from '@/lib/docs/load';
import { DocMarkdown } from './DocMarkdown';
import { DocSkeleton } from './DocSkeleton';
import { DocToc } from './DocToc';

/** Scrolls to the URL's `#anchor` once the doc is on screen, else to the top. */
function useScrollOnLoad(ready: unknown) {
  const { hash } = useLocation();
  useEffect(() => {
    if (!ready) return;
    if (hash) {
      document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
    } else {
      window.scrollTo(0, 0);
    }
  }, [ready, hash]);
}

function NeighbourLink({ entry, direction }: { entry: DocEntry; direction: 'prev' | 'next' }) {
  const next = direction === 'next';
  return (
    <Link
      to={docPath(entry.slug)}
      rel={direction}
      className={`group flex flex-col gap-1 rounded-lg border p-4 transition-colors hover:bg-muted/60 ${next ? 'items-end text-right sm:col-start-2' : ''}`}
    >
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        {!next && <ArrowLeft size={13} />}
        {next ? 'Next' : 'Previous'}
        {next && <ArrowRight size={13} />}
      </span>
      <span className="font-heading text-base font-semibold">{entry.title}</span>
    </Link>
  );
}

function DocFooter({ entry }: { entry: DocEntry }) {
  const { prev, next } = docNeighbours(entry.slug);
  return (
    <footer className="mt-14 space-y-6 border-t pt-6">
      <a
        href={githubEditUrl(entry.path)}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <SquarePen size={14} />
        Edit on GitHub
        <span className="font-mono text-xs">({entry.path})</span>
      </a>
      {(prev || next) && (
        <nav aria-label="Previous and next pages" className="grid gap-3 sm:grid-cols-2">
          {prev && <NeighbourLink entry={prev} direction="prev" />}
          {next && <NeighbourLink entry={next} direction="next" />}
        </nav>
      )}
    </footer>
  );
}

function DocNotFound({ slug }: { slug: string }) {
  return (
    <div className="max-w-3xl py-8">
      <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Docs</p>
      <h1 className="mt-2 font-heading text-3xl font-semibold tracking-tight">Page not found</h1>
      <p className="mt-4 text-muted-foreground">
        There is no page called <code className="font-mono text-[0.9em]">{slug}</code> in the docs. Pick one from the
        list, or start at the <Link to="/docs" className="font-medium text-foreground underline underline-offset-4">documentation index</Link>.
      </p>
    </div>
  );
}

function DocError({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="max-w-3xl rounded-lg border p-6">
      <p className="font-medium">This page could not be loaded.</p>
      <p className="mt-1 text-sm text-muted-foreground">Check your connection and try again.</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
      >
        Try again
      </button>
    </div>
  );
}

/**
 * `/docs` and `/docs/:slug` (spec 2026-11-01 public site, D5): one markdown
 * file from the repo's `docs/`, with a table of contents on wide screens,
 * previous / next links and a link to edit the source on GitHub.
 */
export function DocPage() {
  const { slug } = useParams();
  const entry = findDoc(slug);
  const key = entry?.slug ?? '';
  const query = useQuery({
    queryKey: ['docs', key],
    queryFn: () => loadDoc(key),
    enabled: entry !== undefined,
    // The markdown is part of the build: it cannot change under a running page.
    staleTime: Infinity,
  });
  const doc = query.data ?? null;

  useDocumentMeta({
    title: entry ? entry.title : 'Page not found',
    description: entry?.description,
  });
  useScrollOnLoad(doc);

  if (!entry) return <DocNotFound slug={slug ?? ''} />;
  const section = DOC_SECTIONS.find((candidate) => candidate.id === entry.section);

  return (
    <div className="xl:grid xl:grid-cols-[minmax(0,48rem)_13rem] xl:justify-between xl:gap-10">
      <article className="min-w-0 max-w-3xl">
        {section && entry.slug !== DOCS_INDEX_SLUG && (
          <p className="mb-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{section.title}</p>
        )}
        {doc ? (
          <DocMarkdown markdown={doc.markdown} path={entry.path} />
        ) : query.isError ? (
          <DocError onRetry={() => void query.refetch()} />
        ) : (
          <DocSkeleton />
        )}
        <DocFooter entry={entry} />
      </article>
      {doc && doc.toc.length > 0 && (
        <aside className="hidden xl:block">
          <div className="sticky top-[var(--site-header-height,0px)] max-h-[calc(100dvh-var(--site-header-height,0px))] overflow-y-auto py-2">
            <DocToc items={doc.toc} />
          </div>
        </aside>
      )}
    </div>
  );
}

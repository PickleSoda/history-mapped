import { Globe } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useDocumentMeta } from '@/lib/document-meta';
import { ATLAS_PATH } from '@/lib/site-links';

/** The not-found body, shared by unknown paths and missing entities / chronicles. */
export function NotFoundContent({
  title = 'Page not found',
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <section className="mx-auto w-full max-w-3xl px-4 py-16 sm:px-6 md:py-24">
      <p aria-hidden className="font-heading text-[64px] font-semibold leading-none text-muted-foreground/30">
        404
      </p>
      <h1 className="mt-4 text-balance font-heading text-[32px] font-semibold leading-tight tracking-tight md:text-[40px]">
        {title}
      </h1>
      <p className="mt-3 max-w-prose text-[15px] leading-relaxed text-muted-foreground">
        {children ?? 'There is nothing at this address. The link may be mistyped, or the page may have moved.'}
      </p>
      <div className="mt-8 flex flex-wrap items-center gap-2">
        <Link
          to="/browse"
          className="inline-flex h-9 items-center rounded-lg border bg-card px-3.5 text-[13px] font-medium shadow-xs transition-colors hover:bg-muted"
        >
          Browse the atlas
        </Link>
        <Link
          to={ATLAS_PATH}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground shadow-xs transition-colors hover:bg-primary/85"
        >
          <Globe size={14} aria-hidden /> Open the globe
        </Link>
        <Link to="/" className="px-2 text-[13px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">
          Home
        </Link>
      </div>
    </section>
  );
}

/** Unknown path under the site frame. */
export function NotFoundPage() {
  useDocumentMeta({ title: 'Page not found' });
  return <NotFoundContent />;
}

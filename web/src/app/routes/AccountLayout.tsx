import { ArrowLeft, Compass } from 'lucide-react';
import { Suspense } from 'react';
import type { ReactNode } from 'react';
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { UserMenu } from '@/components/account/UserMenu';
import { ThemeToggle } from '@/components/atlas/ThemeToggle';
import { useMe } from '@/hooks';

/** Shown while an account page chunk loads. */
function PageFallback() {
  return (
    <div className="grid place-items-center py-24 text-[13px] text-muted-foreground">
      <span className="animate-pulse motion-reduce:animate-none">Loading…</span>
    </div>
  );
}

/**
 * Chrome for the account pages (sign in, saved, contributions): the brand
 * back to the atlas, theme and the user menu, over a normally scrolling page.
 */
export function AccountLayout() {
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <header className="sticky top-0 z-20 flex h-[54px] items-center gap-3 border-b bg-card/95 px-4 backdrop-blur">
        <Link to="/" className="flex items-center gap-2" aria-label="History Mapped — back to the atlas">
          <span className="grid size-[30px] place-items-center rounded-lg bg-primary text-primary-foreground">
            <Compass size={17} />
          </span>
          <span className="hidden font-heading text-[17px] font-semibold tracking-tight sm:inline">
            History Mapped
          </span>
        </Link>
        <Link
          to="/"
          className="ml-1 inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[12px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ArrowLeft size={14} /> Atlas
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          <UserMenu />
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1120px] px-4 pb-20 pt-8 md:px-8">
        <Suspense fallback={<PageFallback />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}

/** Gate a page on a signed-in user; guests go to sign in and come back. */
export function RequireUser({ children }: { children: ReactNode }) {
  const { me, isLoading } = useMe();
  const location = useLocation();
  if (isLoading) return <PageFallback />;
  if (!me) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return children;
}

/** Page heading used across the account pages. */
export function AccountHeading({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-8">
      <h1 className="font-heading text-[30px] font-semibold leading-tight tracking-tight md:text-[36px]">
        {title}
      </h1>
      {children && <p className="mt-2 max-w-prose text-[14px] text-muted-foreground">{children}</p>}
    </div>
  );
}

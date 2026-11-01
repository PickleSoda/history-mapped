import { Suspense } from 'react';
import { Link, Outlet } from 'react-router-dom';

/**
 * Frame for every page except the atlas (`/app`) and the account pages:
 * header, the routed page, footer (spec 2026-11-01 public site, D2).
 * Skeleton version; track B replaces it.
 */
export function SiteLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <header className="border-b">
        <nav className="mx-auto flex w-full max-w-5xl items-center gap-4 px-4 py-3 text-sm">
          <Link to="/" className="font-heading text-base font-semibold">
            History Mapped
          </Link>
          <Link to="/browse" className="text-muted-foreground hover:text-foreground">
            Browse
          </Link>
          <Link to="/docs" className="text-muted-foreground hover:text-foreground">
            Docs
          </Link>
          <Link to="/app" className="ml-auto rounded-md border px-3 py-1.5 hover:bg-muted">
            Open the globe
          </Link>
        </nav>
      </header>
      <main className="flex-1">
        <Suspense fallback={null}>
          <Outlet />
        </Suspense>
      </main>
      <footer className="border-t">
        <div className="mx-auto w-full max-w-5xl px-4 py-6 text-xs text-muted-foreground">
          History Mapped · an interactive historical atlas
        </div>
      </footer>
    </div>
  );
}

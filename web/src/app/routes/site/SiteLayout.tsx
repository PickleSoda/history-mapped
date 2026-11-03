import { Compass, Globe, Menu, X } from 'lucide-react';
import { Suspense, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigationType } from 'react-router-dom';
import { UserMenu } from '@/components/account/UserMenu';
import { ThemeToggle } from '@/components/atlas/ThemeToggle';
import { useMe } from '@/hooks';
import { ATLAS_PATH, GITHUB_URL, storiesPath } from '@/lib/site-links';
import { cn } from '@/lib/utils';

/** Light placeholder while a site page's chunk loads. */
export function SitePageSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading"
      className="mx-auto w-full max-w-3xl animate-pulse px-4 py-12 motion-reduce:animate-none sm:px-6"
    >
      <div className="h-4 w-28 rounded-full bg-muted" />
      <div className="mt-5 h-10 w-2/3 rounded-lg bg-muted" />
      <div className="mt-8 space-y-2.5">
        <div className="h-3.5 rounded bg-muted" />
        <div className="h-3.5 w-11/12 rounded bg-muted" />
        <div className="h-3.5 w-4/5 rounded bg-muted" />
      </div>
    </div>
  );
}

/** The compass mark + wordmark, linking home. */
function Brand({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn('flex flex-none items-center gap-2', className)}>
      <span className="grid size-[30px] place-items-center rounded-lg bg-primary text-primary-foreground">
        <Compass size={17} aria-hidden />
      </span>
      <span className="font-heading text-[17px] font-semibold tracking-tight">History Mapped</span>
    </Link>
  );
}

const NAV = [
  { to: '/browse', label: 'Browse' },
  { to: '/docs', label: 'Docs' },
] as const;

const GLOBE_BUTTON =
  'inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-[13px] font-medium text-primary-foreground shadow-xs transition-colors hover:bg-primary/85';

function SiteHeader() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  // Close the mobile menu on navigation (adjusted during render, not in an effect).
  const [menuPath, setMenuPath] = useState(pathname);
  if (menuPath !== pathname) {
    setMenuPath(pathname);
    setOpen(false);
  }
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <header className="relative z-30 border-b bg-background">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-2 px-4 sm:px-6">
        <Brand />
        <nav aria-label="Site" className="ml-5 hidden items-center gap-0.5 md:flex">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className="rounded-lg px-2.5 py-1.5 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground aria-[current=page]:text-foreground"
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1.5">
          <ThemeToggle className="hidden sm:grid" />
          <UserMenu />
          <Link to={ATLAS_PATH} className={cn(GLOBE_BUTTON, 'hidden md:inline-flex')}>
            <Globe size={14} aria-hidden /> Open the globe
          </Link>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="site-menu"
            aria-label={open ? 'Close menu' : 'Open menu'}
            className="grid size-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:hidden"
          >
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>
      {open && (
        <div id="site-menu" className="absolute inset-x-0 top-full border-b bg-background shadow-lg md:hidden">
          <nav aria-label="Site" className="mx-auto flex w-full max-w-6xl flex-col gap-0.5 px-4 py-3">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                className="rounded-lg px-3 py-2.5 text-[15px] font-medium text-foreground/80 hover:bg-muted aria-[current=page]:text-foreground"
              >
                {n.label}
              </NavLink>
            ))}
            <div className="flex items-center justify-between rounded-lg px-3 py-1.5 text-[15px] font-medium text-foreground/80">
              Theme
              <ThemeToggle />
            </div>
            <Link to={ATLAS_PATH} className={cn(GLOBE_BUTTON, 'mt-2 h-10 justify-center text-[15px]')}>
              <Globe size={16} aria-hidden /> Open the globe
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}

function FooterGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <ul className="mt-2.5 space-y-2">{children}</ul>
    </div>
  );
}

const FOOTER_LINK = 'text-foreground/80 underline-offset-4 hover:text-foreground hover:underline';

function SiteFooter() {
  const { me } = useMe();
  const { pathname, search } = useLocation();
  const next = encodeURIComponent(`${pathname}${search}`);
  return (
    <footer className="border-t bg-card/50">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-10 sm:px-6 md:grid-cols-[minmax(0,1fr)_auto]">
        <div className="max-w-sm">
          <Brand />
          <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
            An open atlas of world history: entities, relationships and chronicles on a map that moves
            through time.
          </p>
          <p className="mt-3 text-[12px] leading-relaxed text-muted-foreground">
            Data from Wikidata and OpenHistoricalMap; images from Wikimedia Commons, credited where they
            appear.
          </p>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-x-12 gap-y-8 text-[13px] sm:grid-cols-3">
          <FooterGroup label="Explore">
            <li>
              <Link to={ATLAS_PATH} className={FOOTER_LINK}>
                Open the globe
              </Link>
            </li>
            <li>
              <Link to="/browse" className={FOOTER_LINK}>
                Browse
              </Link>
            </li>
            <li>
              <Link to={storiesPath()} className={FOOTER_LINK}>
                Battle maps
              </Link>
            </li>
          </FooterGroup>
          <FooterGroup label="Project">
            <li>
              <Link to="/docs" className={FOOTER_LINK}>
                Docs
              </Link>
            </li>
            <li>
              <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className={FOOTER_LINK}>
                GitHub
              </a>
            </li>
          </FooterGroup>
          <FooterGroup label="Account">
            {me ? (
              <>
                <li>
                  <Link to="/saved" className={FOOTER_LINK}>
                    Saved
                  </Link>
                </li>
                <li>
                  <Link to="/contributions" className={FOOTER_LINK}>
                    My contributions
                  </Link>
                </li>
              </>
            ) : (
              <>
                <li>
                  <Link to={`/login?next=${next}`} className={FOOTER_LINK}>
                    Sign in
                  </Link>
                </li>
                <li>
                  <Link to={`/register?next=${next}`} className={FOOTER_LINK}>
                    Create an account
                  </Link>
                </li>
              </>
            )}
          </FooterGroup>
        </nav>
      </div>
    </footer>
  );
}

/**
 * Frame for every page except the atlas (`/app`) and the account pages:
 * header (wordmark, Browse, Docs, account, "Open the globe"), the routed page
 * as an ordinary scrolling document, footer (spec 2026-11-01 public site, D2).
 * A new page starts at the top; Back and Forward leave the scroll to the
 * browser, and a `#hash` to the page.
 */
export function SiteLayout() {
  const { pathname, hash } = useLocation();
  const navigationType = useNavigationType();
  useEffect(() => {
    if (navigationType !== 'POP' && !hash) window.scrollTo(0, 0);
  }, [pathname, hash, navigationType]);

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <SiteHeader />
      <main className="flex-1">
        <Suspense fallback={<SitePageSkeleton />}>
          <Outlet />
        </Suspense>
      </main>
      <SiteFooter />
    </div>
  );
}

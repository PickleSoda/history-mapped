import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import type { ComponentType, ReactNode } from 'react';
import type { PageVariant } from '@/components/atlas/page-kit';
import { useFullPage, useReducedMotion } from '@/hooks';
import type { FullPageKind } from '@/lib/full-page';
import { cn } from '@/lib/utils';

export interface FullPageProps {
  /** Entity id (entity page) or chronicle slug (chronicle page). */
  id: string;
  variant?: PageVariant;
}

/** The page modules (and the graph UI they pull in) load on first use, so
 *  they stay out of the atlas entry chunk. Call a preload on intent (hovering
 *  Expand) to have the chunk ready by the click. */
const loadEntityPage = () => import('@/components/atlas/EntityPage');
const loadChroniclePage = () => import('@/components/atlas/ChroniclePage');
export const preloadEntityPage = () => void loadEntityPage();
export const preloadChroniclePage = () => void loadChroniclePage();
const LazyEntityPage = lazy(() => loadEntityPage().then((m) => ({ default: m.EntityPage })));
const LazyChroniclePage = lazy(() => loadChroniclePage().then((m) => ({ default: m.ChroniclePage })));

/** Shown while a page chunk loads (first open only). */
function PageFallback() {
  return (
    <div className="grid h-full place-items-center text-[13px] text-muted-foreground">
      <span className="animate-pulse motion-reduce:animate-none">Opening…</span>
    </div>
  );
}

function EntityPageLoader(props: FullPageProps) {
  return (
    <Suspense fallback={<PageFallback />}>
      <LazyEntityPage {...props} />
    </Suspense>
  );
}

function ChroniclePageLoader(props: FullPageProps) {
  return (
    <Suspense fallback={<PageFallback />}>
      <LazyChroniclePage {...props} />
    </Suspense>
  );
}

/**
 * Page renderers by kind. A kind without a renderer never opens: `full` is
 * ignored for it on desktop and the sheet's full snap keeps its normal body.
 */
export const FULL_PAGES: Partial<Record<FullPageKind, ComponentType<FullPageProps>>> = {
  entity: EntityPageLoader,
  chronicle: ChroniclePageLoader,
};

interface PageTarget {
  kind: FullPageKind;
  id: string;
  Page: ComponentType<FullPageProps>;
}

function target(kind: FullPageKind | null, sel: string | null, chron: string | null): PageTarget | null {
  if (!kind) return null;
  const Page = FULL_PAGES[kind];
  const id = kind === 'entity' ? sel : chron;
  return Page && id ? { kind, id, Page } : null;
}

/** The topmost page open right now (`full` set and renderable), or null. */
export function useOpenPage(): PageTarget | null {
  const { kind, sel, chron } = useFullPage();
  return target(kind, sel, chron);
}

/** The page the current focus would expand into, ignoring `full` (the mobile
 *  sheet shows it at the full snap). */
export function useFocusPage(): PageTarget | null {
  const { focusKind, sel, chron } = useFullPage();
  return target(focusKind, sel, chron);
}

/**
 * Wraps what the page covers (map, sidebars, timeline) and makes it inert
 * while a page is open, so focus and clicks can't reach the hidden map. Takes
 * the shell as `children`, so its own re-renders don't re-render the map.
 */
export function BehindPage({ children }: { children: ReactNode }) {
  const open = useOpenPage() != null;
  return (
    <div inert={open} className="flex min-h-0 flex-1 flex-col">
      {children}
    </div>
  );
}

/**
 * One sliding layer of the desktop host. It rises from the bottom edge with a
 * CSS transform transition (instant under prefers-reduced-motion) and keeps
 * its last page mounted while it slides away, so Close doesn't blank it
 * mid-animation; it unmounts once off-screen. A `covered` layer (the chronicle
 * page under an entity page) stays mounted — keeping its scroll position and
 * graph state — but is inert, and never mounts fresh while covered.
 */
function PageLayer({
  page,
  covered,
  z,
}: {
  page: PageTarget | null;
  covered: boolean;
  z: string;
}) {
  const { collapse } = useFullPage();
  const reducedMotion = useReducedMotion();
  const sectionRef = useRef<HTMLElement>(null);

  const [shown, setShown] = useState<PageTarget | null>(covered ? null : page);
  if (
    page &&
    (!covered || shown) &&
    (page.kind !== shown?.kind || page.id !== shown?.id || page.Page !== shown?.Page)
  ) {
    setShown(page);
  }
  if (!page && shown && reducedMotion) setShown(null);

  // Move focus into the page as it opens (or is uncovered).
  const isOpen = page != null;
  const active = isOpen && !covered;
  useEffect(() => {
    if (active) sectionRef.current?.focus({ preventScroll: true });
  }, [active]);

  const Page = shown?.Page;
  return (
    <section
      ref={sectionRef}
      tabIndex={-1}
      aria-label={shown?.kind === 'chronicle' ? 'Chronicle page' : 'Entity page'}
      aria-hidden={!active}
      inert={!active}
      onKeyDown={(e) => {
        if (e.key === 'Escape' && active) collapse();
      }}
      onTransitionEnd={(e) => {
        if (e.target === e.currentTarget && !isOpen) setShown(null);
      }}
      className={cn(
        'absolute inset-0 flex flex-col bg-background outline-none will-change-transform',
        'transition-[translate,box-shadow] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none',
        isOpen
          ? 'translate-y-0 shadow-[0_-18px_40px_-12px_rgb(0_0_0/0.28)]'
          : 'pointer-events-none translate-y-full shadow-none',
        z,
      )}
    >
      {shown && Page && <Page id={shown.id} variant="page" />}
    </section>
  );
}

/**
 * Desktop host: the open pages rise from the bottom edge over the map and
 * timeline (the TopBar stays). Two layers — the chronicle page, and the entity
 * page above it — so an entity opened from a chronicle page slides up over it
 * and closing it uncovers the chronicle page exactly as it was.
 */
export function FullPageHost() {
  const { stack, sel, chron } = useFullPage();
  const chronicle = stack.includes('chronicle') ? target('chronicle', sel, chron) : null;
  const entity = stack.includes('entity') ? target('entity', sel, chron) : null;
  return (
    <>
      <PageLayer page={chronicle} covered={entity != null} z="z-30" />
      <PageLayer page={entity} covered={false} z="z-40" />
    </>
  );
}

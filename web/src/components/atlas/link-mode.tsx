/**
 * Link mode (spec 2026-11-01 public site, D3): one entity / chronicle page,
 * two homes. Inside the atlas (`/app`) the pages navigate through the atlas
 * hooks, exactly as they always have; on the standalone site routes
 * (`/entities/:id`, `/chronicles/:slug`) the same actions navigate to site
 * pages, or leave for a fresh `/app?…` link when they need the map. Which URL
 * each action goes to is the pure policy in `lib/page-nav.ts`.
 *
 * No provider means atlas mode, so nothing under `/app` has to opt in.
 */
import { createContext, useCallback, useContext, useMemo } from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  useChronicleNav,
  useFullPage,
  useMapFocus,
  useSelection,
  useShowChroniclesTagged,
  useStoryNav,
  useTimeState,
} from '@/hooks';
import type { FullPageKind } from '@/lib/full-page';
import { siteHref } from '@/lib/page-nav';
import type { LinkMode, PageNavIntent } from '@/lib/page-nav';

export type { LinkMode } from '@/lib/page-nav';

const LinkModeContext = createContext<LinkMode>('atlas');

/** Sets how the pages below navigate. Absent = `atlas`. */
export function LinkModeProvider({ mode, children }: { mode: LinkMode; children: ReactNode }) {
  return <LinkModeContext.Provider value={mode}>{children}</LinkModeContext.Provider>;
}

/** The enclosing link mode (`atlas` outside any provider). */
export function useLinkMode(): LinkMode {
  return useContext(LinkModeContext);
}

/** Where "show on map" should land. */
export interface ShowOnMapOptions {
  /** Put the timeline at this year (atlas and site). */
  year?: number | null;
  /** Year to open the globe at when no `year` is given (site only: the atlas
   *  keeps its current time). */
  yearHint?: number | null;
  /** Geometry to frame on the map (atlas only; the site's link selects the
   *  entity, and the atlas frames a selection when its detail opens). */
  geom?: unknown;
}

export interface PageNav {
  mode: LinkMode;
  /** Open another entity: select it (atlas) or go to its page (site). */
  openEntity: (id: string) => void;
  /** Open a chronicle, optionally at a 0-based step. */
  openChronicle: (slug: string, step?: number) => void;
  /** Play a battle map, optionally from a 0-based step (site: on the globe). */
  openStory: (slug: string, step?: number) => void;
  /** Show the entity on the map (atlas: collapse the page; site: open the globe). */
  showOnMap: (entityId: string, options?: ShowOnMapOptions) => void;
  /** Open everything carrying a tag (atlas: the filtered Chronicles tab). */
  openTag: (facet: string, slug: string) => void;
  /** Collapse the full page; a chronicle page returns to the tour at `step`.
   *  No-op on the site. */
  collapse: (step?: number) => void;
  /** Close the full page (an entity page clears the selection, a chronicle
   *  page exits the tour). No-op on the site. */
  close: (page?: FullPageKind) => void;
}

/** Atlas mode: today's hooks, called as the pages always called them. */
function useAtlasPageNav(): PageNav {
  const { select } = useSelection();
  const { enter: enterChronicle, goto: gotoStep } = useChronicleNav();
  const { enter: enterStory } = useStoryNav();
  const { collapse: collapsePage, closeEntity, collapseChronicle, closeChronicle } = useFullPage();
  const { setInstant } = useTimeState();
  const { focusGeometries } = useMapFocus();
  const showTagged = useShowChroniclesTagged();

  const openChronicle = useCallback(
    (slug: string, step?: number) => {
      enterChronicle(slug);
      if (typeof step === 'number' && step > 0) void gotoStep(step);
    },
    [enterChronicle, gotoStep],
  );
  const openStory = useCallback(
    (slug: string, step?: number) => enterStory(slug, typeof step === 'number' ? step : 0),
    [enterStory],
  );
  const showOnMap = useCallback(
    (_entityId: string, options: ShowOnMapOptions = {}) => {
      if (options.year != null) void setInstant(options.year);
      void collapsePage();
      if (options.geom != null) focusGeometries([options.geom]);
    },
    [setInstant, collapsePage, focusGeometries],
  );
  const openTag = useCallback((_facet: string, slug: string) => void showTagged(slug), [showTagged]);
  // Guard on `typeof`: a click handler passed straight through would hand
  // its event in as the step.
  const collapse = useCallback(
    (step?: number) => void (typeof step === 'number' ? collapseChronicle(step) : collapsePage()),
    [collapseChronicle, collapsePage],
  );
  const close = useCallback(
    (page?: FullPageKind) => void (page === 'chronicle' ? closeChronicle() : closeEntity()),
    [closeChronicle, closeEntity],
  );
  const openEntity = useCallback((id: string) => void select(id), [select]);

  return useMemo(
    () => ({ mode: 'atlas', openEntity, openChronicle, openStory, showOnMap, openTag, collapse, close }),
    [openEntity, openChronicle, openStory, showOnMap, openTag, collapse, close],
  );
}

const noop = () => {};

/** Site mode: every action is a navigation to the URL `siteHref` gives. */
function useSitePageNav(): PageNav {
  const navigate = useNavigate();
  return useMemo(() => {
    const go = (intent: PageNavIntent) => void navigate(siteHref(intent));
    return {
      mode: 'site',
      openEntity: (id) => go({ kind: 'entity', id }),
      openChronicle: (slug, step) => go({ kind: 'chronicle', slug, step }),
      openStory: (slug, step) => go({ kind: 'story', slug, step }),
      showOnMap: (entityId, options = {}) =>
        go({ kind: 'map', entityId, year: options.year ?? options.yearHint }),
      openTag: (facet, slug) => go({ kind: 'tag', facet, slug }),
      collapse: noop,
      close: noop,
    };
  }, [navigate]);
}

/**
 * Navigation for the entity and chronicle pages and the components they use.
 * Both implementations are built (hooks can't be conditional); the mode picks
 * one. The atlas one subscribes to the URL keys of the hooks it wraps, which
 * change by navigation or the timeline, never by pan; keep it
 * out of per-row components (pass `openEntity` down as a prop instead).
 */
export function usePageNav(): PageNav {
  const mode = useLinkMode();
  const atlas = useAtlasPageNav();
  const site = useSitePageNav();
  return mode === 'site' ? site : atlas;
}

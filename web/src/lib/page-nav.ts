/**
 * Link-mode policy (spec 2026-11-01 public site, D3), kept pure so it is unit
 * tested and `components/atlas/link-mode.tsx` stays a thin shell over it.
 *
 * The entity and chronicle pages render in two homes: inside the atlas
 * (`/app`, the full page) and as standalone site routes (`/entities/:id`,
 * `/chronicles/:slug`). Their navigation is expressed as intents; in *atlas*
 * mode an intent runs today's atlas hooks, in *site* mode it navigates to the
 * URL below. A site-mode intent never writes atlas state (`sel`, `chron`,
 * `step`, `story`, `sstep`, `full`) into the current URL: it either stays on
 * the site or leaves for a fresh `/app?…` link.
 */
import {
  atlasHref,
  chroniclePagePath,
  entityPagePath,
  facetPath,
} from '@/lib/site-links';

export type LinkMode = 'atlas' | 'site';

/** Something a page asks to open. */
export type PageNavIntent =
  /** Another entity. */
  | { kind: 'entity'; id: string }
  /** A chronicle, optionally at a 0-based step. */
  | { kind: 'chronicle'; slug: string; step?: number | null }
  /** A battle map (map story), optionally at a 0-based step. It needs the map. */
  | { kind: 'story'; slug: string; step?: number | null }
  /** An entity on the map, optionally at a year. */
  | { kind: 'map'; entityId: string; year?: number | null }
  /** Everything carrying a tag. */
  | { kind: 'tag'; facet: string; slug: string };

/** Where an intent goes in site mode. */
export function siteHref(intent: PageNavIntent): string {
  switch (intent.kind) {
    case 'entity':
      return entityPagePath(intent.id);
    case 'chronicle':
      return chroniclePagePath(intent.slug, intent.step);
    case 'story':
      return atlasHref({ story: intent.slug, sstep: intent.step });
    case 'map':
      return atlasHref({ sel: intent.entityId, year: intent.year });
    case 'tag':
      return facetPath(intent.facet, intent.slug);
  }
}

/** A page shown on the site, for its "Open on the globe" link. */
export type SitePage =
  | { kind: 'entity'; id: string }
  | { kind: 'chronicle'; slug: string; step?: number | null };

/** The same page expanded in the atlas: `/app?sel=<id>&full=1` or
 *  `/app?chron=<slug>(&step=n)&full=1`. */
export function globeHref(page: SitePage): string {
  return page.kind === 'entity'
    ? atlasHref({ sel: page.id, full: true })
    : atlasHref({ chron: page.slug, step: page.step, full: true });
}

/** Whether a tag pill opens something: in the atlas, a tag that chronicles
 *  use filters the Chronicles tab; on the site, any tag with content opens
 *  its browse page. */
export function tagOpens(
  mode: LinkMode,
  tag: { chronicle_count: number; entity_count: number },
): boolean {
  return mode === 'site' ? tag.chronicle_count + tag.entity_count > 0 : tag.chronicle_count > 0;
}

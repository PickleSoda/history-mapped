/**
 * Paths the browse pages link to. Same names and shapes as track B's
 * `lib/site-links.ts` (spec 2026-11-01 public site, D1), which is not on this
 * branch yet.
 *
 * TODO(integrator): switch to lib/site-links — replace imports of
 * `./links` with `@/lib/site-links` and delete this file.
 */
import type { TagFacet } from '@/lib/schemas/tag';

const enc = encodeURIComponent;

/** Standalone entity page. */
export function entityPagePath(id: string): string {
  return `/entities/${enc(id)}`;
}

/** Standalone chronicle page, optionally at a step. */
export function chroniclePagePath(slug: string, step?: number): string {
  return step != null && step > 0 ? `/chronicles/${enc(slug)}?step=${step}` : `/chronicles/${enc(slug)}`;
}

/** A curated set. */
export function collectionPath(slug: string): string {
  return `/browse/collections/${enc(slug)}`;
}

/** Everything carrying a tag, e.g. `/browse/era/medieval`. */
export function facetPath(facet: TagFacet, tag: string): string {
  return `/browse/${facet}/${enc(tag)}`;
}

/** The battle-map index. */
export function storiesPath(): string {
  return '/browse/stories';
}

/** The browse index. */
export function browsePath(): string {
  return '/browse';
}

/** The globe at `/app` with atlas search params (`sel`, `full`, `chron`, `story`, `y`…). */
export function atlasHref(params: Record<string, string | number | null | undefined> = {}): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v != null && v !== '') q.set(k, String(v));
  const s = q.toString();
  return s ? `/app?${s}` : '/app';
}

/** "Open on the globe" for an entity: selected, full page open. */
export function entityAtlasHref(id: string): string {
  return atlasHref({ sel: id, full: 1 });
}

/** "Open on the globe" for a chronicle: the tour, playing on the map. */
export function chronicleAtlasHref(slug: string): string {
  return atlasHref({ chron: slug });
}

/** A battle map needs the globe: play it there. */
export function storyAtlasHref(slug: string): string {
  return atlasHref({ story: slug });
}

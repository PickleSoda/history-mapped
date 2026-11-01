/**
 * Paths of the public site and links into the atlas (spec 2026-11-01 public
 * site, D1). The site's pages are routes; the atlas is one shell at `/app`
 * whose state lives in search params (see `lib/url/params.ts`).
 */
import { serializeTime } from '@/lib/url/serialize';

/** Where the atlas shell lives. */
export const ATLAS_PATH = '/app';

/** The project's source repository (footer, docs). */
export const GITHUB_URL = 'https://github.com/PickleSoda/history-mapped';

const seg = (s: string) => encodeURIComponent(s);

/** A valid step index (a non-negative integer), else null. */
function stepOrNull(step: number | null | undefined): number | null {
  return step != null && Number.isInteger(step) && step >= 0 ? step : null;
}

/** Standalone entity page. */
export function entityPagePath(id: string): string {
  return `/entities/${seg(id)}`;
}

/**
 * Standalone chronicle page. `step` (0-based, like the atlas `step` param)
 * opens the page with that step selected; without it the page shows the
 * whole chronicle.
 */
export function chroniclePagePath(slug: string, step?: number | null): string {
  const s = stepOrNull(step);
  return `/chronicles/${seg(slug)}${s == null ? '' : `?step=${s}`}`;
}

/** The `?step=` of a chronicle page: a non-negative integer, else null. */
export function parseStepParam(raw: string | null | undefined): number | null {
  if (raw == null || !/^\d{1,6}$/.test(raw.trim())) return null;
  return Number(raw.trim());
}

/** A curated set. */
export function collectionPath(slug: string): string {
  return `/browse/collections/${seg(slug)}`;
}

/** Everything carrying one tag, e.g. `/browse/era/medieval`. */
export function facetPath(facet: string, tag: string): string {
  return `/browse/${seg(facet)}/${seg(tag)}`;
}

/** The battle maps (map stories) list. */
export function storiesPath(): string {
  return '/browse/stories';
}

/** One docs page; an empty slug is the docs index. */
export function docPath(slug: string): string {
  return slug ? `/docs/${seg(slug)}` : '/docs';
}

/** Atlas state a link can set. Absent / null / false values are left out. */
export interface AtlasLinkParams {
  /** Selected entity id. */
  sel?: string | null;
  /** Chronicle slug and its 0-based step. */
  chron?: string | null;
  step?: number | null;
  /** Map-story slug and its 0-based step. */
  story?: string | null;
  sstep?: number | null;
  /** Expand the focus (entity, else chronicle) into its full page. */
  full?: boolean;
  /** Timeline instant (the `t` param). */
  year?: number | null;
}

/**
 * A link into the atlas: `/app?…` in a fixed key order. A step of 0 is the
 * atlas default and is left out.
 */
export function atlasHref(params: AtlasLinkParams = {}): string {
  const q = new URLSearchParams();
  if (params.sel) q.set('sel', params.sel);
  if (params.chron) {
    q.set('chron', params.chron);
    const s = stepOrNull(params.step);
    if (s) q.set('step', String(s));
  }
  if (params.story) {
    q.set('story', params.story);
    const s = stepOrNull(params.sstep);
    if (s) q.set('sstep', String(s));
  }
  if (params.full) q.set('full', '1');
  if (params.year != null && Number.isFinite(params.year)) {
    q.set('t', serializeTime({ kind: 'instant', year: Math.trunc(params.year) }));
  }
  const qs = q.toString();
  return qs ? `${ATLAS_PATH}?${qs}` : ATLAS_PATH;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Entity ids are UUIDs; anything else is a not-found page, not a request. */
export function isEntityId(id: string | null | undefined): id is string {
  return id != null && UUID.test(id);
}

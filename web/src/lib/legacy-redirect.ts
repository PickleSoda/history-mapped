/**
 * The atlas used to live at `/`, so every link shared before the public site
 * (`/?sel=…&full=1`, `/?chron=…`, `/?story=…`) carries its state as a query
 * on `/`. The landing has no query params of its own, so `/` with any query
 * goes to `/app` with the same query (and hash), replacing the history entry
 * (spec 2026-11-01 public site, D1). Pure, so the index route and
 * `inAppPath` share one tested rule.
 */
import { ATLAS_PATH } from '@/lib/site-links';

export interface LocationLike {
  pathname: string;
  search: string;
  hash?: string;
}

/** The `/app…` URL to replace `loc` with, or null when `loc` stays. */
export function legacyAtlasRedirect(loc: LocationLike): string | null {
  if (loc.pathname !== '/') return null;
  const search = loc.search.startsWith('?') ? loc.search.slice(1) : loc.search;
  if (!search) return null;
  return `${ATLAS_PATH}?${search}${loc.hash ?? ''}`;
}

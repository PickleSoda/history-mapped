/** Deep links into the atlas shell at `/app` (its state lives in search
 *  params). These are "open on the globe" links; the standalone site pages
 *  are in `lib/site-links.ts`. */
import { legacyAtlasRedirect } from '@/lib/legacy-redirect';
import { atlasHref } from '@/lib/site-links';

export function entityHref(id: string): string {
  return atlasHref({ sel: id, full: true });
}

export function chronicleHref(slug: string): string {
  return atlasHref({ chron: slug, full: true });
}

/** An absolute URL on this origin as an in-app path (for router links); null
 *  when it points elsewhere or doesn't parse. A link made when the atlas
 *  lived at `/` (`/?sel=…`) comes back as its `/app?…` equivalent. */
export function inAppPath(url: string | null, origin = window.location.origin): string | null {
  if (!url) return null;
  try {
    const u = new URL(url, origin);
    if (u.origin !== origin) return null;
    return legacyAtlasRedirect(u) ?? `${u.pathname}${u.search}${u.hash}`;
  } catch {
    return null;
  }
}

/** Deep links back into the atlas shell (its state lives in search params). */

export function entityHref(id: string): string {
  return `/?${new URLSearchParams({ sel: id, full: '1' })}`;
}

export function chronicleHref(slug: string): string {
  return `/?${new URLSearchParams({ chron: slug, full: '1' })}`;
}

/** An absolute URL on this origin as an in-app path (for router links); null
 *  when it points elsewhere or doesn't parse. */
export function inAppPath(url: string | null, origin = window.location.origin): string | null {
  if (!url) return null;
  try {
    const u = new URL(url, origin);
    return u.origin === origin ? `${u.pathname}${u.search}${u.hash}` : null;
  } catch {
    return null;
  }
}

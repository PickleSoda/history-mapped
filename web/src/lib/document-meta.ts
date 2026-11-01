/**
 * Document title and meta description for the site pages (spec 2026-11-01
 * public site, D8). No prerendering in v1, so this is what a tab, a history
 * entry and a JavaScript-running crawler see.
 */
import { useEffect } from 'react';

export const SITE_NAME = 'History Mapped';

/** "<title> · History Mapped", or the bare site name. */
export function documentTitle(title?: string | null): string {
  const t = title?.trim();
  return t ? `${t} · ${SITE_NAME}` : SITE_NAME;
}

/** A description trimmed to one search-snippet's length, on a word boundary. */
export function metaDescription(text: string, max = 160): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  if (flat.length <= max) return flat;
  const cut = flat.slice(0, max - 1);
  const space = cut.lastIndexOf(' ');
  return `${(space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,;:.–—-]+$/, '')}…`;
}

/**
 * Set `document.title` and `<meta name="description">` while the calling page
 * is mounted; both go back to what they were on unmount. A missing
 * description leaves the tag alone.
 */
export function useDocumentMeta({
  title,
  description,
}: {
  title?: string | null;
  description?: string | null;
}): void {
  useEffect(() => {
    const previous = document.title;
    document.title = documentTitle(title);
    return () => {
      document.title = previous;
    };
  }, [title]);

  useEffect(() => {
    if (!description?.trim()) return;
    let tag = document.head.querySelector<HTMLMetaElement>('meta[name="description"]');
    const created = tag == null;
    if (!tag) {
      tag = document.createElement('meta');
      tag.name = 'description';
      document.head.appendChild(tag);
    }
    const previous = tag.getAttribute('content');
    tag.setAttribute('content', metaDescription(description));
    const el = tag;
    return () => {
      if (created) el.remove();
      else if (previous == null) el.removeAttribute('content');
      else el.setAttribute('content', previous);
    };
  }, [description]);
}

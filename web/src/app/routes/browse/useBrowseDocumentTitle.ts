/**
 * Document title and meta description for a browse page (spec D8:
 * "Battle of Cannae · History Mapped").
 *
 * TODO(integrator): switch to lib/document-meta — replace with track B's
 * `useDocumentMeta()` and delete this file.
 */
import { useEffect } from 'react';
import { plainText } from './browse-model';

const SITE = 'History Mapped';

/** "Medieval · History Mapped"; just the site name for a null title. */
export function browseDocumentTitle(title: string | null | undefined): string {
  return title ? `${title} · ${SITE}` : SITE;
}

/** Sets `document.title` and `<meta name="description">` while mounted, and
 *  restores the previous values on unmount. */
export function useBrowseDocumentTitle(title: string | null | undefined, description?: string | null) {
  const fullTitle = browseDocumentTitle(title);
  const content = plainText(description, 160);

  useEffect(() => {
    const previous = document.title;
    document.title = fullTitle;
    return () => {
      document.title = previous;
    };
  }, [fullTitle]);

  useEffect(() => {
    if (!content) return;
    let meta = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    const created = !meta;
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'description';
      document.head.appendChild(meta);
    }
    const previous = meta.content;
    meta.content = content;
    return () => {
      if (created) meta.remove();
      else meta.content = previous;
    };
  }, [content]);
}

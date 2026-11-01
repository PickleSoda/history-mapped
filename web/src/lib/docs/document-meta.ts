/**
 * Document title and meta description for the docs pages (spec D8). A local
 * stand-in for the shell track's `lib/document-meta.ts`, which is not on this
 * branch; swap the import when the two meet.
 */
import { useEffect } from 'react';

export const SITE_NAME = 'History Mapped';

/** "Tags · History Mapped"; the bare site name when there is no title. */
export function formatDocumentTitle(title: string | null | undefined): string {
  return title ? `${title} · ${SITE_NAME}` : SITE_NAME;
}

/** Sets `document.title` and `<meta name="description">`, restoring both on unmount. */
export function useDocumentMeta({ title, description }: { title?: string | null; description?: string | null }) {
  useEffect(() => {
    const previous = document.title;
    document.title = formatDocumentTitle(title);
    return () => {
      document.title = previous;
    };
  }, [title]);

  useEffect(() => {
    if (!description) return;
    let meta = document.head.querySelector<HTMLMetaElement>('meta[name="description"]');
    const created = !meta;
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'description';
      document.head.appendChild(meta);
    }
    const previous = meta.content;
    meta.content = description;
    return () => {
      if (created) meta.remove();
      else meta.content = previous;
    };
  }, [description]);
}

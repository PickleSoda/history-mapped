import { Hash } from 'lucide-react';
import { usePageNav } from '@/components/atlas/link-mode';
import { useTags } from '@/hooks';
import { tagOpens } from '@/lib/page-nav';
import { FACETS, displayTags } from '@/lib/tags';
import { cn } from '@/lib/utils';

const PILL =
  'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground';

/**
 * Tag pills for an entity or chronicle, most specific first (China, not also
 * East Asia and Asia). In the atlas a tag that chronicles use opens the
 * Chronicles tab filtered to it; on the site any tag with content opens its
 * browse page (`/browse/:facet/:tag`).
 */
export function TagPills({ slugs, className }: { slugs: string[]; className?: string }) {
  const { index } = useTags();
  const { mode, openTag } = usePageNav();
  const tags = displayTags(slugs, index);
  if (tags.length === 0) return null;

  return (
    <ul className={cn('flex flex-wrap gap-1.5', className)} aria-label="Tags">
      {tags.map((t) => {
        const mark =
          t.facet === 'topic' ? (
            <Hash size={11} />
          ) : (
            <span className="size-[6px] rounded-full" style={{ background: FACETS[t.facet].color }} />
          );
        return (
          <li key={t.slug}>
            {tagOpens(mode, t) ? (
              <button
                type="button"
                onClick={() => openTag(t.facet, t.slug)}
                title={
                  mode === 'site'
                    ? `${FACETS[t.facet].label} · browse everything tagged ${t.name}`
                    : `${FACETS[t.facet].label} · show chronicles tagged ${t.name}`
                }
                className={cn(PILL, 'hover:bg-muted hover:text-foreground')}
              >
                {mark}
                {t.name}
              </button>
            ) : (
              <span className={PILL} title={FACETS[t.facet].label}>
                {mark}
                {t.name}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

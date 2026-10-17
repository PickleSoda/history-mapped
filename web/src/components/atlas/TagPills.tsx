import { Hash } from 'lucide-react';
import { useShowChroniclesTagged, useTags } from '@/hooks';
import { FACETS, displayTags } from '@/lib/tags';
import { cn } from '@/lib/utils';

const PILL =
  'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground';

/**
 * Tag pills for an entity or chronicle, most specific first (China, not also
 * East Asia and Asia). A tag that chronicles use opens the Chronicles tab
 * filtered to it.
 */
export function TagPills({ slugs, className }: { slugs: string[]; className?: string }) {
  const { index } = useTags();
  const showTagged = useShowChroniclesTagged();
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
            {t.chronicle_count > 0 ? (
              <button
                type="button"
                onClick={() => showTagged(t.slug)}
                title={`${FACETS[t.facet].label} · show chronicles tagged ${t.name}`}
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

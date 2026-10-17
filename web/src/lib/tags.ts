/**
 * Tag helpers. Chronicle and entity payloads carry tag slugs *with* their
 * ancestors (china, east-asia, asia); the vocabulary from GET /tags gives names,
 * facets and the parent links used to collapse those back to the most specific
 * tags for display.
 */
import type { Tag, TagFacet } from '@/lib/schemas/tag';

export type IndexedTag = Tag & { order: number };
export type TagIndex = Map<string, IndexedTag>;

export const FACET_ORDER: TagFacet[] = ['era', 'region', 'theme', 'type', 'topic'];

export const FACETS: Record<TagFacet, { label: string; color: string }> = {
  era: { label: 'Era', color: 'var(--g-event)' },
  region: { label: 'Region', color: 'var(--g-place)' },
  theme: { label: 'Theme', color: 'var(--g-culture)' },
  type: { label: 'Type', color: 'var(--g-economy)' },
  topic: { label: 'Topic', color: 'var(--muted-foreground)' },
};

export function indexTags(tags: Tag[]): TagIndex {
  return new Map(tags.map((t, order) => [t.slug, { ...t, order }]));
}

/** Every ancestor slug of `slug` (nearest first). */
export function ancestorsOf(slug: string, index: TagIndex): string[] {
  const out: string[] = [];
  for (let p = index.get(slug)?.parent; p && !out.includes(p); p = index.get(p)?.parent) {
    out.push(p);
  }
  return out;
}

/**
 * Resolve slugs to tags in display order, dropping any tag implied by a more
 * specific one in the same set. Unknown slugs become topic tags named by slug.
 */
export function displayTags(slugs: string[], index: TagIndex): IndexedTag[] {
  const implied = new Set(slugs.flatMap((s) => ancestorsOf(s, index)));
  return [...new Set(slugs)]
    .filter((s) => !implied.has(s))
    .map(
      (s): IndexedTag =>
        index.get(s) ?? {
          slug: s,
          name: s,
          facet: 'topic',
          parent: null,
          description: null,
          start_year: null,
          end_year: null,
          chronicle_count: 0,
          entity_count: 0,
          order: Number.MAX_SAFE_INTEGER,
        },
    )
    .sort((a, b) => a.order - b.order);
}

/**
 * Toggle one tag in a filter selection. Adding a tag drops its selected
 * ancestors and descendants: picking China after Asia narrows to China, rather
 * than OR-ing it with all of Asia.
 */
export function toggleTag(selected: string[], slug: string, index: TagIndex): string[] {
  if (selected.includes(slug)) return selected.filter((s) => s !== slug);
  const ancestors = new Set(ancestorsOf(slug, index));
  return [
    ...selected.filter((s) => !ancestors.has(s) && !ancestorsOf(s, index).includes(slug)),
    slug,
  ];
}

/** Child tags of `slug` (or top-level tags of a facet when `slug` is null). */
export function childrenOf(
  slug: string | null,
  facet: TagFacet,
  tags: IndexedTag[],
): IndexedTag[] {
  return tags.filter((t) => t.facet === facet && t.parent === slug);
}

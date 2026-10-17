/** Zod schema for GET /tags — the vocabulary shared by chronicles and entities. */
import { z } from 'zod';

export const TAG_FACETS = ['era', 'region', 'theme', 'type', 'topic'] as const;
export type TagFacet = (typeof TAG_FACETS)[number];

export const TagSchema = z.object({
  slug: z.string(),
  name: z.string(),
  facet: z.enum(TAG_FACETS).catch('topic'),
  /** Broader tag this one implies (china → east-asia → asia). */
  parent: z.string().nullable().default(null),
  description: z.string().nullable().default(null),
  start_year: z.number().nullable().default(null),
  end_year: z.number().nullable().default(null),
  chronicle_count: z.number().default(0),
  entity_count: z.number().default(0),
});
export type Tag = z.infer<typeof TagSchema>;

/** Ordered by facet, then vocabulary order (the API's order is the display order). */
export const TagListSchema = z.object({
  data: z.array(TagSchema),
});
export type TagList = z.infer<typeof TagListSchema>;

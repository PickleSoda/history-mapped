/** Zod schemas for search, highlights, and timeline-density responses. */
import { z } from 'zod';
import { EntitySummarySchema } from './entity';

export const SearchResultsSchema = z.object({
  items: z.array(EntitySummarySchema),
  total: z.number(),
});
export type SearchResults = z.infer<typeof SearchResultsSchema>;

export const HighlightCardSchema = z.object({
  id: z.string(),
  title: z.string(),
  /** Type-prefixed entity id this card links into (?sel=). */
  sel: z.string(),
});

export const HighlightsSchema = z.object({
  items: z.array(HighlightCardSchema),
});
export type Highlights = z.infer<typeof HighlightsSchema>;

/** Histogram bar under the scrubber: count of entities active in a year band. */
export const DensityBucketSchema = z.object({
  year: z.number(),
  count: z.number(),
});

export const DensitySchema = z.object({
  buckets: z.array(DensityBucketSchema),
});
export type Density = z.infer<typeof DensitySchema>;

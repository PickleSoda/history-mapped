/**
 * Zod schema for GET /map-stories — the battle-map (map story) index for the
 * public browse pages (spec 2026-11-01 public site, D4). Rows extend the
 * summary the entity and chronicle payloads already carry with the story's
 * entity and chronicle, when it has them. Lenient: an unknown key is dropped,
 * a malformed optional field degrades to null rather than failing the page.
 */
import { z } from 'zod';
import { MapStorySummarySchema } from './map-story';

const PaginatorMetaSchema = z.object({
  current_page: z.number(),
  last_page: z.number(),
  per_page: z.number(),
  total: z.number(),
});

/** The entity a story is about (a battle, a siege, an epidemic…). */
export const MapStoryEntityRefSchema = z.object({
  id: z.string(),
  name: z.string(),
  entity_type: z.string().nullable().catch(null).default(null),
});
export type MapStoryEntityRef = z.infer<typeof MapStoryEntityRefSchema>;

/** The chronicle a story is the map layer of. */
export const MapStoryChronicleRefSchema = z.object({
  slug: z.string(),
  title: z.string(),
});
export type MapStoryChronicleRef = z.infer<typeof MapStoryChronicleRefSchema>;

/** One row of GET /map-stories (MapStorySummaryResource). */
export const MapStoryListItemSchema = MapStorySummarySchema.extend({
  entity: MapStoryEntityRefSchema.nullable().catch(null).default(null),
  chronicle: MapStoryChronicleRefSchema.nullable().catch(null).default(null),
});
export type MapStoryListItem = z.infer<typeof MapStoryListItemSchema>;

/** GET /map-stories — Laravel-paginated. */
export const MapStoryListSchema = z.object({
  data: z.array(MapStoryListItemSchema),
  meta: PaginatorMetaSchema,
});
export type MapStoryList = z.infer<typeof MapStoryListSchema>;

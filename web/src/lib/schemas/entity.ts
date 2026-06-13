/**
 * Zod schemas for entity API responses.
 *
 * NOTE: the viewport endpoint contract is provisional — it is defined by the
 * backend map-query-optimization work. These schemas encode the shape the
 * frontend needs (prominence-ranked summaries with an optional point for pins,
 * a total count for the "show all N" affordance) and validate at the boundary.
 */
import { z } from 'zod';
import { ENTITY_GROUPS } from '@/types/atlas';

export const EntityGroupSchema = z.enum(ENTITY_GROUPS);

/** Lightweight summary used for map pins and the "notable here" list. */
export const EntitySummarySchema = z.object({
  id: z.string(),
  group: EntityGroupSchema,
  name: z.string(),
  /** Prominence score for the current scope; drives ranking. */
  prominence: z.number().default(0),
  /** [lng, lat] for a point pin, or null when the entity is not placed. */
  point: z.tuple([z.number(), z.number()]).nullable().default(null),
  /** True when the entity carries polygon geometry (territory overlay). */
  hasGeometry: z.boolean().default(false),
});
export type EntitySummary = z.infer<typeof EntitySummarySchema>;

/** Viewport response: ranked items + total count for the current scope. */
export const EntitiesInViewSchema = z.object({
  items: z.array(EntitySummarySchema),
  total: z.number(),
});
export type EntitiesInView = z.infer<typeof EntitiesInViewSchema>;

/** Full detail-panel payload. Kept loose where the contract is still forming. */
export const EntityDetailSchema = z.object({
  id: z.string(),
  group: EntityGroupSchema,
  name: z.string(),
  summary: z.string().nullable().default(null),
  /** GeoJSON geometry or null ("not placed"). */
  geometry: z.unknown().nullable().default(null),
  attributes: z.record(z.string(), z.unknown()).default({}),
});
export type EntityDetail = z.infer<typeof EntityDetailSchema>;

export const EntityConnectionSchema = z.object({
  id: z.string(),
  group: EntityGroupSchema,
  name: z.string(),
  relationship: z.string(),
});

export const EntityConnectionsSchema = z.object({
  items: z.array(EntityConnectionSchema),
});
export type EntityConnections = z.infer<typeof EntityConnectionsSchema>;

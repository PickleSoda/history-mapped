/**
 * Zod schemas for the real entity endpoints.
 *
 * - List/search: GET /entities  -> EntitySummaryResource collection (paginated).
 * - Detail:      GET /entities/{id} -> EntityResource.
 * - Connections: GET /entities/{id}/relationships -> RelationshipResource collection.
 *
 * Backend entity_group is UPPERCASE (POLITY, …); we map it to the frontend's
 * lowercase EntityGroup at the boundary.
 */
import { z } from 'zod';
import { ENTITY_GROUPS } from '@/types/atlas';

/** Map the backend's UPPERCASE group to the frontend lowercase token. */
export const GroupFromApi = z
  .string()
  .transform((v) => v.toLowerCase())
  .pipe(z.enum(ENTITY_GROUPS));

/** One row of the "notable here" list / search results (EntitySummaryResource). */
export const EntitySummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  entity_type: z.string().nullable().default(null),
  entity_group: GroupFromApi,
  summary: z.string().nullable().default(null),
  impact_score: z.number().nullable().default(null),
  temporal_start: z.number().nullable().default(null),
  temporal_end: z.number().nullable().default(null),
  era_label: z.string().nullable().default(null),
  location_name: z.string().nullable().default(null),
  /** GeoJSON point geometry or null (unplaced). */
  geom: z.unknown().nullable().default(null),
  icon_class: z.string().nullable().default(null),
});
export type EntitySummary = z.infer<typeof EntitySummarySchema>;

/** Laravel paginator meta (only the fields we use). */
const PaginatorMetaSchema = z.object({
  current_page: z.number(),
  last_page: z.number(),
  per_page: z.number(),
  total: z.number(),
});

/** GET /entities — paginated EntitySummaryResource collection. */
export const EntityListSchema = z.object({
  data: z.array(EntitySummarySchema),
  meta: PaginatorMetaSchema,
});
export type EntityList = z.infer<typeof EntityListSchema>;

/**
 * GET /entities/{id} — EntityResource. Kept permissive: the detail panel reads
 * a known subset and the resource carries many optional/conditional fields.
 */
export const EntityDetailSchema = z.object({
  id: z.string(),
  name: z.string(),
  entity_type: z.string().nullable().default(null),
  entity_group: GroupFromApi,
  summary: z.string().nullable().default(null),
  significance: z.string().nullable().default(null),
  impact_score: z.number().nullable().default(null),
  attributes: z.record(z.string(), z.unknown()).default({}),
  temporal_start: z.union([z.number(), z.string()]).nullable().default(null),
  temporal_end: z.union([z.number(), z.string()]).nullable().default(null),
  era_label: z.string().nullable().default(null),
  location_name: z.string().nullable().default(null),
  /** GeoJSON geometry or null ("not placed"). */
  geom: z.unknown().nullable().default(null),
  icon_class: z.string().nullable().default(null),
});
export type EntityDetail = z.infer<typeof EntityDetailSchema>;

/** One relationship (RelationshipResource). The endpoint eager-loads both
 *  related entities, so the summaries are present. */
export const RelationshipSchema = z.object({
  id: z.string(),
  source_entity_id: z.string(),
  target_entity_id: z.string(),
  relationship_type: z.string().nullable().default(null),
  temporal_start: z.number().nullable().default(null),
  temporal_end: z.number().nullable().default(null),
  description: z.string().nullable().default(null),
  source_entity: EntitySummarySchema.optional(),
  target_entity: EntitySummarySchema.optional(),
});
export type Relationship = z.infer<typeof RelationshipSchema>;

/** GET /entities/{id}/relationships — RelationshipResource collection. */
export const RelationshipsSchema = z.object({
  data: z.array(RelationshipSchema),
});
export type Relationships = z.infer<typeof RelationshipsSchema>;

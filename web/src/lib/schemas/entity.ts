/**
 * Zod schemas for the real entity endpoints.
 *
 * - List/search: GET /entities  -> EntitySummaryResource collection (paginated).
 * - Detail:      GET /entities/{id} -> EntityResource.
 * - Connections: GET /entities/{id}/relationships -> RelationshipResource collection.
 * - Timeline:    GET /entities/{id}/timeline -> EntityTimelineEntrySummaryResource collection.
 *
 * Backend entity_group is UPPERCASE (POLITY, …); we map it to the frontend's
 * lowercase EntityGroup at the boundary.
 */
import { z } from 'zod';
import { ENTITY_GROUPS } from '@/types/atlas';

/** Map the backend's UPPERCASE group to the frontend lowercase token. Tolerant:
 *  an unexpected/null group falls back rather than failing the whole response. */
export const GroupFromApi = z
  .string()
  .transform((v) => v.toLowerCase())
  .pipe(z.enum(ENTITY_GROUPS))
  .catch('polity');

/** One row of the "notable here" list / search results (EntitySummaryResource). */
export const EntitySummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  entity_type: z.string().nullable().default(null),
  entity_group: GroupFromApi,
  summary: z.string().nullable().default(null),
  impact_score: z.number().nullable().default(null),
  /** Backend returns these as DATE strings (or null), not year numbers. */
  temporal_start: z.union([z.number(), z.string()]).nullable().default(null),
  temporal_end: z.union([z.number(), z.string()]).nullable().default(null),
  /** Pre-formatted display range, when available. */
  temporal_display_range: z.string().nullable().default(null),
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

/** Trust levels (ConfidenceLevel enum). Unknown values degrade to null. */
export const CONFIDENCE_LEVELS = ['high', 'medium', 'low', 'unresolved'] as const;
export type ConfidenceLevel = (typeof CONFIDENCE_LEVELS)[number];
export const ConfidenceSchema = z.enum(CONFIDENCE_LEVELS).nullable().catch(null);

/** Review ladder (VerificationStatus enum), lowest → highest. */
export const VERIFICATION_STATUSES = [
  'pipeline_draft',
  'needs_review',
  'human_verified',
  'expert_verified',
] as const;
export type VerificationStatus = (typeof VERIFICATION_STATUSES)[number];

/** A list of strings; anything else (null, `{}`) becomes `[]`. */
const StringList = z.array(z.string()).catch([]);

/**
 * GET /entities/{id} — EntityResource. Kept permissive: the resource carries
 * many optional/conditional fields, and the free-form JSON ones
 * (`source_citations`, `media_refs`) are passed through untyped for the page to
 * render defensively.
 */
export const EntityDetailSchema = z.object({
  id: z.string(),
  name: z.string(),
  alternative_names: StringList,
  wikidata_id: z.string().nullable().default(null),
  entity_type: z.string().nullable().default(null),
  entity_group: GroupFromApi,
  summary: z.string().nullable().default(null),
  significance: z.string().nullable().default(null),
  tags: StringList,
  impact_score: z.number().nullable().default(null),
  // Backend sends `[]` (a JSON array) when an entity has no attributes, which a
  // strict record() would reject — tolerate it.
  attributes: z.record(z.string(), z.unknown()).catch({}),
  temporal_start: z.union([z.number(), z.string()]).nullable().default(null),
  temporal_end: z.union([z.number(), z.string()]).nullable().default(null),
  /** The source's own date wording (e.g. "c. 490 BC"), shown on hover. */
  date_raw: z.string().nullable().catch(null),
  date_confidence: z.string().nullable().catch(null),
  temporal_display_range: z.string().nullable().default(null),
  era_label: z.string().nullable().default(null),
  location_name: z.string().nullable().default(null),
  /** GeoJSON geometry or null ("not placed"). */
  geom: z.unknown().nullable().default(null),
  icon_class: z.string().nullable().default(null),
  confidence: ConfidenceSchema,
  confidence_notes: z.string().nullable().catch(null),
  verification_status: z.enum(VERIFICATION_STATUSES).nullable().catch(null),
  /** Free-form citation JSON (object of keys today; arrays tolerated). */
  source_citations: z.unknown().nullable().default(null),
  media_refs: z.unknown().nullable().default(null),
  timeline_entries_count: z.number().nullable().catch(null),
});
export type EntityDetail = z.infer<typeof EntityDetailSchema>;

/** One relationship (RelationshipResource). The endpoint eager-loads both
 *  related entities, so the summaries are present. */
export const RelationshipSchema = z.object({
  id: z.string(),
  source_entity_id: z.string(),
  target_entity_id: z.string(),
  relationship_type: z.string().nullable().default(null),
  temporal_start: z.union([z.number(), z.string()]).nullable().default(null),
  temporal_end: z.union([z.number(), z.string()]).nullable().default(null),
  description: z.string().nullable().default(null),
  confidence: ConfidenceSchema,
  source_citations: z.unknown().nullable().default(null),
  source_entity: EntitySummarySchema.optional(),
  target_entity: EntitySummarySchema.optional(),
});
export type Relationship = z.infer<typeof RelationshipSchema>;

/** GET /entities/{id}/relationships — RelationshipResource collection. */
export const RelationshipsSchema = z.object({
  data: z.array(RelationshipSchema),
});
export type Relationships = z.infer<typeof RelationshipsSchema>;

/** One derived timeline row (EntityTimelineEntrySummaryResource). */
export const EntityTimelineEntrySchema = z.object({
  id: z.string(),
  entity_id: z.string(),
  /** e.g. "relationship", "territory", "event". */
  entry_kind: z.string().nullable().default(null),
  start_year: z.number().nullable().default(null),
  end_year: z.number().nullable().default(null),
  title: z.string().nullable().default(null),
  description: z.string().nullable().default(null),
  relationship_type: z.string().nullable().default(null),
  related_entity_id: z.string().nullable().default(null),
  related_entity_name: z.string().nullable().default(null),
});
export type EntityTimelineEntry = z.infer<typeof EntityTimelineEntrySchema>;

/** GET /entities/{id}/timeline — ordered by start year server-side. */
export const EntityTimelineSchema = z.object({
  data: z.array(EntityTimelineEntrySchema),
});
export type EntityTimeline = z.infer<typeof EntityTimelineSchema>;

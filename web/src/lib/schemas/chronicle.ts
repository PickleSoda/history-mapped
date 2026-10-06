/** Zod schema for GET /chronicles/{slug} (ChronicleResource + entries). */
import { z } from 'zod';
import { RelationshipSchema } from './entity';

/** A secondary entity referenced by a chronicle entry. */
const SecondaryEntitySchema = z.object({
  entity_id: z.string(),
  name: z.string(),
  entity_type: z.string().nullable().default(null),
  role: z.string().nullable().default(null),
});

/** One chronicle entry (ChronicleEntryResource) — a step in the tour. */
export const ChronicleEntrySchema = z.object({
  entry_id: z.string(),
  sequence_order: z.number(),
  start_year: z.number().nullable().default(null),
  end_year: z.number().nullable().default(null),
  impact_score: z.number().nullable().default(null),
  approximate_location: z.unknown().nullable().default(null),
  narrative_text: z.string().nullable().default(null),
  primary_relationship: RelationshipSchema.nullable().optional(),
  secondary_entities: z.array(SecondaryEntitySchema).optional(),
});
export type ChronicleEntry = z.infer<typeof ChronicleEntrySchema>;

export const ChronicleSchema = z.object({
  chronicle_id: z.string(),
  title: z.string(),
  slug: z.string(),
  /** SourceType enum, e.g. "video_transcript". */
  source_type: z.string().nullable().catch(null),
  /** Free text: a URL, a citation, or an excerpt of the source transcript. */
  source_reference: z.string().nullable().catch(null),
  status: z.string().nullable().catch(null),
  start_year: z.number().nullable().default(null),
  end_year: z.number().nullable().default(null),
  impact_score: z.number().nullable().default(null),
  approximate_location: z.unknown().nullable().default(null),
  /** Generation stats (event_count, generated_at, …); shape not fixed. */
  metadata: z.record(z.string(), z.unknown()).nullable().catch(null),
  entries: z.array(ChronicleEntrySchema).default([]),
});
export type Chronicle = z.infer<typeof ChronicleSchema>;

/** Lightweight chronicle row for the listing (GET /chronicles). */
export const ChronicleSummarySchema = z.object({
  chronicle_id: z.string(),
  title: z.string(),
  slug: z.string(),
  start_year: z.number().nullable().default(null),
  end_year: z.number().nullable().default(null),
  impact_score: z.number().nullable().default(null),
  entry_count: z.number().nullable().default(null),
  status: z.string().nullable().default(null),
});
export type ChronicleSummary = z.infer<typeof ChronicleSummarySchema>;

const PaginatorMetaSchema = z.object({
  current_page: z.number(),
  last_page: z.number(),
  per_page: z.number(),
  total: z.number(),
});

/** GET /chronicles — paginated ChronicleResource collection. */
export const ChronicleListSchema = z.object({
  data: z.array(ChronicleSummarySchema),
  meta: PaginatorMetaSchema,
});
export type ChronicleList = z.infer<typeof ChronicleListSchema>;

/** One chronicle an entity belongs to (GET /entities/{id}/chronicles). Carries
 *  the relationship ids it uses so rows can be flagged as "in a chronicle". */
export const EntityChronicleRefSchema = z.object({
  chronicle_id: z.string(),
  title: z.string(),
  slug: z.string(),
  relationship_ids: z.array(z.string()).default([]),
});
export type EntityChronicleRef = z.infer<typeof EntityChronicleRefSchema>;

export const EntityChroniclesSchema = z.object({
  data: z.array(EntityChronicleRefSchema),
});
export type EntityChronicles = z.infer<typeof EntityChroniclesSchema>;

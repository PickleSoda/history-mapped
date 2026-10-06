/**
 * Zod schemas for the relation-graph endpoints (docs/schemas/relation-graph-api.md).
 *
 * - Entity graph:    GET /entities/{id}/graph    -> { root, nodes, edges, truncated }
 * - Chronicle graph: GET /chronicles/{slug}/graph -> { chronicle_id, slug, nodes, edges, steps }
 *
 * Both share one node and one edge shape; the chronicle variant adds
 * `in_chronicle` / `steps` on nodes and `scope` / `steps` on edges. Those are
 * optional on the base types so the shared graph logic and `RelationGraph`
 * take either payload.
 */
import { z } from 'zod';
import { ConfidenceSchema, GroupFromApi } from './entity';

const Year = z.number().nullable().default(null);

export const EDGE_SCOPES = ['primary', 'internal', 'external'] as const;
export type EdgeScope = (typeof EDGE_SCOPES)[number];

/** A graph node — one entity. `impact_score` is an integer 1–100. */
export const GraphNodeSchema = z.object({
  id: z.string(),
  name: z.string(),
  entity_type: z.string().nullable().default(null),
  entity_group: GroupFromApi,
  start_year: Year,
  end_year: Year,
  impact_score: z.number().nullable().default(null),
  /** Hops from the root (entity graph) or 0 in / 1 outside (chronicle graph). */
  depth: z.number().default(1),
  /** Chronicle graph only: false for external entities. */
  in_chronicle: z.boolean().optional(),
  /** Chronicle graph only: `sequence_order`s of the steps containing it. */
  steps: z.array(z.number()).optional(),
});
export type GraphNode = z.infer<typeof GraphNodeSchema>;

/** A graph edge — one relationship, directed source → target. */
export const GraphEdgeSchema = z.object({
  id: z.string(),
  source: z.string(),
  target: z.string(),
  relationship_type: z.string().nullable().default(null),
  start_year: Year,
  end_year: Year,
  description: z.string().nullable().default(null),
  confidence: ConfidenceSchema,
  /** Chronicle graph only. */
  scope: z.enum(EDGE_SCOPES).optional(),
  /** Chronicle graph only: `sequence_order`s whose step includes it. */
  steps: z.array(z.number()).optional(),
});
export type GraphEdge = z.infer<typeof GraphEdgeSchema>;

/** GET /entities/{id}/graph (unwrapped from `data`). */
export const EntityGraphSchema = z.object({
  root: z.string(),
  nodes: z.array(GraphNodeSchema),
  edges: z.array(GraphEdgeSchema),
  truncated: z.boolean().default(false),
});
export type EntityGraph = z.infer<typeof EntityGraphSchema>;

/** One chronicle entry's slice of the chronicle graph. */
export const ChronicleGraphStepSchema = z.object({
  entry_id: z.string(),
  sequence_order: z.number(),
  start_year: Year,
  end_year: Year,
  primary_relationship_id: z.string().nullable().default(null),
  /** Pivot entities + the primary relationship's two ends. */
  entity_ids: z.array(z.string()).default([]),
  /** The primary relationship + every non-external edge among `entity_ids`. */
  relationship_ids: z.array(z.string()).default([]),
});
export type ChronicleGraphStep = z.infer<typeof ChronicleGraphStepSchema>;

/** GET /chronicles/{slug}/graph (unwrapped from `data`). */
export const ChronicleGraphSchema = z.object({
  chronicle_id: z.string(),
  slug: z.string(),
  nodes: z.array(
    GraphNodeSchema.extend({
      in_chronicle: z.boolean().default(true),
      steps: z.array(z.number()).default([]),
    }),
  ),
  edges: z.array(
    GraphEdgeSchema.extend({
      scope: z.enum(EDGE_SCOPES).catch('internal'),
      steps: z.array(z.number()).default([]),
    }),
  ),
  steps: z.array(ChronicleGraphStepSchema).default([]),
});
export type ChronicleGraph = z.infer<typeof ChronicleGraphSchema>;

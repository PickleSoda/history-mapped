/**
 * Zod schema for GET /map-stories/{slug} — a step-by-step battle map (schema 1).
 *
 * The vocabulary mirrors pipeline/map_stories/schema.py and the API's
 * MapStoryDocument; the authoring guide is docs/implementation-docs/
 * map-story-authoring.md. Parsing is tolerant where the renderer can cope
 * (unknown unit kinds draw as generic blocks) and strict where it can't
 * (coordinates).
 */
import { z } from 'zod';

export const LngLatSchema = z.tuple([z.number(), z.number()]);
export type LngLat = z.infer<typeof LngLatSchema>;

const CameraSchema = z.object({
  center: LngLatSchema,
  zoom: z.number(),
  bearing: z.number().optional(),
});
export type StoryCamera = z.infer<typeof CameraSchema>;

const LinkedSchema = z.object({
  name: z.string(),
  wikidata: z.string().nullish(),
  entity_id: z.string().nullish(),
  role: z.string().nullish(),
});
export type StoryLinked = z.infer<typeof LinkedSchema>;

const SideSchema = z.object({
  id: z.string(),
  name: z.string(),
  color: z.string(),
  polity: LinkedSchema.nullish(),
  commanders: z.array(LinkedSchema).default([]),
  strength: z.string().nullish(),
  losses: z.string().nullish(),
});
export type StorySide = z.infer<typeof SideSchema>;

export const UNIT_KINDS = [
  'infantry', 'heavy_infantry', 'light_infantry', 'pikemen', 'archers', 'slingers',
  'crossbowmen', 'musketeers', 'cavalry', 'heavy_cavalry', 'light_cavalry',
  'horse_archers', 'chariots', 'elephants', 'camels', 'artillery', 'siege_engine',
  'warship', 'transport', 'commander', 'camp', 'baggage',
] as const;
export type UnitKind = (typeof UNIT_KINDS)[number];

/** Kinds drawn as a single pin rather than a formation block. */
export const POINT_UNIT_KINDS: readonly string[] = ['commander', 'camp', 'baggage'];

const UnitSchema = z.object({
  id: z.string(),
  side: z.string(),
  kind: z.string(),
  label: z.string(),
  strength: z.string().nullish(),
  commander: z.string().nullish(),
  note: z.string().nullish(),
  wikidata: z.string().nullish(),
  entity_id: z.string().nullish(),
});
export type StoryUnit = z.infer<typeof UnitSchema>;

export const SHAPES = ['block', 'line', 'column', 'wedge', 'crescent', 'square', 'circle'] as const;
export type Shape = (typeof SHAPES)[number];
export const UNIT_STATES = ['ready', 'engaged', 'wavering', 'routed', 'destroyed', 'hidden'] as const;
export type UnitState = (typeof UNIT_STATES)[number];

const PlacementSchema = z.object({
  at: LngLatSchema.optional(),
  with: z.string().optional(),
  facing: z.number().optional(),
  width: z.number().optional(),
  depth: z.number().optional(),
  shape: z.enum(SHAPES).optional().catch(undefined),
  curve: z.number().optional(),
  state: z.enum(UNIT_STATES).optional().catch(undefined),
  label: z.string().optional(),
  strength: z.string().optional(),
});
export type Placement = z.infer<typeof PlacementSchema>;

export const MOVE_TYPES = [
  'advance', 'attack', 'charge', 'flank', 'feint', 'retreat', 'rout', 'pursuit', 'march', 'fire',
] as const;
export type MoveType = (typeof MOVE_TYPES)[number];

const MoveSchema = z.object({
  unit: z.string().nullish(),
  side: z.string().nullish(),
  type: z.enum(MOVE_TYPES).catch('advance'),
  path: z.array(LngLatSchema).min(2),
  label: z.string().nullish(),
});
export type StoryMove = z.infer<typeof MoveSchema>;

const NoteSchema = z.object({
  at: LngLatSchema,
  text: z.string(),
  kind: z.enum(['label', 'clash', 'death', 'capture', 'event']).catch('label').default('label'),
});
export type StoryNote = z.infer<typeof NoteSchema>;

const TerrainSchema = z.object({
  id: z.string(),
  kind: z.string(),
  label: z.string().nullish(),
  at: LngLatSchema.optional(),
  line: z.array(LngLatSchema).optional(),
  area: z.array(LngLatSchema).optional(),
});
export type StoryTerrain = z.infer<typeof TerrainSchema>;

const StepSchema = z.object({
  id: z.string(),
  title: z.string(),
  time: z.string().nullish(),
  narrative: z.string().default(''),
  camera: CameraSchema.nullish(),
  positions: z.record(z.string(), PlacementSchema).default({}),
  moves: z.array(MoveSchema).default([]),
  notes: z.array(NoteSchema).default([]),
  focus: z.array(z.string()).default([]),
});
export type StoryStep = z.infer<typeof StepSchema>;

const SourceSchema = z.object({
  title: z.string(),
  url: z.string().nullish(),
  kind: z.string().nullish(),
});

export const MapStoryDocumentSchema = z.object({
  schema: z.number(),
  slug: z.string(),
  kind: z.string(),
  entity: LinkedSchema,
  title: z.string(),
  date_label: z.string().default(''),
  year: z.number(),
  intro: z.string().default(''),
  outcome: z.string().default(''),
  uncertainty: z.string().nullish(),
  sources: z.array(SourceSchema).default([]),
  camera: CameraSchema.nullish(),
  sides: z.array(SideSchema),
  units: z.array(UnitSchema),
  terrain: z.array(TerrainSchema).default([]),
  steps: z.array(StepSchema).min(1),
});
export type MapStoryDocument = z.infer<typeof MapStoryDocumentSchema>;

/** GET /map-stories/{slug} (unwrapped from the `data` envelope). */
export const MapStorySchema = z.object({
  id: z.string(),
  slug: z.string(),
  kind: z.string(),
  title: z.string(),
  year: z.number().nullable().default(null),
  step_count: z.number().nullable().default(null),
  entity_id: z.string().nullable().default(null),
  document: MapStoryDocumentSchema,
});
export type MapStory = z.infer<typeof MapStorySchema>;

/** The light list row an entity carries (EntityResource.map_stories). */
export const MapStorySummarySchema = z.object({
  id: z.string(),
  slug: z.string(),
  kind: z.string(),
  title: z.string(),
  year: z.number().nullable().default(null),
  step_count: z.number().nullable().default(null),
});
export type MapStorySummary = z.infer<typeof MapStorySummarySchema>;

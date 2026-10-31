/**
 * Zod schema for GET /map-stories/{slug} — a step-by-step battle map (schema 1
 * or 2; v2 fields are optional and additive).
 *
 * The vocabulary mirrors pipeline/map_stories/schema.py and the API's
 * MapStoryDocument; the authoring guide is docs/implementation-docs/
 * map-story-authoring.md, the v2 contract docs/superpowers/specs/
 * 2026-10-31-map-story-schema-v2-design.md. Parsing is tolerant where the
 * renderer can cope (unknown unit kinds draw as generic blocks, unknown enums
 * fall back to the v1 default, a malformed v2 extra is dropped) and strict
 * where it can't (coordinates).
 */
import { z } from 'zod';

export const LngLatSchema = z.tuple([z.number(), z.number()]);
export type LngLat = z.infer<typeof LngLatSchema>;

/** An optional field that drops to `undefined` rather than failing the story. */
const loose = <T extends z.ZodType>(schema: T) => schema.optional().catch(undefined);

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

/** v2: a contingent within a side (Hanoverians under Wellington, a satrapy). */
const ContingentSchema = z.object({
  id: z.string(),
  name: z.string(),
  color: z.string().nullish(),
});
export type StoryContingent = z.infer<typeof ContingentSchema>;

const SideSchema = z.object({
  id: z.string(),
  name: z.string(),
  color: z.string(),
  polity: LinkedSchema.nullish(),
  commanders: z.array(LinkedSchema).default([]),
  strength: z.string().nullish(),
  losses: z.string().nullish(),
  contingents: z.array(ContingentSchema).default([]).catch([]),
});
export type StorySide = z.infer<typeof SideSchema>;

export const UNIT_KINDS = [
  'infantry', 'heavy_infantry', 'light_infantry', 'pikemen', 'archers', 'slingers',
  'crossbowmen', 'musketeers', 'cavalry', 'heavy_cavalry', 'light_cavalry',
  'horse_archers', 'chariots', 'elephants', 'camels', 'artillery', 'siege_engine',
  'warship', 'transport', 'commander', 'camp', 'baggage', 'standard', 'ship',
] as const;
export type UnitKind = (typeof UNIT_KINDS)[number];

/** Kinds drawn as a single pin rather than a formation block. */
export const POINT_UNIT_KINDS: readonly string[] = ['commander', 'camp', 'baggage', 'standard', 'ship'];

/** Kinds that are hulls: they can be `sunk` or run `aground`. */
export const HULL_UNIT_KINDS: readonly string[] = ['warship', 'ship', 'transport'];

/** v2: one band of a composite unit, front to back. */
const RankSchema = z.object({ kind: z.string(), share: z.number() });
export type StoryRank = z.infer<typeof RankSchema>;

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
  // v2
  ranks: loose(z.array(RankSchema)),
  strength_n: loose(z.number()),
  contingent: loose(z.string()),
});
export type StoryUnit = z.infer<typeof UnitSchema>;

export const SHAPES = ['block', 'line', 'column', 'wedge', 'crescent', 'square', 'circle'] as const;
export type Shape = (typeof SHAPES)[number];
export const UNIT_STATES = [
  'ready', 'engaged', 'wavering', 'routed', 'destroyed', 'hidden',
  // v2
  'killed', 'wounded', 'captured', 'sunk', 'aground', 'burning',
] as const;
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
  // v2
  strength_n: loose(z.number()),
  /** `false`: drawn, but left out of the step's camera framing. */
  frame: loose(z.boolean()),
  /** Detaches from this unit (first placement only). */
  from: loose(z.string()),
  /** Merges into this unit during the step, then leaves the field. */
  into: loose(z.string()),
  /** The captor side, with state `captured`. */
  by: loose(z.string()),
  lines: loose(z.number()),
  lanes: loose(z.number()),
  subunits: loose(z.number()),
  conjectural: loose(z.boolean()),
});
export type Placement = z.infer<typeof PlacementSchema>;

export const MOVE_TYPES = [
  'advance', 'attack', 'charge', 'flank', 'feint', 'retreat', 'rout', 'pursuit', 'march', 'fire',
  // v2
  'ram', 'back_water', 'blockade', 'landing',
] as const;
export type MoveType = (typeof MOVE_TYPES)[number];

const MoveSchema = z.object({
  unit: z.string().nullish(),
  side: z.string().nullish(),
  type: z.enum(MOVE_TYPES).catch('advance'),
  path: z.array(LngLatSchema).min(2),
  label: z.string().nullish(),
  // v2
  /** A fading tail from the arrow's end toward a far (possibly off-map) point. */
  continues: loose(z.object({ toward: LngLatSchema, label: z.string().nullish() })),
  /** The unit's facing follows the path while it moves. */
  orient: loose(z.enum(['path'])),
  /** `fire`: the arrow ends on this unit's position (the path's last point is ignored). */
  target: loose(z.string()),
  /** A ballistic arc instead of a straight line. */
  arc: loose(z.boolean()),
  conjectural: loose(z.boolean()),
});
export type StoryMove = z.infer<typeof MoveSchema>;

export const NOTE_KINDS = ['label', 'clash', 'death', 'capture', 'event'] as const;

const NoteSchema = z.object({
  at: LngLatSchema,
  text: z.string(),
  kind: z.enum(NOTE_KINDS).catch('label').default('label'),
  conjectural: loose(z.boolean()),
});
export type StoryNote = z.infer<typeof NoteSchema>;

const TerrainSchema = z.object({
  id: z.string(),
  kind: z.string(),
  label: z.string().nullish(),
  at: LngLatSchema.optional(),
  line: z.array(LngLatSchema).optional(),
  area: z.array(LngLatSchema).optional(),
  conjectural: loose(z.boolean()),
});
export type StoryTerrain = z.infer<typeof TerrainSchema>;

export const TERRAIN_STATES = ['held', 'contested', 'captured', 'burning', 'destroyed', 'flooded'] as const;
export type TerrainState = (typeof TERRAIN_STATES)[number];

/** v2: who holds a strongpoint and what state it is in; `held_by: null` clears the holder. */
const TerrainStateSchema = z.object({
  held_by: z.string().nullish().catch(undefined),
  state: z.enum(TERRAIN_STATES).nullish().catch(undefined),
  label: z.string().nullish().catch(undefined),
});
export type StoryTerrainState = z.infer<typeof TerrainStateSchema>;

export const LIGHTS = ['night', 'dawn', 'day', 'dusk'] as const;
export type Light = (typeof LIGHTS)[number];

const WindSchema = z.object({
  /** Compass bearing the wind blows from. */
  from: z.number(),
  strength: loose(z.enum(['light', 'strong'])),
  label: z.string().nullish(),
});
export type StoryWind = z.infer<typeof WindSchema>;

const SunSchema = z.object({ from: z.number(), label: z.string().nullish() });
export type StorySun = z.infer<typeof SunSchema>;

/** v2: a sub-phase of a step, played after the step's own movement. */
const BeatSchema = z.object({
  label: z.string().default(''),
  positions: z.record(z.string(), PlacementSchema).default({}),
  moves: z.array(MoveSchema).default([]),
  notes: z.array(NoteSchema).default([]),
});
export type StoryBeat = z.infer<typeof BeatSchema>;

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
  // v2
  beats: z.array(BeatSchema).default([]).catch([]),
  terrain_state: z.record(z.string(), TerrainStateSchema.nullable()).default({}).catch({}),
  /** Light, wind and sun carry forward. */
  light: loose(z.enum(LIGHTS)),
  wind: WindSchema.nullish().catch(undefined),
  sun: SunSchema.nullish().catch(undefined),
});
export type StoryStep = z.infer<typeof StepSchema>;

const SourceSchema = z.object({
  title: z.string(),
  url: z.string().nullish(),
  kind: z.string().nullish(),
});

/** v2: another proposed site of the battle, drawn as a ghost pin. */
const AltSiteSchema = z.object({
  at: LngLatSchema,
  label: z.string(),
  note: z.string().nullish(),
});
export type StoryAltSite = z.infer<typeof AltSiteSchema>;

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
  // v2
  alt_sites: z.array(AltSiteSchema).default([]).catch([]),
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

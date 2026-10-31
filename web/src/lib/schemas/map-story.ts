/**
 * Zod schema for GET /map-stories/{slug} — a step-by-step map story (schema 1,
 * 2 or 3; later fields are optional and additive).
 *
 * The vocabulary mirrors pipeline/map_stories/schema.py and the API's
 * MapStoryDocument; the authoring guide is docs/implementation-docs/
 * map-story-authoring.md, the v2 contract docs/superpowers/specs/
 * 2026-10-31-map-story-schema-v2-design.md, the v3 contract (generic stories:
 * dated steps, step entities, routes/regions/places, chronicle layers, ambient)
 * docs/superpowers/plans/2026-10-31-generic-map-stories.md. Parsing is
 * tolerant where the renderer can cope (unknown unit kinds draw as generic
 * blocks, unknown enums fall back to the v1 default, a malformed extra is
 * dropped) and strict where it can't (coordinates). Aliases (`terrain` →
 * `features`, `terrain_state` → step `features`, a single `area` ring → a list
 * of rings) are resolved once, in `normalizeDocument`.
 */
import type { FeatureCollection } from 'geojson';
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

/** v3: an entity relevant to a step; `show` draws its atlas geometry. */
const StepEntitySchema = LinkedSchema.extend({ show: loose(z.boolean()) });
export type StoryStepEntity = z.infer<typeof StepEntitySchema>;

/** v3: an entity whose atlas geometry stands in for an area (sync adds `entity_id`). */
const EntityRefSchema = z.object({
  name: z.string().nullish(),
  wikidata: z.string().nullish(),
  entity_id: z.string().nullish(),
});
export type StoryEntityRef = z.infer<typeof EntityRefSchema>;

/** v3: a date, in the same year numbering as `year` (negative = BCE). */
const DateSpecSchema = z.object({
  year: z.number(),
  month: loose(z.number().int().min(1).max(12)),
  day: loose(z.number().int().min(1).max(31)),
});
export type StoryDateSpec = z.infer<typeof DateSpecSchema>;

/** v3: a step's date, optionally a span. */
const StepDateSchema = DateSpecSchema.extend({ end: loose(DateSpecSchema) });
export type StoryDate = z.infer<typeof StepDateSchema>;

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
  // v3: campaign-scale markers
  'army', 'fleet', 'caravan', 'merchant_ship', 'expedition', 'group',
] as const;
export type UnitKind = (typeof UNIT_KINDS)[number];

/** Kinds drawn as a single pin rather than a formation block. */
export const POINT_UNIT_KINDS: readonly string[] = [
  'commander', 'camp', 'baggage', 'standard', 'ship',
  'army', 'fleet', 'caravan', 'merchant_ship', 'expedition', 'group',
];

/** Kinds that are hulls: they can be `sunk` or run `aground`. */
export const HULL_UNIT_KINDS: readonly string[] = ['warship', 'ship', 'transport'];

/** v2: one band of a composite unit, front to back. */
const RankSchema = z.object({ kind: z.string(), share: z.number() });
export type StoryRank = z.infer<typeof RankSchema>;

const UnitSchema = z.object({
  id: z.string(),
  /** v3: optional when the story has no sides (drawn in a neutral colour). */
  side: z.string().nullish(),
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
  // v3
  'sail', 'trade', 'migrate', 'explore', 'spread',
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

/** A polygon as one ring or several (a multipolygon of simple polygons). */
const AreaSchema = z.array(z.array(LngLatSchema));

/**
 * A persistent feature: v1/v2 terrain (rivers, woods, villages, masks) and the
 * v3 kinds — places (`city`, `port`, `market`, `mine`, `outbreak`, `site`),
 * `route`s and `region`s. Per-step state (`step.features`) can recolour,
 * resize, move, hide or reshape it.
 */
const FeatureSchema = z.object({
  id: z.string(),
  kind: z.string(),
  label: z.string().nullish(),
  at: LngLatSchema.optional(),
  line: z.array(LngLatSchema).optional(),
  area: AreaSchema.optional(),
  conjectural: loose(z.boolean()),
  // v3
  entity: loose(LinkedSchema),
  side: loose(z.string()),
  goods: z.array(z.string()).default([]).catch([]),
  route_kind: loose(z.string()),
  region_kind: loose(z.string()),
  bidirectional: loose(z.boolean()),
  active: loose(z.boolean()),
  value_n: loose(z.number()),
  value_label: loose(z.string()),
  intensity: loose(z.number()),
});
export type StoryFeature = z.infer<typeof FeatureSchema>;
/** v1/v2 name for a feature. */
export type StoryTerrain = StoryFeature;

/** v3 place kinds: drawn as circles sized by `value_n`. */
export const PLACE_KINDS = ['city', 'port', 'market', 'mine', 'outbreak', 'site'] as const;
export const ROUTE_KINDS = ['trade', 'voyage', 'migration', 'pilgrimage', 'campaign', 'road'] as const;
export const REGION_KINDS = ['spread', 'extent', 'influence', 'affected', 'front'] as const;
/** Feature kinds drawn per step (the rest are static terrain). */
export const DYNAMIC_FEATURE_KINDS: readonly string[] = [...PLACE_KINDS, 'route', 'region'];

export const TERRAIN_STATES = ['held', 'contested', 'captured', 'burning', 'destroyed', 'flooded'] as const;
export const FEATURE_STATES = [
  ...TERRAIN_STATES,
  // v3
  'infected', 'peak', 'recovered', 'founded', 'abandoned', 'disrupted', 'new',
] as const;
export type FeatureState = (typeof FEATURE_STATES)[number];
export type TerrainState = FeatureState;

/**
 * A feature's state at a step. v2: who holds it, its state badge and label
 * (`held_by: null` clears the holder). v3: shown or not, a value and its
 * label, an intensity (0–1), and geometry that replaces the feature's from
 * this step on (`area_from_entity`: an entity's atlas geometry). Each key
 * carries forward on its own.
 */
const FeatureStateSchema = z.object({
  held_by: z.string().nullish().catch(undefined),
  state: z.enum(FEATURE_STATES).nullish().catch(undefined),
  label: z.string().nullish().catch(undefined),
  // v3
  active: z.boolean().nullish().catch(undefined),
  value_n: z.number().nullish().catch(undefined),
  value_label: z.string().nullish().catch(undefined),
  intensity: z.number().nullish().catch(undefined),
  at: LngLatSchema.nullish().catch(undefined),
  line: z.array(LngLatSchema).min(2).nullish().catch(undefined),
  area: AreaSchema.nullish().catch(undefined),
  area_from_entity: EntityRefSchema.nullish().catch(undefined),
});
export type StoryFeatureState = z.infer<typeof FeatureStateSchema>;
export type StoryTerrainState = StoryFeatureState;

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
  /** Feature state by feature id (v2 `terrain_state`); `null` clears it. */
  features: z.record(z.string(), FeatureStateSchema.nullable()).default({}).catch({}),
  /** Light, wind and sun carry forward. */
  light: loose(z.enum(LIGHTS)),
  wind: WindSchema.nullish().catch(undefined),
  sun: SunSchema.nullish().catch(undefined),
  // v3
  /** Without one, the step is at the document's `year`. */
  date: loose(StepDateSchema),
  /** Chronicle stories: the entry's sequence_order; sync adds `entry_id`. */
  entry: loose(z.number()),
  entry_id: loose(z.union([z.string(), z.number()]).transform(String)),
  entities: z.array(StepEntitySchema).default([]).catch([]),
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

/** v3: an entry in the player's legend. */
const LegendSchema = z.object({
  swatch: z.string(),
  label: z.string(),
  style: z.enum(['fill', 'line', 'dot']).catch('fill').default('fill'),
});
export type StoryLegend = z.infer<typeof LegendSchema>;

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);

/** One ring (`[[x, y], …]`) becomes a list of one ring; a list of rings passes. */
function rings(area: unknown): unknown {
  return Array.isArray(area) && Array.isArray(area[0]) && typeof area[0][0] === 'number' ? [area] : area;
}

const withRings = (v: unknown): unknown => (isRecord(v) && v.area != null ? { ...v, area: rings(v.area) } : v);

/**
 * Resolve the schema aliases on a raw document, before validation: `terrain`
 * (v1/v2) → `features`, a step's `terrain_state` → its `features` (the v3
 * name wins when a file has both), and a single `area` ring → a list of rings.
 */
export function normalizeDocument(raw: unknown): unknown {
  if (!isRecord(raw)) return raw;
  const { terrain, ...doc } = raw;
  const features = doc.features ?? terrain;
  if (features !== undefined) doc.features = Array.isArray(features) ? features.map(withRings) : features;
  if (Array.isArray(doc.steps)) {
    doc.steps = doc.steps.map((step: unknown) => {
      if (!isRecord(step)) return step;
      const { terrain_state, ...out } = step;
      const states = out.features ?? terrain_state;
      if (states !== undefined) {
        out.features = isRecord(states)
          ? Object.fromEntries(Object.entries(states).map(([k, v]) => [k, withRings(v)]))
          : states;
      }
      return out;
    });
  }
  return doc;
}

const DocumentSchema = z.object({
  schema: z.number(),
  slug: z.string(),
  kind: z.string(),
  /** v3: optional when the story belongs to a chronicle. */
  entity: LinkedSchema.nullable().default(null).catch(null),
  title: z.string(),
  date_label: z.string().default(''),
  year: z.number(),
  intro: z.string().default(''),
  outcome: z.string().default(''),
  uncertainty: z.string().nullish(),
  sources: z.array(SourceSchema).default([]),
  camera: CameraSchema.nullish(),
  sides: z.array(SideSchema).default([]),
  units: z.array(UnitSchema).default([]),
  /** Persistent features (v1/v2 `terrain`). */
  features: z.array(FeatureSchema).default([]),
  steps: z.array(StepSchema).min(1),
  // v2
  alt_sites: z.array(AltSiteSchema).default([]).catch([]),
  // v3
  chronicle: loose(z.object({ slug: z.string().nullish(), chronicle_id: z.string().nullish() })),
  period: loose(z.object({ start: DateSpecSchema, end: DateSpecSchema })),
  ambient: z.boolean().default(false).catch(false),
  legend: z.array(LegendSchema).default([]).catch([]),
});

export const MapStoryDocumentSchema = z.preprocess(normalizeDocument, DocumentSchema);
export type MapStoryDocument = z.infer<typeof DocumentSchema>;

/** GET /map-stories/{slug} (unwrapped from the `data` envelope). */
export const MapStorySchema = z.object({
  id: z.string(),
  slug: z.string(),
  kind: z.string(),
  title: z.string(),
  year: z.number().nullable().default(null),
  step_count: z.number().nullable().default(null),
  entity_id: z.string().nullable().default(null),
  // v3
  chronicle_id: z.string().nullable().default(null).catch(null),
  period: z.object({ start: z.number(), end: z.number() }).nullable().default(null).catch(null),
  ambient: z.boolean().default(false).catch(false),
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

/** One story's state at a year, for the plain atlas (GET /map-stories/ambient). */
export const AmbientStorySchema = z.object({
  slug: z.string(),
  kind: z.string(),
  title: z.string(),
  step_index: z.number().default(0),
  step_title: z.string().nullable().default(null),
  features: z.custom<FeatureCollection>(
    (v) => isRecord(v) && v.type === 'FeatureCollection' && Array.isArray(v.features),
  ),
});
export type AmbientStory = z.infer<typeof AmbientStorySchema>;

export const AmbientStoriesSchema = z.object({ data: z.array(AmbientStorySchema).default([]) });

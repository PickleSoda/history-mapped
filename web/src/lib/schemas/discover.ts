/**
 * Zod schemas for the Discover endpoints (GET /api/v1/discover/…): events on
 * this day, what was going on across the world in a year, the daily
 * expedition (find a place and a time on the map), and suggestions from what
 * this browser opened lately. Design: docs/superpowers/specs/2026-11-20-discover-feed-design.md
 */
import { z } from 'zod';
import { ChronicleSummarySchema } from './chronicle';
import { GroupFromApi } from './entity';
import { MapStorySummarySchema } from './map-story';

const LngLatSchema = z.tuple([z.number(), z.number()]);

/** An entity as every discover endpoint gives it: enough for a card and a link. */
export const DiscoverEntitySchema = z.object({
  id: z.string(),
  name: z.string(),
  entity_type: z.string().nullable().catch(null),
  entity_group: GroupFromApi,
  summary: z.string().nullable().catch(null),
  /** Years, BCE negative. */
  start_year: z.number().nullable().catch(null),
  end_year: z.number().nullable().catch(null),
  /** Its map point, [lng, lat]; null when the atlas does not place it. */
  at: LngLatSchema.nullable().catch(null),
  /** It has a step-by-step battle map. */
  has_map_story: z.boolean().catch(false),
});
export type DiscoverEntity = z.infer<typeof DiscoverEntitySchema>;

// ── on this day ───────────────────────────────────────────────────────────────

/** What the date marks for the entity. */
export const ON_THIS_DAY_KINDS = ['happened', 'began', 'ended', 'born', 'died', 'founded', 'dissolved'] as const;
export type OnThisDayKind = (typeof ON_THIS_DAY_KINDS)[number];

export const OnThisDayItemSchema = DiscoverEntitySchema.extend({
  kind: z.enum(ON_THIS_DAY_KINDS).catch('happened'),
  /** The year it happened (BCE negative) and the full date as stored ("1815-11-20", "-0753-04-21"). */
  year: z.number(),
  date: z.string(),
});
export type OnThisDayItem = z.infer<typeof OnThisDayItemSchema>;

export const OnThisDaySchema = z.object({
  /** The day asked for. */
  month: z.number(),
  day: z.number(),
  /** Days either side that were added to fill the list (0: this day alone). */
  widened: z.number().catch(0),
  items: z.array(OnThisDayItemSchema).catch([]),
});
export type OnThisDay = z.infer<typeof OnThisDaySchema>;

// ── meanwhile ─────────────────────────────────────────────────────────────────

export const MeanwhileRegionSchema = z.object({
  /** Stable key ("east-asia") and display name ("East Asia"). */
  key: z.string(),
  name: z.string(),
  /** The most notable event within the window around the year, if any. */
  event: DiscoverEntitySchema.nullable().catch(null),
  /** The most notable state standing in that year, if any. */
  polity: DiscoverEntitySchema.nullable().catch(null),
  /** How many of each the atlas shows there then. */
  counts: z.object({ events: z.number().catch(0), polities: z.number().catch(0) }),
});
export type MeanwhileRegion = z.infer<typeof MeanwhileRegionSchema>;

export const MeanwhileSchema = z.object({
  year: z.number(),
  /** An event counts when it falls within this many years of `year`. */
  window: z.number().catch(10),
  totals: z.object({ events: z.number().catch(0), polities: z.number().catch(0) }),
  /** Regions with something to show, west to east. */
  regions: z.array(MeanwhileRegionSchema).catch([]),
});
export type Meanwhile = z.infer<typeof MeanwhileSchema>;

// ── the daily expedition ──────────────────────────────────────────────────────

export const QUEST_DIFFICULTIES = ['easy', 'medium', 'hard'] as const;
export type QuestDifficulty = (typeof QUEST_DIFFICULTIES)[number];

/** One place-and-time to find. Always placed and dated. */
export const QuestTargetSchema = DiscoverEntitySchema.extend({
  difficulty: z.enum(QUEST_DIFFICULTIES).catch('medium'),
  /** The year to be in (its start year). */
  year: z.number(),
  at: LngLatSchema,
  /** The world region of its point ("East Asia"): the first "where" hint. */
  region: z.string().nullable().catch(null),
  /** A nearer place name ("Apulia, Italy"), when the atlas has one: the second hint. */
  place: z.string().nullable().catch(null),
});
export type QuestTarget = z.infer<typeof QuestTargetSchema>;

export const QuestSchema = z.object({
  /** The day the expedition is for, YYYY-MM-DD. */
  date: z.string(),
  /** Its number, counted in days from the first one ("Expedition 12"). */
  number: z.number(),
  targets: z.array(QuestTargetSchema).catch([]),
});
export type Quest = z.infer<typeof QuestSchema>;

// ── for you ───────────────────────────────────────────────────────────────────

/** `via`: the id of the opened entity (a `because` row) the suggestion comes from. */
export const ForYouEntitySchema = DiscoverEntitySchema.extend({
  via: z.string(),
  /** The relationship type linking it to `via` ("at_war_with"), when that is why. */
  relation: z.string().nullable().catch(null),
  /**
   * Which way that relationship reads ("source, type, target"): true when the
   * opened entity (`via`) is the source, false when this row is. Null when the
   * API did not say.
   */
  outgoing: z.boolean().nullable().catch(null),
  /** The year the relationship starts, when it has one. */
  year: z.number().nullable().catch(null),
});
export type ForYouEntity = z.infer<typeof ForYouEntitySchema>;

export const ForYouSchema = z.object({
  /** The opened entities that produced a suggestion, most recent first. */
  because: z.array(z.object({ id: z.string(), name: z.string() })).catch([]),
  entities: z.array(ForYouEntitySchema).catch([]),
  /** Rows shaped like GET /chronicles, plus `via`. */
  chronicles: z.array(ChronicleSummarySchema.extend({ via: z.string() })).catch([]),
  /** Rows shaped like GET /map-stories, plus `via`. */
  stories: z.array(MapStorySummarySchema.extend({ via: z.string() })).catch([]),
});
export type ForYou = z.infer<typeof ForYouSchema>;

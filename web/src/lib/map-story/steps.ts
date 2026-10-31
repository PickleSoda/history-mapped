/**
 * Map-story steps on the timeline (schema 3): the year a step puts the atlas
 * at, how its date reads in the player, which step a chronicle entry plays,
 * and the ambient query's snapped viewport.
 */
import { formatYear } from '@/lib/format';
import type { MapStoryDocument, StoryDate, StoryDateSpec } from '@/lib/schemas/map-story';
import type { Bbox } from '@/types/atlas';

/** Kinds that are fought on a battlefield: terrain relief, today's water and names. */
export const BATTLE_KINDS: readonly string[] = ['battle', 'naval_battle', 'siege', 'campaign'];

/**
 * The timeline instant (a year) for step `index`: its own `date.year`, or the
 * document's `year` for an undated step (v1/v2 battles). The timeline is
 * year-based, so a month or day is display-only.
 */
export function stepYear(doc: MapStoryDocument, index: number): number {
  return doc.steps[index]?.date?.year ?? doc.year;
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function dayMonth(d: StoryDateSpec): string {
  const month = d.month ? MONTHS[d.month - 1] : '';
  return month ? `${d.day ? `${d.day} ` : ''}${month}` : '';
}

/** "18 June 1815 CE"; a span "October 1347 CE – March 1348 CE", or "June – August 1348 CE" within a year. */
export function formatStoryDate(date: StoryDate): string {
  const full = (d: StoryDateSpec) => [dayMonth(d), formatYear(d.year)].filter(Boolean).join(' ');
  const end = date.end;
  if (!end || (end.year === date.year && end.month === date.month && end.day === date.day)) return full(date);
  const head = end.year === date.year && dayMonth(date) ? dayMonth(date) : full(date);
  return `${head} – ${full(end)}`;
}

/**
 * The step a chronicle entry plays: the one whose authored `entry` is the
 * entry's `sequence_order` (both as stored). A step without `entry` matches
 * by the `entry_id` sync resolved, which goes stale when a chronicle is
 * re-imported, so it is only the fallback. -1 when none matches.
 */
export function chronicleStepIndex(
  doc: MapStoryDocument,
  entry: { entry_id: string; sequence_order: number } | undefined,
): number {
  if (!entry) return -1;
  return doc.steps.findIndex((s) =>
    s.entry != null ? s.entry === entry.sequence_order : s.entry_id != null && s.entry_id === entry.entry_id,
  );
}

const WORLD: [number, number, number, number] = [-180, -90, 180, 90];

/** A longitude in [-180, 180). */
const wrapLng = (x: number) => ((((x + 180) % 360) + 360) % 360) - 180;

/**
 * The viewport snapped outward to a grid of "tiles" one zoom level's width
 * (so small pans reuse the query), as `[w, s, e, n]`. Longitudes are wrapped;
 * `w > e` means the box crosses the antimeridian, and a box 360° wide or more
 * is the whole world.
 */
export function snapAmbientBbox(b: Bbox): [number, number, number, number] {
  const span = b.e - b.w;
  if (!(span > 0) || span >= 360) return WORLD;
  const z = Math.max(0, Math.min(12, Math.floor(Math.log2(360 / span))));
  const tile = 360 / 2 ** z;
  const w = Math.floor(b.w / tile) * tile;
  const e = Math.ceil(b.e / tile) * tile;
  if (e - w >= 360) return WORLD;
  const s = Math.max(-90, Math.floor(b.s / tile) * tile);
  const n = Math.min(90, Math.ceil(b.n / tile) * tile);
  const west = wrapLng(w);
  const east = west + (e - w);
  return [west, s, east > 180 ? east - 360 : east, n];
}

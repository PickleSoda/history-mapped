/**
 * The daily expedition's rules, as pure functions: how warm the reader is in
 * time and in place, when they have arrived, what a find is worth, how the
 * streak counts, which way the target lies, and the text of a shared result.
 * No React, no map, no storage: the state lives in `quest-store.ts` and the
 * map is read in `quest-map.ts`.
 * Design: docs/superpowers/specs/2026-11-20-discover-feed-design.md §7.
 */
import type { QuestDifficulty, QuestTarget } from '@/lib/schemas/discover';
import { previousDayKey } from './date';

/** [lng, lat] in degrees. */
export type LngLat = [number, number];

// ── warmth ────────────────────────────────────────────────────────────────────

/** Coldest to warmest; `here` is the target itself. */
export const WARMTHS = ['cold', 'cool', 'warm', 'hot', 'here'] as const;
export type Warmth = (typeof WARMTHS)[number];

/** How many of a five-step meter a warmth fills: cold 1 … here 5. */
export function warmthSteps(warmth: Warmth): number {
  return WARMTHS.indexOf(warmth) + 1;
}

// ── in time ───────────────────────────────────────────────────────────────────

/** Years from the target's span up to which the timeline counts as each warmth. */
export const TIME_LIMITS = { here: 10, hot: 50, warm: 200, cool: 800 } as const;

/** Which way the target lies from the timeline's year. */
export type TimeDirection = 'earlier' | 'later';

type Dated = Pick<QuestTarget, 'year' | 'start_year' | 'end_year'>;

/** The years a target covers, [first, last]: one year for most. Always holds `year`. */
export function targetSpan(target: Dated): [number, number] {
  const start = Math.min(target.start_year ?? target.year, target.year);
  const end = Math.max(target.end_year ?? start, target.year);
  return [start, end];
}

/** Years between `year` and a span; 0 inside it. */
export function yearsFromSpan(year: number, [start, end]: [number, number]): number {
  return year < start ? start - year : year > end ? year - end : 0;
}

export function timeWarmth(years: number): Warmth {
  if (years <= TIME_LIMITS.here) return 'here';
  if (years <= TIME_LIMITS.hot) return 'hot';
  if (years <= TIME_LIMITS.warm) return 'warm';
  if (years <= TIME_LIMITS.cool) return 'cool';
  return 'cold';
}

export interface TimeReading {
  warmth: Warmth;
  /** Null inside the target's span. */
  direction: TimeDirection | null;
}

/** How warm the timeline's `year` is for a target, and which way the target lies. */
export function readTime(year: number, target: Dated): TimeReading {
  const span = targetSpan(target);
  return {
    warmth: timeWarmth(yearsFromSpan(year, span)),
    direction: year < span[0] ? 'later' : year > span[1] ? 'earlier' : null,
  };
}

// ── in place ──────────────────────────────────────────────────────────────────

/** Km from the middle of the map up to which it counts as each warmth. */
export const PLACE_LIMITS = { hot: 800, warm: 2500, cool: 6000 } as const;

/** A map wider than this, corner to corner, shows more than a region: having
 *  the target somewhere on it is not being there. */
export const REGIONAL_KM = 3000;

/** What the map shows, as far as the target is concerned. */
export interface PlaceView {
  /** Great-circle km from the middle of the visible map to the target. */
  km: number;
  /** The target is inside the visible map. */
  inView: boolean;
  /** Great-circle km across the visible map, corner to corner. */
  diagonalKm: number;
}

export function placeWarmth({ km, inView, diagonalKm }: PlaceView): Warmth {
  if (inView && diagonalKm <= REGIONAL_KM) return 'here';
  if (km <= PLACE_LIMITS.hot) return 'hot';
  if (km <= PLACE_LIMITS.warm) return 'warm';
  if (km <= PLACE_LIMITS.cool) return 'cool';
  return 'cold';
}

/** Hot and on the map, but the map is too wide to count: zooming in gets there. */
export function needsZoomIn({ km, inView, diagonalKm }: PlaceView): boolean {
  return inView && diagonalKm > REGIONAL_KM && km <= PLACE_LIMITS.hot;
}

/** There in time and in place: only then is the target's marker on the map. */
export function hasArrived(time: Warmth, place: Warmth | null): boolean {
  return time === 'here' && place === 'here';
}

// ── direction and distance ────────────────────────────────────────────────────

const EARTH_KM = 6371.0088;
const RAD = Math.PI / 180;
/** Mercator's own limit; keeps the rhumb line finite at the poles. */
const MAX_LAT = 85.0511;

/** Great-circle km between two points (haversine). */
export function distanceKm(a: LngLat, b: LngLat): number {
  const dLat = (b[1] - a[1]) * RAD;
  const dLng = (b[0] - a[0]) * RAD;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * RAD) * Math.cos(b[1] * RAD) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

/**
 * The compass bearing to hold from `from` to reach `to`: degrees clockwise
 * from north, along the rhumb line (a straight line on the flat map, so "east"
 * is where the reader sees it), the short way round the world.
 */
export function compassBearing(from: LngLat, to: LngLat): number {
  const clamp = (lat: number) => Math.max(-MAX_LAT, Math.min(MAX_LAT, lat)) * RAD;
  const stretch = (lat: number) => Math.log(Math.tan(Math.PI / 4 + clamp(lat) / 2));
  const dLng = ((((to[0] - from[0]) % 360) + 540) % 360) - 180;
  const bearing = Math.atan2(dLng * RAD, stretch(to[1]) - stretch(from[1])) / RAD;
  return (bearing + 360) % 360;
}

export const COMPASS_POINTS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const;
export type CompassPoint = (typeof COMPASS_POINTS)[number];

export const COMPASS_WORDS: Record<CompassPoint, string> = {
  N: 'north',
  NE: 'north-east',
  E: 'east',
  SE: 'south-east',
  S: 'south',
  SW: 'south-west',
  W: 'west',
  NW: 'north-west',
};

/** A bearing (degrees, any sign or size) in eighths of a turn clockwise from north: 0–7. */
export function eighthTurn(bearing: number): number {
  return Math.round((((bearing % 360) + 360) % 360) / 45) % 8;
}

export function compassPoint(bearing: number): CompassPoint {
  return COMPASS_POINTS[eighthTurn(bearing)];
}

/** Closer than this, the target is as good as under the middle of the map: no direction to give. */
export const NEAR_KM = 10;

/** A distance rounded the way it is shown, so a moving map changes the text only now and then. */
export function roundKm(km: number): number {
  const step = km < 100 ? 10 : km < 1000 ? 50 : km < 10_000 ? 100 : 500;
  return Math.round(km / step) * step;
}

/** "about 1,200 km", "under 10 km". */
export function kmText(km: number): string {
  const rounded = roundKm(km);
  return rounded < NEAR_KM ? `under ${NEAR_KM} km` : `about ${rounded.toLocaleString('en-US')} km`;
}

// ── the live reading ──────────────────────────────────────────────────────────

/** What the map shows, with the way to the target. */
export interface MapView extends PlaceView {
  /** Compass bearing from the middle of the visible map to the target. */
  bearing: number;
  /** The same on screen: degrees clockwise from up (the map may be turned). */
  screenBearing: number;
}

/**
 * How the reader stands to the active target, in the few values the strip and
 * the card show. It changes only when one of those does, which is what makes
 * it cheap to publish from a moving map.
 */
export interface QuestReading {
  /** The target it is for. */
  id: string;
  time: Warmth;
  direction: TimeDirection | null;
  /** Null until the map is ready. */
  place: Warmth | null;
  /** See `needsZoomIn`. */
  zoomIn: boolean;
  /** Where the target lies from the middle of the map; null on top of it or without a map. */
  compass: CompassPoint | null;
  /** The same on screen, in eighths of a turn clockwise from up. */
  arrow: number | null;
  /** Rounded km from the middle of the map. */
  km: number | null;
  /** Time and place are both `here`: the marker is on the map. */
  arrived: boolean;
}

/**
 * The reading for a target. The warmth in time follows the year on show (live
 * while the timeline is dragged); arriving needs the year the map itself is
 * at, so a drag passing over the target's years does not flash its marker.
 */
export function takeReading(
  target: Pick<QuestTarget, 'id' | 'year' | 'start_year' | 'end_year'>,
  years: { shown: number; committed: number },
  view: MapView | null,
): QuestReading {
  const time = readTime(years.shown, target);
  const place = view ? placeWarmth(view) : null;
  const apart = view != null && view.km >= NEAR_KM;
  return {
    id: target.id,
    time: time.warmth,
    direction: time.direction,
    place,
    zoomIn: view ? needsZoomIn(view) : false,
    compass: apart ? compassPoint(view.bearing) : null,
    arrow: apart ? eighthTurn(view.screenBearing) : null,
    km: view && Number.isFinite(view.km) ? roundKm(view.km) : null,
    arrived: hasArrived(readTime(years.committed, target).warmth, place),
  };
}

/** The warmth words, the cue and the arrival: what must reach the screen at once. */
export function sameLevels(a: QuestReading, b: QuestReading): boolean {
  return (
    a.id === b.id &&
    a.time === b.time &&
    a.direction === b.direction &&
    a.place === b.place &&
    a.zoomIn === b.zoomIn &&
    a.arrived === b.arrived
  );
}

export function sameReading(a: QuestReading, b: QuestReading): boolean {
  return sameLevels(a, b) && a.compass === b.compass && a.arrow === b.arrow && a.km === b.km;
}

// ── stars ─────────────────────────────────────────────────────────────────────

/** What the reader did about one target. */
export interface TargetProgress {
  /** Asked for the "when" hint. */
  when: boolean;
  /** Asked for the "where" hint. */
  where: boolean;
  /** Was taken there. */
  taken: boolean;
  found: boolean;
}

export const NO_PROGRESS: TargetProgress = { when: false, where: false, taken: false, found: false };

export const MAX_STARS = 3;

/** 3 with no hint, 2 with one, 1 with both, 0 when taken there. */
export function starsFor(progress: Pick<TargetProgress, 'when' | 'where' | 'taken'>): number {
  if (progress.taken) return 0;
  return MAX_STARS - (progress.when ? 1 : 0) - (progress.where ? 1 : 0);
}

export type TargetsProgress = Record<string, TargetProgress>;

/** The day so far: how many of its targets are found, the stars they earned, and whether that is all of them. */
export function tally(
  ids: readonly string[],
  targets: TargetsProgress,
): { found: number; stars: number; complete: boolean } {
  let found = 0;
  let stars = 0;
  for (const id of ids) {
    const progress = targets[id];
    if (!progress?.found) continue;
    found += 1;
    stars += starsFor(progress);
  }
  return { found, stars, complete: ids.length > 0 && found === ids.length };
}

// ── streak ────────────────────────────────────────────────────────────────────

/** Days in a row with every target found; `last` is the latest such day (YYYY-MM-DD). */
export interface Streak {
  count: number;
  last: string | null;
}

export const NO_STREAK: Streak = { count: 0, last: null };

/**
 * The streak once `today`'s expedition is complete: one more when the last
 * complete day was yesterday, else it starts again at 1. A day counts once
 * (and a `last` that is not behind `today`, after a change of time zone,
 * leaves it as it is).
 */
export function completeStreak(streak: Streak, today: string): Streak {
  if (streak.last != null && streak.last >= today) return streak;
  return { count: streak.last === previousDayKey(today) ? streak.count + 1 : 1, last: today };
}

/** The streak to show on `today`: it stands while the last complete day is today or yesterday. */
export function standingStreak(streak: Streak, today: string): number {
  return streak.last != null && streak.last >= previousDayKey(today) ? streak.count : 0;
}

// ── the clue ──────────────────────────────────────────────────────────────────

/** Stands where a year was left out of a clue. */
export const HIDDEN_YEAR = '····';

/** A number as written: digits, with any grouping or decimal marks inside it. */
const NUMBER = /\d+(?:[.,]\d+)*/g;
const ORDINAL = /^(?:st|nd|rd|th)\b/i;

/**
 * A name or a summary without its years. Nearly every summary states the year
 * outright ("1868 battle where …"), which would give the "when" away before
 * the reader has looked for it. Left out: a plain number of three or four
 * digits that could be a year near the target's (close enough to count as
 * warm), and any number that is one of the target's own years (which covers
 * the first centuries). Other counts ("444 days"), grouped numbers ("40,000
 * men") and ordinals ("3rd century") stay.
 */
export function hideYears(text: string, target: Dated): string {
  const span = targetSpan(target).map(Math.abs);
  const low = Math.min(...span);
  const high = Math.max(...span);
  return text.replace(NUMBER, (match: string, offset: number) => {
    if (!/^\d+$/.test(match)) return match;
    if (ORDINAL.test(text.slice(offset + match.length, offset + match.length + 3))) return match;
    const n = Number(match);
    const own = n >= low && n <= high;
    const near =
      (match.length === 3 || match.length === 4) && n >= low - TIME_LIMITS.warm && n <= high + TIME_LIMITS.warm;
    return own || near ? HIDDEN_YEAR : match;
  });
}

/** The years show once the reader has them: after the "when" hint, a lift there, or the find. */
export function yearsShown(progress: TargetProgress | undefined): boolean {
  return progress != null && (progress.when || progress.taken || progress.found);
}

/** A target's name or summary as the reader may see it for now. */
export function clueText(text: string, target: Dated, progress: TargetProgress | undefined): string {
  return yearsShown(progress) ? text : hideYears(text, target);
}

// ── the result to share ───────────────────────────────────────────────────────

/** "Expedition 12". Days before the first one have no number to show. */
export function expeditionName(number: number): string {
  return number >= 1 ? `Expedition ${number}` : 'Expedition';
}

/** "★★☆" */
export function starRow(stars: number, of: number = MAX_STARS): string {
  const n = Math.max(0, Math.min(of, Math.trunc(stars)));
  return '★'.repeat(n) + '☆'.repeat(of - n);
}

/**
 * The finished day as plain text to paste anywhere: the expedition's number,
 * a row of stars per target (never their names: no spoilers) and where to play.
 */
export function shareText(
  number: number,
  rows: readonly { difficulty: QuestDifficulty; stars: number }[],
  url: string,
): string {
  return [
    `History Mapped · ${expeditionName(number)}`,
    ...rows.map((row) => `${starRow(row.stars)} ${row.difficulty}`),
    url,
  ].join('\n');
}

/**
 * The choices the Discover feed makes from what the API sent: which rows to
 * show, which year "Meanwhile" takes on the browse page, which two regions
 * lead its sentence. Pure, so each rule is tested on its own.
 */
import type { DiscoverEntity, MeanwhileRegion, OnThisDayItem } from '@/lib/schemas/discover';

/** Rows of the "on this day" card: the sidebar has less room than the page. */
export const ON_THIS_DAY_ROWS = { panel: 5, page: 6 } as const;

/** Regions the browse page's "Meanwhile" shows before "Show all". */
export const MEANWHILE_PAGE_REGIONS = 4;

/**
 * The row "Meanwhile" takes its year from on the browse page: the first event
 * among the rows shown, else the first row. Null with no rows.
 */
export function yearAnchor<T extends Pick<OnThisDayItem, 'entity_group'>>(rows: T[]): T | null {
  return rows.find((row) => row.entity_group === 'event') ?? rows[0] ?? null;
}

const EARTH_RADIUS_KM = 6371;
const rad = (deg: number) => (deg * Math.PI) / 180;

/** Great-circle distance between two `[lng, lat]` points, in kilometres. */
export function distanceKm(a: readonly [number, number], b: readonly [number, number]): number {
  const dLat = rad(b[1] - a[1]);
  const dLng = rad(b[0] - a[0]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

export type RegionWithEvent = MeanwhileRegion & { event: DiscoverEntity };

/**
 * The two regions whose events are farthest apart on the globe, in the order
 * given (west first). When no two events have a map point, the first and the
 * last region with an event stand in (the list runs west to east). Null when
 * fewer than two regions have an event.
 */
export function farthestEvents(regions: MeanwhileRegion[]): [RegionWithEvent, RegionWithEvent] | null {
  const withEvent = regions.filter((region): region is RegionWithEvent => region.event !== null);
  if (withEvent.length < 2) return null;
  let best: [RegionWithEvent, RegionWithEvent] = [withEvent[0], withEvent[withEvent.length - 1]];
  let bestKm = -1;
  for (let i = 0; i < withEvent.length; i += 1) {
    for (let j = i + 1; j < withEvent.length; j += 1) {
      const a = withEvent[i].event.at;
      const b = withEvent[j].event.at;
      if (!a || !b) continue;
      const km = distanceKm(a, b);
      if (km > bestKm) {
        best = [withEvent[i], withEvent[j]];
        bestKm = km;
      }
    }
  }
  return best;
}

type Dated = Pick<DiscoverEntity, 'start_year' | 'end_year'>;

/** The event was going on in `year` itself (not merely within the window around it). */
export function underWay(event: Dated, year: number): boolean {
  const start = event.start_year;
  return start != null && year >= start && year <= (event.end_year ?? start);
}

/**
 * The year to show beside an event that was not under way in `year` itself
 * (the API picks events from a window around it); null when it was, or when
 * its year is unknown.
 */
export function offYear(event: Dated, year: number): number | null {
  return event.start_year == null || underWay(event, year) ? null : event.start_year;
}

/** The two regions the lead sentence sets side by side, and whether their events share the year. */
export interface LeadEvents {
  pair: [RegionWithEvent, RegionWithEvent];
  /** Both events were under way in the card's year: "While …" is true of them. */
  sameYear: boolean;
}

/**
 * The lead's pair for `year`: the two farthest apart among the events under
 * way in that very year, so "While … in A, … in B" holds. With fewer than two
 * of those, the two farthest apart of all (they are from the years around
 * it, and the sentence has to say "around"). Null when fewer than two regions
 * have an event.
 */
export function leadEvents(regions: MeanwhileRegion[], year: number): LeadEvents | null {
  const thatYear = farthestEvents(regions.filter((region) => region.event !== null && underWay(region.event, year)));
  if (thatYear) return { pair: thatYear, sameYear: true };
  const around = farthestEvents(regions);
  return around ? { pair: around, sameYear: false } : null;
}

/**
 * The items without repeats, the first of each kept: a suggestion related to
 * two of the opened entities is listed once, under the more recent one.
 */
export function uniqueBy<T>(items: T[], key: (item: T) => string): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const k = key(item);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

/**
 * `count` of the items, spread evenly over the list with both ends included
 * and the order kept: a sample of a west-to-east list that still spans the map.
 */
export function spread<T>(items: T[], count: number): T[] {
  if (count <= 0) return [];
  if (items.length <= count) return items;
  if (count === 1) return [items[0]];
  const step = (items.length - 1) / (count - 1);
  return Array.from({ length: count }, (_, i) => items[Math.round(i * step)]);
}

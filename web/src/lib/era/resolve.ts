import { boxArea, GLOBAL_ERAS, REGIONAL_ERAS, REGIONAL_MAX_SPAN } from '@/lib/era/manifest';
import type { Box, EraEntry } from '@/lib/era/types';
import type { Bbox } from '@/types/atlas';

function contains([w, s, e, n]: Box, lng: number, lat: number): boolean {
  return lng >= w && lng <= e && lat >= s && lat <= n;
}

/** The global era for a year (the global rows tile the whole timeline). */
export function globalEra(year: number): EraEntry {
  const found = GLOBAL_ERAS.find((e) => year >= e.start && year <= e.end);
  if (found) return found;
  return year < GLOBAL_ERAS[0].start ? GLOBAL_ERAS[0] : GLOBAL_ERAS[GLOBAL_ERAS.length - 1];
}

/**
 * The era for a year and the visible map. Zoomed in (the view at most
 * REGIONAL_MAX_SPAN degrees wide), a regional era whose years include `year`
 * and whose region holds the view's centre wins: the highest priority, then
 * the smallest matching box. Otherwise, the global era for the year.
 */
export function resolveEra(year: number, bbox: Bbox | null): EraEntry {
  if (bbox && bbox.e - bbox.w <= REGIONAL_MAX_SPAN) {
    const lng = (bbox.w + bbox.e) / 2;
    const lat = (bbox.s + bbox.n) / 2;
    let best: { entry: EraEntry; area: number } | null = null;
    for (const entry of REGIONAL_ERAS) {
      if (year < entry.start || year > entry.end) continue;
      const hits = (entry.regions ?? []).filter((box) => contains(box, lng, lat));
      if (!hits.length) continue;
      const area = Math.min(...hits.map(boxArea));
      const priority = entry.priority ?? 0;
      const bestPriority = best?.entry.priority ?? 0;
      if (!best || priority > bestPriority || (priority === bestPriority && area < best.area)) {
        best = { entry, area };
      }
    }
    if (best) return best.entry;
  }
  return globalEra(year);
}

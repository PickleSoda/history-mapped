/**
 * Snapping — the heart of caching (spec §3).
 *
 * The raw map bbox changes on every pixel of pan. If we keyed the cache on the
 * raw bbox we'd get a fresh fetch and zero cache hits. So we snap the bbox to a
 * tile grid and time to the timeline resolution *before* building a query key.
 * Pan a little -> snapped scope unchanged -> cache hit. Pan past a tile boundary
 * -> snapped scope changes -> one fetch.
 */
import type { Bbox, EntityGroup, Scope, TimeState } from '@/types/atlas';
import { latToTileY, lonToTileX, tileXToLon, tileYToLat } from './tiles';

/** Extra ring of tiles fetched around the viewport so small pans never refetch
 *  and just-off-screen pins are already loaded (spec: over-fetch ~1.3×). */
const OVERFETCH_TILES = 1;

/** Estimate an integer tile-zoom level from the bbox's longitude span. */
export function zoomFromBbox(bbox: Bbox): number {
  const span = Math.abs(bbox.e - bbox.w) || 1e-6;
  const z = Math.round(Math.log2(360 / span));
  return Math.max(0, Math.min(22, z));
}

/** Expand a bbox outward to whole tile boundaries at zoom `z`, padding by
 *  `OVERFETCH_TILES` on each side. */
export function snapBboxToTiles(bbox: Bbox, z: number): Bbox {
  const maxTile = 2 ** z - 1;
  const clampX = (x: number) => Math.max(0, Math.min(maxTile, x));
  const clampY = (y: number) => Math.max(0, Math.min(maxTile, y));

  // North is "up" => smaller tile-Y. west/north give the min tile corner.
  const xMin = clampX(lonToTileX(bbox.w, z) - OVERFETCH_TILES);
  const xMax = clampX(lonToTileX(bbox.e, z) + OVERFETCH_TILES);
  const yMin = clampY(latToTileY(bbox.n, z) - OVERFETCH_TILES);
  const yMax = clampY(latToTileY(bbox.s, z) + OVERFETCH_TILES);

  return {
    w: tileXToLon(xMin, z),
    e: tileXToLon(xMax + 1, z),
    n: tileYToLat(yMin, z),
    s: tileYToLat(yMax + 1, z),
  };
}

/** Snap a year to a resolution band (1 = year, 10 = decade, 100 = century). */
function snapYear(year: number, resolution: number): number {
  return Math.round(year / resolution) * resolution;
}

export function snapTime(time: TimeState, resolution = 1): TimeState {
  return time.kind === 'instant'
    ? { kind: 'instant', year: snapYear(time.year, resolution) }
    : {
        kind: 'range',
        start: snapYear(time.start, resolution),
        end: snapYear(time.end, resolution),
      };
}

/**
 * Map an integer tile-zoom to a time resolution. Coarser map zoom -> coarser
 * time band. TODO: drive this from the timeline's own zoom once the scrubber
 * exists; for now it is a reasonable monotonic default.
 */
function timeResolutionForZoom(z: number): number {
  if (z <= 3) return 100;
  if (z <= 6) return 10;
  return 1;
}

export interface RawScope {
  bbox: Bbox;
  time: TimeState;
  groups: EntityGroup[];
  /** Optional measured map zoom; falls back to `zoomFromBbox`. */
  zoom?: number;
}

/** Build the snapped {bbox, z, time, groups} that query keys use. */
export function snapScope(raw: RawScope): Scope {
  const z = Math.round(raw.zoom ?? zoomFromBbox(raw.bbox));
  return {
    z,
    bbox: snapBboxToTiles(raw.bbox, z),
    time: snapTime(raw.time, timeResolutionForZoom(z)),
    groups: [...raw.groups].sort(),
  };
}

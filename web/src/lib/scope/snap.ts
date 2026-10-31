/**
 * Snapping — the heart of caching (spec §3).
 *
 * The raw map bbox changes on every pixel of pan. If we keyed the cache on the
 * raw bbox we'd get a fresh fetch and zero cache hits. So we snap the bbox to a
 * tile grid and time to the timeline resolution *before* building a query key.
 * Pan a little -> snapped scope unchanged -> cache hit. Pan past a tile boundary
 * -> snapped scope changes -> one fetch.
 */
import type { Bbox, EntityGroup, MapInsets, Scope, TimeState } from '@/types/atlas';
import {
  latToMercatorY,
  latToTileY,
  lonToTileX,
  mercatorYToLat,
  tileXToLon,
  tileYToLat,
} from './tiles';

/** Extra ring of tiles fetched around the viewport so small pans never refetch
 *  and just-off-screen pins are already loaded. Only the sparse `outer` box
 *  gets it. */
const OVERFETCH_TILES = 1;

/**
 * How many levels finer than the map zoom the snapping grid is. At `z` a tile
 * is about one viewport wide, so snapping there (plus the ring) fetched ~16× the
 * visible area; two levels finer a tile is ~¼ viewport, which keeps the outer
 * box near 1.5–2× the visible span and small pans still a cache hit.
 */
const GRID_ZOOM_OFFSET = 2;

/** The core is the middle half of the visible area on each axis. */
const CORE_INSETS: MapInsets = { top: 0.25, right: 0.25, bottom: 0.25, left: 0.25 };

/** Floating UI never shrinks either axis below this share of the map, so a
 *  near-full mobile sheet can't collapse the query to a sliver. */
const MIN_VISIBLE = 0.3;

/** Estimate an integer tile-zoom level from the bbox's longitude span. */
export function zoomFromBbox(bbox: Bbox): number {
  const span = Math.abs(bbox.e - bbox.w) || 1e-6;
  const z = Math.round(Math.log2(360 / span));
  return Math.max(0, Math.min(22, z));
}

/** Two opposite insets, scaled down together if they'd leave less than
 *  `MIN_VISIBLE` of the axis. */
function fitInsets(a: number, b: number): [number, number] {
  const lo = Math.max(0, a);
  const hi = Math.max(0, b);
  const covered = lo + hi;
  if (covered <= 1 - MIN_VISIBLE) return [lo, hi];
  const k = (1 - MIN_VISIBLE) / covered;
  return [lo * k, hi * k];
}

/**
 * The part of `bbox` left after trimming each side by its inset share of the
 * screen. Longitude is linear across a Mercator screen and latitude linear in
 * Mercator y, so this matches `unproject` on a flat map; on the globe it is a
 * close-enough approximation for a fetch box.
 */
export function cropBbox(bbox: Bbox, insets: MapInsets): Bbox {
  const [left, right] = fitInsets(insets.left, insets.right);
  const [top, bottom] = fitInsets(insets.top, insets.bottom);
  const lngSpan = bbox.e - bbox.w;
  const yN = latToMercatorY(bbox.n);
  const yS = latToMercatorY(bbox.s);
  return {
    w: bbox.w + lngSpan * left,
    e: bbox.e - lngSpan * right,
    n: mercatorYToLat(yN - (yN - yS) * top),
    s: mercatorYToLat(yS + (yN - yS) * bottom),
  };
}

/** Expand a bbox outward to whole tile boundaries at zoom `z`, padding by
 *  `ring` tiles on each side. */
export function snapBboxToTiles(bbox: Bbox, z: number, ring = 0): Bbox {
  const maxTile = 2 ** z - 1;
  const clampX = (x: number) => Math.max(0, Math.min(maxTile, x));
  const clampY = (y: number) => Math.max(0, Math.min(maxTile, y));

  // North is "up" => smaller tile-Y. west/north give the min tile corner.
  const xMin = clampX(lonToTileX(bbox.w, z) - ring);
  const xMax = clampX(lonToTileX(bbox.e, z) + ring);
  const yMin = clampY(latToTileY(bbox.n, z) - ring);
  const yMax = clampY(latToTileY(bbox.s, z) + ring);

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
  /** Map share hidden under floating UI; omitted = the whole map is visible. */
  insets?: MapInsets;
}

/**
 * Build the snapped scope that query keys use. `z` comes from the whole map so
 * opening a panel doesn't change the impact threshold; the boxes come from the
 * visible part only, so nothing hidden under a panel or sheet is fetched.
 */
export function snapScope(raw: RawScope): Scope {
  const z = Math.round(raw.zoom ?? zoomFromBbox(raw.bbox));
  const grid = z + GRID_ZOOM_OFFSET;
  const visible = raw.insets ? cropBbox(raw.bbox, raw.insets) : raw.bbox;
  return {
    z,
    bbox: snapBboxToTiles(visible, grid),
    outer: snapBboxToTiles(visible, grid, OVERFETCH_TILES),
    // A grid level finer still: the core is half the span, so it keeps the
    // same tile-to-box ratio as `bbox`.
    core: snapBboxToTiles(cropBbox(visible, CORE_INSETS), grid + 1),
    // An instant is a precise year the user picked (and the scrubber commits on
    // release, not continuously), so snap it at full resolution — otherwise at a
    // world/continent zoom the 100-year band swallows the year change and the
    // map never refetches. Range queries keep the zoom-banded aggregation.
    time:
      raw.time.kind === 'instant'
        ? snapTime(raw.time, 1)
        : snapTime(raw.time, timeResolutionForZoom(z)),
    groups: [...raw.groups].sort(),
  };
}

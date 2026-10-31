/**
 * Map the frontend's snapped `Scope` onto the real backend query params.
 *
 * Backend conventions (see MapEntitiesRequest / ListEntitiesRequest):
 * - bbox is four separate floats: bbox_min_lng/lat, bbox_max_lng/lat
 * - time is `year` (instant) or `temporal_start`/`temporal_end` (range)
 * - groups are UPPERCASE enum values; omitted = all groups
 * - map ranking uses `zoom_level` -> impact threshold
 */
import { ENTITY_GROUPS } from '@/types/atlas';
import type { Bbox, EntityGroup, Scope } from '@/types/atlas';

type Params = Record<string, string | number | string[]>;

/**
 * Keep the map populated: when the zoom-derived impact threshold would leave
 * fewer than this many entities in view (zoomed out, or a group filter applied),
 * the API backfills with the next highest-impact ones. Pure declutter stays
 * wherever more than this clears the threshold.
 */
const MAP_MIN_RESULTS = 24;

/**
 * The map is fetched in two layers: `outer` (the whole visible area plus a
 * ring, at the map's own impact threshold) and `core` (its middle, fetched as
 * if zoomed this many levels closer — roughly one impact band lower). So the
 * map is densest where the user is looking and only prominent at the edges.
 */
export type MapLayer = 'outer' | 'core';
const CORE_ZOOM_BOOST = 3;

function bboxParams(bbox: Bbox): Params {
  return {
    bbox_min_lng: bbox.w,
    bbox_min_lat: bbox.s,
    bbox_max_lng: bbox.e,
    bbox_max_lat: bbox.n,
  };
}

/** UPPERCASE group values, only when a strict subset is selected (else omit). */
function groupValues(groups: EntityGroup[]): string[] | undefined {
  if (groups.length === 0 || groups.length === ENTITY_GROUPS.length) return undefined;
  return groups.map((g) => g.toUpperCase());
}

/** Params for GET /entities/map (pins/borders FeatureCollection), one layer. */
export function mapParams(scope: Scope, layer: MapLayer = 'outer', limit = 2000): Params {
  const zoom = layer === 'core' ? scope.z + CORE_ZOOM_BOOST : scope.z;
  const params: Params = {
    ...bboxParams(layer === 'core' ? scope.core : scope.outer),
    zoom_level: Math.max(0, Math.min(22, zoom)),
    min_results: MAP_MIN_RESULTS,
    limit,
  };

  if (scope.time.kind === 'instant') {
    params.year = scope.time.year;
  } else {
    // Year-based borders endpoint; anchor at range start and add the window.
    params.year = scope.time.start;
    params.temporal_start = scope.time.start;
    params.temporal_end = scope.time.end;
  }

  const groups = groupValues(scope.groups);
  if (groups) params.groups = groups;

  return params;
}

export interface ListOptions {
  page?: number;
  perPage?: number;
  sort?: 'impact' | 'relevance' | 'recent' | 'chronological' | 'name';
  search?: string;
}

/** Params for GET /entities (ranked "notable here" list + search). */
export function listParams(scope: Scope, opts: ListOptions = {}): Params {
  const params: Params = {
    sort: opts.sort ?? (opts.search ? 'relevance' : 'impact'),
    per_page: opts.perPage ?? 50,
    page: opts.page ?? 1,
  };

  // Only entities placed in the visible area (their primary location) — the
  // part of the map not under a panel or the sheet.
  Object.assign(params, bboxParams(scope.bbox));

  // Temporal presence: only entities that exist at the current year (instant) or
  // overlap the selected range. The backend's exists_at / range filter uses an
  // int4range containment where a NULL start/end is unbounded — a missing bound
  // is treated as ±infinity (open-ended entities match), never as year 0.
  if (scope.time.kind === 'instant') {
    params.exists_at = scope.time.year;
  } else {
    params.temporal_start = scope.time.start;
    params.temporal_end = scope.time.end;
  }

  const groups = groupValues(scope.groups);
  if (groups) params.groups = groups;
  if (opts.search) params.search = opts.search;

  return params;
}

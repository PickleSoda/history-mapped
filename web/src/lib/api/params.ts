/**
 * Map the frontend's snapped `Scope` onto the real backend query params.
 *
 * Backend conventions (see MapEntitiesRequest / ListEntitiesRequest):
 * - bbox is four separate floats: bbox_min_lng/lat, bbox_max_lng/lat
 * - time is `year` (instant) or `temporal_start`/`temporal_end` (range)
 * - groups are UPPERCASE enum values; omitted = all groups
 * - map ranking uses `zoom_level` -> impact threshold
 */
import { ENTITY_GROUPS, type EntityGroup, type Scope } from '@/types/atlas';

type Params = Record<string, string | number | string[]>;

function bboxParams(scope: Scope): Params {
  return {
    bbox_min_lng: scope.bbox.w,
    bbox_min_lat: scope.bbox.s,
    bbox_max_lng: scope.bbox.e,
    bbox_max_lat: scope.bbox.n,
  };
}

/** UPPERCASE group values, only when a strict subset is selected (else omit). */
function groupValues(groups: EntityGroup[]): string[] | undefined {
  if (groups.length === 0 || groups.length === ENTITY_GROUPS.length) return undefined;
  return groups.map((g) => g.toUpperCase());
}

/** Params for GET /entities/map (pins/borders FeatureCollection). */
export function mapParams(scope: Scope, limit = 2000): Params {
  const params: Params = {
    ...bboxParams(scope),
    zoom_level: Math.max(0, Math.min(22, scope.z)),
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
    ...bboxParams(scope),
    sort: opts.sort ?? (opts.search ? 'relevance' : 'impact'),
    per_page: opts.perPage ?? 50,
    page: opts.page ?? 1,
  };

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

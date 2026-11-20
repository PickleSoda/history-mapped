/** Typed entity endpoints against the real Laravel API. */
import {
  EntityDetailSchema,
  EntityListSchema,
  EntityTimelineSchema,
  RelationshipsSchema
  
  
  
} from '@/lib/schemas/entity';
import type {
  EntityDetail,
  EntityList,
  EntityTimeline,
  Relationships,
} from '@/lib/schemas/entity';
import { asFeatureCollection  } from '@/lib/schemas/map';
import type {MapFeatureCollection} from '@/lib/schemas/map';
import { ENTITY_GROUPS } from '@/types/atlas';
import type { EntityGroup, Scope } from '@/types/atlas';
import { api } from './client';
import { listParams, mapParams  } from './params';
import type { ListOptions, MapLayer } from './params';

/**
 * GET /entities/map — the viewport query, for one layer of the scope (see
 * `MapLayer`). Returns a GeoJSON FeatureCollection of border/point geometries.
 * Already a single optimized PostGIS query server-side; we pass the
 * FeatureCollection straight to maplibre without a deep parse (only a shallow
 * envelope check).
 */
export async function entitiesInView(
  scope: Scope,
  layer: MapLayer,
  signal?: AbortSignal,
): Promise<MapFeatureCollection> {
  const { data } = await api.get('/api/v1/entities/map', {
    signal,
    params: mapParams(scope, layer),
  });
  return asFeatureCollection(data);
}

/** What the map is narrowed to: an entity with its relations, or a search word. */
export type MapFocusTarget =
  | { kind: 'related'; id: string }
  | { kind: 'search'; q: string };

/**
 * GET /entities/map/focus — one point per entity of a focused set, whatever
 * the year, the view or the zoom: an entity and its relations one and two
 * hops out (`depth` on each feature = hops), or the placed matches of a word.
 */
export async function mapFocus(
  target: MapFocusTarget,
  groups: EntityGroup[],
  signal?: AbortSignal,
): Promise<MapFeatureCollection> {
  const params: Record<string, string | number | string[]> =
    target.kind === 'related' ? { related_to: target.id, depth: 2 } : { search: target.q };
  if (groups.length > 0 && groups.length < ENTITY_GROUPS.length) {
    params.groups = groups.map((g) => g.toUpperCase());
  }
  const { data } = await api.get('/api/v1/entities/map/focus', { signal, params });
  return asFeatureCollection(data);
}

/**
 * GET /entities — the ranked "notable here" list (and search). Paginated, with
 * a real total in `meta`. Includes unplaced entities (no geometry required).
 */
export async function entityList(
  scope: Scope,
  opts?: ListOptions,
  signal?: AbortSignal,
): Promise<EntityList> {
  const { data } = await api.get('/api/v1/entities', {
    signal,
    params: listParams(scope, opts),
  });
  return EntityListSchema.parse(data);
}

/** GET /entities/{id} — full detail for the selected entity. Laravel wraps a
 *  single resource in a `data` envelope, so unwrap before parsing. */
export async function entity(
  id: string,
  signal?: AbortSignal,
): Promise<EntityDetail> {
  const { data } = await api.get(`/api/v1/entities/${encodeURIComponent(id)}`, {
    signal,
  });
  const payload = (data as { data?: unknown }).data ?? data;
  return EntityDetailSchema.parse(payload);
}

/** GET /entities/{id}/relationships — related-entities list. */
export async function entityConnections(
  id: string,
  signal?: AbortSignal,
): Promise<Relationships> {
  const { data } = await api.get(
    `/api/v1/entities/${encodeURIComponent(id)}/relationships`,
    { signal },
  );
  return RelationshipsSchema.parse(data);
}

/** GET /entities/{id}/timeline — the entity's derived timeline rows. */
export async function entityTimeline(
  id: string,
  signal?: AbortSignal,
): Promise<EntityTimeline> {
  const { data } = await api.get(
    `/api/v1/entities/${encodeURIComponent(id)}/timeline`,
    { signal },
  );
  return EntityTimelineSchema.parse(data);
}

/** Typed entity endpoints against the real Laravel API. */
import {
  EntityDetailSchema,
  EntityListSchema,
  RelationshipsSchema
  
  
  
} from '@/lib/schemas/entity';
import type {EntityDetail, EntityList, Relationships} from '@/lib/schemas/entity';
import { asFeatureCollection  } from '@/lib/schemas/map';
import type {MapFeatureCollection} from '@/lib/schemas/map';
import type { Scope } from '@/types/atlas';
import { api } from './client';
import { listParams, mapParams  } from './params';
import type {ListOptions} from './params';

/**
 * GET /entities/map — the viewport query. Returns a GeoJSON FeatureCollection
 * of border/point geometries for the scope. Already a single optimized PostGIS
 * query server-side; we pass the FeatureCollection straight to maplibre without
 * a deep parse (only a shallow envelope check).
 */
export async function entitiesInView(
  scope: Scope,
  signal?: AbortSignal,
): Promise<MapFeatureCollection> {
  const { data } = await api.get('/api/v1/entities/map', {
    signal,
    params: mapParams(scope),
  });
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

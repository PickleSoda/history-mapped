/** Typed entity endpoints. Each parses its response through a zod schema. */
import {
  EntitiesInViewSchema,
  EntityConnectionsSchema,
  EntityDetailSchema,
  type EntitiesInView,
  type EntityConnections,
  type EntityDetail,
} from '@/lib/schemas/entity';
import { serializeBbox, serializeTime } from '@/lib/url/serialize';
import type { Scope } from '@/types/atlas';
import { api } from './client';

/** The viewport query — geospatial + temporal filter pushed to the server in
 *  one request (no per-entity round trips). Keyed on the snapped scope. */
export async function entitiesInView(
  scope: Scope,
  signal?: AbortSignal,
): Promise<EntitiesInView> {
  const { data } = await api.get('/api/v1/atlas/entities', {
    signal,
    params: {
      bbox: serializeBbox(scope.bbox),
      t: serializeTime(scope.time),
      z: scope.z,
      groups: scope.groups.join(','),
    },
  });
  return EntitiesInViewSchema.parse(data);
}

export async function entity(
  id: string,
  signal?: AbortSignal,
): Promise<EntityDetail> {
  const { data } = await api.get(`/api/v1/atlas/entities/${encodeURIComponent(id)}`, {
    signal,
  });
  return EntityDetailSchema.parse(data);
}

export async function entityConnections(
  id: string,
  signal?: AbortSignal,
): Promise<EntityConnections> {
  const { data } = await api.get(
    `/api/v1/atlas/entities/${encodeURIComponent(id)}/connections`,
    { signal },
  );
  return EntityConnectionsSchema.parse(data);
}

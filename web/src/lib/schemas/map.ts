/**
 * Map FeatureCollection types for GET /entities/map.
 *
 * The endpoint streams a GeoJSON FeatureCollection of border/point geometries,
 * potentially thousands of features. We deliberately do NOT run a deep zod
 * parse over it — that would be the client-side equivalent of the geometry
 * reserialization we avoid on the server. Instead we type it and do a shallow
 * envelope check; maplibre consumes the raw FeatureCollection directly.
 */
import type { Feature, FeatureCollection, Geometry } from 'geojson';
import type { EntityGroup } from '@/types/atlas';

/** Properties carried on each map feature (see MapEntitiesAction). */
export interface MapFeatureProperties {
  id: string;
  name: string;
  entity_type: string | null;
  /** Backend emits UPPERCASE; consumers lowercase as needed. */
  entity_group: string;
  impact_score: number | null;
  display_priority: number | null;
  icon_class: string | null;
  period_type: string | null;
  geometry_period_id: string | null;
  start_year: number | null;
  end_year: number | null;
}

export type MapFeature = Feature<Geometry | null, MapFeatureProperties>;
export type MapFeatureCollection = FeatureCollection<Geometry | null, MapFeatureProperties>;

/** Normalize a feature's group to the frontend's lowercase EntityGroup. */
export function featureGroup(f: MapFeature): EntityGroup {
  return f.properties.entity_group.toLowerCase() as EntityGroup;
}

/** Shallow runtime guard — confirms the envelope without walking every feature. */
export function asFeatureCollection(data: unknown): MapFeatureCollection {
  const fc = data as MapFeatureCollection;
  if (!fc || fc.type !== 'FeatureCollection' || !Array.isArray(fc.features)) {
    throw new Error('Expected a GeoJSON FeatureCollection from /entities/map');
  }
  return fc;
}

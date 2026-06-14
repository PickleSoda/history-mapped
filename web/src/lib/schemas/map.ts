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

/** Properties carried on each map feature (see MapEntitiesAction — trimmed, MQ-8). */
export interface MapFeatureProperties {
  id: string;
  name: string;
  entity_type: string | null;
  /** Backend emits UPPERCASE; consumers lowercase as needed. */
  entity_group: string;
  impact_score: number | null;
  start_year: number | null;
  end_year: number | null;
  /** attributes->>'entity_color' (hex) or null. */
  entity_color: string | null;
  /** OHM basemap reference (for OHM-linked entities) — drive layer highlight. */
  ohm_provider: string | null;
  ohm_external_type: string | null;
  ohm_external_id: string | null;
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

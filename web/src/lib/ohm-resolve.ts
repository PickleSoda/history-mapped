/**
 * Resolve a click on the OpenHistoricalMap basemap to one of our entities.
 *
 * The OHM vector layers carry an `@id` ("relation/1880") or `osm_type`/`osm_id`
 * on each feature. We pull that identity off the rendered features near the
 * click and ask the public resolver (GET /map/resolve-ohm-feature) whether any
 * of them is linked to an entity via a geo-ref. Ported from the admin editor's
 * detection, trimmed to the read path.
 */
import type { Map as MapLibreMap, MapMouseEvent, PointLike } from 'maplibre-gl';
import { api } from '@/lib/api/client';

type ExternalType = 'node' | 'way' | 'relation';
interface OhmIdentity {
  external_type: ExternalType;
  external_id: string;
}

/** How many distinct nearby OHM features to try before giving up. */
const MAX_CANDIDATES = 5;
/** Square half-size (px) around the click used to catch thin boundary lines. */
const HIT_RADIUS_PX = 6;

function prefixToType(prefix: string): ExternalType {
  if (prefix === 'n') return 'node';
  if (prefix === 'w') return 'way';
  return 'relation';
}

/** Pull a {type,id} OHM identity off a rendered feature, or null. */
function extractIdentity(props: Record<string, unknown>): OhmIdentity | null {
  const rawAtId = props['@id'];
  if (typeof rawAtId === 'string' && rawAtId.trim() !== '') {
    const normalized = rawAtId.trim().toLowerCase();
    const slash = normalized.match(/^(node|way|relation)\/(\d+)$/);
    if (slash) return { external_type: slash[1] as ExternalType, external_id: slash[2] };
    const prefix = normalized.match(/^([nwr])(\d+)$/);
    if (prefix) return { external_type: prefixToType(prefix[1]), external_id: prefix[2] };
  }

  const osmType = typeof props.osm_type === 'string' ? props.osm_type.toLowerCase() : null;
  const osmId = props.osm_id;
  if (
    (osmType === 'node' || osmType === 'way' || osmType === 'relation') &&
    (typeof osmId === 'string' || typeof osmId === 'number')
  ) {
    return { external_type: osmType, external_id: String(osmId) };
  }

  return null;
}

/** Visible OHM basemap layer ids (boundaries + labels) we can query. */
function ohmLayerIds(map: MapLibreMap): string[] {
  const layers = map.getStyle()?.layers ?? [];
  return layers
    .filter((layer) => 'source' in layer && layer.source === 'ohm')
    .filter(
      (layer) =>
        !('layout' in layer) ||
        layer.layout?.visibility === undefined ||
        layer.layout.visibility !== 'none',
    )
    .filter((layer) => layer.type === 'line' || layer.type === 'fill' || layer.type === 'symbol')
    .map((layer) => layer.id);
}

/** Distinct OHM identities near the click, nearest-first (query order). */
function candidateIdentities(map: MapLibreMap, e: MapMouseEvent): OhmIdentity[] {
  const layers = ohmLayerIds(map).filter((id) => map.getLayer(id));
  if (layers.length === 0) return [];

  const box: [PointLike, PointLike] = [
    [e.point.x - HIT_RADIUS_PX, e.point.y - HIT_RADIUS_PX],
    [e.point.x + HIT_RADIUS_PX, e.point.y + HIT_RADIUS_PX],
  ];
  const features = map.queryRenderedFeatures(box, { layers });

  const seen = new Set<string>();
  const out: OhmIdentity[] = [];
  for (const f of features) {
    const identity = extractIdentity((f.properties ?? {}) as Record<string, unknown>);
    if (!identity) continue;
    const key = `${identity.external_type}/${identity.external_id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(identity);
    if (out.length >= MAX_CANDIDATES) break;
  }
  return out;
}

/** GET the public resolver; returns the entity id on a hit, null on 404. */
async function resolveIdentity(
  identity: OhmIdentity,
  year: number,
  signal?: AbortSignal,
): Promise<string | null> {
  try {
    const { data } = await api.get('/api/v1/map/resolve-ohm-feature', {
      signal,
      params: {
        provider: 'ohm',
        external_type: identity.external_type,
        external_id: identity.external_id,
        target_year: year,
      },
    });
    const id = (data as { data?: { entity?: { id?: string } } }).data?.entity?.id;
    return typeof id === 'string' && id ? id : null;
  } catch {
    return null; // 404 (no linked entity) or transient error — treat as a miss.
  }
}

/**
 * Resolve an OHM basemap click to an entity id, or null if nothing nearby is
 * linked. Tries the nearest few features in order and returns the first hit.
 */
export async function resolveOhmClickToEntity(
  map: MapLibreMap,
  e: MapMouseEvent,
  year: number,
  signal?: AbortSignal,
): Promise<string | null> {
  for (const identity of candidateIdentities(map, e)) {
    const entityId = await resolveIdentity(identity, year, signal);
    if (entityId) return entityId;
  }
  return null;
}

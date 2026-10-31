/**
 * Resolve a click on the OpenHistoricalMap basemap to one of our entities.
 *
 * OHM's Martin-served tiles name each feature by a signed `osm_id` only
 * (negative = relation, positive = node or way; spec §1, D3). Older tiles
 * carried `@id` ("relation/1880") or `osm_type` + unsigned `osm_id`; both are
 * folded into the same signed id. For each OHM feature near the click we
 * first look the id up in our loaded entity tiles (`ohm_osm_id`, tile mode
 * only), then ask the public resolver (GET /map/resolve-ohm-feature?osm_id=).
 */
import type { Map as MapLibreMap, MapMouseEvent, PointLike } from 'maplibre-gl';
import { api } from '@/lib/api/client';
import { ENTITY_SOURCE_LAYER, SOURCE_ID, isMapTilesEnabled } from '@/lib/map-tiles';
import { yearToDecdate } from '@/lib/ohm-date';

/** An OHM feature named by its signed OSM id (negative = relation). */
export interface OhmIdentity {
  osm_id: number;
}

/** How many distinct nearby OHM features to try before giving up. */
const MAX_CANDIDATES = 5;
/** Square half-size (px) around the click used to catch thin boundary lines. */
const HIT_RADIUS_PX = 6;
/**
 * Slack on the decimal-date comparison: tile decdates are computed in
 * Postgres and the click year in JS, so a window starting in the clicked year
 * must not hinge on both sides rounding the sum identically.
 */
const DECDATE_EPSILON = 1e-6;

/** A non-zero integer id from a number or numeric string, else null. */
function toOsmId(value: unknown): number | null {
  let n = Number.NaN;
  if (typeof value === 'number') n = value;
  else if (typeof value === 'string' && /^\s*-?\d+\s*$/.test(value)) n = Number(value);
  return Number.isSafeInteger(n) && n !== 0 ? n : null;
}

/** Pull a signed OHM identity off a rendered feature's properties, or null. */
export function extractIdentity(props: Record<string, unknown>): OhmIdentity | null {
  const rawAtId = props['@id'];
  if (typeof rawAtId === 'string' && rawAtId.trim() !== '') {
    const normalized = rawAtId.trim().toLowerCase();
    const match =
      normalized.match(/^(node|way|relation)\/(\d+)$/) ?? normalized.match(/^([nwr])(\d+)$/);
    const id = match ? toOsmId(match[2]) : null;
    if (match && id !== null) return { osm_id: match[1].startsWith('r') ? -id : id };
  }

  const osmId = toOsmId(props.osm_id);
  if (osmId === null) return null;

  // Legacy tiles paired an unsigned id with its type; sign it the same way.
  const osmType = typeof props.osm_type === 'string' ? props.osm_type.toLowerCase() : null;
  if (osmType === 'relation') return { osm_id: -Math.abs(osmId) };
  if (osmType === 'node' || osmType === 'way') return { osm_id: Math.abs(osmId) };
  return { osm_id: osmId };
}

/** A finite number from a tile property, else null (absent bound). */
function toDecdate(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/**
 * The first feature whose `[start_decdate, end_decdate]` window contains the
 * start of `year` (OHM convention, D2), or null. A missing bound is
 * open-ended, as the layer filter treats a missing `end_decdate`.
 */
export function pickFeatureForYear<T extends { properties?: Record<string, unknown> | null }>(
  features: readonly T[],
  year: number,
): T | null {
  const at = yearToDecdate(year, 'start');
  for (const feature of features) {
    const start = toDecdate(feature.properties?.start_decdate);
    const end = toDecdate(feature.properties?.end_decdate);
    const started = start === null || start <= at + DECDATE_EPSILON;
    const notEnded = end === null || end >= at - DECDATE_EPSILON;
    if (started && notEnded) return feature;
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

  const seen = new Set<number>();
  const out: OhmIdentity[] = [];
  for (const f of features) {
    const identity = extractIdentity((f.properties ?? {}) as Record<string, unknown>);
    if (!identity || seen.has(identity.osm_id)) continue;
    seen.add(identity.osm_id);
    out.push(identity);
    if (out.length >= MAX_CANDIDATES) break;
  }
  return out;
}

/**
 * Tile mode: the entity linked to `osmId` among our loaded entity tiles
 * (`ohm_osm_id`, spec D3) and visible in `year`, or null. Only loaded tiles
 * are searched, and low zooms cap features per tile (D4), so a miss here
 * falls through to the resolver.
 */
function resolveFromTiles(map: MapLibreMap, osmId: number, year: number): string | null {
  if (!isMapTilesEnabled() || !map.getSource(SOURCE_ID)) return null;
  const features = map.querySourceFeatures(SOURCE_ID, {
    sourceLayer: ENTITY_SOURCE_LAYER,
    filter: ['==', ['get', 'ohm_osm_id'], osmId],
  });
  const id = pickFeatureForYear(features, year)?.properties?.id;
  return typeof id === 'string' && id ? id : null;
}

/** Local tile lookup, else GET the public resolver; the entity id or null. */
async function resolveIdentity(
  map: MapLibreMap,
  identity: OhmIdentity,
  year: number,
  signal?: AbortSignal,
): Promise<string | null> {
  const local = resolveFromTiles(map, identity.osm_id, year);
  if (local) return local;

  try {
    const { data } = await api.get('/api/v1/map/resolve-ohm-feature', {
      signal,
      params: { provider: 'ohm', osm_id: identity.osm_id, target_year: year },
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
    const entityId = await resolveIdentity(map, identity, year, signal);
    if (entityId) return entityId;
  }
  return null;
}

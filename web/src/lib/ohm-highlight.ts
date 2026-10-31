/**
 * Correlation highlight between our entities and OpenHistoricalMap features
 * (spec D5). The key is the signed OSM id (D3): tile features carry it as
 * `ohm_osm_id`, REST features as `ohm_external_type` + `ohm_external_id`, and
 * OHM's label points (`ohm` / `land_ohm_centroids`) and admin polygons
 * (`ohm_admin` / `boundaries`) as `osm_id`, promoted to the feature id in the
 * normalised style (map-config.ts) so feature-state can address them.
 *
 * - Linked OHM labels get feature-state `linked` (painted in LINK_COLOR).
 * - The hovered / selected entity's OHM polygon gets `hover` / `selected` on
 *   two `ohm_admin` layers that stay hidden until first needed: hidden layers
 *   mark their source unused, so MapLibre fetches none of its heavy tiles.
 *   Once shown they stay visible until a quiet period or a camera move,
 *   because each visibility change reloads the source's tiles.
 * - Hovering a linked OHM label resolves to our entity through the index.
 *
 * Feature-state changes never reload a source; layout / filter changes do,
 * so the hover path avoids both (the hovered marker has its own GeoJSON).
 */
import type { Feature, FeatureCollection } from 'geojson';
import type { ExpressionSpecification, Map as MapLibreMap, PointLike } from 'maplibre-gl';
import { pickFeatureForYear } from '@/lib/ohm-resolve';

/** Accent for everything linked to OHM: our labels, OHM labels, polygons. */
export const LINK_COLOR = '#b4552d';
/** Default dark label colour on the (always light) OHM basemaps. */
const LABEL_COLOR = '#2a2722';

/** OHM's general tileset in every house style. */
export const OHM_SOURCE = 'ohm';
/** OHM's polygon tileset, added to the normalised style (map-config.ts). */
export const OHM_ADMIN_SOURCE = 'ohm_admin';
/** The polygon layer inside `ohm_admin` tiles. */
export const OHM_ADMIN_LAYER = 'boundaries';
/** Polity label points in `ohm` tiles; `osm_id` < 0 is the relation id. */
export const OHM_CENTROID_SOURCE_LAYER = 'land_ohm_centroids';

export const OHM_ADMIN_FILL_LAYER = 'ohm-admin-fill';
export const OHM_ADMIN_LINE_LAYER = 'ohm-admin-line';
const OHM_ADMIN_LAYERS = [OHM_ADMIN_FILL_LAYER, OHM_ADMIN_LINE_LAYER];
/** Hide the admin layers after this long with nothing hovered / selected. */
export const OHM_ADMIN_HIDE_DELAY_MS = 4000;

const LINKED: ExpressionSpecification = ['boolean', ['feature-state', 'linked'], false];
const HOVER: ExpressionSpecification = ['boolean', ['feature-state', 'hover'], false];
const SELECTED: ExpressionSpecification = ['boolean', ['feature-state', 'selected'], false];

type FeatureLike = { properties?: object | null };

const EMPTY_FC: FeatureCollection = { type: 'FeatureCollection', features: [] };

/** A non-zero safe integer from a number or numeric string, else null. */
function toOsmId(value: unknown): number | null {
  let n = Number.NaN;
  if (typeof value === 'number') n = value;
  else if (typeof value === 'string' && /^\s*-?\d+\s*$/.test(value)) n = Number(value);
  return Number.isSafeInteger(n) && n !== 0 ? n : null;
}

/** The signed OSM id a tile or REST feature links to, or null. */
function linkedOsmId(props: Record<string, unknown>): number | null {
  const signed = toOsmId(props.ohm_osm_id);
  if (signed !== null) return signed;

  const id = toOsmId(props.ohm_external_id);
  if (id === null) return null;
  switch (props.ohm_external_type) {
    case 'relation':
      return -Math.abs(id);
    case 'node':
    case 'way':
      return Math.abs(id);
    default:
      return null;
  }
}

/** Each linked feature's (entity id, signed OSM id), in feature order. */
function* links(features: Iterable<FeatureLike>): Generator<[string, number]> {
  for (const feature of features) {
    const props = (feature.properties ?? {}) as Record<string, unknown>;
    const entityId = props.id;
    const osmId = linkedOsmId(props);
    if (osmId !== null && typeof entityId === 'string' && entityId) yield [entityId, osmId];
  }
}

/**
 * Signed OSM id → entity id over our loaded features, tile-shaped
 * (`ohm_osm_id`) or REST-shaped (`ohm_external_*`). The first entity wins when
 * several link the same OHM feature (an OHM label resolves to one entity).
 */
export function linkIndexFromFeatures(features: Iterable<FeatureLike>): Map<number, string> {
  const index = new Map<number, string>();
  for (const [entityId, osmId] of links(features)) {
    if (!index.has(osmId)) index.set(osmId, entityId);
  }
  return index;
}

/**
 * Entity id → signed OSM id, built from the features themselves, so every
 * entity linking a shared OHM feature can still emphasise it.
 */
export function entityOsmIdsFromFeatures(features: Iterable<FeatureLike>): Map<string, number> {
  const byEntity = new Map<string, number>();
  for (const [entityId, osmId] of links(features)) {
    if (!byEntity.has(entityId)) byEntity.set(entityId, osmId);
  }
  return byEntity;
}

/** What to add and remove to go from `prev` to `next`. */
export function diffLinkedState(
  prev: ReadonlySet<number>,
  next: ReadonlySet<number>,
): { add: number[]; remove: number[] } {
  return {
    add: [...next].filter((id) => !prev.has(id)),
    remove: [...prev].filter((id) => !next.has(id)),
  };
}

type StateMap = Pick<MapLibreMap, 'getSource' | 'setFeatureState' | 'removeFeatureState'>;

/**
 * Mark the OHM labels of every linked feature in `index` (`linked`), clearing
 * those no longer linked; returns the ids now marked. Feature state lives on
 * the source, so labels in tiles that load later pick it up too.
 */
export function syncLinkedLabels(
  map: StateMap,
  index: ReadonlyMap<number, string>,
  prev: ReadonlySet<number>,
): Set<number> {
  if (!map.getSource(OHM_SOURCE)) return new Set();
  const next = new Set(index.keys());
  const { add, remove } = diffLinkedState(prev, next);
  const target = { source: OHM_SOURCE, sourceLayer: OHM_CENTROID_SOURCE_LAYER };
  for (const id of remove) map.removeFeatureState({ ...target, id }, 'linked');
  for (const id of add) map.setFeatureState({ ...target, id }, { linked: true });
  return next;
}

/** The OHM polygons to emphasise, by signed OSM id. */
export interface Emphasis {
  hoverOsmId: number | null;
  selectedOsmId: number | null;
}

export const NO_EMPHASIS: Emphasis = { hoverOsmId: null, selectedOsmId: null };

type EmphasisMap = Pick<MapLibreMap, 'getLayer' | 'setFeatureState' | 'removeFeatureState'>;

/**
 * Move `hover` / `selected` feature-state on the `ohm_admin` polygons from
 * `prev` to `next` (feature-state only: no source reload). Returns the
 * applied state, NO_EMPHASIS when the style has no admin layers.
 */
export function applyEmphasis(map: EmphasisMap, next: Emphasis, prev: Emphasis): Emphasis {
  if (!OHM_ADMIN_LAYERS.some((id) => map.getLayer(id))) return NO_EMPHASIS;

  const target = { source: OHM_ADMIN_SOURCE, sourceLayer: OHM_ADMIN_LAYER };
  const keys = [
    ['hover', prev.hoverOsmId, next.hoverOsmId],
    ['selected', prev.selectedOsmId, next.selectedOsmId],
  ] as const;
  for (const [key, before, after] of keys) {
    if (before === after) continue;
    if (before !== null) map.removeFeatureState({ ...target, id: before }, key);
    if (after !== null) map.setFeatureState({ ...target, id: after }, { [key]: true });
  }
  return next;
}

/** Show or hide both admin layers (those present). Reloads their source. */
export function setOhmAdminVisibility(
  map: Pick<MapLibreMap, 'getLayer' | 'setLayoutProperty'>,
  visible: boolean,
): void {
  for (const id of OHM_ADMIN_LAYERS) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
  }
}

/**
 * Where the admin layers go: below the basemap's first symbol layer (so the
 * tint never washes over labels), searched only below `fallbackBeforeId`
 * (our overlay); else below `fallbackBeforeId` itself.
 */
export function adminLayersBeforeId(
  map: Pick<MapLibreMap, 'getLayersOrder' | 'getLayer'>,
  fallbackBeforeId?: string,
): string | undefined {
  for (const id of map.getLayersOrder()) {
    if (id === fallbackBeforeId) break;
    if (map.getLayer(id)?.type === 'symbol') return id;
  }
  return fallbackBeforeId && map.getLayer(fallbackBeforeId) ? fallbackBeforeId : undefined;
}

/**
 * The OHM polygon highlight: a fill and an outline in LINK_COLOR whose
 * opacity follows `selected` > `hover` > nothing, both hidden until first
 * needed. Inserted below the basemap labels (see adminLayersBeforeId). Not
 * date-filtered: only the hovered / selected relation ever shows.
 */
export function addOhmAdminLayers(
  map: Pick<MapLibreMap, 'getSource' | 'getLayer' | 'getLayersOrder' | 'addLayer'>,
  fallbackBeforeId?: string,
): void {
  if (!map.getSource(OHM_ADMIN_SOURCE)) return;
  const before = adminLayersBeforeId(map, fallbackBeforeId);
  const common = {
    source: OHM_ADMIN_SOURCE,
    'source-layer': OHM_ADMIN_LAYER,
    layout: { visibility: 'none' as const },
  };
  if (!map.getLayer(OHM_ADMIN_FILL_LAYER)) {
    map.addLayer(
      {
        id: OHM_ADMIN_FILL_LAYER,
        type: 'fill',
        ...common,
        paint: {
          'fill-color': LINK_COLOR,
          'fill-opacity': ['case', SELECTED, 0.22, HOVER, 0.12, 0],
        },
      },
      before,
    );
  }
  if (!map.getLayer(OHM_ADMIN_LINE_LAYER)) {
    map.addLayer(
      {
        id: OHM_ADMIN_LINE_LAYER,
        type: 'line',
        ...common,
        paint: {
          'line-color': LINK_COLOR,
          'line-width': 2,
          'line-opacity': ['case', SELECTED, 0.9, HOVER, 0.6, 0],
        },
      },
      before,
    );
  }
}

const INTERPOLATE_OPS = new Set(['interpolate', 'interpolate-hcl', 'interpolate-lab']);

/** Index of the first output of a zoom curve, or null if `value` is not one. */
function zoomCurveFirstOutput(value: unknown[]): number | null {
  if (INTERPOLATE_OPS.has(value[0] as string)) {
    // [op, type, input, z0, out0, z1, out1, …]
    return Array.isArray(value[2]) && value[2][0] === 'zoom' ? 4 : null;
  }
  if (value[0] === 'step') {
    // [op, input, out0, z1, out1, …]
    return Array.isArray(value[1]) && value[1][0] === 'zoom' ? 2 : null;
  }
  return null;
}

/**
 * An OHM label layer's `text-color`, switched to LINK_COLOR for features with
 * `linked` state. A zoom curve must stay the top-level expression, so the
 * switch goes into each of its outputs instead. Legacy function objects are
 * returned unchanged (no OHM house style uses one on label points today).
 */
export function linkedLabelColor(original: unknown): unknown {
  const linkedOr = (color: unknown) => ['case', LINKED, LINK_COLOR, color];
  if (original === undefined || original === null) return linkedOr(LABEL_COLOR);
  if (typeof original === 'string') return linkedOr(original);
  if (!Array.isArray(original)) return original;

  const firstOutput = zoomCurveFirstOutput(original);
  if (firstOutput !== null) {
    return original.map((part, i) =>
      i >= firstOutput && (i - firstOutput) % 2 === 0 ? linkedOr(part) : part,
    );
  }
  return linkedOr(original);
}

/** The style's OHM label-point symbol layers, in style order. */
export function centroidLayerIds(map: Pick<MapLibreMap, 'getLayersOrder' | 'getLayer'>): string[] {
  return map.getLayersOrder().filter((id) => {
    const layer = map.getLayer(id);
    return (
      layer?.type === 'symbol' &&
      layer.source === OHM_SOURCE &&
      layer.sourceLayer === OHM_CENTROID_SOURCE_LAYER
    );
  });
}

type GeoFeatureLike = { geometry?: unknown; properties?: object | null };

/**
 * Data for the hovered-marker source: the hovered entity's point among
 * `candidates` (tile features from querySourceFeatures, or REST features),
 * the one whose decdate window contains `year` when it has several periods.
 */
export function hoverMarkerData(
  candidates: readonly GeoFeatureLike[],
  hoverId: string | null,
  year: number,
): FeatureCollection {
  if (hoverId === null) return EMPTY_FC;
  const points = candidates
    .map((f) => ({
      geometry: f.geometry as Feature['geometry'] | null | undefined,
      properties: (f.properties ?? {}) as Record<string, unknown>,
    }))
    .filter((f) => f.properties.id === hoverId && f.geometry?.type === 'Point');
  const picked = pickFeatureForYear(points, year);
  if (!picked?.geometry) return EMPTY_FC;
  return {
    type: 'FeatureCollection',
    features: [{ type: 'Feature', geometry: picked.geometry, properties: { ...picked.properties } }],
  };
}

type CorrelationMap = StateMap &
  EmphasisMap &
  Pick<MapLibreMap, 'getLayersOrder' | 'queryRenderedFeatures' | 'setLayoutProperty'>;

/**
 * The correlation state of one map: the osm-id index of our loaded entity
 * features, which OHM labels are marked, the polygon emphasis for the
 * hovered / selected entity and whether the admin layers are shown. Callers
 * feed it features, style swaps, camera moves and the hover / selection.
 */
export class OhmCorrelation {
  private index = new Map<number, string>();
  private osmByEntity = new Map<string, number>();
  private linked = new Set<number>();
  private emphasis: Emphasis = NO_EMPHASIS;
  private centroidLayers: string[] = [];
  private hoverId: string | null = null;
  private selectedId: string | null = null;
  private adminVisible = false;
  private hideTimer: ReturnType<typeof setTimeout> | undefined;

  constructor(private readonly map: CorrelationMap) {}

  /** A new style was loaded: its sources carry no feature state yet. */
  styleLoaded(hoverId: string | null, selectedId: string | null): void {
    this.cancelHide();
    this.linked = new Set();
    this.emphasis = NO_EMPHASIS;
    this.adminVisible = false; // new admin layers start hidden
    this.centroidLayers = centroidLayerIds(this.map);
    this.linked = syncLinkedLabels(this.map, this.index, this.linked);
    this.emphasize(hoverId, selectedId);
  }

  /** Rebuild the index from our loaded features and re-sync the highlight. */
  setFeatures(features: Iterable<FeatureLike>): void {
    const list = [...features];
    this.index = linkIndexFromFeatures(list);
    this.osmByEntity = entityOsmIdsFromFeatures(list);
    this.linked = syncLinkedLabels(this.map, this.index, this.linked);
    this.emphasize(this.hoverId, this.selectedId);
  }

  /** Emphasise the OHM polygons linked to the hovered / selected entities. */
  emphasize(hoverId: string | null, selectedId: string | null): void {
    this.hoverId = hoverId;
    this.selectedId = selectedId;
    const osm = (id: string | null) => (id === null ? null : (this.osmByEntity.get(id) ?? null));
    this.emphasis = applyEmphasis(
      this.map,
      { hoverOsmId: osm(hoverId), selectedOsmId: osm(selectedId) },
      this.emphasis,
    );

    if (this.isEmphasised()) {
      // Show at once and keep showing: toggling reloads the admin tiles.
      this.cancelHide();
      this.setAdminVisible(true);
    } else if (hoverId !== null || selectedId !== null) {
      // Still hovering / selecting (an unlinked entity): a list scan goes on.
      this.cancelHide();
    } else if (this.adminVisible && this.hideTimer === undefined) {
      // Idle: hide after a quiet period with nothing hovered or selected.
      this.hideTimer = setTimeout(() => {
        this.hideTimer = undefined;
        if (!this.isEmphasised()) this.setAdminVisible(false);
      }, OHM_ADMIN_HIDE_DELAY_MS);
    }
  }

  /** The camera moved: drop idle admin layers before they fetch new tiles. */
  viewMoved(): void {
    if (this.isEmphasised()) return;
    this.cancelHide();
    this.setAdminVisible(false);
  }

  /** Stop the pending hide (the map is going away). */
  dispose(): void {
    this.cancelHide();
  }

  /**
   * The entity under the pointer: one of our markers on `markerLayer` first,
   * else a linked OHM label resolved through the index; null otherwise.
   */
  entityAt(point: PointLike, markerLayer: string): string | null {
    const layers = [markerLayer, ...this.centroidLayers].filter((id) => this.map.getLayer(id));
    if (layers.length === 0) return null;

    for (const feature of this.map.queryRenderedFeatures(point, { layers })) {
      if (feature.layer.id === markerLayer) {
        const id = feature.properties?.id;
        if (typeof id === 'string' && id) return id;
        continue;
      }
      if (!feature.state?.linked) continue;
      const osmId = toOsmId(feature.id ?? feature.properties?.osm_id);
      const entityId = osmId === null ? undefined : this.index.get(osmId);
      if (entityId) return entityId;
    }
    return null;
  }

  private isEmphasised(): boolean {
    return this.emphasis.hoverOsmId !== null || this.emphasis.selectedOsmId !== null;
  }

  private setAdminVisible(visible: boolean): void {
    if (visible === this.adminVisible) return;
    this.adminVisible = visible;
    setOhmAdminVisibility(this.map, visible);
  }

  private cancelHide(): void {
    clearTimeout(this.hideTimer);
    this.hideTimer = undefined;
  }
}

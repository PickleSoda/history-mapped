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
 *   two `ohm_admin` layers that stay hidden otherwise: hidden layers mark
 *   their source unused, so MapLibre fetches none of its heavy tiles.
 * - Hovering a linked OHM label resolves to our entity through the index.
 */
import type {
  ExpressionSpecification,
  FilterSpecification,
  Map as MapLibreMap,
  PointLike,
} from 'maplibre-gl';
import { entityLayerFilter, isMapTilesEnabled, isPoint } from '@/lib/map-tiles';
import type { EntityGroup, TimeState } from '@/types/atlas';

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

const LINKED: ExpressionSpecification = ['boolean', ['feature-state', 'linked'], false];
const HOVER: ExpressionSpecification = ['boolean', ['feature-state', 'hover'], false];
const SELECTED: ExpressionSpecification = ['boolean', ['feature-state', 'selected'], false];

type FeatureLike = { properties?: object | null };

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

/**
 * Signed OSM id → entity id over our loaded features, tile-shaped
 * (`ohm_osm_id`) or REST-shaped (`ohm_external_*`). The first entity wins when
 * several link the same OHM feature.
 */
export function linkIndexFromFeatures(features: Iterable<FeatureLike>): Map<number, string> {
  const index = new Map<number, string>();
  for (const feature of features) {
    const props = (feature.properties ?? {}) as Record<string, unknown>;
    const entityId = props.id;
    const osmId = linkedOsmId(props);
    if (osmId === null || typeof entityId !== 'string' || !entityId) continue;
    if (!index.has(osmId)) index.set(osmId, entityId);
  }
  return index;
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

type EmphasisMap = Pick<
  MapLibreMap,
  'getLayer' | 'setFeatureState' | 'removeFeatureState' | 'setLayoutProperty'
>;

/**
 * Move `hover` / `selected` feature-state on the `ohm_admin` polygons from
 * `prev` to `next`, and show the admin layers only while something is
 * emphasised (hidden layers keep their tiles from loading). Returns the
 * applied state, NO_EMPHASIS when the style has no admin layers.
 */
export function applyEmphasis(map: EmphasisMap, next: Emphasis, prev: Emphasis): Emphasis {
  const layers = OHM_ADMIN_LAYERS.filter((id) => map.getLayer(id));
  if (layers.length === 0) return NO_EMPHASIS;

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

  const visible = next.hoverOsmId !== null || next.selectedOsmId !== null;
  for (const id of layers) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
  return next;
}

/**
 * The OHM polygon highlight: a fill and an outline in LINK_COLOR whose
 * opacity follows `selected` > `hover` > nothing, both hidden until
 * `applyEmphasis` shows them. Inserted below `beforeId` (our entity layers).
 * Not date-filtered: only the hovered / selected relation ever shows.
 */
export function addOhmAdminLayers(
  map: Pick<MapLibreMap, 'getSource' | 'getLayer' | 'addLayer'>,
  beforeId?: string,
): void {
  if (!map.getSource(OHM_ADMIN_SOURCE)) return;
  const before = beforeId && map.getLayer(beforeId) ? beforeId : undefined;
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

function isZoomCurve(value: unknown[]): boolean {
  const input = value[0] === 'interpolate' ? value[2] : value[0] === 'step' ? value[1] : null;
  return Array.isArray(input) && input[0] === 'zoom';
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

  if (isZoomCurve(original)) {
    // interpolate: [op, type, input, z0, out0, z1, out1, …]; step: [op, input, out0, z1, out1, …]
    const firstOutput = original[0] === 'interpolate' ? 4 : 2;
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

export interface HoverMarkerFilterOptions {
  hoverId: string | null;
  time: TimeState;
  groups: readonly EntityGroup[];
}

/**
 * The filter for the hovered-marker layer: the hovered entity's points only.
 * Tiles carry every period of an entity, so tile mode also applies the
 * symbol layer's time / group window; GeoJSON is already year-filtered.
 */
export function hoverMarkerFilter({
  hoverId,
  time,
  groups,
}: HoverMarkerFilterOptions): FilterSpecification {
  const base = isMapTilesEnabled() ? entityLayerFilter({ geometry: 'point', time, groups }) : isPoint;
  return ['all', base, ['==', ['get', 'id'], hoverId ?? '']] as FilterSpecification;
}

type CorrelationMap = StateMap &
  EmphasisMap &
  Pick<MapLibreMap, 'getLayersOrder' | 'queryRenderedFeatures'>;

/**
 * The correlation state of one map: the osm-id index of our loaded entity
 * features, which OHM labels are marked, and the polygon emphasis for the
 * hovered / selected entity. Callers feed it features, style swaps and the
 * hover / selection; it keeps the feature-state in step.
 */
export class OhmCorrelation {
  private index = new Map<number, string>();
  private osmByEntity = new Map<string, number>();
  private linked = new Set<number>();
  private emphasis: Emphasis = NO_EMPHASIS;
  private centroidLayers: string[] = [];
  private hoverId: string | null = null;
  private selectedId: string | null = null;

  constructor(private readonly map: CorrelationMap) {}

  /** A new style was loaded: its sources carry no feature state yet. */
  styleLoaded(hoverId: string | null, selectedId: string | null): void {
    this.linked = new Set();
    this.emphasis = NO_EMPHASIS;
    this.centroidLayers = centroidLayerIds(this.map);
    this.linked = syncLinkedLabels(this.map, this.index, this.linked);
    this.emphasize(hoverId, selectedId);
  }

  /** Rebuild the index from our loaded features and re-sync the highlight. */
  setFeatures(features: Iterable<FeatureLike>): void {
    this.index = linkIndexFromFeatures(features);
    this.osmByEntity = new Map();
    for (const [osmId, entityId] of this.index) {
      if (!this.osmByEntity.has(entityId)) this.osmByEntity.set(entityId, osmId);
    }
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
}

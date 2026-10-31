/**
 * Tile mode for our entity overlay (spec D1, D7). With `VITE_MAP_TILES_URL`
 * set, the `entities` source reads all-time vector tiles from Martin instead
 * of GeoJSON viewport queries, so the timeline year and the group filter
 * become client-side filter expressions on our three entity layers, built
 * here. The OHM basemap layers keep their own date filter
 * (`applyOhmLayerDateFilter`).
 *
 * Tile contract: docs/schemas/atlas-tiles.md (spec §4).
 */
import type {
  FilterSpecification,
  Map as MapLibreMap,
  VectorSourceSpecification,
} from 'maplibre-gl';
import { yearToOhmDate } from '@/lib/ohm-date';
import { ohmDateRange } from '@/lib/ohm-layer-date-filter';
import { ENTITY_GROUPS } from '@/types/atlas';
import type { EntityGroup, TimeState } from '@/types/atlas';

/** Our overlay's source id, in both GeoJSON and tile mode. */
export const SOURCE_ID = 'entities';
/** The layer inside each atlas_entities tile. */
export const ENTITY_SOURCE_LAYER = 'entities';
/** Martin's function source name (`tiles.atlas_entities`). */
const TILE_FUNCTION = 'atlas_entities';

/** Territories (fill + outline layers). */
export const isPolygon: FilterSpecification = [
  'match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false,
];
/** Points (the symbol layer). */
export const isPoint: FilterSpecification = [
  'match', ['geometry-type'], ['Point', 'MultiPoint'], true, false,
];

/**
 * The Martin tile root without a trailing slash, or `null` when tile mode is
 * off. Read on each call, not at module load, so tests can stub the env.
 */
export function mapTilesUrl(): string | null {
  const raw = import.meta.env.VITE_MAP_TILES_URL;
  const url = typeof raw === 'string' ? raw.trim().replace(/\/+$/, '') : '';
  return url || null;
}

/** True when the entity overlay comes from vector tiles (D7). */
export function isMapTilesEnabled(): boolean {
  return mapTilesUrl() !== null;
}

/** The vector source for our overlay in tile mode. */
export function entityTileSource(): VectorSourceSpecification {
  return {
    type: 'vector',
    tiles: [`${mapTilesUrl() ?? ''}/${TILE_FUNCTION}/{z}/{x}/{y}`],
    minzoom: 0,
    maxzoom: 14,
  };
}

export interface EntityLayerFilterOptions {
  geometry: 'point' | 'polygon';
  time: TimeState;
  /** Active groups (lowercase); empty or all of them = no group filter. */
  groups: readonly EntityGroup[];
}

/** The OHM-convention input for the timeline position. */
function timeDateInput(time: TimeState) {
  return time.kind === 'instant'
    ? yearToOhmDate(time.year)
    : { start: yearToOhmDate(time.start), end: yearToOhmDate(time.end) };
}

/**
 * The filter for one of our layers in tile mode: geometry type, then the
 * visibility window (`start_decdate` / `end_decdate`, a missing end being
 * open-ended), then the group subset. The same decimal bounds as the OHM
 * layers' filter (`ohmDateRange`).
 */
export function entityLayerFilter({
  geometry,
  time,
  groups,
}: EntityLayerFilterOptions): FilterSpecification {
  const parts: unknown[] = ['all', geometry === 'point' ? isPoint : isPolygon];

  const range = ohmDateRange(timeDateInput(time));
  if (range) {
    parts.push([
      'all',
      ['<=', ['to-number', ['get', 'start_decdate']], range.endDecimalDate],
      [
        'any',
        ['!', ['has', 'end_decdate']],
        ['>=', ['to-number', ['get', 'end_decdate']], range.startDecimalDate],
      ],
    ]);
  }

  if (groups.length > 0 && groups.length < ENTITY_GROUPS.length) {
    parts.push([
      'in',
      ['get', 'entity_group'],
      ['literal', groups.map((g) => g.toUpperCase())],
    ]);
  }

  return parts as FilterSpecification;
}

export interface ApplyEntityLayerFiltersOptions {
  layers: { fill: string; line: string; symbol: string };
  time: TimeState;
  groups: readonly EntityGroup[];
}

/** Filter our fill / line / symbol layers (those present) for tile mode. */
export function applyEntityLayerFilters(
  map: Pick<MapLibreMap, 'getLayer' | 'setFilter'>,
  { layers, time, groups }: ApplyEntityLayerFiltersOptions,
): void {
  const polygon = entityLayerFilter({ geometry: 'polygon', time, groups });
  const point = entityLayerFilter({ geometry: 'point', time, groups });
  const targets: [string, FilterSpecification][] = [
    [layers.fill, polygon],
    [layers.line, polygon],
    [layers.symbol, point],
  ];
  for (const [id, filter] of targets) {
    if (map.getLayer(id)) map.setFilter(id, filter);
  }
}

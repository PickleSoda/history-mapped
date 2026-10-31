import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api/client';
import { ENTITY_SOURCE_LAYER, SOURCE_ID } from './map-tiles';
import { yearToDecdate } from './ohm-date';
import {
  extractIdentity,
  pickFeatureForYear,
  resolveOhmClickToEntity,
} from './ohm-resolve';

vi.mock('@/lib/api/client', () => ({ api: { get: vi.fn() } }));

describe('extractIdentity', () => {
  it('takes the signed osm_id that Martin-served OHM tiles carry', () => {
    expect(extractIdentity({ osm_id: -1880 })).toEqual({ osm_id: -1880 });
    expect(extractIdentity({ osm_id: 42 })).toEqual({ osm_id: 42 });
  });

  it('signs a legacy @id by its type (relation = negative)', () => {
    expect(extractIdentity({ '@id': 'relation/1880' })).toEqual({ osm_id: -1880 });
    expect(extractIdentity({ '@id': 'r1880' })).toEqual({ osm_id: -1880 });
    expect(extractIdentity({ '@id': 'way/7' })).toEqual({ osm_id: 7 });
    expect(extractIdentity({ '@id': 'n9' })).toEqual({ osm_id: 9 });
  });

  it('signs a legacy osm_type + unsigned osm_id pair', () => {
    expect(extractIdentity({ osm_type: 'node', osm_id: 42 })).toEqual({ osm_id: 42 });
    expect(extractIdentity({ osm_type: 'relation', osm_id: 1880 })).toEqual({
      osm_id: -1880,
    });
  });

  it('accepts a numeric string id', () => {
    expect(extractIdentity({ osm_id: '-1880' })).toEqual({ osm_id: -1880 });
  });

  it('returns null without a usable non-zero id', () => {
    expect(extractIdentity({ osm_id: 0 })).toBeNull();
    expect(extractIdentity({})).toBeNull();
    expect(extractIdentity({ osm_id: 1.5 })).toBeNull();
    expect(extractIdentity({ osm_id: 'abc' })).toBeNull();
    expect(extractIdentity({ '@id': 'garbage' })).toBeNull();
  });
});

/** A tile feature living over [startYear, endYear] (end omitted = open). */
function feature(id: string, startYear: number, endYear?: number) {
  const properties: Record<string, unknown> = {
    id,
    start_decdate: yearToDecdate(startYear, 'start'),
  };
  if (endYear !== undefined) properties.end_decdate = yearToDecdate(endYear, 'end');
  return { properties };
}

describe('pickFeatureForYear', () => {
  const early = feature('early', 900, 1000);
  const middle = feature('middle', 1001, 1100);
  const open = feature('open', 1500);

  it('returns the feature whose window contains the year', () => {
    expect(pickFeatureForYear([early, middle, open], 1066)).toBe(middle);
    expect(pickFeatureForYear([early, middle, open], 1000)).toBe(early);
    expect(pickFeatureForYear([early, middle, open], 1001)).toBe(middle);
  });

  it('treats a missing end_decdate as open-ended', () => {
    expect(pickFeatureForYear([early, middle, open], 1900)).toBe(open);
  });

  it('returns null when no window contains the year', () => {
    expect(pickFeatureForYear([early, middle, open], 1200)).toBeNull();
    expect(pickFeatureForYear([early, middle, open], 899)).toBeNull();
    expect(pickFeatureForYear([], 1066)).toBeNull();
  });

  it('tolerates float noise on a window that starts in the year itself', () => {
    // The tile value comes from Postgres; a feature starting this very year
    // must not drop out because the two sides rounded the sum differently.
    const noisy = {
      properties: { id: 'noisy', start_decdate: yearToDecdate(1066, 'start') + 1e-9 },
    };
    expect(pickFeatureForYear([noisy], 1066)).toBe(noisy);
  });
});

describe('resolveOhmClickToEntity', () => {
  const event = { point: { x: 100, y: 100 } } as unknown as MapMouseEvent;
  const get = vi.mocked(api.get);

  /** The OHM polity label under the click (relation 1880). */
  const label = { sourceLayer: 'land_ohm_centroids', properties: { osm_id: -1880 } };

  /** A map stub with one OHM layer, the rendered features under the click, and tile features. */
  function stubMap(
    tileFeatures: { properties: Record<string, unknown> }[],
    rendered: { sourceLayer: string; properties: Record<string, unknown> }[] = [label],
  ) {
    const querySourceFeatures = vi.fn(() => tileFeatures);
    const map = {
      getStyle: () => ({ layers: [{ id: 'ohm-label', type: 'symbol', source: 'ohm' }] }),
      getLayer: () => ({}),
      getSource: (id: string) => (id === SOURCE_ID ? {} : undefined),
      queryRenderedFeatures: () => rendered,
      querySourceFeatures,
    } as unknown as MapLibreMap;
    return { map, querySourceFeatures };
  }

  beforeEach(() => {
    get.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('resolves from the loaded entity tiles without a request', async () => {
    vi.stubEnv('VITE_MAP_TILES_URL', 'http://t/tiles');
    const { map, querySourceFeatures } = stubMap([feature('entity-1', 1000, 1100)]);

    await expect(resolveOhmClickToEntity(map, event, 1066)).resolves.toBe('entity-1');
    expect(querySourceFeatures).toHaveBeenCalledWith(SOURCE_ID, {
      sourceLayer: ENTITY_SOURCE_LAYER,
      filter: ['==', ['get', 'ohm_osm_id'], -1880],
    });
    expect(get).not.toHaveBeenCalled();
  });

  it('asks the resolver by signed osm_id when the tiles have no match', async () => {
    vi.stubEnv('VITE_MAP_TILES_URL', 'http://t/tiles');
    const { map } = stubMap([feature('entity-1', 1500, 1600)]);
    get.mockResolvedValue({ data: { data: { entity: { id: 'entity-2' } } } });

    await expect(resolveOhmClickToEntity(map, event, 1066)).resolves.toBe('entity-2');
    expect(get).toHaveBeenCalledWith('/api/v1/map/resolve-ohm-feature', {
      signal: undefined,
      params: { provider: 'ohm', osm_id: -1880, target_year: 1066 },
    });
  });

  it('skips the tile lookup when tile mode is off', async () => {
    vi.stubEnv('VITE_MAP_TILES_URL', '');
    const { map, querySourceFeatures } = stubMap([feature('entity-1', 1000, 1100)]);
    get.mockRejectedValue(new Error('404'));

    await expect(resolveOhmClickToEntity(map, event, 1066)).resolves.toBeNull();
    expect(querySourceFeatures).not.toHaveBeenCalled();
    expect(get).toHaveBeenCalledTimes(1);
  });

  it('skips boundary-line way ids and tries only the label relation', async () => {
    vi.stubEnv('VITE_MAP_TILES_URL', 'http://t/tiles');
    const line = { sourceLayer: 'land_ohm_lines', properties: { osm_id: 1880 } };
    const { map, querySourceFeatures } = stubMap([], [line, label]);
    get.mockResolvedValue({ data: { data: { entity: { id: 'entity-3' } } } });

    await expect(resolveOhmClickToEntity(map, event, 1066)).resolves.toBe('entity-3');
    expect(querySourceFeatures).toHaveBeenCalledTimes(1);
    expect(querySourceFeatures).toHaveBeenCalledWith(SOURCE_ID, {
      sourceLayer: ENTITY_SOURCE_LAYER,
      filter: ['==', ['get', 'ohm_osm_id'], -1880],
    });
    expect(get).toHaveBeenCalledTimes(1);
    expect(get.mock.calls[0]![1]).toMatchObject({ params: { osm_id: -1880 } });
  });

  it('treats a throwing tile query as a miss instead of rejecting', async () => {
    vi.stubEnv('VITE_MAP_TILES_URL', 'http://t/tiles');
    const { map, querySourceFeatures } = stubMap([]);
    querySourceFeatures.mockImplementation(() => {
      throw new Error('style not loaded');
    });

    await expect(resolveOhmClickToEntity(map, event, 1066)).resolves.toBeNull();
  });
});

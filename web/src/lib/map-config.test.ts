import type { StyleSpecification } from 'maplibre-gl';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LINK_COLOR } from './ohm-highlight';

const OHM_TILES = 'https://vtiles.openhistoricalmap.org/maps/ohm/{z}/{x}/{y}.pbf';
const LINKED = ['boolean', ['feature-state', 'linked'], false];

/** A trimmed OHM house style: two label-point layers and one other symbol layer. */
function rawStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      ohm: { type: 'vector', tiles: [OHM_TILES], maxzoom: 14 },
      ne: { type: 'vector', tiles: ['https://example.test/ne/{z}/{x}/{y}.pbf'] },
    },
    layers: [
      { id: 'background', type: 'background', paint: { 'background-color': '#fff' } },
      {
        id: 'country_labels',
        type: 'symbol',
        source: 'ohm',
        'source-layer': 'land_ohm_centroids',
        layout: { 'text-field': '{name}' },
        paint: { 'text-color': '#495049' },
      },
      {
        id: 'state_labels',
        type: 'symbol',
        source: 'ohm',
        'source-layer': 'land_ohm_centroids',
        layout: { 'text-field': '{name}' },
        paint: { 'text-color': ['interpolate', ['linear'], ['zoom'], 0, '#111', 5, '#222'] },
      },
      {
        id: 'place_labels',
        type: 'symbol',
        source: 'ohm',
        'source-layer': 'place_points_centroids',
        layout: { 'text-field': '{name}' },
        paint: { 'text-color': '#333' },
      },
    ],
  } as StyleSpecification;
}

/** Load the historical basemap from a fresh module whose fetch returns `doc`. */
async function loadWith(doc: StyleSpecification) {
  vi.resetModules();
  const fetchMock = vi.fn(async () => ({ ok: true, json: async () => doc }));
  vi.stubGlobal('fetch', fetchMock);
  const { loadHistoricalBasemapStyle } = await import('./map-config');
  return { load: () => loadHistoricalBasemapStyle('historical'), fetchMock };
}

function textColor(style: StyleSpecification, id: string): unknown {
  const layer = style.layers.find((l) => l.id === id) as { paint?: Record<string, unknown> };
  return layer.paint?.['text-color'];
}

describe('loadHistoricalBasemapStyle normalisation', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('never mutates the cached style document', async () => {
    const doc = rawStyle();
    const pristine = structuredClone(doc);
    const { load, fetchMock } = await loadWith(doc);

    const first = await load();
    const second = await load(); // served from the style cache

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(doc).toEqual(pristine);
    // Normalised once per load, not stacked on the cached copy.
    expect(textColor(second, 'country_labels')).toEqual(textColor(first, 'country_labels'));
    expect(second.sources).toEqual(first.sources);
  });

  it('promotes osm_id to the feature id on OHM label points', async () => {
    const { load } = await loadWith(rawStyle());
    const style = await load();
    expect(style.sources.ohm).toEqual({
      type: 'vector',
      tiles: [OHM_TILES],
      maxzoom: 14,
      promoteId: { land_ohm_centroids: 'osm_id' },
    });
  });

  it('adds the ohm_admin polygon source', async () => {
    const { load } = await loadWith(rawStyle());
    const style = await load();
    expect(style.sources.ohm_admin).toMatchObject({
      type: 'vector',
      tiles: ['https://vtiles.openhistoricalmap.org/maps/ohm_admin/{z}/{x}/{y}.pbf'],
      minzoom: 2,
      maxzoom: 14,
      promoteId: 'osm_id',
    });
    expect((style.sources.ohm_admin as { attribution?: string }).attribution).toContain(
      'OpenHistoricalMap',
    );
    // Other sources are left as they were.
    expect(style.sources.ne).toEqual(rawStyle().sources.ne);
  });

  it('adds no correlation source to a style without the ohm source', async () => {
    const doc = rawStyle();
    delete (doc.sources as Record<string, unknown>).ohm;
    const { load } = await loadWith(doc);
    const style = await load();
    expect(Object.keys(style.sources)).toEqual(['ne']);
  });

  it('paints linked OHM labels in the link colour (plain colour)', async () => {
    const { load } = await loadWith(rawStyle());
    const style = await load();
    expect(textColor(style, 'country_labels')).toEqual(['case', LINKED, LINK_COLOR, '#495049']);
  });

  it('keeps a zoom interpolation top-level and wraps each stop', async () => {
    const { load } = await loadWith(rawStyle());
    const style = await load();
    expect(textColor(style, 'state_labels')).toEqual([
      'interpolate',
      ['linear'],
      ['zoom'],
      0,
      ['case', LINKED, LINK_COLOR, '#111'],
      5,
      ['case', LINKED, LINK_COLOR, '#222'],
    ]);
  });

  it('leaves symbol layers of other source layers alone', async () => {
    const { load } = await loadWith(rawStyle());
    const style = await load();
    expect(textColor(style, 'place_labels')).toBe('#333');
  });
});

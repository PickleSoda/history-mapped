/**
 * The battle-map overlay on the MapLibre map: GeoJSON builders for one frame
 * and the sources/layers that draw them (terrain under everything, then
 * arrows, formations, glyphs and labels, pins, arrowheads, notes).
 */
import type { Feature, FeatureCollection } from 'geojson';
import type {
  ExpressionSpecification,
  FilterSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
} from 'maplibre-gl';
import type { MapStoryDocument, StoryStep } from '@/lib/schemas/map-story';
import { POINT_UNIT_KINDS } from '@/lib/schemas/map-story';
import { bearing, formation } from './geometry';
import type { Frame } from './geometry';
import { arrowId, noteId, pinId, unitGlyphId } from './icons';

export const STORY_SOURCES = {
  terrain: 'story-terrain',
  units: 'story-units',
  points: 'story-unit-points',
  moves: 'story-moves',
  notes: 'story-notes',
  dem: 'story-dem',
  modern: 'story-modern',
} as const;

/** Sources added from remote tiles rather than our GeoJSON. */
const REMOTE_SOURCES: string[] = [STORY_SOURCES.dem, STORY_SOURCES.modern];

/** Layers a pointer can hover/click for unit details. */
export const STORY_INTERACTIVE_LAYERS = ['story-unit-fill', 'story-unit-glyphs', 'story-pins'];

/** Our entity overlay, hidden while a story plays (MapCanvas's layer ids). */
const ENTITY_LAYERS = ['entities-fill', 'entities-line', 'entities-symbols'];

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] };

// Every OHM style shares one glyph server, which serves the OpenHistorical
// family (it has no Open Sans Bold/Italic).
const FONT_BOLD = ['OpenHistorical Bold'];
const FONT_ITALIC = ['OpenHistorical Italic'];

const TERRAIN_FILL: Record<string, [string, number]> = {
  hill: ['#a16207', 0.16],
  woods: ['#166534', 0.26],
  marsh: ['#0f766e', 0.22],
  lake: ['#2563eb', 0.32],
  sea: ['#1d4ed8', 0.22],
  island: ['#78716c', 0.08],
  fortification: ['#57534e', 0.32],
  camp: ['#78716c', 0.2],
  field: ['#ca8a04', 0.12],
};
const TERRAIN_LINE: Record<string, string> = {
  river: '#2563eb',
  stream: '#3b82f6',
  road: '#78716c',
  ridge: '#92400e',
  wall: '#44403c',
  coast: '#1e3a8a',
};

const STATE_OPACITY: Record<string, number> = {
  ready: 0.8,
  engaged: 0.88,
  wavering: 0.6,
  routed: 0.34,
  destroyed: 0.12,
};

const close = <T,>(ring: T[]): T[] => (ring.length && ring[0] !== ring[ring.length - 1] ? [...ring, ring[0]] : ring);

/** Static terrain (rivers, ridges, woods, villages…). */
export function terrainCollection(doc: MapStoryDocument): FeatureCollection {
  const features: Feature[] = [];
  for (const t of doc.terrain) {
    const properties = { kind: t.kind, label: t.label ?? '' };
    if (t.area && t.area.length >= 3) {
      features.push({ type: 'Feature', properties, geometry: { type: 'Polygon', coordinates: [close(t.area)] } });
    } else if (t.line && t.line.length >= 2) {
      features.push({ type: 'Feature', properties, geometry: { type: 'LineString', coordinates: t.line } });
    } else if (t.at) {
      features.push({ type: 'Feature', properties, geometry: { type: 'Point', coordinates: t.at } });
    }
  }
  return { type: 'FeatureCollection', features };
}

/**
 * One frame's units: formation polygons and front edges (units source), and
 * glyph/label points plus marker pins (points source). Units outside `focus`
 * (when a step names some) are dimmed.
 */
export function unitCollections(
  doc: MapStoryDocument,
  frame: Frame,
  focus: string[],
): { units: FeatureCollection; points: FeatureCollection } {
  const sides = new Map(doc.sides.map((s) => [s.id, s]));
  const units = new Map(doc.units.map((u) => [u.id, u]));
  const shapes: Feature[] = [];
  const points: Feature[] = [];
  const focused = new Set(focus);

  for (const [uid, r] of frame) {
    const unit = units.get(uid);
    const side = unit ? sides.get(unit.side) : undefined;
    if (!unit || !side) continue;
    const dim = focused.size > 0 && !focused.has(uid);
    const base = {
      id: uid,
      color: side.color,
      state: r.state,
      opacity: (STATE_OPACITY[r.state] ?? 0.8) * (dim ? 0.5 : 1),
      label: r.label ?? unit.label,
    };

    if (POINT_UNIT_KINDS.includes(unit.kind)) {
      points.push({
        type: 'Feature',
        properties: { ...base, role: 'pin', icon: pinId(unit.kind, side.color) },
        geometry: { type: 'Point', coordinates: r.at },
      });
      continue;
    }

    const { ring, front } = formation(r);
    shapes.push({ type: 'Feature', properties: { ...base, role: 'body' }, geometry: { type: 'Polygon', coordinates: [ring] } });
    shapes.push({ type: 'Feature', properties: { ...base, role: 'front' }, geometry: { type: 'LineString', coordinates: front } });
    points.push({
      type: 'Feature',
      properties: { ...base, role: 'glyph', icon: unitGlyphId(unit.kind) },
      geometry: { type: 'Point', coordinates: r.at },
    });
  }
  return {
    units: { type: 'FeatureCollection', features: shapes },
    points: { type: 'FeatureCollection', features: points },
  };
}

const DASH: Record<string, 'solid' | 'dashed' | 'dotted'> = {
  retreat: 'dashed',
  rout: 'dashed',
  feint: 'dashed',
  march: 'dotted',
  fire: 'dotted',
};

/** A step's movement arrows (lines + arrowheads at their ends). */
export function moveCollection(doc: MapStoryDocument, step: StoryStep | undefined): FeatureCollection {
  const units = new Map(doc.units.map((u) => [u.id, u]));
  const sides = new Map(doc.sides.map((s) => [s.id, s]));
  const features: Feature[] = [];
  for (const mv of step?.moves ?? []) {
    const sideId = mv.side ?? (mv.unit ? units.get(mv.unit)?.side : undefined);
    const color = (sideId && sides.get(sideId)?.color) || '#3f3f46';
    const props = {
      color,
      type: mv.type,
      dash: DASH[mv.type] ?? 'solid',
      weight: mv.type === 'charge' ? 1.6 : mv.type === 'fire' ? 0.55 : 1,
      label: mv.label ?? '',
    };
    features.push({ type: 'Feature', properties: props, geometry: { type: 'LineString', coordinates: mv.path } });
    const end = mv.path[mv.path.length - 1];
    const before = mv.path[mv.path.length - 2];
    features.push({
      type: 'Feature',
      properties: { ...props, icon: arrowId(color), bearing: bearing(before, end) },
      geometry: { type: 'Point', coordinates: end },
    });
  }
  return { type: 'FeatureCollection', features };
}

/** A step's map notes (clash, death, capture… callouts). */
export function noteCollection(step: StoryStep | undefined): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: (step?.notes ?? []).map((n) => ({
      type: 'Feature',
      properties: { text: n.text, kind: n.kind, icon: n.kind === 'label' ? '' : noteId(n.kind) },
      geometry: { type: 'Point', coordinates: n.at },
    })),
  };
}

/** `match` on the feature's `kind` (TS can't type a spread match expression). */
function matchKind(values: Record<string, string | number>, fallback: string | number): ExpressionSpecification {
  return ['match', ['get', 'kind'], ...Object.entries(values).flat(), fallback] as unknown as ExpressionSpecification;
}

/** A value growing with zoom. MapLibre allows `zoom` only in a top-level
 *  interpolate, so per-feature variation goes inside the stops. */
const zoomed = (
  lo: number | ExpressionSpecification,
  hi: number | ExpressionSpecification,
): ExpressionSpecification => ['interpolate', ['linear'], ['zoom'], 9, lo, 15, hi];

/**
 * Add the overlay's sources and layers on top of the current style
 * (idempotent). The hillshade goes under the basemap's labels so terrain
 * reads at battlefield zoom, where the historical styles have no relief.
 */
export function addStoryLayers(map: MapLibreMap): void {
  if (map.getSource(STORY_SOURCES.units)) return;

  if (!map.getSource(STORY_SOURCES.dem)) {
    map.addSource(STORY_SOURCES.dem, {
      type: 'raster-dem',
      tiles: ['https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png'],
      encoding: 'terrarium',
      tileSize: 256,
      maxzoom: 14,
      attribution: 'Terrain: <a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener">AWS Terrain Tiles</a>',
    });
  }
  const firstSymbol = map.getStyle().layers?.find((l) => l.type === 'symbol')?.id;
  map.addLayer(
    {
      id: 'story-hillshade',
      type: 'hillshade',
      source: STORY_SOURCES.dem,
      paint: {
        'hillshade-exaggeration': 0.55,
        'hillshade-shadow-color': '#3f3a2e',
        'hillshade-highlight-color': '#fffdf5',
        'hillshade-accent-color': '#6b5d45',
      },
    },
    firstSymbol,
  );

  // Today's water and village names, faint: the historical styles are blank
  // paper at battlefield zoom, and these are what a reader can find again.
  if (!map.getSource(STORY_SOURCES.modern)) {
    map.addSource(STORY_SOURCES.modern, {
      type: 'vector',
      url: 'https://tiles.openfreemap.org/planet',
      attribution:
        '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
    });
  }
  map.addLayer({
    id: 'story-modern-water',
    type: 'fill',
    source: STORY_SOURCES.modern,
    'source-layer': 'water',
    minzoom: 9,
    // Inland water only: the basemaps draw the sea themselves.
    filter: ['!=', ['get', 'class'], 'ocean'],
    paint: { 'fill-color': '#9fc0dc', 'fill-opacity': 0.55 },
  });
  map.addLayer({
    id: 'story-modern-waterway',
    type: 'line',
    source: STORY_SOURCES.modern,
    'source-layer': 'waterway',
    minzoom: 9,
    filter: ['in', ['get', 'class'], ['literal', ['river', 'stream', 'canal']]],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#7fa7cc',
      'line-opacity': 0.8,
      'line-width': zoomed(
        ['match', ['get', 'class'], 'river', 1.2, 0.6],
        ['match', ['get', 'class'], 'river', 3.5, 1.6],
      ),
    },
  });
  map.addLayer({
    id: 'story-modern-places',
    type: 'symbol',
    source: STORY_SOURCES.modern,
    'source-layer': 'place',
    minzoom: 10,
    filter: ['in', ['get', 'class'], ['literal', ['city', 'town', 'village', 'hamlet']]],
    layout: {
      'text-field': ['coalesce', ['get', 'name:en'], ['get', 'name']],
      'text-font': FONT_ITALIC,
      'text-size': ['match', ['get', 'class'], 'city', 13, 'town', 12, 11],
      'text-optional': true,
    },
    paint: { 'text-color': '#7a7064', 'text-halo-color': 'rgba(250,247,240,0.85)', 'text-halo-width': 1.2 },
  });

  for (const id of Object.values(STORY_SOURCES)) {
    if (!REMOTE_SOURCES.includes(id) && !map.getSource(id)) map.addSource(id, { type: 'geojson', data: EMPTY });
  }

  const isArea: FilterSpecification = ['==', ['geometry-type'], 'Polygon'];
  const isLine: FilterSpecification = ['==', ['geometry-type'], 'LineString'];
  const isPoint: FilterSpecification = ['==', ['geometry-type'], 'Point'];
  const fillColor = matchKind(Object.fromEntries(Object.entries(TERRAIN_FILL).map(([k, [c]]) => [k, c])), '#a8a29e');
  const fillOpacity = matchKind(Object.fromEntries(Object.entries(TERRAIN_FILL).map(([k, [, o]]) => [k, o])), 0.12);
  const lineColor = matchKind(TERRAIN_LINE, '#57534e');

  // ── terrain ──
  map.addLayer({ id: 'story-terrain-fill', type: 'fill', source: STORY_SOURCES.terrain, filter: isArea, paint: { 'fill-color': fillColor, 'fill-opacity': fillOpacity } });
  map.addLayer({ id: 'story-terrain-edge', type: 'line', source: STORY_SOURCES.terrain, filter: isArea, paint: { 'line-color': fillColor, 'line-opacity': 0.55, 'line-width': 1, 'line-dasharray': [3, 2] } });
  map.addLayer({
    id: 'story-terrain-line',
    type: 'line',
    source: STORY_SOURCES.terrain,
    filter: ['all', isLine, ['!=', ['get', 'kind'], 'road']],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': lineColor,
      'line-opacity': 0.85,
      'line-width': zoomed(
        ['match', ['get', 'kind'], 'river', 2, 'ridge', 1.5, 1],
        ['match', ['get', 'kind'], 'river', 5, 'ridge', 3.5, 2.5],
      ),
    },
  });
  map.addLayer({
    id: 'story-terrain-road',
    type: 'line',
    source: STORY_SOURCES.terrain,
    filter: ['all', isLine, ['==', ['get', 'kind'], 'road']],
    paint: { 'line-color': lineColor, 'line-opacity': 0.8, 'line-width': zoomed(1, 2.5), 'line-dasharray': [4, 2] },
  });
  map.addLayer({
    id: 'story-terrain-dot',
    type: 'circle',
    source: STORY_SOURCES.terrain,
    filter: isPoint,
    paint: { 'circle-radius': 3.5, 'circle-color': '#fffdf7', 'circle-stroke-color': '#292524', 'circle-stroke-width': 1.5 },
  });
  // Labels: along rivers, roads and ridges; beside villages; inside areas.
  const labelPaint = { 'text-color': '#3f2d14', 'text-halo-color': 'rgba(255,253,245,0.92)', 'text-halo-width': 1.6 };
  map.addLayer({
    id: 'story-terrain-label-line',
    type: 'symbol',
    source: STORY_SOURCES.terrain,
    filter: isLine,
    layout: {
      'text-field': ['get', 'label'],
      'text-size': 12,
      'text-font': FONT_ITALIC,
      'symbol-placement': 'line',
      'text-optional': true,
    },
    paint: labelPaint,
  });
  map.addLayer({
    id: 'story-terrain-label',
    type: 'symbol',
    source: STORY_SOURCES.terrain,
    filter: ['!', isLine],
    layout: {
      'text-field': ['get', 'label'],
      'text-size': 12,
      'text-font': FONT_ITALIC,
      'text-offset': ['match', ['geometry-type'], 'Point', ['literal', [0.6, 0]], ['literal', [0, 0]]],
      'text-anchor': ['match', ['geometry-type'], 'Point', 'left', 'center'],
      'text-max-width': 9,
      'text-optional': true,
    },
    paint: labelPaint,
  });

  // ── formations ──
  map.addLayer({
    id: 'story-unit-fill',
    type: 'fill',
    source: STORY_SOURCES.units,
    filter: isArea,
    paint: { 'fill-color': ['get', 'color'], 'fill-opacity': ['get', 'opacity'] },
  });
  map.addLayer({
    id: 'story-unit-outline',
    type: 'line',
    source: STORY_SOURCES.units,
    filter: isArea,
    paint: {
      'line-color': '#1c1917',
      'line-opacity': ['case', ['in', ['get', 'state'], ['literal', ['routed', 'destroyed']]], 0.45, 0.8],
      'line-width': ['case', ['==', ['get', 'state'], 'engaged'], 1.8, 1],
    },
  });
  map.addLayer({
    id: 'story-unit-front',
    type: 'line',
    source: STORY_SOURCES.units,
    filter: ['all', isLine, ['!', ['in', ['get', 'state'], ['literal', ['routed', 'destroyed']]]]],
    layout: { 'line-cap': 'round' },
    paint: { 'line-color': '#1c1917', 'line-opacity': 0.85, 'line-width': ['case', ['==', ['get', 'state'], 'engaged'], 3.2, 2.2] },
  });
  // ── movement arrows, over the blocks (a unit often moves along its own arrow) ──
  // A pale casing keeps an arrow readable over a block of its own colour.
  map.addLayer({
    id: 'story-move-casing',
    type: 'line',
    source: STORY_SOURCES.moves,
    filter: ['all', isLine, ['==', ['get', 'dash'], 'solid']],
    layout: { 'line-cap': 'butt', 'line-join': 'round' },
    paint: {
      'line-color': '#fffdf5',
      'line-opacity': 0.75,
      'line-width': zoomed(['+', ['*', ['get', 'weight'], 2.5], 2.5], ['+', ['*', ['get', 'weight'], 6], 3.5]),
    },
  });
  for (const dash of ['solid', 'dashed', 'dotted'] as const) {
    map.addLayer({
      id: `story-move-${dash}`,
      type: 'line',
      source: STORY_SOURCES.moves,
      filter: ['all', isLine, ['==', ['get', 'dash'], dash]],
      layout: { 'line-cap': dash === 'dotted' ? 'round' : 'butt', 'line-join': 'round' },
      paint: {
        'line-color': ['get', 'color'],
        'line-opacity': 0.9,
        'line-width': zoomed(['*', ['get', 'weight'], 2.5], ['*', ['get', 'weight'], 6]),
        ...(dash === 'solid' ? {} : { 'line-dasharray': dash === 'dashed' ? [2.2, 1.6] : [0.1, 1.8] }),
      },
    });
  }

  map.addLayer({
    id: 'story-unit-glyphs',
    type: 'symbol',
    source: STORY_SOURCES.points,
    filter: ['==', ['get', 'role'], 'glyph'],
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-size': zoomed(0.5, 0.85),
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      'text-field': ['get', 'label'],
      'text-size': 11.5,
      'text-font': FONT_BOLD,
      'text-offset': [0, 1.15],
      'text-anchor': 'top',
      'text-max-width': 10,
      'text-optional': true,
    },
    paint: {
      'icon-opacity': ['min', 1, ['+', ['get', 'opacity'], 0.25]],
      'text-color': '#1c1917',
      'text-halo-color': 'rgba(255,253,245,0.95)',
      'text-halo-width': 1.6,
      'text-opacity': ['min', 1, ['+', ['get', 'opacity'], 0.3]],
    },
  });
  map.addLayer({
    id: 'story-pins',
    type: 'symbol',
    source: STORY_SOURCES.points,
    filter: ['==', ['get', 'role'], 'pin'],
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-size': zoomed(0.6, 0.9),
      'icon-allow-overlap': true,
      'text-field': ['get', 'label'],
      'text-size': 11.5,
      'text-font': FONT_BOLD,
      'text-offset': [1.1, 0],
      'text-anchor': 'left',
      'text-optional': true,
    },
    paint: { 'text-color': '#1c1917', 'text-halo-color': 'rgba(255,253,245,0.95)', 'text-halo-width': 1.6 },
  });

  // ── arrowheads and notes on top ──
  map.addLayer({
    id: 'story-move-heads',
    type: 'symbol',
    source: STORY_SOURCES.moves,
    filter: isPoint,
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-size': zoomed(
        ['*', ['max', 0.8, ['get', 'weight']], 0.7],
        ['*', ['max', 0.8, ['get', 'weight']], 1.15],
      ),
      'icon-rotate': ['get', 'bearing'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
  });
  map.addLayer({
    id: 'story-notes',
    type: 'symbol',
    source: STORY_SOURCES.notes,
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-size': 0.7,
      'icon-allow-overlap': true,
      'text-field': ['get', 'text'],
      'text-size': 12,
      'text-font': FONT_BOLD,
      'text-offset': [0, -1.4],
      'text-anchor': 'bottom',
      'text-max-width': 14,
    },
    paint: { 'text-color': '#7c2d12', 'text-halo-color': 'rgba(255,251,235,0.97)', 'text-halo-width': 2 },
  });
}

export function removeStoryLayers(map: MapLibreMap): void {
  for (const layer of map.getStyle()?.layers ?? []) {
    if (layer.id.startsWith('story-')) map.removeLayer(layer.id);
  }
  for (const id of Object.values(STORY_SOURCES)) {
    if (map.getSource(id)) map.removeSource(id);
  }
}

/** Hide (or restore) the atlas's own entity pins and territories. */
export function setEntityLayersVisible(map: MapLibreMap, visible: boolean): void {
  for (const id of ENTITY_LAYERS) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
  }
}

export function setSourceData(map: MapLibreMap, id: string, data: FeatureCollection): void {
  (map.getSource(id) as GeoJSONSource | undefined)?.setData(data);
}

/** Fade the arrows in as a step's movement starts. */
export function setMoveOpacity(map: MapLibreMap, opacity: number): void {
  for (const id of ['story-move-solid', 'story-move-dashed', 'story-move-dotted']) {
    if (map.getLayer(id)) map.setPaintProperty(id, 'line-opacity', 0.9 * opacity);
  }
  if (map.getLayer('story-move-casing')) map.setPaintProperty('story-move-casing', 'line-opacity', 0.75 * opacity);
  if (map.getLayer('story-move-heads')) map.setPaintProperty('story-move-heads', 'icon-opacity', opacity);
}

/**
 * The chronicle player's step layer on the MapLibre map: sources, layers and
 * the paint changes that animate them. What goes in them is `scene.ts`.
 *
 * Bottom to top: the step's OpenHistoricalMap borders (under the basemap's
 * labels), the trail of earlier steps, spokes, the relationship's arc (a
 * white casing and a gradient line that grows from its source, then a glow
 * that travels along it), its arrowhead, the ripple at the step's anchor,
 * rings under the step's entities, the trail's numbered stops and the step's
 * entities with their labels. While a step shows, the atlas's own markers fade
 * and those of the step's entities hide (theirs are drawn here, on top).
 */
import type { Feature, FeatureCollection } from 'geojson';
import type { ExpressionSpecification, GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl';
import { yearToOhmDate } from '@/lib/ohm-date';
import { adminLayersBeforeId, OHM_ADMIN_LAYER, OHM_ADMIN_SOURCE } from '@/lib/ohm-highlight';
import { ohmDateFilter } from '@/lib/ohm-layer-date-filter';
import type { StepScene } from './scene';

export const CHRONICLE_SOURCES = {
  trail: 'chron-trail',
  spokes: 'chron-spokes',
  arc: 'chron-arc',
  points: 'chron-points',
  /** Our own OHM boundary tiles, for a style without its `ohm_admin` source. */
  ohmAdmin: 'chron-ohm-admin',
} as const;

/** Layers whose features open something on a click (a step, an entity). */
export const CHRONICLE_INTERACTIVE_LAYERS = ['chron-trail-stop', 'chron-cast'];

const LAYERS = [
  'chron-trail-line',
  'chron-spokes',
  'chron-arc-casing',
  'chron-arc',
  'chron-arc-dashed',
  'chron-pulse',
  'chron-ring',
  'chron-arrow',
  'chron-trail-stop',
  'chron-trail-label',
  'chron-cast',
];
const AREA_LAYERS = ['chron-area-fill', 'chron-area-line'];

const ARROW_IMAGE = 'chron-arrow';
const FONT_BOLD = ['OpenHistorical Bold'];
const TRAIL_COLOR = '#44403c';
const OTHER_COLOR = '#78716c';
const TRANSPARENT = 'rgba(0,0,0,0)';
const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] };
const OHM_ADMIN_TILES = 'https://vtiles.openhistoricalmap.org/maps/ohm_admin/{z}/{x}/{y}.pbf';

/** The atlas's own layers (MapCanvas) that fade while a step shows. */
const ENTITY_SYMBOLS = 'entities-symbols';
const ENTITY_FILL = 'entities-fill';
const ENTITY_LINE = 'entities-line';

const role = (r: string): ExpressionSpecification => ['==', ['get', 'role'], r];
/** An arc fully drawn, plain. */
const FULL = { soft: false, grown: 1, glowAt: null };

/** An upward triangle, white, as an SDF image (tinted per feature with `icon-color`). */
function registerArrow(map: MapLibreMap): void {
  if (map.hasImage(ARROW_IMAGE)) return;
  const size = 32;
  const el = document.createElement('canvas');
  el.width = el.height = size;
  const ctx = el.getContext('2d');
  if (!ctx) return;
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.moveTo(size / 2, 3);
  ctx.lineTo(size - 5, size - 5);
  ctx.lineTo(size / 2, size - 11);
  ctx.lineTo(5, size - 5);
  ctx.closePath();
  ctx.fill();
  map.addImage(ARROW_IMAGE, ctx.getImageData(0, 0, size, size), { sdf: true, pixelRatio: 2 });
}

/** Add the step layer's sources and layers on top of the style (idempotent). */
export function addChronicleLayers(map: MapLibreMap): void {
  if (map.getSource(CHRONICLE_SOURCES.points)) return;
  registerArrow(map);
  for (const id of [CHRONICLE_SOURCES.trail, CHRONICLE_SOURCES.spokes, CHRONICLE_SOURCES.points]) {
    map.addSource(id, { type: 'geojson', data: EMPTY });
  }
  // line-progress (the arc's growth and glow) needs line metrics.
  map.addSource(CHRONICLE_SOURCES.arc, { type: 'geojson', data: EMPTY, lineMetrics: true });

  map.addLayer({
    id: 'chron-trail-line',
    type: 'line',
    source: CHRONICLE_SOURCES.trail,
    filter: role('segment'),
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': TRAIL_COLOR,
      'line-width': 2,
      'line-dasharray': [0.6, 2],
      'line-opacity': ['interpolate', ['linear'], ['get', 'age'], 0, 0.8, 10, 0.25],
    },
  });
  map.addLayer({
    id: 'chron-spokes',
    type: 'line',
    source: CHRONICLE_SOURCES.spokes,
    layout: { 'line-cap': 'round' },
    paint: { 'line-color': OTHER_COLOR, 'line-width': 1.4, 'line-dasharray': [2, 2], 'line-opacity': 0.55 },
  });
  const solid: ExpressionSpecification = ['!=', ['get', 'dashed'], true];
  map.addLayer({
    id: 'chron-arc-casing',
    type: 'line',
    source: CHRONICLE_SOURCES.arc,
    filter: solid,
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-width': 7, 'line-opacity': 0.85, 'line-gradient': arcGradient(OTHER_COLOR, FULL, true) },
  });
  map.addLayer({
    id: 'chron-arc',
    type: 'line',
    source: CHRONICLE_SOURCES.arc,
    filter: solid,
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-width': 3.5, 'line-gradient': arcGradient(OTHER_COLOR, FULL) },
  });
  map.addLayer({
    id: 'chron-arc-dashed',
    type: 'line',
    source: CHRONICLE_SOURCES.arc,
    filter: ['==', ['get', 'dashed'], true],
    layout: { 'line-join': 'round' },
    paint: { 'line-color': ['get', 'color'], 'line-width': 3, 'line-dasharray': [1.6, 1.2], 'line-opacity': 0.9 },
  });
  map.addLayer({
    id: 'chron-pulse',
    type: 'circle',
    source: CHRONICLE_SOURCES.points,
    filter: role('pulse'),
    paint: {
      'circle-color': ['get', 'color'],
      'circle-radius': 14,
      'circle-opacity': 0.12,
      'circle-stroke-color': ['get', 'color'],
      'circle-stroke-width': 2,
      'circle-stroke-opacity': 0.5,
      'circle-pitch-alignment': 'map',
    },
  });
  map.addLayer({
    id: 'chron-ring',
    type: 'circle',
    source: CHRONICLE_SOURCES.points,
    filter: role('cast'),
    paint: {
      'circle-color': ['get', 'color'],
      'circle-radius': ['case', ['get', 'primary'], 9, 6],
      'circle-opacity': ['case', ['get', 'primary'], 0.22, 0.14],
      'circle-stroke-color': ['get', 'color'],
      'circle-stroke-width': ['case', ['get', 'primary'], 2, 1.2],
      'circle-stroke-opacity': 0.85,
      'circle-pitch-alignment': 'map',
    },
  });
  map.addLayer({
    id: 'chron-arrow',
    type: 'symbol',
    source: CHRONICLE_SOURCES.points,
    filter: role('arrow'),
    layout: {
      'icon-image': ARROW_IMAGE,
      'icon-size': 1,
      'icon-rotate': ['get', 'bearing'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
    paint: { 'icon-color': ['get', 'color'], 'icon-halo-color': '#ffffff', 'icon-halo-width': 1.5, 'icon-opacity': 1 },
  });
  map.addLayer({
    id: 'chron-trail-stop',
    type: 'circle',
    source: CHRONICLE_SOURCES.trail,
    filter: role('stop'),
    paint: {
      'circle-radius': 8,
      'circle-color': '#fffdf7',
      'circle-stroke-color': TRAIL_COLOR,
      'circle-stroke-width': 1.5,
      'circle-opacity': ['interpolate', ['linear'], ['get', 'age'], 1, 0.95, 12, 0.55],
      'circle-stroke-opacity': ['interpolate', ['linear'], ['get', 'age'], 1, 0.95, 12, 0.45],
    },
  });
  map.addLayer({
    id: 'chron-trail-label',
    type: 'symbol',
    source: CHRONICLE_SOURCES.trail,
    filter: role('stop'),
    layout: {
      'text-field': ['get', 'label'],
      'text-font': FONT_BOLD,
      'text-size': 10,
      'text-allow-overlap': true,
      'text-ignore-placement': true,
    },
    paint: { 'text-color': TRAIL_COLOR },
  });
  map.addLayer({
    id: 'chron-cast',
    type: 'symbol',
    source: CHRONICLE_SOURCES.points,
    filter: role('cast'),
    layout: {
      'icon-image': ['coalesce', ['image', ['concat', 'marker-', ['get', 'group']]], ['image', 'marker-DEFAULT']],
      'icon-size': ['case', ['get', 'primary'], 1.05, 0.85],
      'icon-anchor': 'bottom',
      'icon-allow-overlap': true,
      'symbol-sort-key': ['case', ['get', 'primary'], 0, 1],
      'text-field': ['get', 'name'],
      'text-font': FONT_BOLD,
      'text-size': ['case', ['get', 'primary'], 12.5, 11],
      'text-anchor': 'top',
      'text-offset': [0, 0.5],
      'text-max-width': 9,
      'text-optional': true,
    },
    paint: {
      'text-color': '#1c1917',
      'text-halo-color': 'rgba(255,253,247,0.95)',
      'text-halo-width': 1.8,
    },
  });
}

/** Remove the step layer, its borders and its sources. */
export function removeChronicleLayers(map: MapLibreMap): void {
  for (const id of [...LAYERS, ...AREA_LAYERS]) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of Object.values(CHRONICLE_SOURCES)) if (map.getSource(id)) map.removeSource(id);
}

const setData = (map: MapLibreMap, id: string, data: FeatureCollection) =>
  (map.getSource(id) as GeoJSONSource | undefined)?.setData(data);

/** Draw `scene` (null: nothing) and the trail. */
export function setChronicleData(map: MapLibreMap, scene: StepScene | null, trail: FeatureCollection): void {
  setData(map, CHRONICLE_SOURCES.trail, trail);
  setData(map, CHRONICLE_SOURCES.spokes, { type: 'FeatureCollection', features: scene?.spokes ?? [] });
  setData(map, CHRONICLE_SOURCES.arc, { type: 'FeatureCollection', features: scene?.arc ? [scene.arc] : [] });
  const points: Feature[] = [];
  if (scene) {
    if (scene.anchor) {
      points.push({ type: 'Feature', properties: { role: 'pulse', color: scene.color }, geometry: { type: 'Point', coordinates: scene.anchor } });
    }
    for (const m of scene.cast) {
      points.push({
        type: 'Feature',
        properties: { role: 'cast', id: m.id, name: m.name, group: m.group, primary: m.primary, color: m.primary ? scene.color : OTHER_COLOR },
        geometry: { type: 'Point', coordinates: m.at },
      });
    }
    if (scene.arrow) {
      points.push({
        type: 'Feature',
        properties: { role: 'arrow', color: scene.color, bearing: scene.arrow.bearing },
        geometry: { type: 'Point', coordinates: scene.arrow.at },
      });
    }
  }
  setData(map, CHRONICLE_SOURCES.points, { type: 'FeatureCollection', features: points });
}

// ── the step's borders ────────────────────────────────────────────────────────

/**
 * Outline the step's OpenHistoricalMap boundaries as they stood in `year`:
 * the relationship's ends in the step's colour, the others in grey. With
 * none (or no year), remove the layers, and our tile source, whose tiles are
 * heavy (about 1.3 MB at z5).
 */
export function setChronicleAreas(
  map: MapLibreMap,
  areas: { primary: number[]; other: number[] } | null,
  year: number | null,
  color: string,
): void {
  const ids = areas ? [...areas.primary, ...areas.other] : [];
  const osmId: ExpressionSpecification = ['to-number', ['get', 'osm_id']];
  const filter = ids.length && year != null ? ohmDateFilter(yearToOhmDate(year), ['in', osmId, ['literal', ids]], { includeUndated: true }) : null;
  if (!filter || !areas) {
    for (const id of AREA_LAYERS) if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource(CHRONICLE_SOURCES.ohmAdmin)) map.removeSource(CHRONICLE_SOURCES.ohmAdmin);
    return;
  }
  const primary: ExpressionSpecification = ['in', osmId, ['literal', areas.primary]];
  const tint: ExpressionSpecification = ['case', primary, color, OTHER_COLOR];
  if (!map.getLayer(AREA_LAYERS[0])) {
    let source: string = OHM_ADMIN_SOURCE;
    if (!map.getSource(source)) {
      source = CHRONICLE_SOURCES.ohmAdmin;
      if (!map.getSource(source)) map.addSource(source, { type: 'vector', tiles: [OHM_ADMIN_TILES], minzoom: 0, maxzoom: 14 });
    }
    // Under the basemap's labels, like the atlas's own border highlight.
    const before = adminLayersBeforeId(map, ENTITY_FILL);
    const common = { source, 'source-layer': OHM_ADMIN_LAYER, filter } as const;
    map.addLayer({ id: AREA_LAYERS[0], type: 'fill', ...common, paint: { 'fill-color': tint, 'fill-opacity': ['case', primary, 0.14, 0.06] } }, before);
    map.addLayer(
      {
        id: AREA_LAYERS[1],
        type: 'line',
        ...common,
        layout: { 'line-join': 'round' },
        paint: { 'line-color': tint, 'line-opacity': 0.85, 'line-width': ['case', primary, 2, 1.1], 'line-dasharray': [3, 1.5] },
      },
      before,
    );
    return;
  }
  for (const id of AREA_LAYERS) map.setFilter(id, filter);
  map.setPaintProperty(AREA_LAYERS[0], 'fill-color', tint);
  map.setPaintProperty(AREA_LAYERS[0], 'fill-opacity', ['case', primary, 0.14, 0.06]);
  map.setPaintProperty(AREA_LAYERS[1], 'line-color', tint);
  map.setPaintProperty(AREA_LAYERS[1], 'line-width', ['case', primary, 2, 1.1]);
}

// ── the atlas's own markers, faded ───────────────────────────────────────────

const FADED: [string, string][] = [
  [ENTITY_SYMBOLS, 'icon-opacity'],
  [ENTITY_SYMBOLS, 'text-opacity'],
  [ENTITY_FILL, 'fill-opacity'],
  [ENTITY_LINE, 'line-opacity'],
];
/** Paint values before the fade, per map (a rebuilt style starts afresh). */
const ORIGINAL = new WeakMap<MapLibreMap, Map<string, unknown>>();

/**
 * Fade the atlas's markers while a step shows, hiding those of the step's own
 * entities (`castIds`, drawn by the step layer); null restores them. Paint
 * only: a filter change would reload the entity source.
 */
export function fadeEntityLayers(map: MapLibreMap, castIds: string[] | null): void {
  let saved = ORIGINAL.get(map);
  if (castIds === null) {
    if (!saved) return;
    for (const [layer, prop] of FADED) {
      // `null` puts a property back to the style default.
      if (map.getLayer(layer)) map.setPaintProperty(layer, prop, saved.get(`${layer}|${prop}`) ?? null);
    }
    ORIGINAL.delete(map);
    return;
  }
  if (!saved) {
    saved = new Map();
    for (const [layer, prop] of FADED) if (map.getLayer(layer)) saved.set(`${layer}|${prop}`, map.getPaintProperty(layer, prop));
    ORIGINAL.set(map, saved);
  }
  const mine: ExpressionSpecification = ['in', ['get', 'id'], ['literal', castIds]];
  const values: Record<string, unknown> = {
    'icon-opacity': ['case', mine, 0, 0.28],
    'text-opacity': ['case', mine, 0, 0.35],
    'fill-opacity': 0.05,
    'line-opacity': 0.35,
  };
  for (const [layer, prop] of FADED) if (map.getLayer(layer)) map.setPaintProperty(layer, prop, values[prop]);
}

/** Forget the saved paint (the style was rebuilt: its layers start at their defaults). */
export function forgetFade(map: MapLibreMap): void {
  ORIGINAL.delete(map);
}

// ── animation ─────────────────────────────────────────────────────────────────

/** The share of a soft arc (one from a polity) over which it fades in. */
const SOFT_SPAN = 0.35;
/** Half the width of the travelling glow, as a share of the arc. */
const GLOW_HALF = 0.12;

const rgbOf = (hex: string): [number, number, number] => {
  const n = Number.parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

export interface ArcLook {
  /** Fade in from the start (an arc from a polity). */
  soft: boolean;
  /** Grown to this share (0–1) of its length; transparent beyond. */
  grown: number;
  /** The centre (0–1) of a lighter band, or null for none. */
  glowAt: number | null;
}

/**
 * The arc's `line-gradient`: `color` (white for the casing) along the line,
 * faded at a soft start, cut where it has grown to, lightened around the
 * glow. Built by sampling the look at the points where it changes, so any mix
 * of the three stays a valid, ascending `interpolate`.
 */
export function arcGradient(color: string, look: ArcLook, casing = false): ExpressionSpecification {
  const [r, g, b] = rgbOf(casing ? '#ffffff' : color);
  const grown = Math.min(1, Math.max(0.001, look.grown));
  const keys = new Set<number>([0, 1]);
  for (let i = 1; i < 10; i++) keys.add(i / 10);
  if (look.soft) keys.add(SOFT_SPAN);
  if (grown < 1) {
    keys.add(grown);
    keys.add(Math.min(1, grown + 0.002));
  }
  if (look.glowAt != null && !casing) {
    for (const k of [look.glowAt - GLOW_HALF, look.glowAt, look.glowAt + GLOW_HALF]) if (k > 0 && k < 1) keys.add(k);
  }
  const stops: (number | string)[] = [];
  for (const x of [...keys].sort((m, n) => m - n)) {
    if (x > grown) {
      stops.push(x, TRANSPARENT);
      continue;
    }
    const alpha = look.soft ? Math.min(1, 0.08 + (0.92 * x) / SOFT_SPAN) : 1;
    const light = look.glowAt != null && !casing ? 0.55 * Math.max(0, 1 - Math.abs(x - look.glowAt) / GLOW_HALF) : 0;
    const mix = (c: number) => Math.round(c + (255 - c) * light);
    stops.push(x, `rgba(${mix(r)},${mix(g)},${mix(b)},${alpha.toFixed(3)})`);
  }
  return ['interpolate', ['linear'], ['line-progress'], ...stops] as unknown as ExpressionSpecification;
}

/** The arc grown to `p` (0–1) of its length; the spokes and the arrowhead fade in with it. */
export function setReveal(map: MapLibreMap, color: string, grown: number, soft = false): void {
  const p = Math.min(1, Math.max(0, grown));
  const look: ArcLook = { soft, grown: p, glowAt: null };
  if (map.getLayer('chron-arc')) map.setPaintProperty('chron-arc', 'line-gradient', arcGradient(color, look));
  if (map.getLayer('chron-arc-casing')) map.setPaintProperty('chron-arc-casing', 'line-gradient', arcGradient(color, look, true));
  if (map.getLayer('chron-arc-dashed')) map.setPaintProperty('chron-arc-dashed', 'line-opacity', 0.9 * p);
  if (map.getLayer('chron-spokes')) map.setPaintProperty('chron-spokes', 'line-opacity', 0.55 * p);
  if (map.getLayer('chron-arrow')) map.setPaintProperty('chron-arrow', 'icon-opacity', p >= 1 ? 1 : 0);
}

/** The glow at `phase` (0–1) along the grown arc. */
export function setGlow(map: MapLibreMap, color: string, phase: number, soft = false): void {
  if (!map.getLayer('chron-arc')) return;
  map.setPaintProperty('chron-arc', 'line-gradient', arcGradient(color, { soft, grown: 1, glowAt: phase }));
}

/** The anchor's ripple at `phase` (0–1): it widens and fades. */
export function setPulse(map: MapLibreMap, phase: number): void {
  if (!map.getLayer('chron-pulse')) return;
  map.setPaintProperty('chron-pulse', 'circle-radius', 7 + 22 * phase);
  map.setPaintProperty('chron-pulse', 'circle-opacity', 0.28 * (1 - phase));
  map.setPaintProperty('chron-pulse', 'circle-stroke-opacity', 0.85 * (1 - phase));
}

import type { LayerSpecification, Map as MapLibreMap } from 'maplibre-gl';
import { mix } from '@/lib/era/color';
import { textureImage } from '@/lib/era/textures';
import type { EraTheme } from '@/lib/era/types';

/**
 * The era's look on the map, applied on top of whichever OHM basemap is
 * loaded, without touching the style loader: border paint (colour, width,
 * dashes) on OHM's admin lines, plus three layers of our own: a sea wash, a
 * land wash and a land texture. Each call first restores everything the last
 * call changed, so switching eras (or turning them off) never compounds.
 * After a basemap switch the new style starts clean; call again.
 */
export const ERA_SEA_LAYER = 'era-sea-tint';
export const ERA_LAND_LAYER = 'era-land-tint';
export const ERA_TEXTURE_LAYER = 'era-land-texture';
export const ERA_TEXTURE_IMAGE = 'era-texture';
const OWN_LAYERS = [ERA_SEA_LAYER, ERA_LAND_LAYER, ERA_TEXTURE_LAYER];

const BORDER_SOURCE_LAYER = 'land_ohm_lines';
/**
 * A border the basemap draws with a line-pattern (woodblock's soft, splotchy
 * stroke) is several pixels wide; drawn in a solid colour it needs to be much
 * thinner to read as a line.
 */
export const PATTERNED_WIDTH = 0.35;
const LAND_SOURCE_LAYER = 'land';

export type BorderRole = 'country' | 'case' | 'other';

type Paint = Record<string, unknown>;
type Layer = LayerSpecification & { source?: string; 'source-layer'?: string; filter?: unknown };

interface StyleState {
  /** Paint values from before our overrides, per layer. */
  originals: Map<string, Paint>;
  /** The texture currently registered as ERA_TEXTURE_IMAGE. */
  imageKey: string | null;
}

/** Keyed by MapLibre's style object, so a new style starts with no state. */
const states = new WeakMap<object, StyleState>();

function stateFor(map: MapLibreMap): StyleState | null {
  const style = (map as unknown as { style?: object }).style;
  if (!style) return null;
  let state = states.get(style);
  if (!state) {
    state = { originals: new Map(), imageKey: null };
    states.set(style, state);
  }
  return state;
}

/** Which kind of OHM boundary line a layer draws, or null for any other layer. */
export function borderRole(layer: Layer): BorderRole | null {
  if (layer.type !== 'line' || layer['source-layer'] !== BORDER_SOURCE_LAYER) return null;
  if (/case/i.test(layer.id)) return 'case';
  const filter = JSON.stringify(layer.filter ?? null);
  const country =
    /country/i.test(layer.id) ||
    /\["get","admin_level"\],\["literal",\[1,2\]\]/.test(filter) ||
    /\["get","admin_level"\],[12]\]/.test(filter) ||
    /"admin_level",[12]\]/.test(filter);
  return country ? 'country' : 'other';
}

/**
 * A line width times `k`: a number, a zoom `interpolate`/`step` expression
 * (each output scaled, since a zoom expression must stay top-level) or a
 * legacy `{stops}` function. Anything else is returned unchanged.
 */
export function scaleWidth(value: unknown, k: number): unknown {
  if (typeof value === 'number') return value * k;
  if (Array.isArray(value) && value[0] === 'interpolate') {
    return value.map((v, i) => (i >= 4 && i % 2 === 0 && typeof v === 'number' ? v * k : v));
  }
  if (Array.isArray(value) && value[0] === 'step') {
    return value.map((v, i) => (i >= 2 && i % 2 === 0 && typeof v === 'number' ? v * k : v));
  }
  if (value && typeof value === 'object' && 'stops' in value) {
    const fn = value as { stops: [number, number][] };
    return { ...fn, stops: fn.stops.map(([z, v]) => [z, typeof v === 'number' ? v * k : v]) };
  }
  return value;
}

/** The paint a border layer should get under `theme` (only the changed keys). */
export function borderPaint(role: BorderRole, current: (prop: string) => unknown, theme: EraTheme): Paint {
  const style = theme.map;
  const paint: Paint = {};
  const patterned = current('line-pattern') !== undefined;
  const dropPattern = () => {
    if (patterned) paint['line-pattern'] = undefined;
  };
  if (role === 'country') {
    paint['line-color'] = style.border;
    dropPattern();
    const k = (style.borderWidth ?? 1) * (patterned ? PATTERNED_WIDTH : 1);
    if (k !== 1) paint['line-width'] = scaleWidth(current('line-width'), k);
    if (style.borderDash) paint['line-dasharray'] = style.borderDash;
    if (style.borderBlur !== undefined) paint['line-blur'] = style.borderBlur;
    if (style.borderOpacity !== undefined) paint['line-opacity'] = style.borderOpacity;
  } else if (role === 'case') {
    paint['line-color'] = mix(style.border, theme.paper, 0.72);
  } else {
    paint['line-color'] = mix(style.border, theme.paper, 0.35);
    dropPattern();
    if (patterned) paint['line-width'] = scaleWidth(current('line-width'), PATTERNED_WIDTH);
  }
  return paint;
}

function setPaint(map: MapLibreMap, id: string, prop: string, value: unknown): void {
  map.setPaintProperty(id, prop, value as never);
}

function restore(map: MapLibreMap, state: StyleState): void {
  for (const [id, props] of state.originals) {
    if (!map.getLayer(id)) continue;
    for (const [prop, value] of Object.entries(props)) setPaint(map, id, prop, value);
  }
  state.originals.clear();
}

function removeOwn(map: MapLibreMap, state: StyleState): void {
  for (const id of OWN_LAYERS) if (map.getLayer(id)) map.removeLayer(id);
  if (map.hasImage(ERA_TEXTURE_IMAGE)) map.removeImage(ERA_TEXTURE_IMAGE);
  state.imageKey = null;
}

function styleLayers(map: MapLibreMap): Layer[] {
  return ((map.getStyle().layers ?? []) as Layer[]).filter((l) => !OWN_LAYERS.includes(l.id));
}

const imageCache = new Map<string, ImageData | null>();

function cachedTexture(key: string, make: () => ImageData | null): ImageData | null {
  if (!imageCache.has(key)) imageCache.set(key, make());
  return imageCache.get(key) ?? null;
}

/** Restyle the map for `theme`, or put the basemap back as it was (null). */
export function applyEraToMap(map: MapLibreMap, theme: EraTheme | null): void {
  const state = stateFor(map);
  if (!state) return;
  restore(map, state);
  if (!theme) {
    removeOwn(map, state);
    return;
  }

  const layers = styleLayers(map);

  // Borders.
  for (const layer of layers) {
    const role = borderRole(layer);
    if (!role || !map.getLayer(layer.id)) continue;
    const next = borderPaint(role, (prop) => map.getPaintProperty(layer.id, prop), theme);
    const before: Paint = {};
    for (const prop of Object.keys(next)) before[prop] = map.getPaintProperty(layer.id, prop);
    state.originals.set(layer.id, before);
    for (const [prop, value] of Object.entries(next)) setPaint(map, layer.id, prop, value);
  }

  // Sea wash: a background layer just above the basemap's own backgrounds,
  // so the land (drawn later) covers it.
  const sea = theme.map.sea;
  const firstOver = layers.find((l) => l.type !== 'background');
  if (sea && firstOver) {
    if (!map.getLayer(ERA_SEA_LAYER)) {
      map.addLayer({ id: ERA_SEA_LAYER, type: 'background', paint: {} }, firstOver.id);
    }
    setPaint(map, ERA_SEA_LAYER, 'background-color', sea.color);
    setPaint(map, ERA_SEA_LAYER, 'background-opacity', sea.opacity);
  } else if (map.getLayer(ERA_SEA_LAYER)) {
    map.removeLayer(ERA_SEA_LAYER);
  }

  // Land wash and texture: right above the basemap's land fill, under
  // everything drawn on the land.
  const lastLand = layers.map((l) => l['source-layer']).lastIndexOf(LAND_SOURCE_LAYER);
  const land = lastLand >= 0 ? layers[lastLand] : null;
  const above = lastLand >= 0 ? layers[lastLand + 1]?.id : undefined;
  if (land?.source && theme.map.land) {
    if (!map.getLayer(ERA_LAND_LAYER)) {
      map.addLayer(
        { id: ERA_LAND_LAYER, type: 'fill', source: land.source, 'source-layer': LAND_SOURCE_LAYER, paint: {} },
        above,
      );
    }
    setPaint(map, ERA_LAND_LAYER, 'fill-color', theme.map.land.color);
    setPaint(map, ERA_LAND_LAYER, 'fill-opacity', theme.map.land.opacity);
  } else if (map.getLayer(ERA_LAND_LAYER)) {
    map.removeLayer(ERA_LAND_LAYER);
  }

  const texture = theme.texture;
  const key = texture ? `${texture.kind}:${texture.color}` : null;
  if (land?.source && texture && texture.map > 0 && key) {
    if (state.imageKey !== key) {
      const image = cachedTexture(key, () => textureImage(texture.kind, texture.color));
      if (map.getLayer(ERA_TEXTURE_LAYER)) map.removeLayer(ERA_TEXTURE_LAYER);
      if (map.hasImage(ERA_TEXTURE_IMAGE)) map.removeImage(ERA_TEXTURE_IMAGE);
      if (image) map.addImage(ERA_TEXTURE_IMAGE, image, { pixelRatio: 2 });
      state.imageKey = image ? key : null;
    }
    if (state.imageKey && !map.getLayer(ERA_TEXTURE_LAYER)) {
      map.addLayer(
        {
          id: ERA_TEXTURE_LAYER,
          type: 'fill',
          source: land.source,
          'source-layer': LAND_SOURCE_LAYER,
          paint: { 'fill-pattern': ERA_TEXTURE_IMAGE },
        },
        above,
      );
    }
    if (map.getLayer(ERA_TEXTURE_LAYER)) setPaint(map, ERA_TEXTURE_LAYER, 'fill-opacity', texture.map);
  } else {
    if (map.getLayer(ERA_TEXTURE_LAYER)) map.removeLayer(ERA_TEXTURE_LAYER);
    if (map.hasImage(ERA_TEXTURE_IMAGE)) map.removeImage(ERA_TEXTURE_IMAGE);
    state.imageKey = null;
  }
}

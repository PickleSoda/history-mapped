/**
 * The battle-map overlay on the MapLibre map: GeoJSON builders for one frame
 * and the sources/layers that draw them (masks and terrain under everything,
 * then strongpoint state and the light tint, units, arrows, glyphs and
 * labels, pins, arrowheads, notes).
 */
import type { Feature, FeatureCollection, Geometry } from 'geojson';
import type {
  ExpressionSpecification,
  FilterSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
} from 'maplibre-gl';
import type { Light, LngLat, MapStoryDocument, StorySide, StoryStep, StoryUnit } from '@/lib/schemas/map-story';
import { POINT_UNIT_KINDS } from '@/lib/schemas/map-story';
import { unitColor } from './colors';
import { along, bearing, dest, formation, movePath, onField, rankBands, stepPhases } from './geometry';
import type { Frame, TerrainHold } from './geometry';
import {
  ALT_SITE_ICON,
  arrowId,
  capturedId,
  hatchId,
  landingId,
  noteId,
  pinId,
  ramId,
  shipId,
  standardId,
  stateId,
  terrainStateId,
  unitGlyphId,
} from './icons';

export const STORY_SOURCES = {
  terrain: 'story-terrain',
  mask: 'story-mask',
  hold: 'story-hold',
  light: 'story-light',
  alt: 'story-alt',
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
export const STORY_INTERACTIVE_LAYERS = ['story-unit-fill', 'story-unit-glyphs', 'story-pins', 'story-standards', 'story-ships'];

/** Our entity overlay, hidden while a story plays (MapCanvas's layer ids,
 *  including the hovered-entity marker). */
const ENTITY_LAYERS = ['entities-fill', 'entities-line', 'entities-symbols', 'entities-hover'];

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
  sunk: 0.22,
  aground: 0.5,
};

/** A pin's own opacity by state (pins don't dim with focus). */
const PIN_OPACITY: Record<string, number> = { killed: 0.6, sunk: 0.4, aground: 0.6, destroyed: 0.4 };

/** Unit-state overlays drawn over the unit's glyph or pin. */
const STATE_OVERLAYS = new Set(['killed', 'wounded', 'sunk', 'burning']);

/** The colour of a terrain feature nobody holds (a burning village, say). */
const NEUTRAL = '#57534e';

const close = <T,>(ring: T[]): T[] => (ring.length && ring[0] !== ring[ring.length - 1] ? [...ring, ring[0]] : ring);

/** Lookups for a document, built once rather than per animation frame. */
interface StoryIndex {
  units: Map<string, StoryUnit>;
  sides: Map<string, StorySide>;
  /** unit id → the colour it is drawn in (its contingent's, else its side's). */
  colors: Map<string, string>;
}

const INDEX = new WeakMap<MapStoryDocument, StoryIndex>();

function storyIndex(doc: MapStoryDocument): StoryIndex {
  let idx = INDEX.get(doc);
  if (!idx) {
    const sides = new Map(doc.sides.map((s) => [s.id, s]));
    const colors = new Map<string, string>();
    for (const u of doc.units) {
      const side = sides.get(u.side);
      if (side) colors.set(u.id, unitColor(side, u));
    }
    idx = { units: new Map(doc.units.map((u) => [u.id, u])), sides, colors };
    INDEX.set(doc, idx);
  }
  return idx;
}

function terrainGeometry(t: MapStoryDocument['terrain'][number]): Geometry | null {
  if (t.area && t.area.length >= 3) return { type: 'Polygon', coordinates: [close(t.area)] };
  if (t.line && t.line.length >= 2) return { type: 'LineString', coordinates: t.line };
  if (t.at) return { type: 'Point', coordinates: t.at };
  return null;
}

/** Static terrain (rivers, ridges, woods, villages…), masks excluded. */
export function terrainCollection(doc: MapStoryDocument): FeatureCollection {
  const features: Feature[] = [];
  for (const t of doc.terrain) {
    const geometry = t.kind === 'mask' ? null : terrainGeometry(t);
    if (geometry) features.push({ type: 'Feature', properties: { kind: t.kind, label: t.label ?? '', conj: t.conjectural === true }, geometry });
  }
  return { type: 'FeatureCollection', features };
}

/** `mask` areas: land-coloured patches hiding today's water and names (landfill, reservoirs). */
export function maskCollection(doc: MapStoryDocument): FeatureCollection {
  const features: Feature[] = [];
  for (const t of doc.terrain) {
    if (t.kind === 'mask' && t.area && t.area.length >= 3) {
      features.push({ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [close(t.area)] } });
    }
  }
  return { type: 'FeatureCollection', features };
}

/** Other proposed sites of the battle: ghost pins on every step. */
export function altSiteCollection(doc: MapStoryDocument): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: doc.alt_sites.map((s) => ({
      type: 'Feature',
      properties: { label: s.label },
      geometry: { type: 'Point', coordinates: s.at },
    })),
  };
}

/** A world-covering polygon for the light tint. */
const WORLD: FeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: {},
      geometry: { type: 'Polygon', coordinates: [[[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]]] },
    },
  ],
};

/**
 * Who holds which strongpoint at a step: the feature tinted or outlined in
 * its holder's colour, and a badge for its state (flames, crossed swords, the
 * captor's flag…) with the step's label for it.
 */
export function holdCollection(doc: MapStoryDocument, holds: Map<string, TerrainHold>): FeatureCollection {
  const { sides } = storyIndex(doc);
  const features: Feature[] = [];
  for (const [tid, h] of holds) {
    const t = doc.terrain.find((x) => x.id === tid);
    const geometry = t && terrainGeometry(t);
    if (!t || !geometry) continue;
    const color = (h.held_by && sides.get(h.held_by)?.color) || NEUTRAL;
    if (h.held_by) {
      const role = geometry.type === 'Polygon' ? 'area' : geometry.type === 'LineString' ? 'line' : 'spot';
      features.push({ type: 'Feature', properties: { role, color }, geometry });
    }
    const icon = h.state && h.state !== 'held' ? terrainStateId(h.state, color) : '';
    if (!icon && !h.label) continue;
    const at: LngLat = t.area
      ? [t.area.reduce((s, p) => s + p[0], 0) / t.area.length, t.area.reduce((s, p) => s + p[1], 0) / t.area.length]
      : t.line
        ? along(t.line, 0.5)
        : (t.at as LngLat);
    features.push({ type: 'Feature', properties: { role: 'badge', icon, label: h.label ?? '' }, geometry: { type: 'Point', coordinates: at } });
  }
  return { type: 'FeatureCollection', features };
}

/**
 * One frame's units: formation polygons, front edges and rank dividers (units
 * source), and glyph/label points, marker pins, standards, ships and state
 * overlays (points source). Units outside `focus` (when a step names some)
 * are dimmed; conjectural ones are paler with a dashed outline.
 */
export function unitCollections(
  doc: MapStoryDocument,
  frame: Frame,
  focus: string[],
): { units: FeatureCollection; points: FeatureCollection } {
  const { units, sides, colors } = storyIndex(doc);
  const shapes: Feature[] = [];
  const points: Feature[] = [];
  const focused = new Set(focus);

  for (const [uid, r] of frame) {
    const unit = units.get(uid);
    const side = unit ? sides.get(unit.side) : undefined;
    if (!unit || !side || !onField(r)) continue;
    const color = colors.get(uid) ?? side.color;
    const dim = focused.size > 0 && !focused.has(uid);
    const fade = r.fade ?? 1;
    const captor = r.state === 'captured' && r.by ? sides.get(r.by)?.color : undefined;
    const base = {
      id: uid,
      color,
      state: r.state,
      fade,
      conj: r.conjectural,
      opacity: (STATE_OPACITY[r.state] ?? 0.8) * (dim ? 0.5 : 1) * (r.conjectural ? 0.6 : 1),
      label: r.label ?? unit.label,
    };
    const point = POINT_UNIT_KINDS.includes(unit.kind);
    // Killed, wounded, sunk, burning: a mark over the glyph or pin; a captured
    // pin is hatched in the captor's colour (a captured block, below).
    const overlay = (at: LngLat) => {
      const icon = STATE_OVERLAYS.has(r.state) ? stateId(r.state) : captor && point ? capturedId(captor) : '';
      if (icon) points.push({ type: 'Feature', properties: { ...base, role: 'state', icon }, geometry: { type: 'Point', coordinates: at } });
    };

    if (point) {
      const ship = unit.kind === 'ship';
      points.push({
        type: 'Feature',
        properties: {
          ...base,
          role: ship ? 'ship' : unit.kind === 'standard' ? 'standard' : 'pin',
          icon: ship ? shipId(color) : unit.kind === 'standard' ? standardId(color) : pinId(unit.kind, color),
          // A ship turns to its facing; one run aground lists.
          rotate: ship ? r.facing + (r.state === 'aground' ? 28 : 0) : 0,
          pinOpacity: (PIN_OPACITY[r.state] ?? 1) * (r.conjectural ? 0.6 : 1) * fade,
        },
        geometry: { type: 'Point', coordinates: r.at },
      });
      overlay(r.at);
      continue;
    }

    const f = formation(r);
    shapes.push({
      type: 'Feature',
      properties: { ...base, role: 'body', hatch: captor ? hatchId(captor) : '' },
      geometry: f.parts.length === 1 ? { type: 'Polygon', coordinates: f.parts[0] } : { type: 'MultiPolygon', coordinates: f.parts },
    });
    shapes.push({
      type: 'Feature',
      properties: { ...base, role: 'front' },
      geometry: f.fronts.length === 1 ? { type: 'LineString', coordinates: f.fronts[0] } : { type: 'MultiLineString', coordinates: f.fronts },
    });
    const tilt = r.state === 'aground' ? 28 : 0;
    const ranks = unit.ranks ?? [];
    if (ranks.length > 1) {
      // A composite unit: one glyph per band, front to back, and lines between bands.
      const { centres, dividers } = rankBands(r, ranks.map((k) => k.share));
      shapes.push({ type: 'Feature', properties: { ...base, role: 'divider' }, geometry: { type: 'MultiLineString', coordinates: dividers } });
      centres.forEach((at, i) =>
        points.push({
          type: 'Feature',
          properties: { ...base, role: 'glyph', tilt, icon: unitGlyphId(ranks[i].kind), label: i === centres.length - 1 ? base.label : '' },
          geometry: { type: 'Point', coordinates: at },
        }),
      );
    } else {
      points.push({
        type: 'Feature',
        properties: { ...base, role: 'glyph', tilt, icon: unitGlyphId(unit.kind) },
        geometry: { type: 'Point', coordinates: r.at },
      });
    }
    overlay(r.at);
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
  back_water: 'dashed',
  march: 'dotted',
  fire: 'dotted',
  blockade: 'dotted',
};

const WEIGHT: Record<string, number> = { charge: 1.6, fire: 0.55, ram: 1.9, blockade: 0.8, landing: 1.15 };

/** Segments a `continues` tail fades over. */
const TAIL_STEPS = 8;

/** The colour of a move's arrow: its unit's (contingent) colour, else its side's. */
function moveColor(doc: MapStoryDocument, mv: { unit?: string | null; side?: string | null }): string {
  const { units, sides, colors } = storyIndex(doc);
  const sideId = mv.side ?? (mv.unit ? units.get(mv.unit)?.side : undefined);
  return (mv.unit && colors.get(mv.unit)) || (sideId && sides.get(sideId)?.color) || '#3f3f46';
}

/**
 * A step's movement arrows (lines + heads at their ends), for its own phase
 * and its beats up to `upto` (each beat's arrows stay once it has played).
 * `frames` are the step's phase frames (`resolveBeats`): a `fire` arrow ends
 * on its target there, and a blockade's ticks face the enemy there.
 */
export function moveCollection(
  doc: MapStoryDocument,
  step: StoryStep | undefined,
  frames: Frame[] = [],
  upto = Infinity,
): FeatureCollection {
  const { units } = storyIndex(doc);
  const features: Feature[] = [];
  stepPhases(step).forEach((phase, q) => {
    if (q > upto) return;
    const frame = frames[Math.min(q, frames.length - 1)];
    for (const mv of phase.moves) {
      const color = moveColor(doc, mv);
      const conj = mv.conjectural === true;
      const dash = DASH[mv.type] ?? (conj ? 'dashed' : 'solid');
      const props = { color, type: mv.type, dash, weight: WEIGHT[mv.type] ?? 1, label: mv.label ?? '', alpha: conj ? 0.6 : 1 };
      const path = movePath(mv, frame);
      features.push({ type: 'Feature', properties: props, geometry: { type: 'LineString', coordinates: path } });
      const end = path[path.length - 1];
      const heading = bearing(path[path.length - 2], end);

      if (mv.type === 'blockade') {
        // No head: ticks along the line, on the side the enemy stands.
        const sideId = mv.side ?? (mv.unit ? units.get(mv.unit)?.side : undefined);
        features.push({ type: 'Feature', properties: { ...props, dash: 'tick' }, geometry: { type: 'MultiLineString', coordinates: blockadeTicks(doc, path, sideId, frame) } });
      } else {
        const icon = mv.type === 'ram' ? ramId(color) : mv.type === 'landing' ? landingId(color) : arrowId(color);
        features.push({ type: 'Feature', properties: { ...props, icon, bearing: heading }, geometry: { type: 'Point', coordinates: end } });
      }

      if (mv.continues) {
        // A fading dashed tail on toward the far point.
        const { toward } = mv.continues;
        for (let k = 0; k < TAIL_STEPS; k++) {
          const a: LngLat = [end[0] + ((toward[0] - end[0]) * k) / TAIL_STEPS, end[1] + ((toward[1] - end[1]) * k) / TAIL_STEPS];
          const b: LngLat = [end[0] + ((toward[0] - end[0]) * (k + 1)) / TAIL_STEPS, end[1] + ((toward[1] - end[1]) * (k + 1)) / TAIL_STEPS];
          features.push({
            type: 'Feature',
            properties: { ...props, dash: 'tail', alpha: props.alpha * 0.85 * (1 - k / TAIL_STEPS) },
            geometry: { type: 'LineString', coordinates: [a, b] },
          });
        }
      }
    }
  });
  return { type: 'FeatureCollection', features };
}

/** A blockade line's tick marks, pointing toward the enemy's centre of mass. */
function blockadeTicks(doc: MapStoryDocument, path: LngLat[], sideId: string | null | undefined, frame: Frame | undefined): LngLat[][] {
  const { units } = storyIndex(doc);
  let sx = 0;
  let sy = 0;
  let n = 0;
  for (const [uid, r] of frame ?? []) {
    const side = units.get(uid)?.side;
    if (side && side !== sideId && onField(r)) {
      sx += r.at[0];
      sy += r.at[1];
      n++;
    }
  }
  const mid = along(path, 0.5);
  const midHeading = bearing(along(path, 0.45), along(path, 0.55));
  const toEnemy = n ? (bearing(mid, [sx / n, sy / n]) - midHeading + 360) % 360 : 270;
  const turn = toEnemy < 180 ? 90 : -90;
  let length = 0;
  for (let i = 1; i < path.length; i++) {
    const dx = (path[i][0] - path[i - 1][0]) * Math.cos((path[i][1] * Math.PI) / 180);
    length += Math.hypot(dx, path[i][1] - path[i - 1][1]) * 111_320;
  }
  const count = Math.max(3, Math.min(24, Math.round(length / 180)));
  const tick = Math.max(40, Math.min(160, length / 25));
  const ticks: LngLat[][] = [];
  for (let i = 0; i < count; i++) {
    const t = (i + 0.5) / count;
    const p = along(path, t);
    const h = bearing(along(path, Math.max(0, t - 0.02)), along(path, Math.min(1, t + 0.02)));
    ticks.push([p, dest(p, h + turn, tick)]);
  }
  return ticks;
}

/** A `continues` tail, for the edge label the overlay draws in the DOM. */
export interface MoveTail {
  from: LngLat;
  toward: LngLat;
  label: string;
  color: string;
}

export function moveTails(doc: MapStoryDocument, step: StoryStep | undefined, frames: Frame[] = [], upto = Infinity): MoveTail[] {
  const tails: MoveTail[] = [];
  stepPhases(step).forEach((phase, q) => {
    if (q > upto) return;
    for (const mv of phase.moves) {
      if (!mv.continues?.label) continue;
      const path = movePath(mv, frames[Math.min(q, frames.length - 1)]);
      tails.push({ from: path[path.length - 1], toward: mv.continues.toward, label: mv.continues.label, color: moveColor(doc, mv) });
    }
  });
  return tails;
}

/** A step's map notes (clash, death, capture… callouts), its beats' up to `upto`. */
export function noteCollection(step: StoryStep | undefined, upto = Infinity): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: stepPhases(step)
      .filter((_, q) => q <= upto)
      .flatMap((phase) =>
        phase.notes.map(
          (n): Feature => ({
            type: 'Feature',
            properties: { text: n.text, kind: n.kind, icon: n.kind === 'label' ? '' : noteId(n.kind), alpha: n.conjectural ? 0.6 : 1 },
            geometry: { type: 'Point', coordinates: n.at },
          }),
        ),
      ),
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

/** Masks are drawn in the historical styles' land parchment. (A style's
 *  `background` is no guide: OHM's is a saturated tan its land fills cover.) */
const MASK_COLOR = '#f3ebdc';

const role = (r: string): ExpressionSpecification => ['==', ['get', 'role'], r];

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
  (map.getSource(STORY_SOURCES.light) as GeoJSONSource).setData(WORLD);

  const isArea: FilterSpecification = ['==', ['geometry-type'], 'Polygon'];
  const isLine: FilterSpecification = ['==', ['geometry-type'], 'LineString'];
  const isPoint: FilterSpecification = ['==', ['geometry-type'], 'Point'];
  const conj: ExpressionSpecification = ['==', ['get', 'conj'], true];
  const notConj: ExpressionSpecification = ['!=', ['get', 'conj'], true];
  const conjFade = (v: number, light: number): ExpressionSpecification => ['case', ['==', ['get', 'conj'], true], light, v];
  const fillColor = matchKind(Object.fromEntries(Object.entries(TERRAIN_FILL).map(([k, [c]]) => [k, c])), '#a8a29e');
  const fillOpacity = matchKind(Object.fromEntries(Object.entries(TERRAIN_FILL).map(([k, [, o]]) => [k, o])), 0.12);
  const lineColor = matchKind(TERRAIN_LINE, '#57534e');

  // ── masks: today's water and names hidden where the ground was different ──
  map.addLayer({ id: 'story-mask', type: 'fill', source: STORY_SOURCES.mask, paint: { 'fill-color': MASK_COLOR, 'fill-opacity': 1 } });

  // ── terrain ──
  map.addLayer({
    id: 'story-terrain-fill',
    type: 'fill',
    source: STORY_SOURCES.terrain,
    filter: isArea,
    paint: { 'fill-color': fillColor, 'fill-opacity': ['*', fillOpacity, conjFade(1, 0.5)] },
  });
  map.addLayer({ id: 'story-terrain-edge', type: 'line', source: STORY_SOURCES.terrain, filter: isArea, paint: { 'line-color': fillColor, 'line-opacity': 0.55, 'line-width': 1, 'line-dasharray': [3, 2] } });
  const terrainLineWidth = zoomed(
    ['match', ['get', 'kind'], 'river', 2, 'ridge', 1.5, 1],
    ['match', ['get', 'kind'], 'river', 5, 'ridge', 3.5, 2.5],
  );
  map.addLayer({
    id: 'story-terrain-line',
    type: 'line',
    source: STORY_SOURCES.terrain,
    filter: ['all', isLine, ['!=', ['get', 'kind'], 'road'], notConj],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': lineColor, 'line-opacity': 0.85, 'line-width': terrainLineWidth },
  });
  map.addLayer({
    id: 'story-terrain-line-conj',
    type: 'line',
    source: STORY_SOURCES.terrain,
    filter: ['all', isLine, ['!=', ['get', 'kind'], 'road'], conj],
    paint: { 'line-color': lineColor, 'line-opacity': 0.55, 'line-width': terrainLineWidth, 'line-dasharray': [2, 1.5] },
  });
  map.addLayer({
    id: 'story-terrain-road',
    type: 'line',
    source: STORY_SOURCES.terrain,
    filter: ['all', isLine, ['==', ['get', 'kind'], 'road']],
    paint: { 'line-color': lineColor, 'line-opacity': conjFade(0.8, 0.45), 'line-width': zoomed(1, 2.5), 'line-dasharray': [4, 2] },
  });
  map.addLayer({
    id: 'story-terrain-dot',
    type: 'circle',
    source: STORY_SOURCES.terrain,
    filter: isPoint,
    paint: {
      'circle-radius': 3.5,
      'circle-color': '#fffdf7',
      'circle-stroke-color': '#292524',
      'circle-stroke-width': 1.5,
      'circle-opacity': conjFade(1, 0.5),
      'circle-stroke-opacity': conjFade(1, 0.45),
    },
  });

  // ── who holds the strongpoints ──
  map.addLayer({ id: 'story-hold-fill', type: 'fill', source: STORY_SOURCES.hold, filter: role('area'), paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.24 } });
  map.addLayer({ id: 'story-hold-edge', type: 'line', source: STORY_SOURCES.hold, filter: role('area'), paint: { 'line-color': ['get', 'color'], 'line-opacity': 0.9, 'line-width': 2.2 } });
  map.addLayer({ id: 'story-hold-line', type: 'line', source: STORY_SOURCES.hold, filter: role('line'), layout: { 'line-cap': 'round' }, paint: { 'line-color': ['get', 'color'], 'line-opacity': 0.35, 'line-width': zoomed(4, 9) } });
  map.addLayer({
    id: 'story-hold-spot',
    type: 'circle',
    source: STORY_SOURCES.hold,
    filter: role('spot'),
    paint: { 'circle-radius': 9, 'circle-color': ['get', 'color'], 'circle-opacity': 0.3, 'circle-stroke-color': ['get', 'color'], 'circle-stroke-width': 2.2 },
  });

  // ── light: night, dawn and dusk tint the ground; units and labels stay clear ──
  map.addLayer({ id: 'story-light', type: 'fill', source: STORY_SOURCES.light, paint: { 'fill-color': LIGHT_TINT.day[0], 'fill-opacity': 0 } });

  // Labels: along rivers, roads and ridges; beside villages; inside areas.
  const labelPaint = {
    'text-color': '#3f2d14',
    'text-halo-color': 'rgba(255,253,245,0.92)',
    'text-halo-width': 1.6,
    'text-opacity': conjFade(1, 0.7),
  };
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
  map.addLayer({
    id: 'story-alt-sites',
    type: 'symbol',
    source: STORY_SOURCES.alt,
    layout: {
      'icon-image': ALT_SITE_ICON,
      'icon-size': 0.72,
      'icon-allow-overlap': true,
      'text-field': ['get', 'label'],
      'text-size': 11,
      'text-font': FONT_ITALIC,
      'text-offset': [0, 1.2],
      'text-anchor': 'top',
      'text-max-width': 10,
      'text-optional': true,
    },
    paint: { 'icon-opacity': 0.8, 'text-color': '#57534e', 'text-halo-color': 'rgba(255,253,245,0.9)', 'text-halo-width': 1.4 },
  });

  // ── formations ──
  const fade: ExpressionSpecification = ['get', 'fade'];
  map.addLayer({
    id: 'story-unit-fill',
    type: 'fill',
    source: STORY_SOURCES.units,
    filter: role('body'),
    paint: { 'fill-color': ['get', 'color'], 'fill-opacity': ['*', ['get', 'opacity'], fade] },
  });
  map.addLayer({
    id: 'story-unit-hatch',
    type: 'fill',
    source: STORY_SOURCES.units,
    filter: ['all', role('body'), ['!=', ['get', 'hatch'], '']],
    paint: { 'fill-pattern': ['get', 'hatch'], 'fill-opacity': ['*', 0.9, fade] },
  });
  const outlinePaint = {
    'line-color': '#1c1917',
    'line-opacity': ['*', fade, ['case', ['in', ['get', 'state'], ['literal', ['routed', 'destroyed', 'sunk']]], 0.45, 0.8]] as ExpressionSpecification,
    'line-width': ['case', ['==', ['get', 'state'], 'engaged'], 1.8, 1] as ExpressionSpecification,
  };
  map.addLayer({ id: 'story-unit-outline', type: 'line', source: STORY_SOURCES.units, filter: ['all', role('body'), notConj], paint: outlinePaint });
  map.addLayer({ id: 'story-unit-outline-conj', type: 'line', source: STORY_SOURCES.units, filter: ['all', role('body'), conj], paint: { ...outlinePaint, 'line-dasharray': [2.5, 2] } });
  map.addLayer({
    id: 'story-unit-dividers',
    type: 'line',
    source: STORY_SOURCES.units,
    filter: role('divider'),
    paint: { 'line-color': '#fffdf5', 'line-opacity': ['*', 0.8, fade], 'line-width': 1.2, 'line-dasharray': [3, 2] },
  });
  map.addLayer({
    id: 'story-unit-front',
    type: 'line',
    source: STORY_SOURCES.units,
    filter: ['all', role('front'), ['!', ['in', ['get', 'state'], ['literal', ['routed', 'destroyed', 'sunk']]]]],
    layout: { 'line-cap': 'round' },
    paint: {
      'line-color': '#1c1917',
      'line-opacity': ['*', 0.85, fade],
      'line-width': ['case', ['==', ['get', 'state'], 'engaged'], 3.2, 2.2],
    },
  });
  // ── movement arrows, over the blocks (a unit often moves along its own arrow) ──
  // A pale casing keeps an arrow readable over a block of its own colour.
  const moveWidth = zoomed(['*', ['get', 'weight'], 2.5], ['*', ['get', 'weight'], 6]);
  map.addLayer({
    id: 'story-move-casing',
    type: 'line',
    source: STORY_SOURCES.moves,
    filter: ['all', isLine, ['==', ['get', 'dash'], 'solid']],
    layout: { 'line-cap': 'butt', 'line-join': 'round' },
    paint: {
      'line-color': '#fffdf5',
      'line-opacity': MOVE_OPACITY.casing,
      'line-width': zoomed(['+', ['*', ['get', 'weight'], 2.5], 2.5], ['+', ['*', ['get', 'weight'], 6], 3.5]),
    },
  });
  for (const dash of ['solid', 'dashed', 'dotted', 'tail'] as const) {
    map.addLayer({
      id: `story-move-${dash}`,
      type: 'line',
      source: STORY_SOURCES.moves,
      filter: ['all', isLine, ['==', ['get', 'dash'], dash]],
      layout: { 'line-cap': dash === 'dotted' ? 'round' : 'butt', 'line-join': 'round' },
      paint: {
        'line-color': ['get', 'color'],
        'line-opacity': moveOpacity(1),
        'line-width': dash === 'tail' ? zoomed(1.6, 3.5) : moveWidth,
        ...(dash === 'solid' ? {} : { 'line-dasharray': dash === 'dotted' ? [0.1, 1.8] : dash === 'tail' ? [2, 2] : [2.2, 1.6] }),
      },
    });
  }
  map.addLayer({
    id: 'story-move-ticks',
    type: 'line',
    source: STORY_SOURCES.moves,
    filter: ['==', ['get', 'dash'], 'tick'],
    layout: { 'line-cap': 'round' },
    paint: { 'line-color': ['get', 'color'], 'line-opacity': moveOpacity(1), 'line-width': zoomed(1.5, 3) },
  });

  map.addLayer({
    id: 'story-hold-badges',
    type: 'symbol',
    source: STORY_SOURCES.hold,
    filter: role('badge'),
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-size': zoomed(0.55, 0.8),
      // Up and left of the feature, clear of a garrison's glyph and the place name.
      'icon-offset': [-18, -18],
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      'text-field': ['get', 'label'],
      'text-size': 11,
      'text-font': FONT_BOLD,
      'text-offset': [-1.1, -2.6],
      'text-anchor': 'bottom',
      'text-max-width': 12,
      'text-optional': true,
    },
    paint: { 'text-color': '#44403c', 'text-halo-color': 'rgba(255,253,245,0.95)', 'text-halo-width': 1.6 },
  });

  const glyphOpacity: ExpressionSpecification = ['*', fade, ['min', 1, ['+', ['get', 'opacity'], 0.25]]];
  map.addLayer({
    id: 'story-unit-glyphs',
    type: 'symbol',
    source: STORY_SOURCES.points,
    filter: role('glyph'),
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-size': zoomed(0.5, 0.85),
      'icon-rotate': ['get', 'tilt'],
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
      'icon-opacity': glyphOpacity,
      'text-color': '#1c1917',
      'text-halo-color': 'rgba(255,253,245,0.95)',
      'text-halo-width': 1.6,
      'text-opacity': ['*', fade, ['min', 1, ['+', ['get', 'opacity'], 0.3]]],
    },
  });
  const pinText = {
    'text-field': ['get', 'label'] as ExpressionSpecification,
    'text-size': 11.5,
    'text-font': FONT_BOLD,
    'text-offset': [1.1, 0] as [number, number],
    'text-anchor': 'left' as const,
    'text-optional': true,
  };
  const pinPaint = {
    'icon-opacity': ['get', 'pinOpacity'] as ExpressionSpecification,
    'text-opacity': fade,
    'text-color': '#1c1917',
    'text-halo-color': 'rgba(255,253,245,0.95)',
    'text-halo-width': 1.6,
  };
  map.addLayer({
    id: 'story-pins',
    type: 'symbol',
    source: STORY_SOURCES.points,
    filter: role('pin'),
    layout: { 'icon-image': ['get', 'icon'], 'icon-size': zoomed(0.6, 0.9), 'icon-allow-overlap': true, ...pinText },
    paint: pinPaint,
  });
  map.addLayer({
    id: 'story-standards',
    type: 'symbol',
    source: STORY_SOURCES.points,
    filter: role('standard'),
    layout: { 'icon-image': ['get', 'icon'], 'icon-size': zoomed(0.65, 1), 'icon-anchor': 'bottom', 'icon-allow-overlap': true, ...pinText, 'text-offset': [0.9, -1] },
    paint: pinPaint,
  });
  map.addLayer({
    id: 'story-ships',
    type: 'symbol',
    source: STORY_SOURCES.points,
    filter: role('ship'),
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-size': zoomed(0.6, 1),
      'icon-rotate': ['get', 'rotate'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      ...pinText,
    },
    paint: pinPaint,
  });
  map.addLayer({
    id: 'story-unit-states',
    type: 'symbol',
    source: STORY_SOURCES.points,
    filter: role('state'),
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-size': zoomed(0.55, 0.85),
      // A wound or a fire sits at the marker's shoulder; the rest cover it.
      'icon-offset': ['match', ['get', 'state'], 'wounded', ['literal', [15, -15]], 'burning', ['literal', [14, -16]], ['literal', [0, 0]]],
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
    paint: { 'icon-opacity': fade },
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
    paint: { 'icon-opacity': moveOpacity(1) },
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
    paint: {
      'icon-opacity': ['get', 'alpha'],
      'text-opacity': ['get', 'alpha'],
      'text-color': '#7c2d12',
      'text-halo-color': 'rgba(255,251,235,0.97)',
      'text-halo-width': 2,
    },
  });
}

export function removeStoryLayers(map: MapLibreMap): void {
  for (const layer of map.getStyle()?.layers ?? []) {
    if (layer.id.startsWith('story-')) map.removeLayer(layer.id);
  }
  for (const id of Object.values(STORY_SOURCES)) {
    if (map.getSource(id)) map.removeSource(id);
  }
  SHOWN_MOVE_OPACITY.delete(map);
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

const MOVE_OPACITY = { line: 0.9, casing: 0.75 };

/** An arrow's opacity: the step's fade-in times the feature's own `alpha` (conjectural, tails). */
const moveOpacity = (opacity: number): ExpressionSpecification => ['*', MOVE_OPACITY.line * opacity, ['get', 'alpha']];

/** What each map's arrows were last faded to, so a finished fade isn't re-sent every frame. */
const SHOWN_MOVE_OPACITY = new WeakMap<MapLibreMap, number>();

/** Fade the arrows in as a step's movement starts. */
export function setMoveOpacity(map: MapLibreMap, opacity: number): void {
  if (SHOWN_MOVE_OPACITY.get(map) === opacity) return;
  SHOWN_MOVE_OPACITY.set(map, opacity);
  for (const id of ['story-move-solid', 'story-move-dashed', 'story-move-dotted', 'story-move-tail', 'story-move-ticks']) {
    if (map.getLayer(id)) map.setPaintProperty(id, 'line-opacity', moveOpacity(opacity));
  }
  if (map.getLayer('story-move-casing')) map.setPaintProperty('story-move-casing', 'line-opacity', MOVE_OPACITY.casing * opacity);
  if (map.getLayer('story-move-heads')) map.setPaintProperty('story-move-heads', 'icon-opacity', moveOpacity(opacity));
}

/** The tint per light: colour and opacity over the ground. */
const LIGHT_TINT: Record<Light, [string, number]> = {
  night: ['#0b1736', 0.42],
  dawn: ['#f97316', 0.14],
  day: ['#0b1736', 0],
  dusk: ['#9a3412', 0.22],
};

/** Tint the map for the step's light, easing over ~1 s unless `animate` is off. */
export function setLight(map: MapLibreMap, light: Light, animate: boolean): void {
  if (!map.getLayer('story-light')) return;
  const [color, opacity] = LIGHT_TINT[light] ?? LIGHT_TINT.day;
  const transition = { duration: animate ? 1000 : 0, delay: 0 };
  map.setPaintProperty('story-light', 'fill-color-transition', transition);
  map.setPaintProperty('story-light', 'fill-opacity-transition', transition);
  map.setPaintProperty('story-light', 'fill-color', color);
  map.setPaintProperty('story-light', 'fill-opacity', opacity);
}

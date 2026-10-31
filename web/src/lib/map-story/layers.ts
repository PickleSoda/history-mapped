/**
 * The map-story overlay on the MapLibre map: GeoJSON builders for one frame
 * and the sources/layers that draw them (the step's highlighted entities,
 * masks and terrain under everything, then regions, strongpoint state and the
 * light tint, routes and places, units, arrows, glyphs and labels, pins,
 * arrowheads, notes).
 */
import type { Feature, FeatureCollection, Geometry } from 'geojson';
import type {
  ExpressionSpecification,
  FilterSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
} from 'maplibre-gl';
import { ohmDateFilter } from '@/lib/ohm-layer-date-filter';
import type {
  AmbientStory,
  Light,
  LngLat,
  MapStoryDocument,
  StoryFeature,
  StorySide,
  StoryStep,
  StoryStepEntity,
  StoryUnit,
} from '@/lib/schemas/map-story';
import { DYNAMIC_FEATURE_KINDS, POINT_UNIT_KINDS } from '@/lib/schemas/map-story';
import { DISRUPTED_COLOR, featureColor, NEUTRAL_COLOR, unitColor } from './colors';
import { along, bearing, dest, formation, movePath, onField, rankBands, stepPhases } from './geometry';
import type { FeatureHold, Frame } from './geometry';
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
  entities: 'story-entities',
  terrain: 'story-terrain',
  regions: 'story-regions',
  regionsOld: 'story-regions-old',
  routes: 'story-routes',
  places: 'story-places',
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
  ohmAdmin: 'story-ohm-admin',
} as const;

/** Sources added from remote tiles rather than our GeoJSON. */
const REMOTE_SOURCES: string[] = [STORY_SOURCES.dem, STORY_SOURCES.modern, STORY_SOURCES.ohmAdmin];

/** Layers a pointer can hover/click for unit details. */
export const STORY_INTERACTIVE_LAYERS = ['story-unit-fill', 'story-unit-glyphs', 'story-pins', 'story-standards', 'story-ships'];

/** Layers a pointer can hover/click for a route, region or place's details. */
export const STORY_FEATURE_LAYERS = ['story-place-circle', 'story-route-base', 'story-route-disrupted', 'story-region-fill'];

/** Our entity overlay, hidden while a story plays (MapCanvas's layer ids, bottom first). */
export const ENTITY_LAYERS = ['entities-fill', 'entities-line', 'entities-symbols'];

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
  /** unit id → the colour it is drawn in (its contingent's, else its side's, else neutral). */
  colors: Map<string, string>;
  /** The largest `value_n` any route / place reaches (scales widths and circles). */
  maxRoute: number;
  maxPlace: number;
}

const INDEX = new WeakMap<MapStoryDocument, StoryIndex>();

function storyIndex(doc: MapStoryDocument): StoryIndex {
  let idx = INDEX.get(doc);
  if (!idx) {
    const sides = new Map(doc.sides.map((s) => [s.id, s]));
    const colors = new Map<string, string>();
    for (const u of doc.units) {
      const side = u.side ? sides.get(u.side) : undefined;
      if (side) colors.set(u.id, unitColor(side, u));
      else if (!u.side) colors.set(u.id, NEUTRAL_COLOR);
    }
    // Every value a route or place takes, on the feature or at a step.
    const values = new Map<string, number[]>();
    for (const f of doc.features) values.set(f.id, f.value_n != null ? [f.value_n] : []);
    for (const step of doc.steps) {
      for (const [fid, fs] of Object.entries(step.features)) {
        if (fs?.value_n != null) values.get(fid)?.push(fs.value_n);
      }
    }
    const maxOf = (pred: (f: StoryFeature) => boolean) =>
      Math.max(0, ...doc.features.filter(pred).flatMap((f) => values.get(f.id) ?? []));
    idx = {
      units: new Map(doc.units.map((u) => [u.id, u])),
      sides,
      colors,
      maxRoute: maxOf((f) => f.kind === 'route'),
      maxPlace: maxOf((f) => f.kind !== 'route' && f.kind !== 'region'),
    };
    INDEX.set(doc, idx);
  }
  return idx;
}

/** Rings as a Polygon (one) or a MultiPolygon (several), closed; degenerate rings dropped. */
function areaGeometry(area: LngLat[][]): Geometry | null {
  const polys = area.filter((r) => r.length >= 3).map((r) => [close(r)]);
  if (polys.length === 0) return null;
  return polys.length === 1 ? { type: 'Polygon', coordinates: polys[0] } : { type: 'MultiPolygon', coordinates: polys };
}

function terrainGeometry(t: StoryFeature): Geometry | null {
  const area = t.area && areaGeometry(t.area);
  if (area) return area;
  if (t.line && t.line.length >= 2) return { type: 'LineString', coordinates: t.line };
  if (t.at) return { type: 'Point', coordinates: t.at };
  return null;
}

/** The middle of a set of rings: the centre of the largest ring's vertices. */
function ringsCentre(area: LngLat[][]): LngLat | null {
  let best: LngLat[] | null = null;
  for (const r of area) if (!best || r.length > best.length) best = r;
  if (!best || best.length === 0) return null;
  return [best.reduce((s, p) => s + p[0], 0) / best.length, best.reduce((s, p) => s + p[1], 0) / best.length];
}

/** Static terrain (rivers, ridges, woods, villages…): masks and the per-step kinds excluded. */
export function terrainCollection(doc: MapStoryDocument): FeatureCollection {
  const features: Feature[] = [];
  for (const t of doc.features) {
    const geometry = t.kind === 'mask' || DYNAMIC_FEATURE_KINDS.includes(t.kind) ? null : terrainGeometry(t);
    if (geometry) features.push({ type: 'Feature', properties: { kind: t.kind, label: t.label ?? '', conj: t.conjectural === true }, geometry });
  }
  return { type: 'FeatureCollection', features };
}

/** `mask` areas: land-coloured patches hiding today's water and names (landfill, reservoirs). */
export function maskCollection(doc: MapStoryDocument): FeatureCollection {
  const features: Feature[] = [];
  for (const t of doc.features) {
    const geometry = t.kind === 'mask' && t.area ? areaGeometry(t.area) : null;
    if (geometry) features.push({ type: 'Feature', properties: {}, geometry });
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
export function holdCollection(doc: MapStoryDocument, holds: Map<string, FeatureHold>): FeatureCollection {
  const { sides } = storyIndex(doc);
  const features: Feature[] = [];
  for (const [tid, h] of holds) {
    // Routes, regions and places show their state themselves (featureCollections).
    const t = doc.features.find((x) => x.id === tid && !DYNAMIC_FEATURE_KINDS.includes(x.kind));
    const geometry = t && terrainGeometry(t);
    if (!t || !geometry) continue;
    const color = (h.held_by && sides.get(h.held_by)?.color) || NEUTRAL;
    if (h.held_by) {
      const role = geometry.type === 'Polygon' ? 'area' : geometry.type === 'LineString' ? 'line' : 'spot';
      features.push({ type: 'Feature', properties: { role, color }, geometry });
    }
    const icon = h.state && h.state !== 'held' ? terrainStateId(h.state, color) : '';
    if (!icon && !h.label) continue;
    const at: LngLat = (t.area && ringsCentre(t.area)) || (t.line ? along(t.line, 0.5) : (t.at as LngLat));
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
    const side = unit?.side ? sides.get(unit.side) : undefined;
    // A unit without a side is drawn in the neutral colour; one with an unknown side isn't drawn.
    if (!unit || (unit.side && !side) || !onField(r)) continue;
    const color = colors.get(uid) ?? side?.color ?? NEUTRAL_COLOR;
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
  // v3
  trade: 'dashed',
  spread: 'dashed',
  explore: 'dotted',
};

const WEIGHT: Record<string, number> = { charge: 1.6, fire: 0.55, ram: 1.9, blockade: 0.8, landing: 1.15, migrate: 1.2, spread: 1.2, sail: 0.9 };

/** Segments a `continues` tail fades over. */
const TAIL_STEPS = 8;

/** The colour of a move's arrow: its unit's (contingent) colour, else its side's. */
function moveColor(doc: MapStoryDocument, mv: { unit?: string | null; side?: string | null }): string {
  const { units, sides, colors } = storyIndex(doc);
  const sideId = mv.side ?? (mv.unit ? units.get(mv.unit)?.side : undefined);
  return (mv.unit && colors.get(mv.unit)) || (sideId && sides.get(sideId)?.color) || NEUTRAL_COLOR;
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

// ── routes, regions and places (schema 3) ─────────────────────────────────────

/** A route's width (px) with no value, and the range a value scales over. */
const ROUTE_WIDTH = { plain: 3, min: 2, span: 7 };
/** A place's radius (px) with no value, and the range a value scales over. */
const PLACE_RADIUS = { plain: 5, min: 4, span: 14 };

/** The step's routes, regions and places, ready for their sources. */
export interface FeatureSet {
  /** Region polygons (`role: 'area'`) and their label points (`role: 'label'`). */
  regions: FeatureCollection;
  routes: FeatureCollection;
  /** Place circles (`role: 'place'`) and state badges for all three (`role: 'badge'`). */
  places: FeatureCollection;
  /** region id → what its geometry was drawn from (by identity), to tell a reshape from a reshade. */
  regionRefs: Map<string, unknown>;
}

/** A GeoJSON geometry out of an entity's `geom` (a Feature or a bare geometry). */
export function asGeometry(geom: unknown): Geometry | null {
  if (!geom || typeof geom !== 'object') return null;
  const g = geom as { type?: string; geometry?: unknown };
  if (g.type === 'Feature') return asGeometry(g.geometry);
  return typeof g.type === 'string' && g.type !== 'FeatureCollection' ? (geom as Geometry) : null;
}

/** The first outer ring's centre of a Polygon / MultiPolygon. */
function polygonCentre(g: Geometry): LngLat | null {
  if (g.type === 'Polygon') return ringsCentre([g.coordinates[0] as LngLat[]]);
  if (g.type === 'MultiPolygon') return ringsCentre(g.coordinates.map((p) => p[0] as LngLat[]));
  return null;
}

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

/**
 * The step's routes, regions and places, from each feature and its state at
 * the step (`holds`). `active: false` hides one; `line`, `at`, `area` or an
 * entity's area (`areaGeoms`, entity id → geometry) replace its geometry.
 * Routes are as wide as their value, places as large; regions are shaded by
 * intensity. Colours: the holder's side, the feature's side, the palette.
 */
export function featureCollections(
  doc: MapStoryDocument,
  holds: Map<string, FeatureHold> | undefined,
  areaGeoms: Map<string, unknown> = new Map(),
): FeatureSet {
  const { sides, maxRoute, maxPlace } = storyIndex(doc);
  const regions: Feature[] = [];
  const labels: Feature[] = [];
  const routes: Feature[] = [];
  const places: Feature[] = [];
  const badges: Feature[] = [];
  const regionRefs = new Map<string, unknown>();

  for (const f of doc.features) {
    if (!DYNAMIC_FEATURE_KINDS.includes(f.kind)) continue;
    const h = holds?.get(f.id);
    if ((h?.active ?? f.active ?? true) === false) continue;
    const color = featureColor(sides, f, h?.held_by);
    const label = h?.label ?? f.label ?? '';
    const valueN = h?.value_n ?? f.value_n ?? null;
    const valueLabel = h?.value_label ?? f.value_label ?? '';
    const state = h?.state ?? '';
    const base = { id: f.id, kind: f.kind, color, label, value_label: valueLabel, state, conj: f.conjectural === true };
    let badgeAt: LngLat | null = null;

    if (f.kind === 'route') {
      const line = h?.line ?? f.line;
      if (!line || line.length < 2) continue;
      const disrupted = state === 'disrupted';
      const width = valueN != null && maxRoute > 0 ? ROUTE_WIDTH.min + ROUTE_WIDTH.span * Math.sqrt(Math.max(0, valueN) / maxRoute) : ROUTE_WIDTH.plain;
      routes.push({
        type: 'Feature',
        properties: {
          ...base,
          route_kind: f.route_kind ?? '',
          goods: f.goods.join(', '),
          width,
          disrupted,
          flow: !disrupted,
          bidir: f.bidirectional === true,
        },
        geometry: { type: 'LineString', coordinates: line },
      });
      badgeAt = along(line, 0.5);
    } else if (f.kind === 'region') {
      const entityId = h?.area_entity?.entity_id;
      const fromEntity = entityId ? asGeometry(areaGeoms.get(entityId)) : null;
      const area = h?.area ?? (h?.area_entity ? null : f.area);
      const geometry =
        fromEntity && (fromEntity.type === 'Polygon' || fromEntity.type === 'MultiPolygon') ? fromEntity : area ? areaGeometry(area) : null;
      if (!geometry) continue;
      const shade = 0.1 + 0.45 * clamp01(h?.intensity ?? f.intensity ?? 0.5);
      regions.push({
        type: 'Feature',
        properties: { ...base, role: 'area', region_kind: f.region_kind ?? '', shade, shade0: shade, xf: false },
        geometry,
      });
      regionRefs.set(f.id, fromEntity ?? area);
      badgeAt = (area && ringsCentre(area)) || polygonCentre(geometry);
      const text = [label, valueLabel].filter(Boolean).join('\n');
      if (text && badgeAt) {
        labels.push({ type: 'Feature', properties: { id: f.id, role: 'label', text, xf: false }, geometry: { type: 'Point', coordinates: badgeAt } });
      }
    } else {
      const at = h?.at ?? f.at;
      if (!at) continue;
      const radius =
        valueN != null && maxPlace > 0 ? PLACE_RADIUS.min + PLACE_RADIUS.span * Math.sqrt(Math.max(0, valueN) / maxPlace) : PLACE_RADIUS.plain;
      places.push({
        type: 'Feature',
        properties: { ...base, role: 'place', radius, text: [label, valueLabel].filter(Boolean).join('\n') },
        geometry: { type: 'Point', coordinates: at },
      });
      badgeAt = at;
    }

    // A captured feature flies its holder's flag; other states have a badge of their own.
    const holder = h?.held_by ? sides.get(h.held_by)?.color : undefined;
    if (badgeAt && state && state !== 'held' && (state !== 'captured' || holder)) {
      badges.push({
        type: 'Feature',
        properties: { id: f.id, role: 'badge', icon: terrainStateId(state, holder ?? '') },
        geometry: { type: 'Point', coordinates: badgeAt },
      });
    }
  }
  // Small circles over large ones.
  places.sort((a, b) => (b.properties?.radius ?? 0) - (a.properties?.radius ?? 0));
  return {
    regions: { type: 'FeatureCollection', features: [...regions, ...labels] },
    routes: { type: 'FeatureCollection', features: routes },
    places: { type: 'FeatureCollection', features: [...places, ...badges] },
    regionRefs,
  };
}

/** Every coordinate of a step's routes, regions and places (for framing it). */
export function featurePoints(set: FeatureSet): LngLat[] {
  const pts: LngLat[] = [];
  const walk = (c: unknown): void => {
    if (!Array.isArray(c)) return;
    if (typeof c[0] === 'number') pts.push(c as LngLat);
    else for (const x of c) walk(x);
  };
  for (const fc of [set.regions, set.routes, set.places]) {
    for (const f of fc.features) if (f.geometry.type !== 'GeometryCollection') walk(f.geometry.coordinates);
  }
  return pts;
}

/** Regions on screen: id → the geometry they were drawn from, and their shade. */
export type ShownRegions = Map<string, { ref: unknown; shade: number; feature: Feature; label: Feature | null }>;

/**
 * The step change from the regions `shown` to `next`: regions reshaped or new
 * fade in (`xf`), those whose geometry is the same reshade from `shade0`, and
 * the old shapes of reshaped or dropped regions fade out (`old`).
 */
export function regionTransition(
  shown: ShownRegions,
  next: FeatureSet,
): { current: FeatureCollection; old: FeatureCollection; shown: ShownRegions; changed: boolean } {
  const out: ShownRegions = new Map();
  const current: Feature[] = [];
  const labels: Feature[] = [];
  const old: Feature[] = [];
  let changed = false;
  const labelOf = new Map<string, Feature>();
  for (const f of next.regions.features) if (f.properties?.role === 'label') labelOf.set(f.properties.id, f);

  for (const f of next.regions.features) {
    if (f.properties?.role !== 'area') continue;
    const id: string = f.properties.id;
    const ref = next.regionRefs.get(id);
    const prev = shown.get(id);
    const same = prev != null && prev.ref === ref;
    const shade: number = f.properties.shade;
    if (!same || prev.shade !== shade) changed = true;
    const feature: Feature = { ...f, properties: { ...f.properties, xf: !same, shade0: same ? prev.shade : shade } };
    const label = labelOf.get(id) ?? null;
    current.push(feature);
    if (label) labels.push({ ...label, properties: { ...label.properties, xf: !same || prev.label?.properties?.text !== label.properties?.text } });
    out.set(id, { ref, shade, feature: f, label });
  }
  for (const [id, prev] of shown) {
    const now = out.get(id);
    if (now && now.ref === prev.ref) continue;
    changed = true;
    old.push(prev.feature);
  }
  return {
    current: { type: 'FeatureCollection', features: [...current, ...labels] },
    old: { type: 'FeatureCollection', features: old },
    shown: out,
    changed,
  };
}

/** The step's `show` entities, drawn from their atlas geometry (aligned `geoms`). */
/**
 * The shown step entities whose geometry the player fetches (their undated
 * `geom`): those without a `geometry` of their own, i.e. stories saved before
 * sync added it and admin preview drafts.
 */
export function stepEntityFetchIds(entities: StoryStepEntity[]): string[] {
  return entities.filter((e) => e.geometry === undefined && e.entity_id).map((e) => e.entity_id as string);
}

/**
 * Each shown step entity's geometry: its own `geometry` (sync's atlas geometry
 * at the step's date; null draws nothing), else the one fetched for it
 * (`fetched`, aligned to stepEntityFetchIds).
 */
export function stepEntityGeoms(entities: StoryStepEntity[], fetchIds: string[], fetched: unknown[]): unknown[] {
  return entities.map((e) => {
    const i = e.entity_id ? fetchIds.indexOf(e.entity_id) : -1;
    const geom = e.geometry !== undefined ? e.geometry : i >= 0 ? (fetched[i] ?? null) : null;
    // An entity outlined on OHM's boundaries (`ohm`) needs no dot of its own.
    const g = asGeometry(geom);
    return e.ohm?.length && g?.type !== 'Polygon' && g?.type !== 'MultiPolygon' ? null : geom;
  });
}

// ── the step's entities outlined on OpenHistoricalMap's boundary polygons ──
//
// OHM's general `ohm` tiles carry boundary *lines* by way id, which can't be
// matched to a polity; its `ohm_admin` tiles carry the boundary polygons with
// a signed `osm_id` (negative: the relation id). The outline layers read
// those tiles (heavy, so only while a step outlines something), filtered to
// the step's boundaries and to the step's date the way the basemap is.

/** OHM's boundary-polygon tiles (`boundaries` layer; heavy: about 1.3 MB a tile at z5). */
const OHM_ADMIN_TILES = 'https://vtiles.openhistoricalmap.org/maps/ohm_admin/{z}/{x}/{y}.pbf';
/** The style's own `ohm_admin` source, when it has one, is used instead of ours. */
const STYLE_OHM_ADMIN_SOURCE = 'ohm_admin';
export const OHM_ADMIN_SOURCE_LAYER = 'boundaries';
export const OHM_OUTLINE_LAYERS = ['story-ohm-fill', 'story-ohm-line'];

/** "relation/123" → -123, "way/456" → 456 (OHM's signed `osm_id`); anything else is dropped. */
export function ohmOsmIds(refs: string[]): number[] {
  const ids = new Set<number>();
  for (const ref of refs) {
    const m = /^(relation|way)\/(\d+)$/.exec(ref);
    if (m) ids.add(m[1] === 'relation' ? -Number(m[2]) : Number(m[2]));
  }
  return [...ids];
}

/** The outline layers' filter: these boundaries, current at `date` (an OHM date string); null for none. */
export function ohmOutlineFilter(ids: number[], date: string | null): FilterSpecification | null {
  if (ids.length === 0 || !date) return null;
  const byId: ExpressionSpecification = ['in', ['to-number', ['get', 'osm_id']], ['literal', ids]];
  return ohmDateFilter(date, byId, { includeUndated: true });
}

/**
 * Outline the step's OHM boundaries (`ids`, signed) as they stood at `date`,
 * styled like the step's highlighted entities; with none, remove the layers
 * (and our tile source, so its tiles stop loading).
 */
export function setOhmOutline(map: MapLibreMap, ids: number[], date: string | null): void {
  const filter = ohmOutlineFilter(ids, date);
  if (!filter) {
    for (const id of OHM_OUTLINE_LAYERS) if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource(STORY_SOURCES.ohmAdmin)) map.removeSource(STORY_SOURCES.ohmAdmin);
    return;
  }
  if (map.getLayer(OHM_OUTLINE_LAYERS[0])) {
    for (const id of OHM_OUTLINE_LAYERS) map.setFilter(id, filter);
    return;
  }
  let source = STYLE_OHM_ADMIN_SOURCE;
  if (!map.getSource(source)) {
    source = STORY_SOURCES.ohmAdmin;
    if (!map.getSource(source)) {
      // From z0: a world-wide story (an epidemic) frames below z2. (About 1–1.5 MB a tile there.)
      map.addSource(source, { type: 'vector', tiles: [OHM_ADMIN_TILES], minzoom: 0, maxzoom: 14 });
    }
  }
  // Under everything of the story's, like the step's own entities.
  const before = map.getLayer('story-entity-fill') ? 'story-entity-fill' : undefined;
  const common = { source, 'source-layer': OHM_ADMIN_SOURCE_LAYER, filter } as const;
  map.addLayer({ id: OHM_OUTLINE_LAYERS[0], type: 'fill', ...common, paint: { 'fill-color': ENTITY_HIGHLIGHT, 'fill-opacity': 0.08 } }, before);
  map.addLayer(
    {
      id: OHM_OUTLINE_LAYERS[1],
      type: 'line',
      ...common,
      layout: { 'line-join': 'round' },
      paint: { 'line-color': ENTITY_HIGHLIGHT, 'line-opacity': 0.8, 'line-width': 1.8, 'line-dasharray': [3, 1.5] },
    },
    before,
  );
}

export function entityCollection(entities: StoryStepEntity[], geoms: unknown[]): FeatureCollection {
  const features: Feature[] = [];
  entities.forEach((e, i) => {
    const geometry = asGeometry(geoms[i]);
    if (!geometry) return;
    features.push({ type: 'Feature', properties: { name: e.name, role: 'shape' }, geometry });
    const at = geometry.type === 'Point' ? null : polygonCentre(geometry);
    if (at) features.push({ type: 'Feature', properties: { name: e.name, role: 'label' }, geometry: { type: 'Point', coordinates: at } });
  });
  return { type: 'FeatureCollection', features };
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

/** The step's own entities, drawn from the atlas under the story. */
const ENTITY_HIGHLIGHT = '#4338ca';

const role = (r: string): ExpressionSpecification => ['==', ['get', 'role'], r];

/** Battlefield relief: a hillshade under the basemap's labels, and today's
 *  water and village names, faint, for orientation. */
function addRelief(map: MapLibreMap): void {
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

}

/** A region's fill opacity `t` (0–1) of the way through a step change:
 *  reshaped ones fade in, reshaded ones blend from `shade0` to `shade`. */
const regionShade = (t: number): ExpressionSpecification => [
  'case',
  ['==', ['get', 'xf'], true],
  ['*', ['get', 'shade'], t],
  ['+', ['get', 'shade0'], ['*', ['-', ['get', 'shade'], ['get', 'shade0']], t]],
];
const fadeIn = (t: number, v: number): ExpressionSpecification => ['case', ['==', ['get', 'xf'], true], v * t, v];

/** The flowing dashes of a route: one period of a 3-on/4-off pattern in 14
 *  phases (MapLibre's "animate a line" sequence), stepped to make them move. */
export const ROUTE_DASHES: number[][] = [
  [0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0],
  [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5],
];

/**
 * Add the overlay's sources and layers on top of the current style
 * (idempotent). With `relief` (battlefields), a hillshade goes under the
 * basemap's labels so terrain reads at battlefield zoom, where the historical
 * styles have no relief, with today's water and place names over it.
 */
export function addStoryLayers(map: MapLibreMap, { relief = true }: { relief?: boolean } = {}): void {
  if (map.getSource(STORY_SOURCES.units)) return;
  if (relief) addRelief(map);

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

  // ── the step's entities, from the atlas, under everything of the story's ──
  const shape = role('shape');
  map.addLayer({
    id: 'story-entity-fill',
    type: 'fill',
    source: STORY_SOURCES.entities,
    filter: ['all', shape, ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false]],
    paint: { 'fill-color': ENTITY_HIGHLIGHT, 'fill-opacity': 0.1 },
  });
  map.addLayer({
    id: 'story-entity-line',
    type: 'line',
    source: STORY_SOURCES.entities,
    filter: ['all', shape, ['!=', ['geometry-type'], 'Point']],
    layout: { 'line-join': 'round' },
    paint: { 'line-color': ENTITY_HIGHLIGHT, 'line-opacity': 0.8, 'line-width': 1.8, 'line-dasharray': [3, 1.5] },
  });
  map.addLayer({
    id: 'story-entity-dot',
    type: 'circle',
    source: STORY_SOURCES.entities,
    filter: ['all', shape, ['==', ['geometry-type'], 'Point']],
    paint: { 'circle-radius': 6, 'circle-color': ENTITY_HIGHLIGHT, 'circle-opacity': 0.25, 'circle-stroke-color': ENTITY_HIGHLIGHT, 'circle-stroke-width': 2 },
  });

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

  // ── regions: the old shapes fade out as the new ones fade in ──
  const isPolygon: FilterSpecification = ['all', role('area'), ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false]];
  const regionEdge = (opacity: ExpressionSpecification | number) => ({
    'line-color': ['get', 'color'] as ExpressionSpecification,
    'line-opacity': opacity,
    'line-width': 1.3,
  });
  map.addLayer({ id: 'story-region-old-fill', type: 'fill', source: STORY_SOURCES.regionsOld, filter: isPolygon, paint: { 'fill-color': ['get', 'color'], 'fill-opacity': ['get', 'shade'] } });
  map.addLayer({ id: 'story-region-old-edge', type: 'line', source: STORY_SOURCES.regionsOld, filter: isPolygon, paint: regionEdge(REGION_EDGE) });
  map.addLayer({ id: 'story-region-fill', type: 'fill', source: STORY_SOURCES.regions, filter: isPolygon, paint: { 'fill-color': ['get', 'color'], 'fill-opacity': regionShade(1) } });
  map.addLayer({ id: 'story-region-edge', type: 'line', source: STORY_SOURCES.regions, filter: ['all', isPolygon, notConj], paint: regionEdge(fadeIn(1, REGION_EDGE)) });
  map.addLayer({
    id: 'story-region-edge-conj',
    type: 'line',
    source: STORY_SOURCES.regions,
    filter: ['all', isPolygon, conj],
    paint: { ...regionEdge(fadeIn(1, REGION_EDGE)), 'line-dasharray': [3, 2] },
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

  // ── routes: a pale line with dashes flowing along it (both ways when bidirectional) ──
  const width: ExpressionSpecification = ['get', 'width'];
  const bidir: ExpressionSpecification = ['==', ['get', 'bidir'], true];
  const disrupted: ExpressionSpecification = ['==', ['get', 'disrupted'], true];
  map.addLayer({
    id: 'story-route-casing',
    type: 'line',
    source: STORY_SOURCES.routes,
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#fffdf5', 'line-opacity': conjFade(0.55, 0.3), 'line-width': ['+', width, 2.5] },
  });
  map.addLayer({
    id: 'story-route-base',
    type: 'line',
    source: STORY_SOURCES.routes,
    filter: ['!', disrupted],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': ['get', 'color'], 'line-opacity': conjFade(0.32, 0.2), 'line-width': width },
  });
  map.addLayer({
    id: 'story-route-disrupted',
    type: 'line',
    source: STORY_SOURCES.routes,
    filter: disrupted,
    paint: { 'line-color': DISRUPTED_COLOR, 'line-opacity': 0.9, 'line-width': width, 'line-dasharray': [1.6, 1.2] },
  });
  const flow = (back: boolean) => ({
    'line-color': ['get', 'color'] as ExpressionSpecification,
    'line-opacity': conjFade(0.95, 0.6),
    'line-width': ['case', bidir, ['*', width, 0.55], width] as ExpressionSpecification,
    'line-offset': ['case', bidir, ['*', width, back ? -0.35 : 0.35], 0] as ExpressionSpecification,
    'line-dasharray': ROUTE_DASHES[0],
    'line-dasharray-transition': { duration: 0, delay: 0 },
  });
  map.addLayer({ id: 'story-route-flow', type: 'line', source: STORY_SOURCES.routes, filter: ['==', ['get', 'flow'], true], paint: flow(false) });
  map.addLayer({ id: 'story-route-flow-back', type: 'line', source: STORY_SOURCES.routes, filter: ['all', ['==', ['get', 'flow'], true], bidir], paint: flow(true) });

  // ── places: circles sized by their value ──
  map.addLayer({
    id: 'story-place-circle',
    type: 'circle',
    source: STORY_SOURCES.places,
    filter: role('place'),
    paint: {
      'circle-radius': ['get', 'radius'],
      'circle-color': ['get', 'color'],
      'circle-opacity': conjFade(0.72, 0.4),
      'circle-stroke-color': '#fffdf5',
      'circle-stroke-width': 1.6,
      'circle-stroke-opacity': conjFade(1, 0.6),
    },
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

  // Place and region labels, values beside them, and their state badges.
  const featureText = {
    'text-color': '#292524',
    'text-halo-color': 'rgba(255,253,245,0.95)',
    'text-halo-width': 1.6,
  };
  map.addLayer({
    id: 'story-region-label',
    type: 'symbol',
    source: STORY_SOURCES.regions,
    filter: role('label'),
    layout: { 'text-field': ['get', 'text'], 'text-size': 12, 'text-font': FONT_ITALIC, 'text-max-width': 10, 'text-optional': true },
    paint: { ...featureText, 'text-opacity': fadeIn(1, 1) },
  });
  map.addLayer({
    id: 'story-place-label',
    type: 'symbol',
    source: STORY_SOURCES.places,
    filter: role('place'),
    layout: {
      'text-field': ['get', 'text'],
      'text-size': 11.5,
      'text-font': FONT_BOLD,
      'text-radial-offset': ['+', 0.5, ['/', ['get', 'radius'], 11.5]],
      'text-variable-anchor': ['left', 'right', 'top', 'bottom'],
      'text-max-width': 10,
      'text-optional': true,
    },
    paint: featureText,
  });
  map.addLayer({
    id: 'story-entity-label',
    type: 'symbol',
    source: STORY_SOURCES.entities,
    filter: ['==', ['geometry-type'], 'Point'],
    layout: {
      'text-field': ['get', 'name'],
      'text-size': 12,
      'text-font': FONT_ITALIC,
      'text-variable-anchor': ['left', 'right', 'top', 'bottom'],
      'text-radial-offset': ['case', ['==', ['get', 'role'], 'label'], 0, 0.9],
      'text-max-width': 10,
      'text-optional': true,
    },
    paint: { 'text-color': ENTITY_HIGHLIGHT, 'text-halo-color': 'rgba(255,253,245,0.92)', 'text-halo-width': 1.6 },
  });
  map.addLayer({
    id: 'story-feature-badges',
    type: 'symbol',
    source: STORY_SOURCES.places,
    filter: role('badge'),
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-size': 0.6,
      'icon-offset': [-16, -16],
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
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
  SHOWN_REGION_FADE.delete(map);
  SHOWN_DASH.delete(map);
}

/** Region opacity per layer at full strength. */
const REGION_EDGE = 0.75;

/** Where each map's region crossfade and route dashes were last set, so a frame that changes nothing sends nothing. */
const SHOWN_REGION_FADE = new WeakMap<MapLibreMap, number>();
const SHOWN_DASH = new WeakMap<MapLibreMap, number>();

/**
 * Set the regions `t` (0–1) of the way through a step change: new and
 * reshaped regions fade in while the old shapes fade out (a crossfade over two
 * sources), and regions that only change shade blend from the old to the new.
 */
export function setRegionFade(map: MapLibreMap, t: number): void {
  if (SHOWN_REGION_FADE.get(map) === t || !map.getLayer('story-region-fill')) return;
  SHOWN_REGION_FADE.set(map, t);
  map.setPaintProperty('story-region-fill', 'fill-opacity', regionShade(t));
  map.setPaintProperty('story-region-edge', 'line-opacity', fadeIn(t, REGION_EDGE));
  map.setPaintProperty('story-region-edge-conj', 'line-opacity', fadeIn(t, REGION_EDGE));
  map.setPaintProperty('story-region-label', 'text-opacity', fadeIn(t, 1));
  map.setPaintProperty('story-region-old-fill', 'fill-opacity', ['*', ['get', 'shade'], 1 - t]);
  map.setPaintProperty('story-region-old-edge', 'line-opacity', REGION_EDGE * (1 - t));
}

/** Show phase `k` of the routes' flowing dashes (the back layer runs the other way). */
export function setRouteDash(map: MapLibreMap, k: number): void {
  const n = ROUTE_DASHES.length;
  const phase = ((k % n) + n) % n;
  if (SHOWN_DASH.get(map) === phase || !map.getLayer('story-route-flow')) return;
  SHOWN_DASH.set(map, phase);
  map.setPaintProperty('story-route-flow', 'line-dasharray', ROUTE_DASHES[phase]);
  map.setPaintProperty('story-route-flow-back', 'line-dasharray', ROUTE_DASHES[(n - phase) % n]);
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

// ── ambient mode: stories faint on the plain atlas ───────────────────────────

export const AMBIENT_SOURCE = 'ambient-stories';
export const AMBIENT_LAYERS = {
  fill: 'ambient-region-fill',
  edge: 'ambient-region-edge',
  route: 'ambient-route',
  place: 'ambient-place',
} as const;
/** Ambient layers a pointer can hover (story title) and click ("Play" card), topmost first. */
export const AMBIENT_INTERACTIVE_LAYERS: string[] = [AMBIENT_LAYERS.place, AMBIENT_LAYERS.route, AMBIENT_LAYERS.fill];

/**
 * Every ambient story's features in one collection, each tagged with its
 * story (`story`, `title`, `step`, `step_title`) and sized against the
 * largest value in view: faint shades, thin routes, small circles.
 */
export function ambientCollection(stories: AmbientStory[]): FeatureCollection {
  let maxRoute = 0;
  let maxPlace = 0;
  for (const s of stories) {
    for (const f of s.features.features) {
      const v = f.properties?.value_n;
      if (typeof v !== 'number') continue;
      if (f.geometry?.type === 'LineString') maxRoute = Math.max(maxRoute, v);
      else if (f.geometry?.type === 'Point') maxPlace = Math.max(maxPlace, v);
    }
  }
  const features: Feature[] = [];
  for (const s of stories) {
    for (const f of s.features.features) {
      if (!f.geometry) continue;
      const p = f.properties ?? {};
      const v = typeof p.value_n === 'number' ? p.value_n : null;
      const intensity = typeof p.intensity === 'number' ? p.intensity : 0.5;
      features.push({
        type: 'Feature',
        geometry: f.geometry,
        properties: {
          id: p.id ?? '',
          label: p.label ?? '',
          color: typeof p.color === 'string' && p.color ? p.color : NEUTRAL_COLOR,
          disrupted: p.state === 'disrupted',
          shade: 0.05 + 0.17 * clamp01(intensity),
          width: v != null && maxRoute > 0 ? 1 + 3 * Math.sqrt(Math.max(0, v) / maxRoute) : 1.6,
          radius: v != null && maxPlace > 0 ? 2.5 + 6 * Math.sqrt(Math.max(0, v) / maxPlace) : 3,
          story: s.slug,
          kind: s.kind,
          title: s.title,
          step: s.step_index,
          step_title: s.step_title ?? '',
        },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}

/** Add the ambient source and layers under `beforeId` (the entity overlay), idempotently. */
export function addAmbientLayers(map: MapLibreMap, beforeId: string | undefined): void {
  if (map.getSource(AMBIENT_SOURCE)) return;
  map.addSource(AMBIENT_SOURCE, { type: 'geojson', data: EMPTY });
  const polygon: FilterSpecification = ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false];
  const color: ExpressionSpecification = ['get', 'color'];
  map.addLayer({ id: AMBIENT_LAYERS.fill, type: 'fill', source: AMBIENT_SOURCE, filter: polygon, paint: { 'fill-color': color, 'fill-opacity': ['get', 'shade'] } }, beforeId);
  map.addLayer({ id: AMBIENT_LAYERS.edge, type: 'line', source: AMBIENT_SOURCE, filter: polygon, paint: { 'line-color': color, 'line-opacity': 0.3, 'line-width': 0.8 } }, beforeId);
  map.addLayer(
    {
      id: AMBIENT_LAYERS.route,
      type: 'line',
      source: AMBIENT_SOURCE,
      filter: ['==', ['geometry-type'], 'LineString'],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ['case', ['==', ['get', 'disrupted'], true], DISRUPTED_COLOR, color],
        'line-opacity': 0.45,
        'line-width': ['get', 'width'],
      },
    },
    beforeId,
  );
  map.addLayer(
    {
      id: AMBIENT_LAYERS.place,
      type: 'circle',
      source: AMBIENT_SOURCE,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': ['get', 'radius'],
        'circle-color': color,
        'circle-opacity': 0.5,
        'circle-stroke-color': '#fffdf5',
        'circle-stroke-width': 0.8,
        'circle-stroke-opacity': 0.7,
      },
    },
    beforeId,
  );
}

export function removeAmbientLayers(map: MapLibreMap): void {
  for (const id of Object.values(AMBIENT_LAYERS)) if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(AMBIENT_SOURCE)) map.removeSource(AMBIENT_SOURCE);
}

export function setAmbientVisible(map: MapLibreMap, visible: boolean): void {
  for (const id of Object.values(AMBIENT_LAYERS)) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
  }
}

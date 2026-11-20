/**
 * What the chronicle player draws on the map for a step (pure; no MapLibre).
 *
 * A step's primary relationship decides the look: a battle is a red arc from
 * the side to the battlefield, a succession a dashed violet one, and "who
 * controls what" an outlined territory rather than a line. Around it: the
 * step's other placed entities, those who took part joined to the step's
 * anchor (where it happens) by faint spokes, the OpenHistoricalMap borders of
 * its polities at the step's year, and the trail of the last few steps.
 *
 * A step that follows something spreading (a disease, a religion, a crop) is
 * drawn as that spread instead: a teal arc to each place the step says it
 * reached, each from the nearest place it had reached before. Which places it
 * reached is recorded (`reaches`); the way it took is not, and "from the
 * nearest place it had already reached" is this layer's reading of it.
 *
 * Geometry comes from GET /chronicles/{slug}/places (`Places`): an entity is
 * drawn only where the atlas places it.
 */
import type { Feature, FeatureCollection, LineString, Point } from 'geojson';
import type { ChronicleEntry, ChroniclePlace } from '@/lib/schemas/chronicle';
import type { LngLat } from '@/lib/schemas/map-story';

export type Places = ReadonlyMap<string, ChroniclePlace>;

export type RelationKind =
  | 'conflict'
  | 'flow'
  | 'succession'
  | 'control'
  | 'life'
  | 'alliance'
  | 'link'
  | 'none';

/** Line colours, chosen for the (always light) historical basemaps. */
export const KIND_COLOR: Record<RelationKind, string> = {
  conflict: '#b91c1c',
  flow: '#0f766e',
  succession: '#7c3aed',
  control: '#4338ca',
  life: '#b45309',
  alliance: '#0369a1',
  link: '#57534e',
  none: '#57534e',
};

/** What the reader sees for each kind, in the step panel's legend. */
export const KIND_LABEL: Record<RelationKind, string> = {
  conflict: 'Conflict',
  flow: 'Spread or exchange',
  succession: 'Succession',
  control: 'Rule or territory',
  life: 'A life or a founding',
  alliance: 'Alliance',
  link: 'Connection',
  none: 'Not a place-to-place link',
};

const KIND_BY_TYPE: Record<string, RelationKind> = {
  victorious_at: 'conflict',
  defeated_at: 'conflict',
  fought_at: 'conflict',
  at_war_with: 'conflict',
  destroyed_by: 'conflict',
  assassinated_by: 'conflict',
  persecuted_by: 'conflict',
  violated_by: 'conflict',
  weakened: 'conflict',

  spread_to: 'flow',
  adopted: 'flow',
  influenced_by: 'flow',
  trades_with: 'flow',
  connects: 'flow',
  supplies: 'flow',
  produces: 'flow',
  extracts: 'flow',
  used_currency: 'flow',
  passes_through: 'flow',

  succeeded_by: 'succession',
  preceded_by: 'succession',
  replaced_by: 'succession',
  merged_into: 'succession',
  split_from: 'succession',
  restored_by: 'succession',

  located_at: 'control',
  part_of: 'control',
  rules: 'control',
  controlled_by: 'control',
  capital_of: 'control',
  vassal_of: 'control',
  suzerain_of: 'control',
  governed_by: 'control',
  contains: 'control',
  stationed_at: 'control',
  official_religion_of: 'control',
  minted_by: 'control',
  enforced_by: 'control',

  founded: 'life',
  resided_in: 'life',
  died_in: 'life',
  born_in: 'life',
  built_by: 'life',
  taught_at: 'life',

  allied_with: 'alliance',
  enabled: 'alliance',
  strengthened: 'alliance',

  authored: 'none',
  signed_by: 'none',
  commissioned: 'none',
  invented: 'none',
  child_of: 'none',
  parent_of: 'none',
  sibling_of: 'none',
  married_to: 'none',
  member_of_dynasty: 'none',
  adheres_to: 'none',
  patron_of: 'none',
  student_of: 'none',
  mentor_of: 'none',
  required_by: 'none',
  resulted_from: 'none',
  prevented: 'none',
};

/** Read target → source: "X destroyed_by Y" travels from Y to X. */
const REVERSED = new Set([
  'preceded_by',
  'built_by',
  'destroyed_by',
  'assassinated_by',
  'persecuted_by',
  'violated_by',
  'influenced_by',
  'commanded_by',
  'governed_by',
  'controlled_by',
  'minted_by',
  'enforced_by',
  'restored_by',
]);

/** Either way at once: no arrowhead. */
const MUTUAL = new Set(['at_war_with', 'allied_with', 'trades_with', 'connects']);

/** Event types that make "took part in" / "commanded" a fight. */
const FIGHT_TYPES = /battle|siege|war|invasion|campaign|rebellion|revolt|uprising|massacre|conflict|raid|conquest/;

/**
 * The kind of a relationship type. `participated_in` and `commanded(_by)`
 * are a conflict when an end is a fight (a battle, a siege…), else a plain link.
 */
export function relationKind(type: string | null | undefined, endTypes: (string | null | undefined)[] = []): RelationKind {
  if (!type) return 'link';
  if (type === 'participated_in' || type === 'commanded' || type === 'commanded_by' || type === 'contributed_to') {
    return endTypes.some((t) => t && FIGHT_TYPES.test(t)) ? 'conflict' : 'link';
  }
  return KIND_BY_TYPE[type] ?? 'link';
}

// ── geometry ──────────────────────────────────────────────────────────────────

const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;
/** Two points closer than this are one place: no line between them. */
export const MIN_LINE_KM = 3;

const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (Math.max(-85, Math.min(85, lat)) * D2R) / 2)) * R2D;
const latOf = (y: number) => (2 * Math.atan(Math.exp(y * D2R)) - Math.PI / 2) * R2D;

/** Great-circle distance in km. */
export function distanceKm(a: LngLat, b: LngLat): number {
  const dLat = (b[1] - a[1]) * D2R;
  const dLng = (b[0] - a[0]) * D2R;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * D2R) * Math.cos(b[1] * D2R) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** `b`'s longitude shifted by 360° if that takes the short way from `a` (across the antimeridian). */
export function unwrap(a: LngLat, b: LngLat): LngLat {
  const d = b[0] - a[0];
  return d > 180 ? [b[0] - 360, b[1]] : d < -180 ? [b[0] + 360, b[1]] : b;
}

/**
 * A gentle arc from `a` to `b` (a quadratic curve in Web Mercator, bowed to
 * the left of travel by `bend` × its length), as `n + 1` points. Takes the
 * short way across the antimeridian (longitudes may leave ±180).
 */
export function arcPath(a: LngLat, b: LngLat, bend = 0.18, n = 48): LngLat[] {
  const to = unwrap(a, b);
  const x0 = a[0];
  const y0 = mercY(a[1]);
  const x2 = to[0];
  const y2 = mercY(to[1]);
  const dx = x2 - x0;
  const dy = y2 - y0;
  const cx = (x0 + x2) / 2 - dy * bend;
  const cy = (y0 + y2) / 2 + dx * bend;
  const out: LngLat[] = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const u = 1 - t;
    const x = u * u * x0 + 2 * u * t * cx + t * t * x2;
    const y = u * u * y0 + 2 * u * t * cy + t * t * y2;
    out.push([x, latOf(y)]);
  }
  out[0] = a;
  out[n] = to;
  return out;
}

/** The map bearing (degrees clockwise from north) of travel from `a` to `b`, as drawn in Web Mercator. */
export function screenBearing(a: LngLat, b: LngLat): number {
  return (Math.atan2(b[0] - a[0], mercY(b[1]) - mercY(a[1])) * R2D + 360) % 360;
}

// ── a step ────────────────────────────────────────────────────────────────────

/** A GeoJSON point's coordinates (a Point, or a Feature holding one), else null. */
function pointOf(geom: unknown): LngLat | null {
  if (!geom || typeof geom !== 'object') return null;
  const g = geom as { type?: string; coordinates?: unknown; geometry?: unknown };
  if (g.type === 'Feature') return pointOf(g.geometry);
  if (g.type !== 'Point' || !Array.isArray(g.coordinates)) return null;
  const [x, y] = g.coordinates as number[];
  return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
}

const PLACE_GROUPS = new Set(['event', 'place']);

/** One entity of the step, as drawn. */
export interface CastMember {
  id: string;
  name: string;
  /** Uppercase entity group, for the marker icon (`marker-POLITY`…). */
  group: string;
  at: LngLat;
  /** An end of the step's primary relationship. */
  primary: boolean;
  /**
   * Drawn in the step's colour with a full ring: an end of the relationship,
   * a place the spread reached, or one of several places the step names.
   */
  marked: boolean;
}

export type StepArc = Feature<LineString, { kind: RelationKind; color: string; dashed: boolean }>;

export interface StepScene {
  kind: RelationKind;
  color: string;
  /** Where the step happens: the point the camera and the trail lead to. */
  anchor: LngLat | null;
  /**
   * The step's lines. One for the primary relationship, source → target (or
   * reversed, see REVERSED), when both ends are placed apart. Or, for a step
   * drawn as a spread, one to each place it reached, from the nearest place
   * it had reached before.
   */
  arcs: StepArc[];
  /** An arrowhead at the end of each arc that has a direction. */
  arrows: { at: LngLat; bearing: number }[];
  /** The arcs start at a polity, whose point is only somewhere inside a realm: they fade in from there. */
  soft: boolean;
  /** Where the step's rings ripple: its anchor, or each place of a step that names several. */
  pulses: LngLat[];
  /** Faint lines to the anchor from those who took part there. */
  spokes: Feature<LineString>[];
  /** Every placed entity of the step. */
  cast: CastMember[];
  /** OHM boundaries (signed ids) to outline at the step's year: those in the step's colour, then the rest. */
  areas: { primary: number[]; other: number[] };
}

/** At most this many spokes, arcs of a spread and outlined other borders per step. */
const MAX_SPOKES = 8;
const MAX_FAN = 8;
const MAX_OTHER_AREAS = 6;
/** At most this many borders per entity in a year (as the map stories). */
const MAX_BORDERS = 4;

/**
 * An entity's OHM boundaries standing in `year`: those whose years cover it
 * (an open end covers), the primary ones when any covers, else the rest in
 * match order. None without a year.
 */
export function bordersAt(place: ChroniclePlace | undefined, year: number | null): number[] {
  if (!place || year == null) return [];
  const covering = place.borders.filter((b) => (b.from == null || b.from <= year) && (b.to == null || b.to >= year));
  const primary = covering.filter((b) => b.primary);
  return (primary.length > 0 ? primary : covering).slice(0, MAX_BORDERS).map((b) => b.id);
}

/** The arc stops short of the target's marker by this share of its length, for the arrowhead. */
const ARROW_GAP = 0.035;

/**
 * Where a step happens: an entity with the `location` role, else an end of
 * its relationship that is an event or a place (the battlefield, the city),
 * else any event or place in it, else its enriched approximate location, else
 * any placed entity in it.
 */
export function stepAnchor(entry: ChronicleEntry, places: Places): LngLat | null {
  const at = (id: string | undefined | null) => (id ? (places.get(id)?.at ?? null) : null);
  const isPlace = (id: string | undefined | null) => !!id && PLACE_GROUPS.has(places.get(id)?.group ?? '');
  const rel = entry.primary_relationship;
  const secondary = entry.secondary_entities ?? [];

  for (const e of secondary) if (e.role === 'location' && at(e.entity_id)) return at(e.entity_id);
  for (const id of [rel?.target_entity_id, rel?.source_entity_id]) if (isPlace(id) && at(id)) return at(id);
  for (const e of secondary) if (isPlace(e.entity_id) && at(e.entity_id)) return at(e.entity_id);
  const approx = pointOf(entry.approximate_location);
  if (approx) return approx;
  for (const id of [rel?.target_entity_id, rel?.source_entity_id, ...secondary.map((e) => e.entity_id)]) {
    if (at(id)) return at(id);
  }
  return null;
}

const upper = (g: string | null | undefined) => (g ? g.toUpperCase() : 'DEFAULT');

/** Every entity of a step: the relationship's ends first, then the others, each once. */
function stepEntityIds(entry: ChronicleEntry): string[] {
  const rel = entry.primary_relationship;
  const ids = [rel?.source_entity_id, rel?.target_entity_id, ...(entry.secondary_entities ?? []).map((e) => e.entity_id)];
  return [...new Set(ids.filter((id): id is string => !!id))];
}

// ── a spread ──────────────────────────────────────────────────────────────────

/** Two points closer than this are one place for a ring: a town and its harbour. */
export const SAME_PLACE_KM = 25;

/** `points` without those within `SAME_PLACE_KM` of an earlier one. */
function distinctPlaces(points: LngLat[]): LngLat[] {
  const out: LngLat[] = [];
  for (const p of points) if (!out.some((q) => distanceKm(p, q) < SAME_PLACE_KM)) out.push(p);
  return out;
}

/** A place something reached, as an end of an arc. */
export interface ReachedSite {
  id: string;
  at: LngLat;
  /** A polity's point: only somewhere inside its realm. */
  soft: boolean;
}

/** What a step says about something spreading. */
export interface StepSpread {
  /** The thing that spreads. */
  carrier: string;
  /** The step's entities it is recorded as reaching, placed or not. */
  reached: string[];
  /** Those of them with a map point: an arc ends at each. */
  sites: ReachedSite[];
}

/** A recorded link is this step's when it has no year, or one within this many years of the step's. */
export const LINK_YEARS = 10;

/**
 * Whether a link of year `year` belongs to the step. The same two entities
 * can meet again in a step a century on (yellow fever reached the United
 * States in 1793; a step of 1904 names both for another reason).
 */
function inStepYears(year: number | null, entry: ChronicleEntry): boolean {
  if (year == null || entry.start_year == null) return true;
  const end = Math.max(entry.end_year ?? entry.start_year, entry.start_year);
  return year >= entry.start_year - LINK_YEARS && year <= end + LINK_YEARS;
}

/**
 * What a step says `carrier` reached: the step's entities among the carrier's
 * recorded `reaches` of those years. The arcs end at the places it names (a
 * city, a port); a step that names none ends them at whatever is placed (a
 * realm's point). Null when the carrier is not in the step or reached nothing
 * in it.
 */
export function spreadOf(entry: ChronicleEntry, places: Places, carrier: string): StepSpread | null {
  const links = places.get(carrier)?.reaches ?? [];
  if (links.length === 0) return null;
  const ids = stepEntityIds(entry);
  if (!ids.includes(carrier)) return null;
  const now = new Set(links.filter((link) => inStepYears(link.year, entry)).map((link) => link.id));
  const reached = ids.filter((id) => id !== carrier && now.has(id));
  if (reached.length === 0) return null;
  const placed: (ReachedSite & { group: string | null })[] = [];
  for (const id of reached) {
    const place = places.get(id);
    if (place?.at) placed.push({ id, at: place.at, soft: place.group === 'polity', group: place.group });
  }
  const named = placed.filter((site) => site.group === 'place');
  const sites = (named.length > 0 ? named : placed).map(({ id, at, soft }) => ({ id, at, soft }));
  return { carrier, reached, sites };
}

/**
 * The spreading thing a step follows, if any: one of its entities that is
 * recorded as reaching others of them. An end of the step's relationship
 * comes before the rest; among equals, the one that reached the most here.
 */
export function stepSpread(entry: ChronicleEntry, places: Places): StepSpread | null {
  const rel = entry.primary_relationship;
  const ends = [rel?.source_entity_id, rel?.target_entity_id];
  let best: StepSpread | null = null;
  let bestIsEnd = false;
  for (const id of stepEntityIds(entry)) {
    const spread = spreadOf(entry, places, id);
    if (!spread) continue;
    const isEnd = ends.includes(id);
    if (!best || (isEnd && !bestIsEnd) || (isEnd === bestIsEnd && spread.reached.length > best.reached.length)) {
      best = spread;
      bestIsEnd = isEnd;
    }
  }
  return best;
}

/**
 * Where `carrier` had been before a step: every place the earlier steps say
 * it reached. When they name none, its own point, if it has one.
 */
export function reachedBefore(earlier: readonly ChronicleEntry[], places: Places, carrier: string): ReachedSite[] {
  const out: ReachedSite[] = [];
  for (const entry of earlier) {
    for (const site of spreadOf(entry, places, carrier)?.sites ?? []) {
      if (!out.some((o) => distanceKm(o.at, site.at) < MIN_LINE_KM)) out.push(site);
    }
  }
  if (out.length > 0) return out;
  const own = places.get(carrier);
  return own?.at ? [{ id: carrier, at: own.at, soft: own.group === 'polity' }] : [];
}

/** A relationship of these kinds draws no line of its own, so a spread hides nothing. */
const NO_LINE_KINDS = new Set<RelationKind>(['control', 'link', 'none']);

/**
 * Whether a step is drawn as the spread it mentions rather than as its
 * primary relationship: when that relationship is the spread itself (the
 * carrier is one of its ends), or when it would draw no line anyway ("Boston,
 * part of the United States"). A fight, a succession or a trade between two
 * other entities keeps its own line.
 */
function drawnAsSpread(spread: StepSpread, kind: RelationKind, rel: ChronicleEntry['primary_relationship']): boolean {
  if (NO_LINE_KINDS.has(kind)) return true;
  return kind === 'flow' && (rel?.source_entity_id === spread.carrier || rel?.target_entity_id === spread.carrier);
}

function arcTo(from: LngLat, to: LngLat, kind: RelationKind, color: string, pointed: boolean, dashed: boolean) {
  const path = arcPath(from, to);
  const cut = pointed ? trimPath(path, 1 - ARROW_GAP) : path;
  const arc: StepArc = {
    type: 'Feature',
    properties: { kind, color, dashed },
    geometry: { type: 'LineString', coordinates: cut },
  };
  const end = cut[cut.length - 1];
  return { arc, arrow: pointed ? { at: end, bearing: screenBearing(cut[cut.length - 2], end) } : null };
}

/**
 * What to draw for a step. `earlier` are the chronicle's entries before it,
 * in order: a spread starts from where it had been.
 */
export function stepScene(entry: ChronicleEntry, places: Places, earlier: readonly ChronicleEntry[] = []): StepScene {
  const rel = entry.primary_relationship ?? null;
  const relKind = relationKind(rel?.relationship_type, [rel?.source_entity?.entity_type, rel?.target_entity?.entity_type]);
  const mentioned = stepSpread(entry, places);
  const spread = mentioned && drawnAsSpread(mentioned, relKind, rel) ? mentioned : null;
  const kind: RelationKind = spread ? 'flow' : relKind;
  const color = KIND_COLOR[kind];
  const anchor = stepAnchor(entry, places);

  // The step's cast, relationship ends first, each once.
  const cast: CastMember[] = [];
  const areasPrimary: number[] = [];
  const areasOther: number[] = [];
  const seen = new Set<string>();
  const reached = new Set(spread?.reached ?? []);
  const add = (id: string | undefined, name: string | undefined, group: string | null | undefined, primary: boolean) => {
    if (!id || seen.has(id)) return;
    seen.add(id);
    const place = places.get(id);
    const marked = primary || reached.has(id);
    for (const b of bordersAt(place, entry.start_year)) {
      if (!areasPrimary.includes(b) && !areasOther.includes(b)) (marked ? areasPrimary : areasOther).push(b);
    }
    if (place?.at) cast.push({ id, name: name ?? '', group: upper(place.group ?? group), at: place.at, primary, marked });
  };
  add(rel?.source_entity_id, rel?.source_entity?.name, rel?.source_entity?.entity_group, true);
  add(rel?.target_entity_id, rel?.target_entity?.name, rel?.target_entity?.entity_group, true);
  for (const e of entry.secondary_entities ?? []) add(e.entity_id, e.name, null, false);

  const areas = { primary: areasPrimary, other: areasOther.slice(0, MAX_OTHER_AREAS) };
  const arcs: StepArc[] = [];
  const arrows: StepScene['arrows'] = [];

  // ── a spread: an arc to each place reached, from the nearest place it had been ──
  if (spread) {
    const origins = reachedBefore(earlier, places, spread.carrier);
    const targets = spread.sites.slice(0, MAX_FAN);
    let softStarts = 0;
    for (const site of targets) {
      let from: ReachedSite | null = null;
      for (const o of origins) if (!from || distanceKm(o.at, site.at) < distanceKm(from.at, site.at)) from = o;
      // Nowhere to come from (its first appearance), or it was already here.
      if (!from || distanceKm(from.at, site.at) < MIN_LINE_KM) continue;
      const { arc, arrow } = arcTo(from.at, site.at, kind, color, true, false);
      arcs.push(arc);
      if (arrow) arrows.push(arrow);
      if (from.soft) softStarts += 1;
    }
    const pulses = distinctPlaces(targets.map((site) => site.at));
    return {
      kind,
      color,
      anchor,
      arcs,
      arrows,
      soft: arcs.length > 0 && softStarts === arcs.length,
      pulses: pulses.length > 0 ? pulses : anchor ? [anchor] : [],
      // The arcs say who reached what; a line from every other entity would say more than is known.
      spokes: [],
      cast,
      areas,
    };
  }

  // ── the relationship's own line ──
  let soft = false;
  const src = rel ? places.get(rel.source_entity_id) : undefined;
  const tgt = rel ? places.get(rel.target_entity_id) : undefined;
  const reversed = REVERSED.has(rel?.relationship_type ?? '');
  const from = reversed ? tgt?.at : src?.at;
  const to = reversed ? src?.at : tgt?.at;
  const fromGroup = (reversed ? tgt?.group : src?.group) ?? null;
  // Control is shown by its territory; a line only where there is no border to outline.
  const hasArea = areasPrimary.length > 0;
  const drawn = kind !== 'none' && !(kind === 'control' && hasArea);
  if (drawn && from && to && distanceKm(from, to) >= MIN_LINE_KM) {
    const mutual = MUTUAL.has(rel?.relationship_type ?? '');
    const pointed = !mutual && kind !== 'control';
    const { arc, arrow } = arcTo(from, to, kind, color, pointed, kind === 'succession' || kind === 'control');
    arcs.push(arc);
    if (arrow) arrows.push(arrow);
    soft = fromGroup === 'polity';
  }

  // A step that names several places happens at each of them: equal rings,
  // and no line from anything to just one of them.
  const sites = distinctPlaces(cast.filter((m) => m.group === 'PLACE').map((m) => m.at));
  const several = sites.length > 1;
  if (several) for (const m of cast) if (m.group === 'PLACE') m.marked = true;

  // Spokes: those who took part, to where it happens. Never from a place:
  // nothing says two places of a step are tied to each other.
  const spokes: Feature<LineString>[] = [];
  if (anchor && !several) {
    const ends = new Set(arcs.length > 0 ? [from, to].map((p) => (p ? p.join() : '')) : []);
    for (const m of cast) {
      if (spokes.length >= MAX_SPOKES) break;
      if (m.group === 'PLACE' || (m.primary && arcs.length > 0)) continue;
      if (ends.has(m.at.join()) || distanceKm(m.at, anchor) < MIN_LINE_KM) continue;
      spokes.push({
        type: 'Feature',
        properties: { id: m.id },
        geometry: { type: 'LineString', coordinates: arcPath(m.at, anchor, 0.08, 24) },
      });
    }
  }

  return { kind, color, anchor, arcs, arrows, soft, pulses: several ? sites : anchor ? [anchor] : [], spokes, cast, areas };
}

/** The first `frac` (0–1) of a path, by its length in Web Mercator. */
export function trimPath(path: LngLat[], frac: number): LngLat[] {
  if (path.length < 2 || frac >= 1) return path;
  const seg = (a: LngLat, b: LngLat) => Math.hypot(b[0] - a[0], mercY(b[1]) - mercY(a[1]));
  let total = 0;
  for (let i = 1; i < path.length; i++) total += seg(path[i - 1], path[i]);
  let left = total * Math.max(0, frac);
  const out: LngLat[] = [path[0]];
  for (let i = 1; i < path.length; i++) {
    const d = seg(path[i - 1], path[i]);
    if (d >= left) {
      const t = d === 0 ? 0 : left / d;
      const [ax, ay] = path[i - 1];
      const [bx, by] = path[i];
      out.push([ax + (bx - ax) * t, latOf(mercY(ay) + (mercY(by) - mercY(ay)) * t)]);
      return out;
    }
    left -= d;
    out.push(path[i]);
  }
  return out;
}

// ── the trail ─────────────────────────────────────────────────────────────────

export interface TrailStop {
  /** The entry's index in the chronicle (its step). */
  step: number;
  at: LngLat;
}

/** Each step's anchor up to `upto` (inclusive), in order; steps without one are skipped. */
export function trailStops(entries: ChronicleEntry[], places: Places, upto: number): TrailStop[] {
  const stops: TrailStop[] = [];
  for (let i = 0; i <= Math.min(upto, entries.length - 1); i++) {
    const at = stepAnchor(entries[i], places);
    if (at) stops.push({ step: i, at });
  }
  return stops;
}

/** The trail shows this many stops before the current step. */
export const TRAIL_KEEP = 5;

/**
 * The trail to the current step: its last `keep` stops, a segment between
 * each pair of successive ones (`age` = how many steps ago it ended, for
 * fading) and a numbered dot at each. Older stops are dropped: over a long
 * chronicle the whole path is a web across the map. The current step's own
 * point is the scene's anchor.
 */
export function trailCollection(stops: TrailStop[], current: number, keep = TRAIL_KEEP): FeatureCollection<LineString | Point> {
  const before = stops.filter((s) => s.step < current).slice(-Math.max(0, keep));
  const here = stops.find((s) => s.step === current);
  const shown = here ? [...before, here] : before;
  const features: Feature<LineString | Point>[] = [];
  for (let k = 1; k < shown.length; k++) {
    const a = shown[k - 1];
    const b = shown[k];
    if (distanceKm(a.at, b.at) < MIN_LINE_KM) continue;
    features.push({
      type: 'Feature',
      properties: { role: 'segment', age: current - b.step },
      geometry: { type: 'LineString', coordinates: arcPath(a.at, b.at, 0.06, 20) },
    });
  }
  // One dot per place: a place visited twice shows its latest step.
  const dots = new Map<string, TrailStop>();
  for (const s of before) dots.set(s.at.join(), s);
  for (const s of dots.values()) {
    features.push({
      type: 'Feature',
      properties: { role: 'stop', step: s.step, label: String(s.step + 1), age: current - s.step },
      geometry: { type: 'Point', coordinates: s.at },
    });
  }
  return { type: 'FeatureCollection', features };
}

/** The places of a chronicle, by entity id. */
export function placesIndex(list: ChroniclePlace[] | undefined): Places {
  return new Map((list ?? []).map((p) => [p.id, p]));
}

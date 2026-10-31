/**
 * Map-story geometry: where every unit stands at each step (and each beat
 * within it), the formation polygons drawn for them, and the in-between
 * frames the player animates.
 *
 * Mirrors the rules in docs/implementation-docs/map-story-authoring.md (and the
 * authoring preview in pipeline/map_stories/preview.py): placements carry
 * forward, `at` is the formation's centre, `facing` the compass bearing of its
 * front, `width` its frontage and `depth` front-to-back, in metres. Schema 2
 * (docs/superpowers/specs/2026-10-31-map-story-schema-v2-design.md) adds
 * beats, detach/merge (`from`/`into`), split formations and per-step terrain
 * state, light, wind and sun.
 */
import type {
  Light,
  LngLat,
  MapStoryDocument,
  Placement,
  Shape,
  StoryMove,
  StoryNote,
  StoryStep,
  StorySun,
  StoryWind,
  TerrainState,
  UnitState,
} from '@/lib/schemas/map-story';
import { POINT_UNIT_KINDS } from '@/lib/schemas/map-story';

const R = 6_371_008.8;
const RAD = Math.PI / 180;

/** A unit's full placement at one step, every field filled in. */
export interface Resolved {
  at: LngLat;
  facing: number;
  width: number;
  depth: number;
  shape: Shape;
  curve: number;
  state: UnitState;
  label: string | null;
  strength: string | null;
  /** The unit this marker rides with, if pinned. */
  with: string | null;
  strength_n: number | null;
  /** Parallel lines, open lanes and separate blocks (formations only). */
  lines: number;
  lanes: number;
  subunits: number;
  /** The captor side, when `captured`. */
  by: string | null;
  /** False: drawn, but left out of the step's camera framing. */
  framed: boolean;
  conjectural: boolean;
  /** The unit it detached from, in the phase it detaches. */
  from: string | null;
  /** The unit it merged into, in the phase it merges: it stands on that
   *  unit and is not drawn (`onField` is false) once the merge has played. */
  into: string | null;
  /** Mid-animation only: opacity of a unit fading in, or merging away. */
  fade?: number;
}

/** unit id → placement, for one step. Units not on the field are absent. */
export type Frame = Map<string, Resolved>;

/** Whether a frame's unit is drawn: not one that has merged into another. */
export const onField = (r: Resolved): boolean => r.into === null;

// ── spherical helpers ────────────────────────────────────────────────────────

export function dest(p: LngLat, bearing: number, metres: number): LngLat {
  const la1 = p[1] * RAD;
  const lo1 = p[0] * RAD;
  const b = bearing * RAD;
  const d = metres / R;
  const la2 = Math.asin(Math.sin(la1) * Math.cos(d) + Math.cos(la1) * Math.sin(d) * Math.cos(b));
  const lo2 =
    lo1 + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(la1), Math.cos(d) - Math.sin(la1) * Math.sin(la2));
  return [lo2 / RAD, la2 / RAD];
}

export function bearing(a: LngLat, b: LngLat): number {
  const la1 = a[1] * RAD;
  const la2 = b[1] * RAD;
  const dl = (b[0] - a[0]) * RAD;
  const y = Math.sin(dl) * Math.cos(la2);
  const x = Math.cos(la1) * Math.sin(la2) - Math.sin(la1) * Math.cos(la2) * Math.cos(dl);
  return (Math.atan2(y, x) / RAD + 360) % 360;
}

export function distance(a: LngLat, b: LngLat): number {
  const la1 = a[1] * RAD;
  const la2 = b[1] * RAD;
  const h =
    Math.sin((la2 - la1) / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(((b[0] - a[0]) * RAD) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/**
 * A formation's local frame: `(ahead, right)` metres from `c` toward its
 * front and its right flank. Flat-earth, which is exact enough within a
 * battlefield and far cheaper than `dest` for the many points drawn per frame.
 */
function local(c: LngLat, facing: number): (ahead: number, right: number) => LngLat {
  const s = Math.sin(facing * RAD);
  const co = Math.cos(facing * RAD);
  const dLat = 1 / (R * RAD);
  const dLng = dLat / Math.cos(c[1] * RAD);
  return (ahead, right) => [c[0] + (ahead * s + right * co) * dLng, c[1] + (ahead * co - right * s) * dLat];
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function lerpPoint(a: LngLat, b: LngLat, t: number): LngLat {
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t)];
}

/** Interpolate compass angles the short way round. */
function lerpAngle(a: number, b: number, t: number): number {
  const d = ((((b - a) % 360) + 540) % 360) - 180;
  return a + d * t;
}

/** The point a fraction `t` of the way along a polyline (by length). */
export function along(path: LngLat[], t: number): LngLat {
  if (path.length === 1) return path[0];
  const r = route(path);
  return pointAt(r, Math.max(0, Math.min(1, t)) * r.total);
}

/** A polyline with its cumulative lengths, measured once and sampled often. */
interface Route {
  pts: LngLat[];
  cum: number[];
  total: number;
}

function route(pts: LngLat[]): Route {
  const cum = [0];
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + distance(pts[i - 1], pts[i]));
  return { pts, cum, total: cum[cum.length - 1] };
}

function pointAt(r: Route, d: number): LngLat {
  const { pts, cum, total } = r;
  if (total === 0 || d >= total) return pts[pts.length - 1];
  if (d <= 0) return pts[0];
  let i = 1;
  while (cum[i] < d) i++;
  const seg = cum[i] - cum[i - 1];
  return lerpPoint(pts[i - 1], pts[i], seg === 0 ? 1 : (d - cum[i - 1]) / seg);
}

/** The route's direction at `d`, smoothed over a short chord so turns don't snap. */
function headingAt(r: Route, d: number): number {
  const h = Math.min(r.total * 0.06, 120);
  const a = Math.max(0, Math.min(d - h, r.total - 2 * h));
  return bearing(pointAt(r, a), pointAt(r, a + 2 * h));
}

// ── placements ───────────────────────────────────────────────────────────────

const DEFAULT_WIDTH = 300;

function defaultDepth(width: number): number {
  return Math.max(20, Math.min(width / 4, 120));
}

/** A step's own positions/moves/notes, then each beat's, in playing order. */
export interface Phase {
  /** The beat's caption (null for the step's own phase). */
  label: string | null;
  positions: Record<string, Placement>;
  moves: StoryMove[];
  notes: StoryNote[];
}

export function stepPhases(step: StoryStep | undefined): Phase[] {
  if (!step) return [];
  return [
    { label: null, positions: step.positions, moves: step.moves, notes: step.notes },
    ...step.beats.map((b) => ({ label: b.label, positions: b.positions, moves: b.moves, notes: b.notes })),
  ];
}

/**
 * Every step's frames, one per phase: `[before beats, after beat 1, …]`. The
 * last is the step's resolved frame, which carries forward. Placements carry
 * forward key by key. `from` and `into` hold only for the phase that sets
 * them: a unit merging `into` another stands on it in that frame (marked
 * `into`, not drawn once it has arrived) and is `hidden` afterwards, as in
 * the pipeline's `resolve_steps`. `orient: "path"` lands a unit facing along
 * its arrow's last segment unless the placement gives a facing.
 */
export function resolveBeatFrames(doc: MapStoryDocument): Frame[][] {
  const current = new Map<string, Placement>();
  return doc.steps.map((step) =>
    stepPhases(step).map((phase) => {
      for (const [uid, pl] of Object.entries(phase.positions)) {
        const merged: Placement = { ...current.get(uid) };
        for (const [k, v] of Object.entries(pl)) {
          if (v !== undefined) (merged as Record<string, unknown>)[k] = v;
        }
        // A fresh `at` unpins a marker; a fresh `with` re-pins it.
        if (pl.at && !pl.with) delete merged.with;
        if (pl.with && !pl.at) delete merged.at;
        // A detached unit placed without `at` starts where its parent stands.
        if (pl.from && !merged.at && !merged.with) merged.at = current.get(pl.from)?.at;
        current.set(uid, merged);
      }
      for (const mv of phase.moves) {
        const pl = mv.unit ? current.get(mv.unit) : undefined;
        if (!pl || mv.orient !== 'path' || mv.type === 'fire' || phase.positions[mv.unit as string]?.facing != null) continue;
        const n = mv.path.length;
        const heading = bearing(mv.path[n - 2], mv.path[n - 1]);
        pl.facing = mv.type === 'back_water' ? (heading + 180) % 360 : heading;
      }
      const frame = snapshot(current);
      // `from` happens once; a unit merged `into` another leaves the field.
      for (const pl of current.values()) {
        delete pl.from;
        if (pl.into) {
          delete pl.into;
          pl.state = 'hidden';
        }
      }
      return frame;
    }),
  );
}

/** Every step's resolved frame (the state after its last beat). */
export function resolveFrames(doc: MapStoryDocument): Frame[] {
  return resolveBeatFrames(doc).map((phases) => phases[phases.length - 1]);
}

/** Step `i`'s frames: `[frame_before_beats, after_beat_1, …]`. */
export function resolveBeats(doc: MapStoryDocument, i: number): Frame[] {
  return resolveBeatFrames(doc)[i] ?? [];
}

/** The frame for the placements in effect: hidden units drop out, pinned
 *  markers (`with`) stand just behind their unit and move with it, and a unit
 *  merging `into` another stands on it. */
function snapshot(current: Map<string, Placement>): Frame {
  const frame: Frame = new Map();
  const pinned: [string, Placement][] = [];
  const merging: [string, Placement][] = [];
  for (const [uid, pl] of current) {
    if (pl.state === 'hidden') continue;
    if (pl.into) {
      merging.push([uid, pl]);
      continue;
    }
    if (pl.with) {
      pinned.push([uid, pl]);
      continue;
    }
    if (!pl.at) continue;
    frame.set(uid, toResolved(pl, pl.at, null));
  }
  for (const [uid, pl] of pinned) {
    const host = frame.get(pl.with as string);
    if (!host) continue;
    const at = dest(host.at, host.facing + 180, behind(host));
    // A marker riding with an off-stage unit is off-stage too.
    frame.set(uid, { ...toResolved(pl, at, pl.with as string), facing: host.facing, framed: pl.frame ?? host.framed });
  }
  for (const [uid, pl] of merging) {
    const at = frame.get(pl.into as string)?.at ?? pl.at;
    if (at) frame.set(uid, toResolved(pl, at, null));
  }
  return frame;
}

const clampInt = (v: number | undefined, lo: number, hi: number, dflt: number) =>
  v == null || !Number.isFinite(v) ? dflt : Math.max(lo, Math.min(hi, Math.round(v)));

function toResolved(pl: Placement, at: LngLat, withUnit: string | null): Resolved {
  const width = pl.width ?? DEFAULT_WIDTH;
  const shape = pl.shape ?? 'block';
  return {
    at,
    facing: pl.facing ?? 0,
    width,
    depth: pl.depth ?? defaultDepth(width),
    shape,
    // A crescent without an explicit bow bows by ~a fifth of its frontage.
    curve: pl.curve ?? (shape === 'crescent' ? width * 0.18 : 0),
    state: pl.state ?? 'ready',
    label: pl.label ?? null,
    strength: pl.strength ?? null,
    with: withUnit,
    strength_n: pl.strength_n ?? null,
    lines: clampInt(pl.lines, 1, 5, 1),
    lanes: clampInt(pl.lanes, 0, 12, 0),
    // 0 = not split; an explicit 1 still makes a `square` one hollow square.
    subunits: clampInt(pl.subunits, 1, 24, 0),
    by: pl.by ?? null,
    framed: pl.frame !== false,
    conjectural: pl.conjectural === true,
    from: pl.from ?? null,
    into: pl.into ?? null,
  };
}

/** How far behind a unit's centre a pinned marker stands: clear of its back
 *  edge, which a crescent bowed backwards pushes further out at the middle. */
function behind(host: Resolved): number {
  const bow = host.shape === 'crescent' ? Math.max(0, -host.curve / 2) : 0;
  return host.depth / 2 + bow + 60;
}

// ── terrain state, light, wind, sun ──────────────────────────────────────────

/** Who holds a terrain feature and in what state, at one step. */
export interface TerrainHold {
  held_by: string | null;
  state: TerrainState | null;
  label: string | null;
}

/** Each step's terrain state (terrain id → hold): carries forward; `null` clears. */
export function resolveTerrainState(doc: MapStoryDocument): Map<string, TerrainHold>[] {
  const current = new Map<string, TerrainHold>();
  return doc.steps.map((step) => {
    for (const [tid, ts] of Object.entries(step.terrain_state)) {
      const prev = current.get(tid);
      if (!ts) {
        current.delete(tid);
        continue;
      }
      const next: TerrainHold = {
        held_by: ts.held_by !== undefined ? ts.held_by : (prev?.held_by ?? null),
        state: ts.state !== undefined ? ts.state : (prev?.state ?? null),
        label: ts.label !== undefined ? ts.label : (prev?.label ?? null),
      };
      if (next.held_by || next.state || next.label) current.set(tid, next);
      else current.delete(tid);
    }
    return new Map(current);
  });
}

export interface Conditions {
  light: Light;
  wind: StoryWind | null;
  sun: StorySun | null;
}

/** Each step's light (default day), wind and sun, carried forward. */
export function resolveConditions(doc: MapStoryDocument): Conditions[] {
  let c: Conditions = { light: 'day', wind: null, sun: null };
  return doc.steps.map((step) => {
    c = {
      light: step.light ?? c.light,
      wind: step.wind !== undefined ? step.wind : c.wind,
      sun: step.sun !== undefined ? step.sun : c.sun,
    };
    return c;
  });
}

// ── formations ───────────────────────────────────────────────────────────────

/** Shapes that are a band with a (possibly curved) front — they morph into each other. */
const BANDS: readonly Shape[] = ['block', 'line', 'column', 'square', 'crescent'];

/** What `formation` needs of a placement. */
export type FormationSpec = Pick<Resolved, 'at' | 'facing' | 'width' | 'depth' | 'shape' | 'curve'> &
  Partial<Pick<Resolved, 'lines' | 'lanes' | 'subunits'>>;

export interface Formation {
  /** The whole formation's outline (framing, and the shape when not split). */
  ring: LngLat[];
  /** Its front edge (drawn heavier so you can tell which way a block faces). */
  front: LngLat[];
  /** The polygons drawn, each `[outer, ...holes]`: lines, lane blocks, subunits. */
  parts: LngLat[][][];
  /** The front edges of the front line's parts. */
  fronts: LngLat[][];
}

/** Gap between parallel lines, as a share of one line's depth. */
const LINE_GAP = 0.6;

/**
 * The formation's outline as a closed ring plus its front edge, and the parts
 * actually drawn. `lines` stacks parallel lines through the depth, `lanes`
 * cuts open lanes through it, `subunits` splits the front into blocks
 * (checkerboarded when there are several lines; small hollow squares when the
 * shape is `square`). A crescent bends every part along its bow.
 */
export function formation(r: FormationSpec): Formation {
  const { width: w, depth: d } = r;
  const at = local(r.at, r.facing);
  if (r.shape === 'wedge') {
    const tip = at(d / 2, 0);
    const ring = [tip, at(-d / 2, w / 2), at(-d / 2, -w / 2), tip];
    const front = [ring[2], tip, ring[1]];
    return { ring, front, parts: [[ring]], fronts: [front] };
  }
  if (r.shape === 'circle') {
    const ring: LngLat[] = [];
    for (let i = 0; i <= 32; i++) {
      const a = (i / 32) * 2 * Math.PI;
      ring.push(at((Math.cos(a) * d) / 2, (Math.sin(a) * w) / 2));
    }
    const front = ring.slice(28).concat(ring.slice(1, 5));
    return { ring, front, parts: [[ring]], fronts: [front] };
  }

  // Bands: a block is a crescent with no bow, so the two morph smoothly.
  // Centre the bow on `at`: the middle bows forward by bulge/2, the tips back by bulge/2.
  const bulge = r.shape === 'crescent' ? r.curve : 0;
  const bowed = Math.abs(bulge) > 0.5;
  const bow = (x: number) => (bowed ? bulge * (1 - ((2 * x) / w) ** 2) - bulge / 2 : 0);
  const pt = (x: number, y: number) => at(y + bow(x), x);
  /** A closed box from x0..x1 (left to right) and y0..y1 (back to front). */
  const box = (x0: number, x1: number, y0: number, y1: number): { ring: LngLat[]; front: LngLat[] } => {
    const n = bowed ? Math.max(1, Math.ceil((16 * (x1 - x0)) / w)) : 1;
    const front: LngLat[] = [];
    const back: LngLat[] = [];
    for (let i = 0; i <= n; i++) {
      const x = x0 + ((x1 - x0) * i) / n;
      front.push(pt(x, y1));
      back.push(pt(x, y0));
    }
    return { ring: [...front, ...back.reverse(), front[0]], front };
  };

  const whole = box(-w / 2, w / 2, -d / 2, d / 2);
  const lines = r.lines ?? 1;
  const subunits = r.subunits ?? 0;
  const lanes = subunits > 1 ? 0 : (r.lanes ?? 0);
  const hollow = r.shape === 'square' && subunits >= 1;
  if (lines <= 1 && subunits <= 1 && lanes <= 0 && !hollow) {
    return { ring: whole.ring, front: whole.front, parts: [[whole.ring]], fronts: [whole.front] };
  }

  const lineDepth = d / (lines + LINE_GAP * (lines - 1));
  // Across the front: [x0, x1] spans per line.
  const checker = subunits > 1 && lines > 1;
  const spans = (li: number): [number, number][] => {
    if (subunits > 1) {
      // Gap as a share of the pitch; a checkerboard's rear blocks cover the gaps.
      const g = checker ? 0.5 : 0.25;
      const pitch = w / (subunits - g + (checker ? 0.5 : 0));
      const bw = pitch * (1 - g);
      const shift = checker ? (li % 2 ? pitch / 4 : -pitch / 4) + pitch / 4 : 0;
      return Array.from({ length: subunits }, (_, i) => {
        const x0 = -w / 2 + shift + i * pitch;
        return [x0, x0 + bw] as [number, number];
      });
    }
    if (lanes > 0) {
      const lane = (w / (lanes + 1)) * 0.3;
      const cuts = Array.from({ length: lanes }, (_, j) => -w / 2 + (w * (j + 1)) / (lanes + 1));
      return [-w / 2, ...cuts].map((c, j) => [j === 0 ? c : c + lane / 2, j === lanes ? w / 2 : cuts[j] - lane / 2]);
    }
    return [[-w / 2, w / 2]];
  };

  const parts: LngLat[][][] = [];
  const fronts: LngLat[][] = [];
  for (let li = 0; li < lines; li++) {
    const y1 = d / 2 - li * lineDepth * (1 + LINE_GAP);
    const y0 = y1 - lineDepth;
    for (const [x0, x1] of spans(li)) {
      if (hollow) {
        // A small hollow square centred in its cell; walls ~30% of its side.
        const s = Math.min(x1 - x0, lineDepth);
        const cx = (x0 + x1) / 2;
        const cy = (y0 + y1) / 2;
        const outer = box(cx - s / 2, cx + s / 2, cy - s / 2, cy + s / 2);
        const t = s * 0.3;
        const inner = box(cx - s / 2 + t, cx + s / 2 - t, cy - s / 2 + t, cy + s / 2 - t).ring.reverse();
        parts.push([outer.ring, inner]);
        if (li === 0) fronts.push(outer.front);
      } else {
        const b = box(x0, x1, y0, y1);
        parts.push([b.ring]);
        if (li === 0) fronts.push(b.front);
      }
    }
  }
  return { ring: whole.ring, front: whole.front, parts, fronts };
}

/**
 * A composite unit's bands, front to back (`ranks` shares, normalised): the
 * centre point of each band (where its glyph goes) and the lines between them.
 */
export function rankBands(r: FormationSpec, shares: number[]): { centres: LngLat[]; dividers: LngLat[][] } {
  const total = shares.reduce((s, x) => s + Math.max(0, x), 0) || 1;
  const at = local(r.at, r.facing);
  const bulge = r.shape === 'crescent' ? r.curve : 0;
  const bow = (x: number) => bulge * (1 - ((2 * x) / r.width) ** 2) - bulge / 2;
  const centres: LngLat[] = [];
  const dividers: LngLat[][] = [];
  let y = r.depth / 2;
  shares.forEach((share, i) => {
    const h = (Math.max(0, share) / total) * r.depth;
    centres.push(at(y - h / 2 + bow(0), 0));
    y -= h;
    if (i < shares.length - 1) {
      const line: LngLat[] = [];
      for (let k = 0; k <= 8; k++) {
        const x = -r.width / 2 + (r.width * k) / 8;
        line.push(at(y + bow(x), x));
      }
      dividers.push(line);
    }
  });
  return { centres, dividers };
}

// ── arrows ───────────────────────────────────────────────────────────────────

/**
 * The line an arrow is drawn along: a `fire` arrow with a `target` ends on that
 * unit (in `frame`), and `arc` bends it into a ballistic curve.
 */
export function movePath(mv: StoryMove, frame: Frame | undefined): LngLat[] {
  let path = mv.path;
  const target = mv.target ? frame?.get(mv.target) : undefined;
  if (target) path = [...path.slice(0, -1), target.at];
  if (!mv.arc) return path;
  // A quadratic bezier from the first to the last point, bowed to the left.
  const a = path[0];
  const b = path[path.length - 1];
  const len = distance(a, b);
  const ctrl = dest(lerpPoint(a, b, 0.5), bearing(a, b) - 90, len * 0.3);
  const out: LngLat[] = [];
  for (let i = 0; i <= 16; i++) {
    const t = i / 16;
    const u = 1 - t;
    out.push([
      u * u * a[0] + 2 * u * t * ctrl[0] + t * t * b[0],
      u * u * a[1] + 2 * u * t * ctrl[1] + t * t * b[1],
    ]);
  }
  return out;
}

// ── animation ────────────────────────────────────────────────────────────────

/** ease-in-out, so units start and stop rather than lurch. */
export function ease(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
}

/** One unit's journey through a transition, measured once. */
interface Track {
  uid: string;
  from: Resolved;
  to: Resolved;
  route: Route;
  morph: boolean;
  /** Facing follows the route (`orient: "path"`); +180 when backing water. */
  orient: number | null;
  /** Merging into another unit: fades as it arrives. */
  merging: boolean;
}

/**
 * Prepare the frames between `a` and `b` and return the frame at `t` (0–1).
 * A unit with a move arrow slides along the arrow; others glide straight. A
 * unit detaching (`from`) slides out of its parent; one merging (`into`)
 * slides onto its target, shrinking and fading. Units only in `b` fade in
 * where they stand; units only in `a` stay until the end. Everything that
 * doesn't depend on `t` is measured here, once, not per animation frame.
 */
export function tweener(a: Frame, b: Frame, moves: StoryMove[]): (t: number) => Frame {
  const paths = new Map<string, StoryMove>();
  for (const mv of moves) {
    if (mv.unit && mv.type !== 'fire' && !paths.has(mv.unit)) paths.set(mv.unit, mv);
  }
  const tracks: Track[] = [];
  const appear: [string, Resolved][] = [];
  const stay: [string, Resolved][] = [];

  const track = (uid: string, from: Resolved, to: Resolved, merging = false) => {
    const mv = paths.get(uid);
    // The arrow's path, anchored to where the unit really starts and ends.
    const pts = mv ? [from.at, ...mv.path.slice(1, -1), to.at] : [from.at, to.at];
    tracks.push({
      uid,
      from,
      to,
      route: route(pts),
      morph: BANDS.includes(from.shape) && BANDS.includes(to.shape),
      orient: mv?.orient === 'path' ? (mv.type === 'back_water' ? 180 : 0) : null,
      merging,
    });
  };

  for (const [uid, to] of b) {
    const from = a.get(uid);
    if (from && onField(from)) {
      const target = to.into ? b.get(to.into) : undefined;
      if (target) {
        track(uid, from, { ...to, into: null, facing: target.facing, width: Math.min(from.width, target.width) * 0.5, depth: Math.min(from.depth, target.depth) }, true);
      } else if (onField(to)) {
        track(uid, from, to);
      }
      continue;
    }
    if (!onField(to)) continue;
    const parent = to.from ? a.get(to.from) : undefined;
    if (parent && onField(parent)) {
      // Start inside the parent, as a sliver of it.
      track(uid, { ...to, at: parent.at, facing: parent.facing, width: Math.min(parent.width, to.width) * 0.5, depth: Math.min(parent.depth, to.depth) }, to);
    } else {
      appear.push([uid, to]);
    }
  }
  for (const [uid, from] of a) {
    if (!b.has(uid) && onField(from)) stay.push([uid, from]);
  }
  const pinned = [...b.values(), ...a.values()].some((r) => r.with);

  return (t: number): Frame => {
    if (t >= 1) return b;
    const out: Frame = new Map();
    for (const tr of tracks) {
      const { from, to } = tr;
      const d = t * tr.route.total;
      let facing = lerpAngle(from.facing, to.facing, t);
      if (tr.orient !== null && tr.route.total > 0) {
        // Turn onto the path, follow it, then settle on the placement's facing.
        const heading = headingAt(tr.route, d) + tr.orient;
        facing = t < 0.15 ? lerpAngle(from.facing, heading, t / 0.15) : t > 0.85 ? lerpAngle(heading, to.facing, (t - 0.85) / 0.15) : heading;
      }
      out.set(tr.uid, {
        ...to,
        at: pointAt(tr.route, d),
        facing,
        width: lerp(from.width, to.width, t),
        depth: lerp(from.depth, to.depth, t),
        shape: tr.morph ? (from.shape === 'crescent' || to.shape === 'crescent' ? 'crescent' : to.shape) : t < 0.5 ? from.shape : to.shape,
        curve: tr.morph ? lerp(bandCurve(from), bandCurve(to), t) : to.curve,
        state: t < 0.5 ? from.state : to.state,
        lines: t < 0.5 ? from.lines : to.lines,
        lanes: t < 0.5 ? from.lanes : to.lanes,
        subunits: t < 0.5 ? from.subunits : to.subunits,
        ...(tr.merging ? { fade: t < 0.55 ? 1 : 1 - (t - 0.55) / 0.45 } : {}),
      });
    }
    const fadeIn = Math.min(1, t * 2.5);
    for (const [uid, r] of appear) out.set(uid, fadeIn < 1 ? { ...r, fade: fadeIn } : r);
    for (const [uid, r] of stay) out.set(uid, r);
    // Pinned markers follow their unit's tweened position.
    if (pinned) {
      for (const [uid, r] of out) {
        if (!r.with) continue;
        const host = out.get(r.with);
        if (host) out.set(uid, { ...r, at: dest(host.at, host.facing + 180, behind(host)), facing: host.facing, fade: host.fade });
      }
    }
    return out;
  };
}

/** The frame `t` (0–1) of the way from `a` to `b` (see `tweener`). */
export function tween(a: Frame, b: Frame, moves: StoryMove[], t: number): Frame {
  return tweener(a, b, moves)(t);
}

/** A band's bow in metres (a non-crescent band has none). */
function bandCurve(r: Resolved): number {
  return r.shape === 'crescent' ? r.curve : 0;
}

// ── framing ──────────────────────────────────────────────────────────────────

export type Bounds = [[number, number], [number, number]];

/**
 * Bounds of a step: its units' outlines, its arrows and its notes (beats
 * included). Off-stage placements (`frame: false`) and their arrows,
 * `continues` tails and alternative sites are left out.
 */
export function stepBounds(
  doc: MapStoryDocument,
  frame: Frame,
  stepIndex: number,
): Bounds | null {
  const pts: LngLat[] = [];
  const kinds = new Map(doc.units.map((u) => [u.id, u.kind]));
  const offstage = new Set<string>();
  for (const [uid, r] of frame) {
    if (!onField(r)) continue;
    if (!r.framed) {
      offstage.add(uid);
      continue;
    }
    if (POINT_UNIT_KINDS.includes(kinds.get(uid) ?? '')) pts.push(r.at);
    else pts.push(...formation(r).ring);
  }
  for (const phase of stepPhases(doc.steps[stepIndex])) {
    for (const mv of phase.moves) {
      if (mv.unit && offstage.has(mv.unit)) continue;
      // A targeted fire arrow ends on its target, which is framed (or not) itself.
      pts.push(...(mv.target ? mv.path.slice(0, -1) : mv.path));
    }
    for (const n of phase.notes) pts.push(n.at);
  }
  if (pts.length === 0) return null;
  let w = Infinity;
  let s = Infinity;
  let e = -Infinity;
  let n = -Infinity;
  for (const [x, y] of pts) {
    w = Math.min(w, x);
    s = Math.min(s, y);
    e = Math.max(e, x);
    n = Math.max(n, y);
  }
  return [
    [w, s],
    [e, n],
  ];
}

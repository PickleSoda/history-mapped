/**
 * Map-story geometry: where every unit stands at each step, the formation
 * polygons drawn for them, and the in-between frames the player animates.
 *
 * Mirrors the rules in docs/implementation-docs/map-story-authoring.md (and the
 * authoring preview in pipeline/map_stories/preview.py): placements carry
 * forward, `at` is the formation's centre, `facing` the compass bearing of its
 * front, `width` its frontage and `depth` front-to-back, in metres.
 */
import type {
  LngLat,
  MapStoryDocument,
  Placement,
  Shape,
  StoryMove,
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
}

/** unit id → placement, for one step. Units not on the field are absent. */
export type Frame = Map<string, Resolved>;

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

/** A point `ahead` metres toward a formation's front and `right` toward its right flank. */
function rel(c: LngLat, facing: number, ahead: number, right: number): LngLat {
  const q = ahead ? dest(c, facing, ahead) : c;
  return right ? dest(q, facing + 90, right) : q;
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
  const segs = path.slice(1).map((p, i) => distance(path[i], p));
  const total = segs.reduce((s, d) => s + d, 0);
  if (total === 0) return path[path.length - 1];
  let target = Math.max(0, Math.min(1, t)) * total;
  for (let i = 0; i < segs.length; i++) {
    if (target <= segs[i] || i === segs.length - 1) {
      return lerpPoint(path[i], path[i + 1], segs[i] === 0 ? 1 : Math.min(1, target / segs[i]));
    }
    target -= segs[i];
  }
  return path[path.length - 1];
}

// ── placements ───────────────────────────────────────────────────────────────

const DEFAULT_WIDTH = 300;

function defaultDepth(width: number): number {
  return Math.max(20, Math.min(width / 4, 120));
}

/**
 * Every step's frame: placements carry forward (each key a step sets
 * overrides the previous value), hidden units drop out, and pinned markers
 * (`with`) stand just behind their unit and move with it.
 */
export function resolveFrames(doc: MapStoryDocument): Frame[] {
  const current = new Map<string, Placement>();
  const frames: Frame[] = [];

  for (const step of doc.steps) {
    for (const [uid, pl] of Object.entries(step.positions)) {
      const merged: Placement = { ...current.get(uid), ...pl };
      // A fresh `at` unpins a marker; a fresh `with` re-pins it.
      if (pl.at && !pl.with) delete merged.with;
      if (pl.with && !pl.at) delete merged.at;
      current.set(uid, merged);
    }

    const frame: Frame = new Map();
    const pinned: [string, Placement][] = [];
    for (const [uid, pl] of current) {
      if (pl.state === 'hidden') continue;
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
      frame.set(uid, { ...toResolved(pl, at, pl.with as string), facing: host.facing });
    }
    frames.push(frame);
  }
  return frames;
}

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
  };
}

/** How far behind a unit's centre a pinned marker stands: clear of its back
 *  edge, which a crescent bowed backwards pushes further out at the middle. */
function behind(host: Resolved): number {
  const bow = host.shape === 'crescent' ? Math.max(0, -host.curve / 2) : 0;
  return host.depth / 2 + bow + 60;
}

// ── formations ───────────────────────────────────────────────────────────────

/** Shapes that are a band with a (possibly curved) front — they morph into each other. */
const BANDS: readonly Shape[] = ['block', 'line', 'column', 'square', 'crescent'];

/**
 * The formation's outline as a closed ring, plus its front edge (drawn
 * heavier so you can tell which way a block faces).
 */
export function formation(r: Resolved): { ring: LngLat[]; front: LngLat[] } {
  const { at: c, facing: f, width: w, depth: d } = r;
  if (r.shape === 'wedge') {
    const tip = rel(c, f, d / 2, 0);
    const ring = [tip, rel(c, f, -d / 2, w / 2), rel(c, f, -d / 2, -w / 2), tip];
    return { ring, front: [ring[2], tip, ring[1]] };
  }
  if (r.shape === 'circle') {
    const ring: LngLat[] = [];
    for (let i = 0; i <= 32; i++) {
      const a = (i / 32) * 2 * Math.PI;
      ring.push(rel(c, f, (Math.cos(a) * d) / 2, (Math.sin(a) * w) / 2));
    }
    return { ring, front: ring.slice(28).concat(ring.slice(1, 5)) };
  }
  // Bands: a block is a crescent with no bow, so the two morph smoothly.
  const bulge = r.shape === 'crescent' ? r.curve : 0;
  const n = Math.abs(bulge) > 0.5 ? 16 : 1;
  const front: LngLat[] = [];
  const back: LngLat[] = [];
  for (let i = 0; i <= n; i++) {
    const x = -w / 2 + (w * i) / n;
    // Centre the bow on `at`: the middle bows forward by bulge/2, the tips back by bulge/2.
    const k = bulge * (1 - (2 * x / w) ** 2) - bulge / 2;
    front.push(rel(c, f, d / 2 + k, x));
    back.push(rel(c, f, -d / 2 + k, x));
  }
  const ring = [...front, ...back.reverse(), front[0]];
  return { ring, front };
}

// ── animation ────────────────────────────────────────────────────────────────

/** ease-in-out, so units start and stop rather than lurch. */
export function ease(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
}

/**
 * The frame `t` (0–1) of the way from `a` to `b`. A unit with a move arrow in
 * the arriving step slides along the arrow; others glide straight. Units only
 * in `b` fade in where they stand; units only in `a` stay until the end.
 */
export function tween(a: Frame, b: Frame, moves: StoryMove[], t: number): Frame {
  if (t >= 1) return b;
  const paths = new Map<string, LngLat[]>();
  for (const mv of moves) {
    if (mv.unit && mv.type !== 'fire' && !paths.has(mv.unit)) paths.set(mv.unit, mv.path);
  }

  const out: Frame = new Map();
  for (const [uid, to] of b) {
    const from = a.get(uid);
    if (!from) {
      out.set(uid, to);
      continue;
    }
    const path = paths.get(uid);
    // The arrow's path, anchored to where the unit really starts and ends.
    const route = path ? [from.at, ...path.slice(1, -1), to.at] : [from.at, to.at];
    const morph = BANDS.includes(from.shape) && BANDS.includes(to.shape);
    out.set(uid, {
      ...to,
      at: along(route, t),
      facing: lerpAngle(from.facing, to.facing, t),
      width: lerp(from.width, to.width, t),
      depth: lerp(from.depth, to.depth, t),
      shape: morph ? (from.shape === 'crescent' || to.shape === 'crescent' ? 'crescent' : to.shape) : t < 0.5 ? from.shape : to.shape,
      curve: morph ? lerp(bandCurve(from), bandCurve(to), t) : to.curve,
      state: t < 0.5 ? from.state : to.state,
    });
  }
  for (const [uid, from] of a) {
    if (!b.has(uid)) out.set(uid, from);
  }
  // Pinned markers follow their unit's tweened position.
  for (const [uid, r] of out) {
    if (!r.with) continue;
    const host = out.get(r.with);
    if (host) out.set(uid, { ...r, at: dest(host.at, host.facing + 180, behind(host)), facing: host.facing });
  }
  return out;
}

/** A band's bow in metres (a non-crescent band has none). */
function bandCurve(r: Resolved): number {
  return r.shape === 'crescent' ? r.curve : 0;
}

// ── framing ──────────────────────────────────────────────────────────────────

export type Bounds = [[number, number], [number, number]];

/** Bounds of a step: its units' outlines, its arrows and its notes. */
export function stepBounds(
  doc: MapStoryDocument,
  frame: Frame,
  stepIndex: number,
): Bounds | null {
  const pts: LngLat[] = [];
  const kinds = new Map(doc.units.map((u) => [u.id, u.kind]));
  for (const [uid, r] of frame) {
    if (POINT_UNIT_KINDS.includes(kinds.get(uid) ?? '')) pts.push(r.at);
    else pts.push(...formation(r).ring);
  }
  const step = doc.steps[stepIndex];
  for (const mv of step?.moves ?? []) pts.push(...mv.path);
  for (const n of step?.notes ?? []) pts.push(n.at);
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

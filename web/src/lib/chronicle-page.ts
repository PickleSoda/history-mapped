/**
 * Chronicle-page logic — pure, so the defaults and step bookkeeping are
 * unit-tested and the page component stays a thin shell.
 */
import { formatYear } from '@/lib/format';
import type { ChronicleEntry } from '@/lib/schemas/chronicle';
import type { ChronicleGraphStep } from '@/lib/schemas/graph';

/**
 * Above this many edges (externals included) the whole-chronicle graph opens
 * with externals hidden: fcose lays out ~400 elements in a few hundred ms, and
 * past that the outside fringe buries the chronicle's own structure. Measured
 * against the Imperial Rome chronicle (402 nodes / 586 edges with externals,
 * 221 / 355 without) and the 117-step age-of-revolutions one (621 / 1042).
 */
export const EXTERNAL_DEFAULT_MAX_EDGES = 400;

/** Should the whole-chronicle graph start with externals shown? */
export function defaultShowExternal(graph: { edges: readonly unknown[] }): boolean {
  return graph.edges.length <= EXTERNAL_DEFAULT_MAX_EDGES;
}

/** "490 BCE", "490 – 479 BCE" style span; null when no years. */
export function yearSpanText(start: number | null, end: number | null): string | null {
  if (start == null && end == null) return null;
  if (start != null && end != null && start !== end) return `${formatYear(start)} – ${formatYear(end)}`;
  return formatYear((start ?? end) as number);
}

/** One row of the step list: the entry's narrative joined to its graph slice. */
export interface StepRow {
  /** 0-based position — the `step` URL param and scrubber value. */
  index: number;
  entry: ChronicleEntry;
  /** The entry's slice of the chronicle graph (null until it loads / if absent). */
  step: ChronicleGraphStep | null;
}

/** Join the tour's entries (canonical order, as the player indexes them) with
 *  the graph's per-step membership by `entry_id`. */
export function stepRows(
  entries: readonly ChronicleEntry[],
  graphSteps: readonly ChronicleGraphStep[] | undefined,
): StepRow[] {
  const byEntry = new Map((graphSteps ?? []).map((s) => [s.entry_id, s]));
  return entries.map((entry, index) => ({ index, entry, step: byEntry.get(entry.entry_id) ?? null }));
}

/** Clamp a step index into [0, total - 1] (0 for an empty tour). */
export function clampStep(index: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(total - 1, Math.max(0, Math.round(index)));
}

/**
 * Mount hysteresis for lazily mounted step graphs: mount once the row enters
 * the inner (near) zone, keep it while it is inside the outer (far) zone, and
 * unmount only once it leaves the outer zone — so a row scrolling back and
 * forth across one boundary doesn't thrash its canvas. `null` = no reading
 * from that observer yet.
 */
export function nextMounted(prev: boolean, zones: { near: boolean | null; far: boolean | null }): boolean {
  if (zones.near) return true;
  if (zones.far === false) return false;
  return prev;
}

/** Source type token → label ("video_transcript" → "Video transcript"). */
export function sourceTypeLabel(t: string | null): string | null {
  if (!t) return null;
  const s = t.replace(/[_-]+/g, ' ').trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

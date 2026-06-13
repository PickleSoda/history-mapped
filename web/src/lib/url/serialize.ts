/**
 * Pure (de)serializers for URL search-param values.
 *
 * These are framework-agnostic string <-> value functions. The nuqs parsers in
 * `params.ts` wrap these, and the API layer reuses `serializeBbox`/`serializeTime`
 * to build request query strings — one source of truth for the wire format.
 */
import type { Bbox, TimeState } from '@/types/atlas';

/** Round to a fixed number of decimals to keep URLs short and keys stable. */
function round(n: number, dp = 5): number {
  const f = 10 ** dp;
  return Math.round(n * f) / f;
}

// ── bbox: "w,s,e,n" ────────────────────────────────────────────────────────

export function serializeBbox(b: Bbox): string {
  return [b.w, b.s, b.e, b.n].map((n) => round(n)).join(',');
}

export function parseBbox(raw: string): Bbox | null {
  const parts = raw.split(',').map(Number);
  if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) return null;
  const [w, s, e, n] = parts;
  return { w, s, e, n };
}

// ── time: "-490" (instant) or "-490..-480" (range) ─────────────────────────

export function serializeTime(t: TimeState): string {
  return t.kind === 'instant' ? String(t.year) : `${t.start}..${t.end}`;
}

export function parseTime(raw: string): TimeState | null {
  if (raw.includes('..')) {
    const [start, end] = raw.split('..').map(Number);
    if (Number.isNaN(start) || Number.isNaN(end)) return null;
    return { kind: 'range', start, end };
  }
  const year = Number(raw);
  if (Number.isNaN(year)) return null;
  return { kind: 'instant', year };
}

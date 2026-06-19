/**
 * timescope-specific year conversion. The timeline domain is plain historical
 * years (negative = BCE); timescope callbacks hand back `@kikuchan/decimal`
 * values whose `.number()` is that same year. BCE/CE *formatting* is NOT here —
 * use `formatYear` from `@/lib/format`.
 */

/** Minimal shape of the decimal value timescope passes to time callbacks. */
export type DecimalLike = { number(): number };

/**
 * Hard limits for how far the timeline can pan/scrub: 10000 BCE → 2050 CE.
 * Passed to timescope as `timeRange` and used to clamp committed years.
 */
export const AXIS_MIN = -10000;
export const AXIS_MAX = 2050;

/**
 * A timescope time value (Decimal | number | null) → an integer year, or null
 * for null/NaN/Infinity inputs.
 */
export function toYear(v: DecimalLike | number | null): number | null {
  if (v == null) return null;
  const n = typeof v === 'number' ? v : v.number();
  return Number.isFinite(n) ? Math.round(n) : null;
}

/** Clamp a year into the supported axis window. */
export function clampYear(year: number, min = AXIS_MIN, max = AXIS_MAX): number {
  return Math.max(min, Math.min(max, year));
}

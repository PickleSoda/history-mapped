/**
 * Transform API historical periods → timescope gantt spans.
 *
 * Each period becomes a horizontal box: lane = nesting depth, colour = the
 * period's own `color_hex`, label = name. Open-ended or degenerate periods
 * (missing/zero-length ranges) are dropped so the canvas never gets NaN.
 */
import type { HistoricalPeriod } from '@/lib/schemas/reference';

export interface PeriodSpan {
  id: number;
  label: string;
  /** Year (negative = BCE). */
  start: number;
  end: number;
  /** Lane (row) index, 0-based, from the period's depth_level. */
  lane: number;
  /** Canvas-ready hex colour. */
  color: string;
}

/** Neutral fallback when a period has no colour. */
export const DEFAULT_PERIOD_COLOR = '#71717a';

export function periodsToSpans(periods: HistoricalPeriod[]): PeriodSpan[] {
  return periods
    .filter(
      (p) =>
        Number.isFinite(p.start_date) &&
        Number.isFinite(p.end_date) &&
        p.end_date > p.start_date,
    )
    .map((p) => ({
      id: p.period_id,
      label: p.name,
      start: p.start_date,
      end: p.end_date,
      lane: Math.max(0, Math.trunc(p.depth_level)),
      color: p.color_hex || DEFAULT_PERIOD_COLOR,
    }));
}

/** Lane count for a set of spans (max lane + 1), at least 1. */
export function laneCount(spans: PeriodSpan[]): number {
  return spans.reduce((max, s) => Math.max(max, s.lane + 1), 1);
}

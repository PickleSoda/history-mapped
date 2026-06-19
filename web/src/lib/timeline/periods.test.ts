import { describe, it, expect } from 'vitest';
import type { HistoricalPeriod } from '@/lib/schemas/reference';
import { periodsToSpans, laneCount, DEFAULT_PERIOD_COLOR } from './periods';

function period(over: Partial<HistoricalPeriod>): HistoricalPeriod {
  return {
    period_id: 1,
    name: 'Ancient',
    start_date: -3000,
    end_date: 500,
    depth_level: 0,
    parent_period_id: null,
    color_hex: '#8B4513',
    sort_order: 0,
    ...over,
  };
}

describe('periodsToSpans', () => {
  it('maps id/name/dates/colour and lane = depth_level', () => {
    const [s] = periodsToSpans([period({ period_id: 7, name: 'Bronze Age', depth_level: 1 })]);
    expect(s).toEqual({
      id: 7,
      label: 'Bronze Age',
      start: -3000,
      end: 500,
      lane: 1,
      color: '#8B4513',
    });
  });

  it('uses the fallback colour when color_hex is null', () => {
    const [s] = periodsToSpans([period({ color_hex: null })]);
    expect(s.color).toBe(DEFAULT_PERIOD_COLOR);
  });

  it('drops degenerate spans (end <= start) and non-finite dates', () => {
    const out = periodsToSpans([
      period({ period_id: 1, start_date: 100, end_date: 100 }),
      period({ period_id: 2, start_date: 200, end_date: 100 }),
      period({ period_id: 3, start_date: Number.NaN, end_date: 5 }),
      period({ period_id: 4, start_date: -50, end_date: 50 }),
    ]);
    expect(out.map((s) => s.id)).toEqual([4]);
  });

  it('keeps negative (BCE) years intact', () => {
    const [s] = periodsToSpans([period({ start_date: -10000, end_date: -8000 })]);
    expect(s.start).toBe(-10000);
    expect(s.end).toBe(-8000);
  });
});

describe('laneCount', () => {
  it('is max lane + 1', () => {
    expect(laneCount(periodsToSpans([period({ depth_level: 0 }), period({ period_id: 2, depth_level: 3 })]))).toBe(4);
  });
  it('is at least 1 for an empty set', () => {
    expect(laneCount([])).toBe(1);
  });
});

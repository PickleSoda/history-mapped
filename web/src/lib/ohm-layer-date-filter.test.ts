import { describe, expect, it } from 'vitest';
import { ohmDateRange } from './ohm-layer-date-filter';

describe('ohmDateRange', () => {
  it('spans the whole year for a year-only input', () => {
    const range = ohmDateRange('1066');

    expect(range?.startDecimalDate).toBeCloseTo(1066.0, 5);
    expect(range?.endDecimalDate).toBeCloseTo(1067.0, 5);
  });

  it('returns null without a date', () => {
    expect(ohmDateRange(null)).toBeNull();
  });

  it('spans from the start of the first year to the end of the last', () => {
    const range = ohmDateRange({ start: '1000', end: '1100' });

    expect(range?.startDecimalDate).toBeCloseTo(1000.0, 5);
    expect(range?.endDecimalDate).toBeCloseTo(1101.0, 5);
  });
});

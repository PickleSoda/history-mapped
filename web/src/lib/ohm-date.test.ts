import { describe, expect, it } from 'vitest';
import { yearToDecdate } from './ohm-date';

describe('yearToDecdate', () => {
  it('derives the OHM decimal date for a year-only start or end', () => {
    expect(yearToDecdate(1900, 'start')).toBeCloseTo(1900.00137, 5);
    expect(yearToDecdate(1950, 'end')).toBeCloseTo(1950.99863, 5);
  });

  it('applies the same offsets to BCE (negative) years', () => {
    expect(yearToDecdate(-2999, 'start')).toBeCloseTo(-2998.99863, 5);
    expect(yearToDecdate(-2799, 'end')).toBeCloseTo(-2798.00137, 5);
  });
});

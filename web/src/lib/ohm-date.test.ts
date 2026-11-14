import { describe, expect, it } from 'vitest';
import { toOhmDate, toOhmYear, yearToDecdate } from './ohm-date';

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

// Ours is historical (no year 0; -44 is 44 BCE); OHM's is astronomical
// (0000 is 1 BCE; -0043 is 44 BCE).
describe('toOhmYear', () => {
  it('moves a BCE year one toward zero and leaves CE years alone', () => {
    expect(toOhmYear(-44)).toBe(-43);
    expect(toOhmYear(-1)).toBe(0);
    expect(toOhmYear(1)).toBe(1);
    expect(toOhmYear(1453)).toBe(1453);
  });
});

describe('toOhmDate', () => {
  it('converts a BCE date string, keeping its month and day', () => {
    expect(toOhmDate('-0044')).toBe('-0043');
    expect(toOhmDate('-0044-03-15')).toBe('-0043-03-15');
    expect(toOhmDate('-0001')).toBe('0000');
    expect(toOhmDate('-2999-07')).toBe('-2998-07');
  });

  it('leaves CE dates and anything else unchanged', () => {
    expect(toOhmDate('0753')).toBe('0753');
    expect(toOhmDate('1347-10')).toBe('1347-10');
    expect(toOhmDate('not a date')).toBe('not a date');
  });
});

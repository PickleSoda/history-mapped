import { describe, it, expect } from 'vitest';
import { toYear, clampYear, AXIS_MIN, AXIS_MAX } from './year';

describe('toYear', () => {
  it('passes through an integer year', () => expect(toYear(753)).toBe(753));
  it('passes through a negative (BCE) year', () => expect(toYear(-753)).toBe(-753));
  it('rounds a fractional value', () => expect(toYear(-489.6)).toBe(-490));
  it('returns null for null', () => expect(toYear(null)).toBeNull());
  it('unwraps a Decimal-like via .number()', () =>
    expect(toYear({ number: () => -321.4 })).toBe(-321));
});

describe('clampYear', () => {
  it('clamps below the floor', () => expect(clampYear(-99999)).toBe(AXIS_MIN));
  it('clamps above the ceiling', () => expect(clampYear(99999)).toBe(AXIS_MAX));
  it('passes a year inside the window', () => expect(clampYear(476)).toBe(476));
});

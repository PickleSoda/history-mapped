import { describe, expect, it } from 'vitest';
import { ohmDateFilter, ohmDateRange } from './ohm-layer-date-filter';

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

  // Date.UTC reads years 0–99 as 1900–1999; the bounds must not.
  it('spans the right year in the first century', () => {
    for (const year of [1, 50, 98, 99]) {
      const range = ohmDateRange(String(year).padStart(4, '0'));

      expect(range?.startDecimalDate).toBeCloseTo(year, 5);
      expect(range?.endDecimalDate).toBeCloseTo(year + 1, 5);
    }
    expect(ohmDateRange('0050-07')?.startDecimalDate).toBeCloseTo(50 + 181 / 365, 5);
  });

  // Our tiles' decimal dates use our numbering, so the range is read as written.
  it('reads a BCE date as written', () => {
    const range = ohmDateRange('-0044');

    expect(range?.startDecimalDate).toBeCloseTo(-44, 5);
    expect(range?.endDecimalDate).toBeCloseTo(-43, 5);
  });
});

describe('ohmDateFilter', () => {
  const bounds = (date: string) => {
    const json = JSON.stringify(ohmDateFilter(date, null));
    const start = /\["<",\["to-number",\["get","start_decdate"\]\],(-?[\d.]+)\]/.exec(json)?.[1];
    const end = /\[">=",\["to-number",\["get","end_decdate"\]\],(-?[\d.]+)\]/.exec(json)?.[1];
    return [Number(end), Number(start)];
  };

  // OHM numbers years astronomically: 44 BCE is its -0043, 1 BCE its 0000.
  it('looks up a BCE year of ours under OHM\'s number for it', () => {
    expect(bounds('-0044')).toEqual([-43, -42]);
    expect(bounds('-0001')).toEqual([0, 1]);
  });

  it('leaves CE years alone', () => {
    expect(bounds('1066')).toEqual([1066, 1067]);
    expect(bounds('0001')).toEqual([1, 2]);
  });
});

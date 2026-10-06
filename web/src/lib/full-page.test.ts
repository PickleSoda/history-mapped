import { describe, expect, it } from 'vitest';
import {
  closeEntityPage,
  fullForSheet,
  nextSheetForFull,
  openPageKind,
  openPageStack,
  pageKindFor,
} from './full-page';

describe('pageKindFor / openPageKind', () => {
  it('prefers the selected entity over an active chronicle', () => {
    expect(pageKindFor({ sel: 'e1', chron: 'punic' })).toBe('entity');
    expect(pageKindFor({ sel: null, chron: 'punic' })).toBe('chronicle');
    expect(pageKindFor({ sel: null, chron: null })).toBeNull();
  });

  it('is only open while `full` is set', () => {
    expect(openPageKind({ full: false, sel: 'e1', chron: null })).toBeNull();
    expect(openPageKind({ full: true, sel: 'e1', chron: null })).toBe('entity');
    expect(openPageKind({ full: true, sel: null, chron: null })).toBeNull();
  });
});

describe('openPageStack', () => {
  it('stacks the entity page over the chronicle page', () => {
    expect(openPageStack({ full: true, sel: 'e1', chron: 'punic' })).toEqual(['chronicle', 'entity']);
    expect(openPageStack({ full: true, sel: null, chron: 'punic' })).toEqual(['chronicle']);
    expect(openPageStack({ full: true, sel: 'e1', chron: null })).toEqual(['entity']);
    expect(openPageStack({ full: false, sel: 'e1', chron: 'punic' })).toEqual([]);
  });
});

describe('closeEntityPage', () => {
  it('collapses entirely without a chronicle', () => {
    expect(closeEntityPage({ full: true, chron: null })).toEqual({ sel: null, full: false });
  });

  it('falls back to the chronicle page it was opened over', () => {
    expect(closeEntityPage({ full: true, chron: 'punic' })).toEqual({ sel: null, full: true });
  });
});

describe('nextSheetForFull', () => {
  it('snaps to full when the page opens', () => {
    expect(
      nextSheetForFull({ prevFull: false, nextFull: true, hasPage: true, current: 'half' }),
    ).toBe('full');
  });

  it('ignores `full` with nothing to show', () => {
    expect(
      nextSheetForFull({ prevFull: false, nextFull: true, hasPage: false, current: 'peek' }),
    ).toBe('peek');
  });

  it('drops to half when the page collapses from full', () => {
    expect(
      nextSheetForFull({ prevFull: true, nextFull: false, hasPage: true, current: 'full' }),
    ).toBe('half');
    // already dragged down: leave it
    expect(
      nextSheetForFull({ prevFull: true, nextFull: false, hasPage: true, current: 'peek' }),
    ).toBe('peek');
  });
});

describe('fullForSheet', () => {
  it('opens the page when dragged onto the full snap', () => {
    expect(fullForSheet({ height: 'full', full: false, hasPage: true })).toBe(true);
    expect(fullForSheet({ height: 'full', full: false, hasPage: false })).toBeNull();
  });

  it('removes `full` when leaving the full snap', () => {
    expect(fullForSheet({ height: 'half', full: true, hasPage: true })).toBe(false);
    expect(fullForSheet({ height: 'half', full: false, hasPage: true })).toBeNull();
    expect(fullForSheet({ height: 'full', full: true, hasPage: true })).toBeNull();
  });
});

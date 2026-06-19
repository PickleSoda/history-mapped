import { describe, expect, it } from 'vitest';
import {
  heightToSnap,
  nextSheetForSelection,
  sheetContentKind,
  SNAP_POINTS,
  snapToHeight,
} from './sheet';

describe('snap mappers', () => {
  it('maps heights to snap points round-trip', () => {
    expect(heightToSnap('peek')).toBe(SNAP_POINTS[0]);
    expect(heightToSnap('half')).toBe(SNAP_POINTS[1]);
    expect(heightToSnap('full')).toBe(SNAP_POINTS[2]);
    expect(snapToHeight(SNAP_POINTS[0])).toBe('peek');
    expect(snapToHeight(SNAP_POINTS[1])).toBe('half');
    expect(snapToHeight(SNAP_POINTS[2])).toBe('full');
  });
  it('falls back to peek for unknown/null snap', () => {
    expect(snapToHeight(null)).toBe('peek');
    expect(snapToHeight(0.42)).toBe('peek');
  });
});

describe('sheetContentKind', () => {
  it('chronicle wins over selection', () => {
    expect(sheetContentKind({ chronicleActive: true, hasSelection: true })).toBe('chronicle');
  });
  it('selection shows detail', () => {
    expect(sheetContentKind({ chronicleActive: false, hasSelection: true })).toBe('detail');
  });
  it('otherwise list', () => {
    expect(sheetContentKind({ chronicleActive: false, hasSelection: false })).toBe('list');
  });
});

describe('nextSheetForSelection', () => {
  it('raises peek to half when an entity is selected', () => {
    expect(nextSheetForSelection({ prevSel: null, nextSel: 'e:x', current: 'peek' })).toBe('half');
  });
  it('keeps a non-peek height on selection', () => {
    expect(nextSheetForSelection({ prevSel: null, nextSel: 'e:x', current: 'full' })).toBe('full');
  });
  it('drops full to half on deselection', () => {
    expect(nextSheetForSelection({ prevSel: 'e:x', nextSel: null, current: 'full' })).toBe('half');
  });
  it('leaves half alone on deselection', () => {
    expect(nextSheetForSelection({ prevSel: 'e:x', nextSel: null, current: 'half' })).toBe('half');
  });
  it('no change when selection is unchanged', () => {
    expect(nextSheetForSelection({ prevSel: 'e:x', nextSel: 'e:x', current: 'peek' })).toBe('peek');
  });
});

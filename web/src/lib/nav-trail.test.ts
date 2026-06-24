import { describe, expect, it } from 'vitest';
import { focusOf, reconcileTrail } from './nav-trail';
import type { Crumb } from './nav-trail';

const snap = (sel: string | null, chron: string | null, step = 0) => ({ sel, chron, step });

describe('focusOf', () => {
  it('prefers a selected entity over an active chronicle', () => {
    const c = focusOf(snap('rome', 'punic', 3), { entityLabel: 'Rome', entityGroup: 'polity' });
    expect(c).toMatchObject({ key: 'e:rome', kind: 'entity', label: 'Rome', group: 'polity' });
    // captures the tour it branched off from, for restore
    expect(c).toMatchObject({ sel: 'rome', chron: 'punic', step: 3 });
  });

  it('is the chronicle when nothing is selected', () => {
    const c = focusOf(snap(null, 'punic', 2), { chronicleLabel: 'Punic Wars' });
    expect(c).toMatchObject({ key: 'c:punic', kind: 'chronicle', label: 'Punic Wars', sel: null });
  });

  it('is null at the root (list)', () => {
    expect(focusOf(snap(null, null))).toBeNull();
  });

  it('falls back to the id when no label has loaded', () => {
    expect(focusOf(snap('x', null))?.label).toBe('x');
  });
});

describe('reconcileTrail', () => {
  const entity = (id: string, label = id): Crumb => focusOf(snap(id, null), { entityLabel: label })!;

  it('pushes new focuses', () => {
    let t: Crumb[] = [];
    t = reconcileTrail(t, entity('a'));
    t = reconcileTrail(t, entity('b'));
    expect(t.map((c) => c.key)).toEqual(['e:a', 'e:b']);
  });

  it('returns the same reference when nothing changed', () => {
    const t = reconcileTrail([], entity('a'));
    expect(reconcileTrail(t, entity('a'))).toBe(t);
  });

  it('refreshes the tip in place when the label loads', () => {
    const t = reconcileTrail([], focusOf(snap('a', null))!); // label = "a"
    const t2 = reconcileTrail(t, entity('a', 'Athens'));
    expect(t2).not.toBe(t);
    expect(t2).toHaveLength(1);
    expect(t2[0].label).toBe('Athens');
  });

  it('truncates back when revisiting an earlier crumb (browser back / crumb click)', () => {
    let t = [entity('a'), entity('b'), entity('c')];
    t = reconcileTrail(t, entity('a'));
    expect(t.map((c) => c.key)).toEqual(['e:a']);
  });

  it('resets to empty at the root', () => {
    const t = [entity('a'), entity('b')];
    expect(reconcileTrail(t, null)).toEqual([]);
  });

  it('keeps the same empty reference at the root', () => {
    const empty: Crumb[] = [];
    expect(reconcileTrail(empty, null)).toBe(empty);
  });
});

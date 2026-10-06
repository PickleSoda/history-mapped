import { describe, expect, it } from 'vitest';
import {
  computeVisibility,
  groupFacets,
  isFilterActive,
  makeFilter,
  overlapsYears,
  toggled,
  typeFacets,
  UNTYPED,
  yearExtent,
} from './filter';
import { edge, node } from './fixtures';

const nodes = [
  node('r', { depth: 0 }),
  node('a', { entity_group: 'event' }),
  node('b', { entity_group: 'place' }),
  node('c', { entity_group: 'place' }),
];
const edges = [
  edge('ra', 'r', 'a', { relationship_type: 'participated_in', start_year: -490, end_year: -490 }),
  edge('rb', 'r', 'b', { relationship_type: 'located_at', start_year: 100 }),
  edge('bc', 'b', 'c', { relationship_type: 'located_at' }),
];

const ids = (s: Set<string>) => [...s].sort();

describe('computeVisibility', () => {
  it('shows everything with the empty filter', () => {
    const v = computeVisibility(nodes, edges, makeFilter(), { root: 'r' });
    expect(ids(v.nodes)).toEqual(['a', 'b', 'c', 'r']);
    expect(ids(v.edges)).toEqual(['bc', 'ra', 'rb']);
  });

  it('hides a relationship type and the nodes it strands', () => {
    const v = computeVisibility(nodes, edges, makeFilter({ hiddenTypes: new Set(['participated_in']) }), {
      root: 'r',
    });
    expect(ids(v.edges)).toEqual(['bc', 'rb']);
    expect(ids(v.nodes)).toEqual(['b', 'c', 'r']);
  });

  it('hides a group (never the root) and edges to it', () => {
    const v = computeVisibility(
      nodes,
      edges,
      makeFilter({ hiddenGroups: new Set(['place', 'polity']) }),
      { root: 'r' },
    );
    expect(ids(v.nodes)).toEqual(['a', 'r']);
    expect(ids(v.edges)).toEqual(['ra']);
  });

  it('keeps the root even when it has no visible edges', () => {
    const v = computeVisibility(nodes, edges, makeFilter({ hiddenTypes: new Set(['participated_in', 'located_at']) }), {
      root: 'r',
    });
    expect(ids(v.nodes)).toEqual(['r']);
    expect(v.edges.size).toBe(0);
  });

  it('filters by year overlap, letting null bounds pass', () => {
    const v = computeVisibility(nodes, edges, makeFilter({ years: { from: 0, to: 50 } }), {
      root: 'r',
    });
    // ra (-490) is out; rb starts 100 → out; bc has no years → in
    expect(ids(v.edges)).toEqual(['bc']);
    expect(ids(v.nodes)).toEqual(['b', 'c', 'r']);
  });

  it('drops external edges and outside nodes when externals are off', () => {
    const cn = [
      node('x', { in_chronicle: true }),
      node('y', { in_chronicle: true }),
      node('z', { in_chronicle: true }),
      node('out', { in_chronicle: false }),
    ];
    const ce = [
      edge('xy', 'x', 'y', { scope: 'primary' }),
      edge('xo', 'x', 'out', { scope: 'external' }),
    ];
    const anchors = new Set(['x', 'y', 'z']);
    const on = computeVisibility(cn, ce, makeFilter(), { anchors });
    expect(ids(on.nodes)).toEqual(['out', 'x', 'y', 'z']);
    const off = computeVisibility(cn, ce, makeFilter({ external: false }), { anchors });
    expect(ids(off.edges)).toEqual(['xy']);
    // z has no edges but is a chronicle member (anchor) → stays
    expect(ids(off.nodes)).toEqual(['x', 'y', 'z']);
  });
});

describe('facets', () => {
  it('counts types by frequency and groups in display order, skipping the root', () => {
    expect(typeFacets([...edges, edge('n', 'a', 'b', { relationship_type: null })])).toEqual([
      { key: 'located_at', count: 2 },
      { key: 'participated_in', count: 1 },
      { key: UNTYPED, count: 1 },
    ]);
    expect(groupFacets(nodes, ['polity', 'place', 'event'], 'r')).toEqual([
      { key: 'place', count: 2 },
      { key: 'event', count: 1 },
    ]);
  });

  it('spans the known edge years', () => {
    expect(yearExtent(edges)).toEqual({ from: -490, to: 100 });
    expect(yearExtent([edge('n', 'a', 'b')])).toBeNull();
  });
});

describe('helpers', () => {
  it('overlapsYears treats null bounds as open', () => {
    expect(overlapsYears({ start_year: 10, end_year: null }, { from: 500, to: 600 })).toBe(true);
    expect(overlapsYears({ start_year: null, end_year: 10 }, { from: 500, to: 600 })).toBe(false);
    expect(overlapsYears({ start_year: -5, end_year: 5 }, { from: 0, to: 0 })).toBe(true);
  });

  it('toggled flips membership without mutating', () => {
    const s = new Set(['a']);
    expect([...toggled(s, 'b')]).toEqual(['a', 'b']);
    expect([...toggled(s, 'a')]).toEqual([]);
    expect([...s]).toEqual(['a']);
  });

  it('isFilterActive', () => {
    expect(isFilterActive(makeFilter())).toBe(false);
    expect(isFilterActive(makeFilter({ external: false }))).toBe(true);
    expect(isFilterActive(makeFilter({ years: { from: 0, to: 1 } }))).toBe(true);
  });
});

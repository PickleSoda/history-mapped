import { describe, expect, it } from 'vitest';
import { edge, node } from './fixtures';
import {
  BASE,
  collapseExpansion,
  createGraphModel,
  edgesBetween,
  introducedBy,
  isExpanded,
  mergeNeighbourhood,
  nodeDiameter,
  shortestPath,
} from './model';

// root R — A, R — B (base); A's neighbourhood adds C and links A — B.
const base = {
  nodes: [node('r', { depth: 0 }), node('a'), node('b')],
  edges: [edge('ra', 'r', 'a'), edge('rb', 'r', 'b')],
};
const aHood = {
  nodes: [node('a', { depth: 0 }), node('r'), node('b'), node('c')],
  edges: [edge('ra', 'r', 'a'), edge('ab', 'a', 'b'), edge('ac', 'a', 'c')],
};

describe('createGraphModel', () => {
  it('owns everything by BASE and drops dangling edges', () => {
    const m = createGraphModel(
      { nodes: base.nodes, edges: [...base.edges, edge('rx', 'r', 'missing')] },
      'r',
    );
    expect([...m.nodes.keys()]).toEqual(['r', 'a', 'b']);
    expect([...m.edges.keys()]).toEqual(['ra', 'rb']);
    expect(introducedBy(m, 'a')).toBe(BASE);
    expect(m.root).toBe('r');
  });
});

describe('mergeNeighbourhood', () => {
  it('adds only new nodes/edges and records who introduced them', () => {
    const m0 = createGraphModel(base, 'r');
    const { model, added, addedEdges } = mergeNeighbourhood(m0, 'a', aHood);
    expect(added).toEqual(['c']);
    expect(addedEdges).toEqual(['ab', 'ac']);
    expect(introducedBy(model, 'c')).toBe('a');
    // already present: introduced by the base, now also needed by `a`
    expect(introducedBy(model, 'b')).toBe(BASE);
    expect([...(model.nodeOwners.get('b') ?? [])]).toEqual([BASE, 'a']);
    expect(isExpanded(model, 'a')).toBe(true);
    // keeps existing node data (depth from the base, not from the expansion)
    expect(model.nodes.get('a')?.depth).toBe(1);
  });

  it('does not mutate the input model', () => {
    const m0 = createGraphModel(base, 'r');
    mergeNeighbourhood(m0, 'a', aHood);
    expect(m0.nodes.size).toBe(3);
    expect(m0.expansions.size).toBe(0);
  });

  it('is idempotent and ignores unknown or BASE expansion ids', () => {
    const m1 = mergeNeighbourhood(createGraphModel(base, 'r'), 'a', aHood).model;
    expect(mergeNeighbourhood(m1, 'a', aHood).model).toBe(m1);
    expect(mergeNeighbourhood(m1, 'zzz', aHood).model).toBe(m1);
    expect(mergeNeighbourhood(m1, BASE, aHood).model).toBe(m1);
  });

  it('carries the truncated flag onto the expansion', () => {
    const m = mergeNeighbourhood(createGraphModel(base, 'r'), 'a', { ...aHood, truncated: true })
      .model;
    expect(m.expansions.get('a')).toEqual({ added: ['c'], truncated: true });
  });
});

describe('collapseExpansion', () => {
  it('removes exactly what the expansion added', () => {
    const m1 = mergeNeighbourhood(createGraphModel(base, 'r'), 'a', aHood).model;
    const { model, removed, removedEdges } = collapseExpansion(m1, 'a');
    expect(removed).toEqual(['c']);
    expect(removedEdges.sort()).toEqual(['ab', 'ac']);
    expect([...model.nodes.keys()]).toEqual(['r', 'a', 'b']);
    expect([...model.edges.keys()]).toEqual(['ra', 'rb']);
    expect([...(model.nodeOwners.get('b') ?? [])]).toEqual([BASE]);
    expect(isExpanded(model, 'a')).toBe(false);
  });

  it('keeps nodes another expansion still needs', () => {
    const bHood = {
      nodes: [node('b'), node('c'), node('d')],
      edges: [edge('bc', 'b', 'c'), edge('bd', 'b', 'd')],
    };
    let m = createGraphModel(base, 'r');
    m = mergeNeighbourhood(m, 'a', aHood).model;
    m = mergeNeighbourhood(m, 'b', bHood).model;
    const { model, removed } = collapseExpansion(m, 'a');
    expect(removed).toEqual([]); // c is still needed by b's expansion
    expect(model.nodes.has('c')).toBe(true);
    expect(model.edges.has('bc')).toBe(true);
    expect(model.edges.has('ac')).toBe(false);
    expect(introducedBy(model, 'c')).toBe('b');
  });

  it('cascades into expansions of nodes it removes', () => {
    const cHood = {
      nodes: [node('c'), node('e')],
      edges: [edge('ce', 'c', 'e')],
    };
    let m = createGraphModel(base, 'r');
    m = mergeNeighbourhood(m, 'a', aHood).model;
    m = mergeNeighbourhood(m, 'c', cHood).model;
    const { model, removed } = collapseExpansion(m, 'a');
    expect(removed.sort()).toEqual(['c', 'e']);
    expect(model.expansions.size).toBe(0);
    expect([...model.edges.keys()]).toEqual(['ra', 'rb']);
  });

  it('never removes the base and is a no-op for unknown ids', () => {
    const m = createGraphModel(base, 'r');
    expect(collapseExpansion(m, BASE).model).toBe(m);
    expect(collapseExpansion(m, 'a').model).toBe(m);
  });

  it('round-trips a merge back to the base node and edge sets', () => {
    const m0 = createGraphModel(base, 'r');
    const m2 = collapseExpansion(mergeNeighbourhood(m0, 'b', aHood).model, 'b').model;
    expect([...m2.nodes.keys()].sort()).toEqual([...m0.nodes.keys()].sort());
    expect([...m2.edges.keys()].sort()).toEqual([...m0.edges.keys()].sort());
  });
});

describe('shortestPath / edgesBetween', () => {
  const edges = [edge('ra', 'r', 'a'), edge('ab', 'a', 'b'), edge('cb', 'c', 'b')];

  it('walks edges regardless of direction and reports orientation', () => {
    const p = shortestPath(edges, 'r', 'c');
    expect(p?.map((s) => [s.edge.id, s.forward])).toEqual([
      ['ra', true],
      ['ab', true],
      ['cb', false],
    ]);
  });

  it('returns [] for self, null when unreachable or filtered out', () => {
    expect(shortestPath(edges, 'r', 'r')).toEqual([]);
    expect(shortestPath(edges, 'r', 'zzz')).toBeNull();
    expect(shortestPath(edges, 'r', 'c', new Set(['ra', 'cb']))).toBeNull();
  });

  it('finds direct edges in both directions', () => {
    const es = [...edges, edge('br', 'b', 'r')];
    expect(edgesBetween(es, 'r', 'b').map((e) => e.id)).toEqual(['br']);
    expect(edgesBetween(es, 'a', 'r').map((e) => e.id)).toEqual(['ra']);
  });
});

describe('nodeDiameter', () => {
  it('grows with impact, is bounded, and enlarges the root', () => {
    expect(nodeDiameter(1)).toBe(12);
    expect(nodeDiameter(100)).toBe(42);
    expect(nodeDiameter(98)).toBeGreaterThan(nodeDiameter(56));
    expect(nodeDiameter(500)).toBe(42);
    expect(nodeDiameter(null)).toBe(20);
    expect(nodeDiameter(100, true)).toBeGreaterThan(nodeDiameter(100));
  });
});

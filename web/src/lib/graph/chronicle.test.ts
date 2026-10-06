import { describe, expect, it } from 'vitest';
import type { ChronicleGraphStep } from '@/lib/schemas/graph';
import { externalNodeIds, findStep, stepHighlight, stepSubgraph } from './chronicle';
import { edge, node } from './fixtures';

const step = (
  sequence_order: number,
  entity_ids: string[],
  relationship_ids: string[],
  primary_relationship_id: string | null,
): ChronicleGraphStep => ({
  entry_id: `entry-${sequence_order}`,
  sequence_order,
  start_year: null,
  end_year: null,
  primary_relationship_id,
  entity_ids,
  relationship_ids,
});

// Chronicle {a, b, c}; out1/out2 outside it. Step 4 = a, b; step 7 = b, c.
const graph = {
  nodes: [
    node('a', { in_chronicle: true, steps: [4] }),
    node('b', { in_chronicle: true, steps: [4, 7] }),
    node('c', { in_chronicle: true, steps: [7] }),
    node('out1', { in_chronicle: false }),
    node('out2', { in_chronicle: false }),
  ],
  edges: [
    edge('ab', 'a', 'b', { scope: 'primary', steps: [4] }),
    edge('bc', 'b', 'c', { scope: 'primary', steps: [7] }),
    edge('ac', 'a', 'c', { scope: 'internal', steps: [] }),
    edge('a-out1', 'a', 'out1', { scope: 'external' }),
    edge('out2-c', 'out2', 'c', { scope: 'external' }),
  ],
  steps: [step(4, ['a', 'b'], ['ab'], 'ab'), step(7, ['b', 'c'], ['bc'], 'bc')],
};

describe('stepSubgraph', () => {
  it('takes exactly the step’s entities and relationships', () => {
    const s = stepSubgraph(graph, 4);
    expect(s?.nodes.map((n) => n.id)).toEqual(['a', 'b']);
    expect(s?.edges.map((e) => e.id)).toEqual(['ab']);
    expect(s?.primaryEdgeId).toBe('ab');
    expect(s?.externalNodeIds.size).toBe(0);
  });

  it('adds the step’s external edges and their far ends when asked', () => {
    const s = stepSubgraph(graph, 7, { external: true });
    expect(s?.nodes.map((n) => n.id)).toEqual(['b', 'c', 'out2']);
    expect(s?.edges.map((e) => e.id)).toEqual(['bc', 'out2-c']);
    expect([...(s?.externalNodeIds ?? [])]).toEqual(['out2']);
  });

  it('is null for an unknown step and drops a primary that is missing', () => {
    expect(stepSubgraph(graph, 99)).toBeNull();
    const g = { ...graph, steps: [step(1, ['a'], ['gone'], 'gone')] };
    const s = stepSubgraph(g, 1);
    expect(s?.edges).toEqual([]);
    expect(s?.primaryEdgeId).toBeNull();
  });
});

describe('stepHighlight / findStep / externalNodeIds', () => {
  it('returns the step’s id sets by sequence_order', () => {
    const h = stepHighlight(graph, 7);
    expect([...(h?.nodes ?? [])]).toEqual(['b', 'c']);
    expect([...(h?.edges ?? [])]).toEqual(['bc']);
    expect(stepHighlight(graph, 5)).toBeNull();
    expect(findStep(graph, 4)?.entry_id).toBe('entry-4');
  });

  it('lists the nodes outside the chronicle', () => {
    expect([...externalNodeIds(graph)].sort()).toEqual(['out1', 'out2']);
  });
});

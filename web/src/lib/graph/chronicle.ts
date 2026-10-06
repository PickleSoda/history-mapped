/**
 * Chronicle-graph slicing: a step's own subgraph (for the per-step graphs) and
 * its highlight set (for the step scrubber over the whole-chronicle graph).
 */
import type { ChronicleGraphStep, GraphEdge, GraphNode } from '@/lib/schemas/graph';

/** Any chronicle-graph-shaped payload (the API type, or a test fixture). */
export interface ChronicleGraphLike {
  nodes: readonly GraphNode[];
  edges: readonly GraphEdge[];
  steps: readonly ChronicleGraphStep[];
}

export interface StepSubgraph {
  step: ChronicleGraphStep;
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** The step's primary relationship, when it is in the graph. */
  primaryEdgeId: string | null;
  /** Nodes outside the step that `external` pulled in (draw them dimmed). */
  externalNodeIds: Set<string>;
}

/** Find a step by its `sequence_order` (the value node/edge `steps` carry). */
export function findStep(
  graph: Pick<ChronicleGraphLike, 'steps'>,
  sequenceOrder: number,
): ChronicleGraphStep | null {
  return graph.steps.find((s) => s.sequence_order === sequenceOrder) ?? null;
}

/**
 * The subgraph of one step: its `entity_ids` and `relationship_ids`. With
 * `external`, also the external edges touching any of the step's entities and
 * the outside entities at their far ends. Order follows the payload, so the
 * output is stable for memoisation. Null for an unknown step.
 */
export function stepSubgraph(
  graph: ChronicleGraphLike,
  sequenceOrder: number,
  opts: { external?: boolean } = {},
): StepSubgraph | null {
  const step = findStep(graph, sequenceOrder);
  if (!step) return null;
  const nodeIds = new Set(step.entity_ids);
  const edgeIds = new Set(step.relationship_ids);
  const externalNodeIds = new Set<string>();

  if (opts.external) {
    for (const e of graph.edges) {
      if (e.scope !== 'external') continue;
      const inSrc = nodeIds.has(e.source);
      const inTgt = nodeIds.has(e.target);
      if (inSrc === inTgt) continue;
      edgeIds.add(e.id);
      externalNodeIds.add(inSrc ? e.target : e.source);
    }
  }
  const keep = new Set([...nodeIds, ...externalNodeIds]);
  const nodes = graph.nodes.filter((n) => keep.has(n.id));
  const present = new Set(nodes.map((n) => n.id));
  const edges = graph.edges.filter(
    (e) => edgeIds.has(e.id) && present.has(e.source) && present.has(e.target),
  );
  const primaryEdgeId =
    step.primary_relationship_id && edges.some((e) => e.id === step.primary_relationship_id)
      ? step.primary_relationship_id
      : null;
  return { step, nodes, edges, primaryEdgeId, externalNodeIds };
}

/** Node + edge ids to highlight in the whole-chronicle graph for one step. */
export function stepHighlight(
  graph: Pick<ChronicleGraphLike, 'steps'>,
  sequenceOrder: number,
): { nodes: Set<string>; edges: Set<string> } | null {
  const step = findStep(graph, sequenceOrder);
  if (!step) return null;
  return { nodes: new Set(step.entity_ids), edges: new Set(step.relationship_ids) };
}

/** Ids of the nodes outside the chronicle (externals), for `dimmedNodes`. */
export function externalNodeIds(graph: Pick<ChronicleGraphLike, 'nodes'>): Set<string> {
  return new Set(graph.nodes.filter((n) => n.in_chronicle === false).map((n) => n.id));
}

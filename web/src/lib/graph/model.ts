/**
 * Relation-graph model — pure, immutable, framework-free.
 *
 * The graph the user sees is a *base* payload (an entity's neighbourhood, a
 * chronicle graph, a step subgraph) plus any number of *expansions*: depth-1
 * neighbourhoods fetched for nodes the user expanded. Every node and edge
 * records the set of owners that need it — `BASE` or the id of the expanded
 * node whose neighbourhood brought it in — so collapsing an expansion removes
 * exactly what nothing else still needs.
 */
import type { GraphEdge, GraphNode } from '@/lib/schemas/graph';

/** Owner id of the base payload. Never collapsible. */
export const BASE = '@base';

/** A node/edge payload (an API graph response or any slice of one). */
export interface GraphPayload<N extends GraphNode = GraphNode, E extends GraphEdge = GraphEdge> {
  nodes: readonly N[];
  edges: readonly E[];
  truncated?: boolean;
}

export interface Expansion {
  /** Node ids that were new to the graph when this expansion merged. */
  added: string[];
  /** The neighbourhood fetch hit the server's edge limit. */
  truncated: boolean;
}

export interface GraphModel {
  root: string | null;
  nodes: ReadonlyMap<string, GraphNode>;
  edges: ReadonlyMap<string, GraphEdge>;
  /** Owners (BASE / expanded node ids) of each node, in arrival order — the
   *  first owner is the one that introduced it. */
  nodeOwners: ReadonlyMap<string, ReadonlySet<string>>;
  edgeOwners: ReadonlyMap<string, ReadonlySet<string>>;
  /** Expanded node id → what its expansion brought, in expansion order. */
  expansions: ReadonlyMap<string, Expansion>;
}

function withOwner(
  owners: Map<string, ReadonlySet<string>>,
  id: string,
  owner: string,
): void {
  const prev = owners.get(id);
  if (prev?.has(owner)) return;
  owners.set(id, new Set([...(prev ?? []), owner]));
}

/** A fresh model from a base payload. Edges whose ends aren't in the payload
 *  are dropped (the canvas can't draw a dangling edge). */
export function createGraphModel(payload: GraphPayload, root: string | null = null): GraphModel {
  const nodes = new Map<string, GraphNode>();
  const edges = new Map<string, GraphEdge>();
  const nodeOwners = new Map<string, ReadonlySet<string>>();
  const edgeOwners = new Map<string, ReadonlySet<string>>();
  for (const n of payload.nodes) {
    nodes.set(n.id, n);
    withOwner(nodeOwners, n.id, BASE);
  }
  for (const e of payload.edges) {
    if (!nodes.has(e.source) || !nodes.has(e.target)) continue;
    edges.set(e.id, e);
    withOwner(edgeOwners, e.id, BASE);
  }
  return { root, nodes, edges, nodeOwners, edgeOwners, expansions: new Map() };
}

/** Owner that brought a node into the graph (BASE or an expanded node id). */
export function introducedBy(model: GraphModel, id: string): string | null {
  const owners = model.nodeOwners.get(id);
  return owners ? (owners.values().next().value ?? null) : null;
}

export function isExpanded(model: GraphModel, id: string): boolean {
  return model.expansions.has(id);
}

/**
 * Merge a node's depth-1 neighbourhood into the graph as the expansion of
 * `expandedId`. Existing nodes/edges keep their data and gain the owner; new
 * ones are added. Idempotent: re-merging an expanded node is a no-op.
 */
export function mergeNeighbourhood(
  model: GraphModel,
  expandedId: string,
  payload: GraphPayload,
): { model: GraphModel; added: string[]; addedEdges: string[] } {
  if (expandedId === BASE || model.expansions.has(expandedId) || !model.nodes.has(expandedId)) {
    return { model, added: [], addedEdges: [] };
  }
  const nodes = new Map(model.nodes);
  const edges = new Map(model.edges);
  const nodeOwners = new Map(model.nodeOwners);
  const edgeOwners = new Map(model.edgeOwners);
  const added: string[] = [];
  const addedEdges: string[] = [];

  for (const n of payload.nodes) {
    // An expansion never owns its own node: it exists because something else
    // needs it, and must go when that goes (see the cascade in collapse).
    if (n.id === expandedId) continue;
    if (!nodes.has(n.id)) {
      nodes.set(n.id, n);
      added.push(n.id);
    }
    withOwner(nodeOwners, n.id, expandedId);
  }
  for (const e of payload.edges) {
    if (!nodes.has(e.source) || !nodes.has(e.target)) continue;
    if (!edges.has(e.id)) {
      edges.set(e.id, e);
      addedEdges.push(e.id);
    }
    withOwner(edgeOwners, e.id, expandedId);
  }

  const expansions = new Map(model.expansions);
  expansions.set(expandedId, { added, truncated: payload.truncated ?? false });
  return {
    model: { ...model, nodes, edges, nodeOwners, edgeOwners, expansions },
    added,
    addedEdges,
  };
}

/**
 * Undo the expansion of `expandedId`: drop its ownership everywhere and remove
 * the nodes/edges nothing else (BASE or another expansion) still needs. A
 * removed node that was itself expanded is collapsed too (cascade), so no
 * orphaned sub-expansion is left floating. Edges touching a removed node go
 * with it.
 */
export function collapseExpansion(
  model: GraphModel,
  expandedId: string,
): { model: GraphModel; removed: string[]; removedEdges: string[] } {
  if (!model.expansions.has(expandedId)) return { model, removed: [], removedEdges: [] };

  const nodes = new Map(model.nodes);
  const edges = new Map(model.edges);
  const nodeOwners = new Map(model.nodeOwners);
  const edgeOwners = new Map(model.edgeOwners);
  const expansions = new Map(model.expansions);
  const removed: string[] = [];
  const removedEdges = new Set<string>();

  const queue = [expandedId];
  while (queue.length > 0) {
    const owner = queue.shift() as string;
    if (!expansions.delete(owner)) continue;
    for (const [id, owners] of nodeOwners) {
      if (!owners.has(owner)) continue;
      const rest = new Set(owners);
      rest.delete(owner);
      if (rest.size > 0) {
        nodeOwners.set(id, rest);
        continue;
      }
      nodeOwners.delete(id);
      nodes.delete(id);
      removed.push(id);
      if (expansions.has(id)) queue.push(id);
    }
    for (const [id, owners] of edgeOwners) {
      if (!owners.has(owner)) continue;
      const rest = new Set(owners);
      rest.delete(owner);
      if (rest.size > 0) edgeOwners.set(id, rest);
      else removedEdges.add(id);
    }
  }

  // Edges whose owner set emptied, plus any edge left touching a removed node.
  for (const [id, e] of edges) {
    if (removedEdges.has(id) || !nodes.has(e.source) || !nodes.has(e.target)) {
      removedEdges.add(id);
      edges.delete(id);
      edgeOwners.delete(id);
    }
  }
  // Prune `added` lists of surviving expansions so they keep naming live nodes.
  for (const [id, x] of expansions) {
    if (x.added.some((n) => !nodes.has(n))) {
      expansions.set(id, { ...x, added: x.added.filter((n) => nodes.has(n)) });
    }
  }

  return {
    model: { ...model, nodes, edges, nodeOwners, edgeOwners, expansions },
    removed,
    removedEdges: [...removedEdges],
  };
}

/** One step of a path: the edge, and whether it is walked source → target. */
export interface PathStep {
  edge: GraphEdge;
  forward: boolean;
}

/**
 * Shortest undirected path from `from` to `to` through `edges` (BFS), as the
 * edges walked in order. Null when unreachable; empty when `from === to`.
 * `allowed`, when given, restricts the walk to those edge ids (e.g. visible).
 */
export function shortestPath(
  edges: Iterable<GraphEdge>,
  from: string,
  to: string,
  allowed?: ReadonlySet<string>,
): PathStep[] | null {
  if (from === to) return [];
  const adj = new Map<string, GraphEdge[]>();
  for (const e of edges) {
    if (allowed && !allowed.has(e.id)) continue;
    for (const end of [e.source, e.target]) {
      const list = adj.get(end);
      if (list) list.push(e);
      else adj.set(end, [e]);
    }
  }
  const prev = new Map<string, PathStep & { from: string }>();
  const seen = new Set([from]);
  const queue = [from];
  while (queue.length > 0) {
    const at = queue.shift() as string;
    for (const e of adj.get(at) ?? []) {
      const forward = e.source === at;
      const next = forward ? e.target : e.source;
      if (seen.has(next)) continue;
      seen.add(next);
      prev.set(next, { edge: e, forward, from: at });
      if (next === to) {
        const path: PathStep[] = [];
        let cur = to;
        while (cur !== from) {
          const step = prev.get(cur) as PathStep & { from: string };
          path.unshift({ edge: step.edge, forward: step.forward });
          cur = step.from;
        }
        return path;
      }
      queue.push(next);
    }
  }
  return null;
}

/** Every edge directly between `a` and `b`, either direction. */
export function edgesBetween(edges: Iterable<GraphEdge>, a: string, b: string): GraphEdge[] {
  const out: GraphEdge[] = [];
  for (const e of edges) {
    if ((e.source === a && e.target === b) || (e.source === b && e.target === a)) out.push(e);
  }
  return out;
}

/** Node diameter (px) from an integer 1–100 impact score. Quadratic so the
 *  heavy hitters stand out; unknown impact draws mid-small. */
export function nodeDiameter(impact: number | null, root = false): number {
  const t = impact == null ? 0.5 : Math.min(100, Math.max(1, impact)) / 100;
  const d = 12 + 30 * t * t;
  return Math.round(root ? d * 1.25 : d);
}

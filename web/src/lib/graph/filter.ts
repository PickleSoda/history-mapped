/**
 * Client-side graph filters. Filtering never refetches: it computes which
 * loaded elements are visible and the canvas hides the rest, so positions stay
 * put and toggling a chip is instant.
 */
import type { GraphEdge, GraphNode } from '@/lib/schemas/graph';
import type { EntityGroup } from '@/types/atlas';

/** Chip key for an edge without a type. */
export const UNTYPED = 'untyped';

export interface YearRange {
  from: number;
  to: number;
}

export interface GraphFilter {
  /** Relationship types switched off (new types arriving on expand show). */
  hiddenTypes: ReadonlySet<string>;
  hiddenGroups: ReadonlySet<EntityGroup>;
  /** Relationship-year window; null = no year filter. */
  years: YearRange | null;
  /** Chronicle graphs: show edges/nodes outside the chronicle. */
  external: boolean;
}

export const EMPTY_FILTER: GraphFilter = {
  hiddenTypes: new Set(),
  hiddenGroups: new Set(),
  years: null,
  external: true,
};

export function makeFilter(init: Partial<GraphFilter> = {}): GraphFilter {
  return { ...EMPTY_FILTER, ...init };
}

export function isFilterActive(f: GraphFilter): boolean {
  return f.hiddenTypes.size > 0 || f.hiddenGroups.size > 0 || f.years !== null || !f.external;
}

export const edgeTypeKey = (e: GraphEdge): string => e.relationship_type ?? UNTYPED;

/** Toggle membership of `key` in a set, immutably. */
export function toggled<T>(set: ReadonlySet<T>, key: T): Set<T> {
  const next = new Set(set);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}

/**
 * Does an edge's [start, end] overlap the window? Mirrors the API: a null
 * bound is unbounded, and an edge with no years at all always passes.
 */
export function overlapsYears(e: Pick<GraphEdge, 'start_year' | 'end_year'>, r: YearRange): boolean {
  const lo = e.start_year ?? Number.NEGATIVE_INFINITY;
  const hi = e.end_year ?? Number.POSITIVE_INFINITY;
  return lo <= r.to && hi >= r.from;
}

export interface Visibility {
  nodes: Set<string>;
  edges: Set<string>;
}

/**
 * Which nodes and edges the filter leaves visible.
 *
 * - A node is *eligible* unless its group is hidden or (externals off) it sits
 *   outside the chronicle. The root is always eligible.
 * - An edge is visible when both ends are eligible, its type is on, it
 *   overlaps the year window, and (externals off) it isn't an external edge.
 * - A node is visible when eligible and either an anchor (root, chronicle
 *   members) or touched by a visible edge — so filtering doesn't strand
 *   orphan nodes in the canvas.
 */
export function computeVisibility(
  nodes: Iterable<GraphNode>,
  edges: Iterable<GraphEdge>,
  filter: GraphFilter,
  opts: { root?: string | null; anchors?: ReadonlySet<string> } = {},
): Visibility {
  const eligible = new Set<string>();
  const anchors = new Set(opts.anchors ?? []);
  if (opts.root) anchors.add(opts.root);
  for (const n of nodes) {
    if (n.id === opts.root) {
      eligible.add(n.id);
      continue;
    }
    if (filter.hiddenGroups.has(n.entity_group)) continue;
    if (!filter.external && n.in_chronicle === false) continue;
    eligible.add(n.id);
  }

  const visibleEdges = new Set<string>();
  const touched = new Set<string>();
  for (const e of edges) {
    if (!eligible.has(e.source) || !eligible.has(e.target)) continue;
    if (filter.hiddenTypes.has(edgeTypeKey(e))) continue;
    if (filter.years && !overlapsYears(e, filter.years)) continue;
    if (!filter.external && e.scope === 'external') continue;
    visibleEdges.add(e.id);
    touched.add(e.source);
    touched.add(e.target);
  }

  const visibleNodes = new Set<string>();
  for (const id of eligible) {
    if (anchors.has(id) || touched.has(id)) visibleNodes.add(id);
  }
  return { nodes: visibleNodes, edges: visibleEdges };
}

export interface Facet<K extends string = string> {
  key: K;
  count: number;
}

/** Relationship types present, most frequent first (ties alphabetical). */
export function typeFacets(edges: Iterable<GraphEdge>): Facet[] {
  const counts = new Map<string, number>();
  for (const e of edges) counts.set(edgeTypeKey(e), (counts.get(edgeTypeKey(e)) ?? 0) + 1);
  return [...counts]
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count || a.key.localeCompare(b.key));
}

/** Entity groups present (excluding the root), in `order`. */
export function groupFacets(
  nodes: Iterable<GraphNode>,
  order: readonly EntityGroup[],
  root?: string | null,
): Facet<EntityGroup>[] {
  const counts = new Map<EntityGroup, number>();
  for (const n of nodes) {
    if (n.id === root) continue;
    counts.set(n.entity_group, (counts.get(n.entity_group) ?? 0) + 1);
  }
  return order.filter((g) => counts.has(g)).map((g) => ({ key: g, count: counts.get(g) as number }));
}

/** Min/max over the edges' known years, or null when none carry a year. */
export function yearExtent(edges: Iterable<GraphEdge>): YearRange | null {
  let from = Number.POSITIVE_INFINITY;
  let to = Number.NEGATIVE_INFINITY;
  for (const e of edges) {
    for (const y of [e.start_year, e.end_year]) {
      if (y == null) continue;
      if (y < from) from = y;
      if (y > to) to = y;
    }
  }
  return Number.isFinite(from) ? { from, to } : null;
}

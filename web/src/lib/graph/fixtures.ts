/** Test builders for graph nodes / edges (shared by the lib/graph tests). */
import type { GraphEdge, GraphNode } from '@/lib/schemas/graph';

export function node(id: string, extra: Partial<GraphNode> = {}): GraphNode {
  return {
    id,
    name: id.toUpperCase(),
    entity_type: 'political_entity',
    entity_group: 'polity',
    start_year: null,
    end_year: null,
    impact_score: 50,
    depth: 1,
    ...extra,
  };
}

export function edge(
  id: string,
  source: string,
  target: string,
  extra: Partial<GraphEdge> = {},
): GraphEdge {
  return {
    id,
    source,
    target,
    relationship_type: 'part_of',
    start_year: null,
    end_year: null,
    description: null,
    confidence: 'medium',
    ...extra,
  };
}

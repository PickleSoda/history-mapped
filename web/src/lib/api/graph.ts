/** Typed relation-graph endpoints (docs/schemas/relation-graph-api.md). */
import { ChronicleGraphSchema, EntityGraphSchema } from '@/lib/schemas/graph';
import type { ChronicleGraph, EntityGraph } from '@/lib/schemas/graph';
import type { EntityGroup } from '@/types/atlas';
import { api } from './client';

/** Server-side narrowing for GET /entities/{id}/graph. All optional. */
export interface EntityGraphParams {
  /** 1 (default) or 2 hops. */
  depth?: 1 | 2;
  relationshipTypes?: string[];
  groups?: EntityGroup[];
  /** Relationship-year overlap window; null years always pass. */
  from?: number;
  to?: number;
  /** Max edges (server default 300, hard cap 1000). */
  limit?: number;
}

/** Server-side narrowing for GET /chronicles/{slug}/graph. All optional. */
export interface ChronicleGraphParams {
  /** Include edges to entities outside the chronicle (server default true). */
  external?: boolean;
  /** Max external edges per chronicle entity (server default 12). */
  externalLimit?: number;
  relationshipTypes?: string[];
}

type Params = Record<string, string | number>;

const list = (xs: string[] | undefined) =>
  xs && xs.length > 0 ? [...xs].sort().join(',') : undefined;

/** Canonical params — defaults filled, lists sorted — so equal requests share
 *  one query key regardless of how the caller spelled them. */
export function normaliseEntityGraphParams(p: EntityGraphParams = {}): EntityGraphParams {
  const out: EntityGraphParams = { depth: p.depth ?? 1 };
  if (p.relationshipTypes?.length) out.relationshipTypes = [...p.relationshipTypes].sort();
  if (p.groups?.length) out.groups = [...p.groups].sort();
  if (p.from != null) out.from = p.from;
  if (p.to != null) out.to = p.to;
  if (p.limit != null) out.limit = p.limit;
  return out;
}

export function normaliseChronicleGraphParams(
  p: ChronicleGraphParams = {},
): ChronicleGraphParams {
  const out: ChronicleGraphParams = { external: p.external ?? true };
  if (p.externalLimit != null) out.externalLimit = p.externalLimit;
  if (p.relationshipTypes?.length) out.relationshipTypes = [...p.relationshipTypes].sort();
  return out;
}

function entityGraphQuery(p: EntityGraphParams): Params {
  const q: Params = { depth: p.depth ?? 1 };
  const types = list(p.relationshipTypes);
  if (types) q.relationship_types = types;
  const groups = list(p.groups?.map((g) => g.toUpperCase()));
  if (groups) q.groups = groups;
  if (p.from != null) q.from = p.from;
  if (p.to != null) q.to = p.to;
  if (p.limit != null) q.limit = p.limit;
  return q;
}

/** GET /entities/{id}/graph — the entity's 1- or 2-hop neighbourhood. Also the
 *  "expand node" call (depth 1 around the clicked node). */
export async function fetchEntityGraph(
  id: string,
  params: EntityGraphParams = {},
  signal?: AbortSignal,
): Promise<EntityGraph> {
  const { data } = await api.get(`/api/v1/entities/${encodeURIComponent(id)}/graph`, {
    signal,
    params: entityGraphQuery(params),
  });
  const payload = (data as { data?: unknown }).data ?? data;
  return EntityGraphSchema.parse(payload);
}

/** GET /chronicles/{slug}/graph — every chronicle entity, the edges among
 *  them, optional external edges, and per-step membership. */
export async function fetchChronicleGraph(
  slug: string,
  params: ChronicleGraphParams = {},
  signal?: AbortSignal,
): Promise<ChronicleGraph> {
  const q: Params = { external: params.external === false ? 0 : 1 };
  if (params.externalLimit != null) q.external_limit = params.externalLimit;
  const types = list(params.relationshipTypes);
  if (types) q.relationship_types = types;
  const { data } = await api.get(`/api/v1/chronicles/${encodeURIComponent(slug)}/graph`, {
    signal,
    params: q,
  });
  const payload = (data as { data?: unknown }).data ?? data;
  return ChronicleGraphSchema.parse(payload);
}

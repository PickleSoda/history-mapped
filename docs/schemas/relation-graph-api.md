# Relation graph API

Public, read-only endpoints under `/api/v1` that return a node/edge graph. Code: `App\Actions\Graph\GetEntityGraphAction`,
`GetChronicleGraphAction`, shared helpers in `App\Services\RelationGraphSupport`; controllers `EntityGraphController`,
`ChronicleGraphController`; validation in `EntityGraphRequest` / `ChronicleGraphRequest`. Send `Accept: application/json`
so validation errors come back as 422.

## Shapes

```jsonc
// node
{ "id": "<entity uuid>", "name": "…", "entity_type": "…", "entity_group": "…",
  "start_year": -490, "end_year": null,   // primary temporal range, integer years
  "impact_score": 42,                      // integer 1-100
  "depth": 0 }
// edge (direction = source -> target)
{ "id": "<relationship uuid>", "source": "…", "target": "…", "relationship_type": "…",
  "start_year": -490, "end_year": -479, "description": "…",
  "confidence": "high" }                   // high | medium | low | unresolved | null
```

## `GET /entities/{uuid}/graph`

| param | default | notes |
|---|---|---|
| `depth` | 1 | 1 or 2. Depth 2 follows edges out of each depth-1 node and only spends the edge budget left by hop 1. |
| `relationship_types` | all | comma list of `RelationshipType` values |
| `groups` | all | comma list of entity groups; filters non-root nodes, edges to removed nodes are dropped |
| `from`, `to` | – | integer-year overlap with the relationship's `start_year`/`end_year`; null years pass |
| `limit` | 300 | max edges, hard cap 1000 (422 above). Order: confidence (high first), then the other end's impact |

Response `{ "data": { "root", "nodes", "edges", "truncated" } }`. `truncated` is true when more edges matched than `limit`
(at depth 2, hop 2 is skipped when hop 1 already truncated). Node `depth` is 0 (root), 1 or 2. 404 for an unknown or non-uuid id.

## `GET /chronicles/{slug}/graph`

| param | default | notes |
|---|---|---|
| `external` | 1 | include edges from chronicle entities to entities outside it |
| `external_limit` | 12 | max external edges per chronicle entity (0-100), by confidence then the other end's impact |
| `relationship_types` | all | comma list; applies to internal and external edges. Primary relationships are always kept |

Chronicle entity set = `chronicle_entry_entities` pivot entities ∪ both ends of each entry's primary relationship.

Response `{ "data": { "chronicle_id", "slug", "nodes", "edges", "steps" } }`:

- node adds `in_chronicle` (bool; externals are false, depth 1, in-chronicle depth 0) and `steps` (sorted `sequence_order`s containing the entity).
- edge adds `scope` (`primary` | `internal` both ends in set | `external` exactly one end in set) and `steps` (`sequence_order`s whose
  `relationship_ids` include it; always empty for external edges).
- step: `{ entry_id, sequence_order, start_year, end_year, primary_relationship_id, entity_ids, relationship_ids }`, ordered by
  `sequence_order`. `entity_ids` = pivot entities + primary-relationship ends. `relationship_ids` = the primary relationship + every
  non-external edge whose two ends are both in `entity_ids`.

404 for an unknown slug.

## Related fix

`GET /entities/{uuid}/relationships`, `GET /chronicles/{slug}`, and `include_relationships` on entity list/show now eager-load the
embedded `source_entity` / `target_entity` summaries with `withGeoJson()` (via `EntityRelationship::withSummaryEnds()`), so
`temporal_start`, `temporal_end`, `location_name` and `geom` are populated without N+1 queries.

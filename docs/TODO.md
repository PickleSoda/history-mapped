# Engineering Backlog

> Plan- and program-level status lives in [plans/STATUS.md](plans/STATUS.md) (✅/🟡/⬜) — don't duplicate it here.
> This file tracks **fine-grained engineering tasks** that aren't owned by a specific plan.

## Data model & query performance

- [ ] **Recursive ancestor/descendant queries (adjacency list)**
  `parent()` / `children()` need manual chaining and have no recursive eager-load. Add
  [`staudenmeir/laravel-adjacency-list`](https://github.com/staudenmeir/laravel-adjacency-list) for
  `ancestors()` / `descendants()` / `breadthFirst()` via PostgreSQL `WITH RECURSIVE`. Required for
  empire → kingdom → city-state hierarchies.

- [ ] **Standard eager-load spec for relationship endpoints**
  `outgoingRelationships` + `incomingRelationships` trigger N×2 queries when `sourceEntity`/`targetEntity`
  are accessed. Define one eager-load pattern for the entity detail endpoint:
  ```php
  Entity::with([
      'outgoingRelationships.targetEntity:entity_id,name,entity_type,entity_group',
      'incomingRelationships.sourceEntity:entity_id,name,entity_type,entity_group',
  ])->find($id);
  ```

- [ ] **Composite indexes on `relationships` for directional queries**
  "All relationships for entity X" needs two queries (one per direction). Add:
  ```sql
  CREATE INDEX relationships_source_type_idx ON relationships (source_entity_id, relationship_type);
  CREATE INDEX relationships_target_type_idx ON relationships (target_entity_id, relationship_type);
  ```
  Plus an `allRelationshipsFor(string $entityId)` on a `RelationshipBuilder` so controllers don't union both directions by hand.

- [ ] **Composite unique index to prevent duplicate relationships**
  `UNIQUE(source_entity_id, target_entity_id, relationship_type)`. `ResolveRelationshipsJob` only soft-checks; a DB constraint is safer.

- [ ] **Decide inverse-relationship storage strategy**
  The model allows storing both `A [rules] B` and `B [governed_by] A`, but it's optional and inconsistently enforced. Decide: (a) always store both (needs a write-time consistency mechanism), or (b) store one direction and derive the inverse at query time (simpler; needs `allRelationshipsFor` + a `direction` field on responses).

- [ ] **`pg_trgm` GIN index on `entities.name`** for fast fuzzy DB dedup via `similarity()`:
  ```sql
  CREATE INDEX entities_name_trgm_idx ON entities USING gin (name gin_trgm_ops);
  ```

- [ ] **Per-type expression indexes on the `attributes` JSONB**
  `hasAttribute('government_type', 'monarchy')` does a full GIN scan. For high-cardinality filter keys, add PostgreSQL expression indexes scoped per entity type — see [archive/implementation-docs/attributes_and_geometry_snapshots.md](archive/implementation-docs/attributes_and_geometry_snapshots.md) §5.

- [ ] **Harden `geometry_periods` lifecycle for time-varying geometries**
  Ensure all pipelines write canonical period geometries (empires, routes, epidemics), validate non-overlapping periods per geometry role, and keep provenance fields complete.

---

For map-query, agentic-pipeline, and OHM-phase work items, see the corresponding plans in
[plans/](plans/) and the priority view in [plans/STATUS.md](plans/STATUS.md).

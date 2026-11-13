# Engineering Backlog

> Plan- and program-level status lives in [plans/STATUS.md](plans/STATUS.md) (✅/🟡/⬜) — don't duplicate it here.
> This file tracks **fine-grained engineering tasks** that aren't owned by a specific plan.

## Data model & query performance

- [ ] **Recursive ancestor/descendant queries (adjacency list)**
  `parent()` / `children()` need manual chaining and have no recursive eager-load. Add
  [`staudenmeir/laravel-adjacency-list`](https://github.com/staudenmeir/laravel-adjacency-list) for
  `ancestors()` / `descendants()` / `breadthFirst()` via PostgreSQL `WITH RECURSIVE`. Required for
  empire → kingdom → city-state hierarchies.

- [x] **Standard eager-load spec for relationship endpoints**: done as
  `EntityRelationship::withSummaryEnds()`, used by the entity, relationship and chronicle endpoints.

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

- [x] **`pg_trgm` GIN index on `entities.name`**: done in
  `2026_06_14_000000_add_trgm_fuzzy_search_to_entities.php`.

- [ ] **Per-type expression indexes on the `attributes` JSONB**
  `hasAttribute('government_type', 'monarchy')` does a full GIN scan. For high-cardinality filter keys, add PostgreSQL expression indexes scoped per entity type — see [archive/implementation-docs/attributes_and_geometry_snapshots.md](archive/implementation-docs/attributes_and_geometry_snapshots.md) §5.

- [ ] **Harden `geometry_periods` lifecycle for time-varying geometries**
  Ensure all pipelines write canonical period geometries (empires, routes, epidemics), validate non-overlapping periods per geometry role, and keep provenance fields complete.
  `provenance_mode` is unreliable today: `ImportEntityJob` stamps `ohm_import` on any period it
  seeds from a location, and `backfill_geo` writes Wikidata points as `manual`.

- [ ] **Normalize citations into dedicated tables**
  `entities.source_citations`, `relationships.source_citations` and
  `chronicle_entries.source_evidence` are free-form JSONB, and nothing references the `sources`
  table. (Moved from the archived `entity-model/implementation-status.md`.)

## Found in the 2026-11-14 docs review

- [ ] **Run the web Vitest suite in CI.** `.github/workflows/ci.yml` runs web lint, types and build,
  but not `pnpm test` in `web/` (38 test files).
- [ ] **Fix the root `pnpm typecheck` script.** It runs `pnpm -r typecheck`, but neither workspace
  defines `typecheck` (both use `types:check`).
- [ ] **Check BCE alignment with OHM dates.** `web/src/lib/ohm-date.ts` sends `-0044` for 44 BCE.
  Under ISO 8601 astronomical numbering `-0044` is 45 BCE. Confirm OHM's convention and adjust the
  date filter if needed.
- [ ] **Remove dead web code:** the unused `q` URL param, `useSearch`, `useHighlights`,
  `useTimelineDensity`, `useHistoricalPeriods`, and the stale comments in `TimelineScope.tsx` and
  `ChroniclePlayer.tsx`.
- [ ] **Automate database backups** for the hosted site. Today the only dumps are the ones the
  content loader takes before a full replace.
- [ ] **Retire or fix the App Platform path** (`.do/app.yaml` and the `deploy` job). Its routing
  predates the admin, tiles and AI routes.
- [ ] **Make the dev port overrides work from the documented place.** Compose reads `docker/.env`, but
  the root `.env.example` suggests a root `.env`.
- [ ] **API entity writes skip the `entities.verify` check.** `POST`/`PUT /api/v1/entities` accept
  `verification_status` from anyone with `entities.write` (`Api\V1\Requests\UpdateEntityRequest::authorize()`
  returns true). Only the admin form checks `entities.verify`.
- [ ] **Decide what chronicle `status` means in public.** `GET /api/v1/chronicles` and `/chronicles/{slug}`
  ignore status unless asked, so drafts and archived chronicles are listed and shown. The agent creates
  every chronicle as `draft`.
- [ ] **Stop exposing internal entity attributes.** `EntityResource` returns the whole `attributes` JSON,
  including `_media_curated_at`, `validation_flags` and `confidence_notes`.
- [ ] **Rate-limit the public API.** `throttleApi()` is not configured; only `POST /contributions` is
  throttled.
- [ ] **Exclude the `agent_*` tables from the content dump.** AI conversations and proposals are not in
  the `--exclude-table-data` list in `content-data-transfer.md`, so local chats ship to prod.
- [ ] **Align the agent's relation types.** `extract_candidates.py` offers `allied_with`, `trades_with`,
  `caused` and `resulted_from`, but `validate.py`'s `ALLOWED_RELATION_TYPES` blocks them.
- [ ] **Stop borrowed event points in the agent.** `resolve_ohm` emits place-of-association and
  chronicle-centroid points, and `pipeline.locate_events` copies P276/P19 coordinates. Both contradict
  the placement policy that `backfill_geo` and the point audits enforce.
- [ ] **Decide the presence-period gate.** `CreateDerivedPresencePeriodAction::supportsRelationshipType()`
  is never called, so every dated relationship saved through the admin or API derives a presence period.
- [ ] **Let the standalone pipeline scripts read `DATABASE_URL`.** `backfill_geo` and its siblings
  hard-code the dev database address.

## Misc

- [ ] Replace the Laravel logomark SVG in `api/resources/js/components/app-logo-icon.tsx` with a
  History Mapped mark (the sidebar still shows the starter icon next to the rebranded text).

---

For map-query, agentic-pipeline, and OHM-phase work items, see the corresponding plans in
[plans/](plans/) and the priority view in [plans/STATUS.md](plans/STATUS.md).

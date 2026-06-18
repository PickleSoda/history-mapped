# Consolidated Bug Report

> **Status: 🟡 Partial** — verified 2026-06-15; remaining work tracked in [STATUS.md](STATUS.md).
> **Date:** 2026-06-12
> **Method:** Four parallel GitNexus-guided workstreams (Laravel core, map bbox query, frontend dashboard,
> LangGraph pipeline). Every reported bug was put through an adversarial verifier that tried to *refute* it
> from source. Severities below are the **verifier-corrected** values where a verifier ran; map-query items
> marked *(author-confirmed)* were re-checked directly against source for this report because their original
> verifiers were lost to a session interruption.

## Verification legend
- **confirmed** — independently reproduced from source with file:line evidence.
- **author-confirmed** — re-verified directly against source while writing this report (the automated verifier did not run).
- **reported** — produced by a capable auditor and internally consistent, but not independently re-verified; treat as high-probability, not certain.
- **refuted** — the claim was checked and found wrong; listed in the appendix with the disproof.

## Severity rubric
- **critical** — data corruption/loss, a security hole, or guaranteed wrong results on the primary path.
- **high** — incorrect behavior on a common path, or a serious performance cliff in the main flow.
- **medium** — edge-case incorrectness or meaningful performance waste.
- **low** — hygiene / robustness.

---

## Severity-ranked index

| # | Sev | Area | Title | Status |
|---|-----|------|-------|--------|
| PP-1 | 🔴 critical | Pipeline | `commit_writer` writes JSONL to a host path the app container can't see → imports nothing | confirmed |
| PP-2 | 🔴 critical | Pipeline | `commit_writer` never checks the artisan return code → failed imports recorded as success | confirmed |
| PP-3 | 🔴 critical | Pipeline | Agent relations sent to `pipeline:import-borders` with a directory arg + wrong schema | confirmed |
| LC-1 | 🟠 high | Laravel / Map | Map `min_confidence` filter uses inverted PG enum ordering → returns the wrong rows | confirmed |
| LC-2 | 🟠 high | Laravel | `UpdateChronicleRequest` slug-unique rule references a missing route key → 500 on every edit | confirmed |
| MQ-1 | 🟠 high | Map | `temporal_start/end` is ANDed with a hidden default `year=1000` instead of overriding it | author-confirmed |
| MQ-2 | 🟠 high | Map | Live dashboard fetch is unbounded: global extent, limit 100 000, full-resolution geometry | author-confirmed |
| MQ-3 | 🟠 high | Map | `ResolveOhmFeatureAction` issues 4–10 sequential queries per map click | reported |
| PP-4 | 🟠 high | Pipeline | Agent chronicle is written to disk but **never imported** into the DB | confirmed |
| PP-5 | 🟠 high | Pipeline | Confidence floor of 0.95 makes the approval gate a near-rubber-stamp | confirmed |
| PP-6 | 🟠 high | Pipeline | Chronicle entry gets a synthetic `src\|type\|tgt` string in a `uuid` FK column → import rejects the whole file | confirmed |
| PP-7 | 🟠 high | Pipeline | `resolve_entity_ids` reads `record['name']` that `commit_writer` never sets → id resolution no-ops even on success | confirmed |
| FE-1 | 🟠 high | Frontend | OHM basemap date filter silently disabled for years −999…999 (incl. default year 100) | confirmed |
| FE-2 | 🟠 high | Frontend | No debounce + ignored AbortSignal → each keystroke fires an uncancelled global map query | confirmed |
| FE-3 | 🟠 high | Frontend | Whole MapLibre map torn down/recreated when a year has zero features or errors | confirmed |
| LC-3 | 🟡 medium | Laravel | Timeline fallback inserts NULL `start_year` for end-only ranges → NOT NULL crash | confirmed |
| LC-4 | 🟡 medium | Laravel | Chronicle `source_evidence` validated as array but column is text (no cast) → write crash | confirmed |
| LC-5 | 🟡 medium | Laravel | Chronicle `narrative_text` NOT NULL but validator allows null + action defaults null | confirmed |
| LC-6 | 🟡 medium | Laravel | June-11 chronicle temporal/impact/location fields unreachable through every HTTP surface | confirmed |
| MQ-4 | 🟡 medium | Map | `EntityBuilder` bbox/temporal filters use correlated subqueries → full `entities` scan ×2 | reported |
| MQ-5 | 🟡 medium | Map | Per-row correlated alias subquery, unindexed → planner-level N+1 on the map path | confirmed |
| MQ-6 | 🟡 medium | Map | No zoom-keyed simplification; full-resolution polygons serialized at every zoom | confirmed |
| MQ-7 | 🟡 medium | Map | Scalar temporal predicate can't use the dedicated GiST range index (dead index) | confirmed |
| MQ-8 | 🟡 medium | Map / Frontend | Over-fetched columns + feature-contract drift (`temporal_start`/`entity_color` never sent) | confirmed |
| MQ-9 | 🟡 medium | Map | OR-of-two-geometry-columns bbox predicate weakens GiST use + select/serialize mismatch | confirmed |
| MQ-11 | 🟡 medium | Map | `ResolveOhmFeatureAction` excludes open-ended periods (`end_year IS NULL`) | reported |
| MQ-12 | 🟡 medium | Map | `GeoJson` cast fallback does one DB round trip per geometry attribute (latent N+1 engine) | confirmed (mechanism) |
| MQ-13 | 🟡 medium | Map | Validated `group` filter silently ignored by both map actions | author-confirmed |
| MQ-14 | 🟡 medium | Map | `?parent_id=`/`include_children` 500 (`childrenOf` scope + `children` relation don't exist) | author-confirmed |
| MQ-15 | 🟡 medium | Map | `ORDER BY display_priority DESC` puts NULL-priority rows first → curation inverted under LIMIT | author-confirmed |
| MQ-19 | 🟡 medium | Map | Backfill/import ping-pong geometry through PHP (decode/re-encode) in per-row loops | reported |
| FE-4 | 🟡 medium | Frontend | Out-of-order OHM click-resolution responses: last to arrive wins, not last clicked | confirmed |
| FE-5 | 🟡 medium | Frontend | Highlight change re-pushes the entire base FeatureCollection to MapLibre | confirmed |
| FE-7 | 🟡 medium | Frontend | `normalizeToFeatures` mangles Features with null geometry → invalid GeoJSON | confirmed |
| PP-8 | 🟡 medium | Pipeline | Brittle LLM JSON parsing; a schema-invalid item crashes the whole run | confirmed |
| PP-9 | 🟡 medium | Pipeline | No graph-level error handling / checkpointing → one node failure aborts the run, no resume | confirmed |
| LC-7 | 🔵 low | Laravel | `GeoJson` cast builds geometry SQL by string interpolation, not a bound parameter | uncertain |
| MQ-16 | 🔵 low | Map | Duplicate features per entity when multiple periods cover the year (no `DISTINCT ON`) | author-confirmed |
| MQ-17 | 🔵 low | Map | Antimeridian-crossing viewports rejected (422) or invert the envelope | reported |
| MQ-18 | 🔵 low | Map | Validated `include_territories` parameter is dead | author-confirmed |
| FE-6 | 🔵 low | Frontend | `ResizeObserver` effect never attaches (guard on async-created map, empty deps) | confirmed |
| FE-8 | 🔵 low | Frontend | `fitBounds` math ignores antimeridian crossing | confirmed |
| FE-9 | 🔵 low | Frontend | Empty/invalid year snaps to 100 and fetches; input value diverges from rendered year | confirmed |
| FE-10 | 🔵 low | Frontend | Hover popup position goes stale on pan/zoom; reads property names the API never emits | confirmed |
| FE-11 | 🔵 low | Frontend | Debug `console.log` of up to 10 candidate features (full geometry) on every basemap click | confirmed |
| PP-10 | 🔵 low | Pipeline | `approval_gate` appends a plain dict where a `PipelineError` model is expected | confirmed |
| PP-11 | 🔵 low | Pipeline | `resolve_wikidata` overwrites `wikidata_match`, dropping the `existing_entity` dedup flag | confirmed |
| PP-12 | 🔵 low | Pipeline | In-place mutation of shared state lists under a no-reducer `TypedDict` model | confirmed |

**Refuted (see appendix):** pipeline non-idempotent re-run; pipeline "hallucinated" model IDs.

**Totals:** 3 critical · 11 high · 19 medium · 11 low · 2 refuted = **44 standing bugs**.

---

## Critical

### PP-1 — `commit_writer` writes JSONL to a host path the app container cannot see
- **Location:** [commit_writer.py:88-104](../../pipeline/agent/graph/nodes/commit_writer.py#L88-L104); `cfg.output_dir` default `"output/agent_runs"` ([config.py:35](../../pipeline/agent/config.py#L35)); compose mounts only `../api:/var/www/html` ([docker/docker-compose.yml](../../docker/docker-compose.yml)).
- **Impact:** The node writes to repo-root `output/agent_runs/<run_id>/…` on the host, then runs `php artisan pipeline:import output/agent_runs/<run_id>/entities_to_create.jsonl` **inside the app container**, where that relative path resolves to `/var/www/html/output/…` = `api/output/…`, which does not exist. `ImportEntitiesCommand` finds no files, prints "No .jsonl files found" and returns FAILURE. On any real (non-mocked) run, **zero entities are imported** while the run reports success.
- **Blast radius:** `impact(run_artisan_command)` = LOW, 1 direct caller (`commit_writer`); true runtime radius is the entire DB-write half of the pipeline (`resolve_entity_ids` → `chronicle_builder`), invisible to the static graph because nodes are string-wired.
- **Fix (prose):** Stage the JSONL under a container-visible, mounted path (e.g. `api/storage/app/pipeline/...`) and pass the in-container absolute path to artisan; or mount repo-root `output/` into the app service and translate host→container paths. The relation path ([commit_writer.py:115-117](../../pipeline/agent/graph/nodes/commit_writer.py#L115-L117)) has the identical defect and must be fixed together. See open question 8a.

### PP-2 — `commit_writer` never checks the artisan return code
- **Location:** [commit_writer.py:106-137](../../pipeline/agent/graph/nodes/commit_writer.py#L106-L137); `run_artisan_command` uses `subprocess.run` with no `check`/`timeout` ([app_api.py:41](../../pipeline/agent/tools/app_api.py#L41)).
- **Impact:** After `run_artisan_command` returns `{returncode, …}`, the node only *logs* the code and unconditionally appends a `CommittedChange`. Any import failure (missing path, DB down, malformed record, PHP fatal, or a subprocess exception/timeout) is recorded as a successful commit; the manifest shows `committed_count>0, errors_count=0`. Combined with PP-1 the standard run always claims success while writing nothing. **Discovered during verification (compounding):** the entity `CommittedChange.record` ([commit_writer.py:111](../../pipeline/agent/graph/nodes/commit_writer.py#L111)) contains only `{path,count,result}` and no `name`, yet `resolve_entity_ids` reads `record.get('name')` — see PP-7.
- **Blast radius:** Only DB-write node; gates all downstream id resolution. `impact(commit_writer)` = 0 static callers (string-wired); runtime-critical.
- **Fix (prose):** Branch on `result['returncode']`: on non-zero append a `PipelineError(node='commit_writer')` and do **not** record a `CommittedChange` (or mark it failed so `resolve_entity_ids`/`chronicle_builder` skip it). Add a timeout to `run_artisan_command` and treat timeouts/exceptions as import failures.

### PP-3 — Agent relations sent to `pipeline:import-borders` with a directory arg and incompatible schema
- **Location:** [commit_writer.py:115-119](../../pipeline/agent/graph/nodes/commit_writer.py#L115-L119); rejected by [ImportBordersCommand.php:24-28](../../api/app/Console/Commands/ImportBordersCommand.php#L24-L28).
- **Impact:** `rel_dir = output_root` (a **directory**) is passed to `pipeline:import-borders`, which requires `is_file($path)` and errors immediately ("File not found: \<dir\>", FAILURE). Even given a file, the emitted `{source_name,target_name,relationship_type,…}` relation schema lacks the `name`/`entity_type`/`entity_group` keys `ImportBorderEntityJob` requires, so every record is skipped. **Relations are never persisted.** The correct flow (`pipeline:import-border-relations` / `resolve-relationships`, fed relationship-hint JSONL) is never used. Because of PP-2 the FAILURE is swallowed.
- **Blast radius:** Breaks relation persistence and the downstream `relation_id_map`, which feeds chronicle `primary_relationship_id` resolution (→ PP-6).
- **Fix (prose):** Route relation JSONL to a relationship importer (emit hint records compatible with `pipeline:import-border-relations`/`resolve-relationships`, or add a dedicated agent-relations importer), pass a single in-container **file** path, align the schema, and check the return code. See open question 8b.

---

## High

### LC-1 — Map `min_confidence` filter uses inverted PostgreSQL enum ordering
- **Location:** [MapEntitiesAction.php:106](../../api/app/Actions/Entity/MapEntitiesAction.php#L106) **and** [MapEntitiesByYearAction.php:86](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L86).
- **Impact:** `where('entities.confidence', '>=', ConfidenceLevel::from($v)->value)` compares a PG `confidence_level` enum declared `('high','medium','low','unresolved')`. Postgres orders enums by declaration position, so `confidence >= 'medium'` matches **medium, low, unresolved** — everything *except* high, the inverse of a minimum-confidence filter. Only `min_confidence=high` is correct by luck. Silent wrong results on the primary public map path. The codebase's own [`EntityBuilder::withMinConfidence`](../../api/app/Builders/EntityBuilder.php#L65) documents the intended order `unresolved<low<medium<high` and deliberately avoids enum ordinality — proof of intent.
- **Blast radius:** `impact` LOW, 1 direct caller each (the controller); functional severity high (primary map path). Triggers only when the optional filter is supplied with a non-`high` value (default loads unaffected) → high, not critical.
- **Fix (prose):** Build the acceptable-value set from the requested level upward and use `whereIn`, or route both map actions through `EntityBuilder::withMinConfidence`. Fix both call sites together.

### LC-2 — `UpdateChronicleRequest` slug-unique rule references a missing route key → 500 on every edit
- **Location:** [UpdateChronicleRequest.php:26](../../api/app/Http/Requests/Web/UpdateChronicleRequest.php#L26); route declares `{slug}` ([web.php:66](../../api/routes/web.php#L66)).
- **Impact:** The rule is `'unique:chronicles,slug,' . $this->route('chronicle')`, but the param is `{slug}`, so `route('chronicle')` is null and the ignore clause is an empty string. Laravel then runs `WHERE slug = ? AND id <> ''`, but `chronicles` has **no `id` column** (PK is `chronicle_id`) → PostgreSQL `42703 column "id" does not exist`, a **500 on every edit** (the UI always submits the required slug). The controller's slug regeneration runs *after* validation and cannot mask it. **Upgraded low→high by the verifier** (it is a 500 on the primary edit path, not a clean validation message).
- **Blast radius:** `impact(UpdateChronicleRequest)` LOW, 1 direct caller. No Web update test exists.
- **Fix (prose):** Use `Rule::unique('chronicles','slug')->ignore($id, 'chronicle_id')` (resolve the chronicle first), or reference `$this->route('slug')` and ignore by the `slug` column. Align the ignore column with the actual PK.

### MQ-1 — `temporal_start/end` is ANDed with the hidden default `year=1000` instead of overriding it
- **Location:** [MapEntitiesAction.php:66-70](../../api/app/Actions/Entity/MapEntitiesAction.php#L66-L70) (unconditional year filter) vs [:109-116](../../api/app/Actions/Entity/MapEntitiesAction.php#L109-L116) (range filter); default year 1000 at [:185-190](../../api/app/Actions/Entity/MapEntitiesAction.php#L185-L190).
- **Impact:** The comment says the range filter "overrides single-year filter when provided," but the single-year predicate is always applied first (with `year` defaulting to 1000), and the range clauses are **ANDed** on top. `…&temporal_start=1500&temporal_end=1600` returns only periods that *also* cover year 1000 — almost nothing. Guaranteed wrong results for any range request excluding the (possibly defaulted) year.
- **Blast radius:** `impact(MapEntitiesAction)` LOW, 1 direct caller; endpoint has no live consumer yet but is the designated primary map endpoint (see plan 10, P1).
- **Fix (prose):** When a range is supplied, skip the single-year predicate entirely (resolve the year filter only in the no-range branch), or validate the two styles as mutually exclusive. Add a range-without-year feature test.

### MQ-2 — Live dashboard fetch is unbounded (global extent, limit 100 000, full-resolution geometry)
- **Location:** [MapEntitiesByYearAction.php:22](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L22) (limit default 100000), [:48](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L48) (precision 5, no simplification); consumer [dashboard.tsx:76](../../api/resources/js/pages/dashboard.tsx#L76) sends only `year`.
- **Impact:** The dashboard's only data fetch passes no bbox, no zoom, no limit, so every matching geometry period on Earth for the year is serialized at ~1 m precision with zero simplification. Each year change re-downloads a global multi-MB FeatureCollection; the bbox/zoom-aware endpoint exists but has no consumer. This is the project's primary perf problem and the headline of plan 10.
- **Blast radius:** `impact(MapEntitiesByYearAction)` LOW, 1 direct caller. Frontend change is outside the PHP graph; `dashboard.test.tsx` pins the current URL.
- **Fix (prose):** Point the dashboard at `/v1/entities/map` with viewport bbox + zoom + year (debounced refetch), or at minimum give `/map/year` a bounded default limit and zoom-band `min_impact`, plus in-DB zoom-keyed `ST_SimplifyPreserveTopology`. Full plan: [map-query-optimization.md](map-query-optimization.md) P1–P2.

### MQ-3 — `ResolveOhmFeatureAction` issues 4–10 sequential queries per map click
- **Location:** [ResolveOhmFeatureAction.php:26-123](../../api/app/Actions/EntityGeoRef/ResolveOhmFeatureAction.php#L26-L123) (redundant `findOrFail` re-fetch at :54; cast-triggered decodes at :79/:99/:111).
- **Impact:** A raw match query, then a `findOrFail` that **re-fetches the same row**, two eager loads, up to two `GeometryPeriod` queries, and a `SELECT ST_AsGeoJSON(?)` round trip per geometry attribute (via the `GeoJson` cast fallback, MQ-12). Every OHM basemap click — the most-used interactive map flow — costs 4–10+ sequential round trips. *(Reported; the per-attribute cast round-trip mechanism is independently confirmed via LC-7/MQ-12.)*
- **Blast radius:** `impact(ResolveOhmFeatureAction)` LOW, 1 direct caller (`MapResolutionController`).
- **Fix (prose):** Collapse into one statement: CTE for the best geo-ref, `LEFT JOIN LATERAL` the linked + date-matched periods and the primary location, projecting `ST_AsGeoJSON(COALESCE(...))` + a computed `resolution_source`. Drops the re-fetch and all cast round trips. (Plan 10, P3; also fixes MQ-11.)

### PP-4 — Agent chronicle is written to disk but never imported into the database
- **Location:** [chronicle_writer.py:29-40](../../pipeline/agent/graph/nodes/chronicle_writer.py#L29-L40); the real importer `chronicles:import` ([ImportChroniclesCommand.php](../../api/app/Console/Commands/ImportChroniclesCommand.php)) is never invoked anywhere in `pipeline/agent`.
- **Impact:** `chronicle_writer` writes `chronicle.json` and records a "chronicle" `CommittedChange`, but no node imports it — so agent chronicles never reach the `chronicles`/`chronicle_entries` tables, while sibling entity/relation outputs *do* call artisan. The "committed" count conflates "file written" with "DB row written."
- **Blast radius:** Missing call, not a broken one; affects chronicle persistence only.
- **Fix (prose):** After writing the file, invoke `chronicles:import <container-path> --sync` (with return-code checking and a container-visible path, per PP-1/PP-2), or explicitly document chronicle import as a manual step. Note `chronicles:import` has no `--batch-id` (dedup is slug + `--force`). See open question 8c.

### PP-5 — Confidence floor of 0.95 makes the approval gate a near-rubber-stamp
- **Location:** [validate.py:45](../../pipeline/agent/graph/nodes/validate.py#L45) (`confidence = 0.95 + enriched.system_confidence`); thresholds [config.py:48-72](../../pipeline/agent/config.py#L48-L72).
- **Impact:** `system_confidence` only *adds* bonuses (Wikidata +0.3/+0.1, OHM +0.2), so a validated entity with zero enrichment already sits at 0.95. The five low-risk types (auto-commit ≥0.90) commit unconditionally; relations get a flat 0.95; only `person`/`political_entity`/`dynasty` (0.97) need a bonus. The human-review/auto-commit distinction is effectively bypassed; confidence is decoupled from evidence. (Also: the `requires_wikidata` −0.3 penalty is **dead code** — no policy sets the key.)
- **Blast radius:** `impact(validate)` 0 static callers (string-wired); changing the scale shifts what auto-commits (retune thresholds together).
- **Fix (prose):** Derive confidence from evidence (start near 0; add for exact Wikidata/label/description match, OHM geometry, DB corroboration, date overlap; subtract for missing data on sensitive types) and recalibrate thresholds. Don't seed at 0.95. See open question 9.

### PP-6 — Chronicle entry gets a synthetic `src|type|tgt` string in a `uuid` FK column
- **Location:** [chronicle_builder.py:76](../../pipeline/agent/graph/nodes/chronicle_builder.py#L76) (synthetic key) → [:134](../../pipeline/agent/graph/nodes/chronicle_builder.py#L134); imported at [ImportChroniclesCommand.php:250-254](../../api/app/Console/Commands/ImportChroniclesCommand.php#L250); column is `uuid` FK ([migration 2026_06_10_000002:18,30-33](../../api/database/migrations/2026_06_10_000002_create_chronicle_entries_table.php#L18)).
- **Impact:** When `relation_id_map` and the committed scan both miss (a **common** path — empty map on no-DB/dry-run/unmatched, especially given PP-3), `_find_primary_relationship` returns `"Alexander|fought_at|Darius III"`, written verbatim into the `uuid` `primary_relationship_id` column. PostgreSQL rejects the non-UUID at save, the import catch rolls back and **skips the entire chronicle file**. **Upgraded medium→high** (wrong behavior on a common path; fails closed). The report's secondary-entity half (`entity_id` label fallback, :84) was **refuted** — the importer intentionally resolves secondary entities by name.
- **Blast radius:** `impact(chronicle_builder)` 0 static callers (string-wired); feeds `chronicle_writer` + `chronicles:import`.
- **Fix (prose):** When a DB id can't be resolved, leave `primary_relationship_id` null and flag the entry (count it in `orphan_entry_count`, which the synthetic-string branch currently bypasses) so the importer can defer/reject instead of failing the whole file.

### PP-7 — `resolve_entity_ids` reads a `record['name']` that `commit_writer` never sets
- **Location:** [resolve_entity_ids.py:24](../../pipeline/agent/graph/nodes/resolve_entity_ids.py#L24) reads `record.get('name')`; [commit_writer.py:111](../../pipeline/agent/graph/nodes/commit_writer.py#L111) builds the entity record as `{path,count,result}` (no `name`). *(Discovered during PP-2 verification.)*
- **Impact:** Even on a **successful** import, the committed entity record has no `name`, so `resolve_entity_ids` looks nothing up and `entity_id_map` stays empty → `chronicle_builder` substitutes label/synthetic ids (→ PP-6). The chronicle-ids test masks this by hand-building a record *with* a `name` key.
- **Blast radius:** Sits between `commit_writer` and `chronicle_builder` on the linear critical path.
- **Fix (prose):** Have `commit_writer` record the entity/relation natural keys (`name`, `entity_type`, or the resolved `wikidata_id`) it already has in scope, and make `resolve_entity_ids` read the same keys. Add a test that drives resolution from a realistic committed record.

### FE-1 — OHM basemap date filter silently disabled for years −999…999 (incl. default year 100)
- **Location:** [dashboard.tsx:348-350](../../api/resources/js/pages/dashboard.tsx#L348) (`yearToTimeframe`) + [ohm-date.ts:27-28](../../api/resources/js/lib/ohm-date.ts#L27) (`normalizeOhmDate`) + [historical-map-viewer.tsx:1363-1387](../../api/resources/js/components/historical-map-viewer.tsx#L1363).
- **Impact:** `yearToTimeframe` builds `"${year}-01-01"` unpadded (`100` → `"100-01-01"`), but `normalizeOhmDate`'s `\d{4,}` regex rejects sub-4-digit years → returns null → `applyOhmLayerDateFilter` **restores the unfiltered (all-eras) basemap**. At the default year 100, and any year in −999…999, the OHM basemap shows modern boundaries/cities/roads under the correctly-filtered entity layer — anachronistic geography on the primary path. The padding helper `yearToOhmDate` exists but is unused. The dashboard test asserts the broken unpadded format with the viewer mocked, so CI codifies the bug.
- **Blast radius:** `impact(normalizeOhmDate)` = 3 callers, 8 impacted across `HistoricalMapViewer` flows; fixing in `yearToTimeframe` is dashboard-local.
- **Fix (prose):** Pad via `yearToOhmDate` (`"0100-01-01"`) or relax `normalizeOhmDate` to accept 1–4-digit years (consistent with `dateRangeFromISODate`'s own `\d{1,4}` regex, which currently disagrees). Update the test to assert the padded format.

### FE-2 — No debounce + ignored AbortSignal → each keystroke fires an uncancelled global query
- **Location:** [dashboard.tsx:71-90](../../api/resources/js/pages/dashboard.tsx#L71) (query) + [:150-165](../../api/resources/js/pages/dashboard.tsx#L150) (onChange).
- **Impact:** `onChange` sets the year per keystroke; the query key changes immediately and the queryFn ignores React Query's `AbortSignal`, so typing "1453" fires four uncancelled global PostGIS streaming queries (years 1, 14, 145, 1453). The Inertia `QueryClient` defaults (staleTime 0, refetchOnWindowFocus, retry 3) multiply it further. UI copy claims "debounced live refresh" — no debounce exists. This is the refetch-storm multiplier of the most expensive query (MQ-2).
- **Blast radius:** Page entry point (0 upstream callers); runtime radius is API/PostGIS load.
- **Fix (prose):** Debounce the committed year (or commit on blur/Enter), pass the `signal` into `fetch` so superseded requests abort, raise `staleTime` (year-keyed data is effectively immutable), and reduce retry. Fix/remove the "debounced" label.

### FE-3 — Whole MapLibre map torn down/recreated when a year has zero features or errors
- **Location:** [dashboard.tsx:193-217](../../api/resources/js/pages/dashboard.tsx#L193) (render branches; `HistoricalMapViewer` mounted only when `mapFeatures.length > 0`).
- **Impact:** An empty year or a retried failure unmounts the viewer; cleanup calls `map.remove()`, and remount re-fetches the OHM style JSON, recreates the WebGL context, re-adds 3 sources + 9 layers, and re-fetches tiles. Combined with FE-2's un-debounced typing, passing through an empty intermediate year destroys/rebuilds the map mid-keystroke (flash, camera reset, WebGL context churn).
- **Blast radius:** Dashboard-local render-branch change; does not touch the shared viewer component.
- **Fix (prose):** Keep `HistoricalMapViewer` mounted across empty/error states (render it once data has ever loaded; pass an empty `baseGeometries` for empty years — the data-apply effect already handles empties) and overlay the message instead of replacing the map.

---

## Medium

### LC-3 — Timeline fallback inserts NULL `start_year` for end-only ranges (NOT NULL crash)
- **Location:** [EntityTimelineEntryBuilder.php:66](../../api/app/Builders/EntityTimelineEntryBuilder.php#L66); selected by [ProjectEntityTimelineAction.php:250](../../api/app/Actions/Timeline/ProjectEntityTimelineAction.php#L250).
- **Impact:** `fromPrimaryTemporalRange` coalesces end←start but **not** start←end. The projection selects ranges with `start_year NOT NULL OR end_year NOT NULL`, so an open-start range (NULL start, set end — common for BCE/uncertain data) with no geometry periods or year-bearing relationships hits the fallback and inserts NULL into the NOT NULL `entity_timeline_entries.start_year`, throwing inside `RebuildEntityTimelineJob` (so the timeline never builds for that entity).
- **Blast radius:** `impact(fromPrimaryTemporalRange)` LOW, 1 caller; 1 affected process (`RebuildEntityTimelineJob::handle`).
- **Fix (prose):** Coalesce `start_year ?? end_year` symmetrically (mirroring the existing end fallback and `BackfillGeometryPeriodsAction`). Confirm the `start<=end` CHECK still holds when both default to one value.

### LC-4 — Chronicle `source_evidence` validated as array but column is text (no cast)
- **Location:** [StoreChronicleRequest.php:35](../../api/app/Http/Requests/Web/StoreChronicleRequest.php#L35) (`array`); column is `text` ([migration 2026_06_10_000002](../../api/database/migrations/2026_06_10_000002_create_chronicle_entries_table.php)); no cast in [ChronicleEntry.php](../../api/app/Models/ChronicleEntry.php).
- **Impact:** Both FormRequests validate `entries.*.source_evidence` as a nullable **array**, but the column is text and the model has no cast; `CreateChronicleAction` passes it straight to `ChronicleEntry::create`. An array submission triggers "Array to string conversion"/bind error and rolls back the whole transaction. The pipeline path is unaffected (it writes a string `event:N`); the web path is broken; no test covers the array case.
- **Blast radius:** `impact(CreateChronicleAction)` LOW, 2 callers (store/update).
- **Fix (prose):** Pick one representation — either make the column `jsonb` + add an `array`/`json` cast and store the array, or keep text and change the validator to `string` with callers serializing. Make migration, cast, FormRequests, DTO, and import command agree. See open question 1.

### LC-5 — Chronicle `narrative_text` NOT NULL but validator allows null and action defaults null
- **Location:** [CreateChronicleAction.php:63](../../api/app/Actions/Chronicle/CreateChronicleAction.php#L63); column NOT NULL ([migration 2026_06_10_000002](../../api/database/migrations/2026_06_10_000002_create_chronicle_entries_table.php)); validators allow `nullable`.
- **Impact:** An entry omitting `narrative_text` (allowed by validation) inserts NULL into the NOT NULL column → NOT NULL violation, transaction rollback. `ImportChroniclesCommand` avoids it by defaulting to `''`; the web action does not. Uncovered by tests (they always supply the field).
- **Blast radius:** `impact(CreateChronicleAction)` LOW, 2 callers.
- **Fix (prose):** Coalesce `narrative_text` to `''` in the action (matching the import command) or make the column nullable, **and** tighten the FormRequest to require it when an entry is present, so validator/action/schema agree.

### LC-6 — June-11 chronicle temporal/impact/location fields unreachable through every HTTP surface
- **Location:** [StoreChronicleRequest.php](../../api/app/Http/Requests/Web/StoreChronicleRequest.php)/[UpdateChronicleRequest.php](../../api/app/Http/Requests/Web/UpdateChronicleRequest.php) (omit the fields); [ChronicleResource.php](../../api/app/Http/Api/V1/Resources/ChronicleResource.php) + `ChronicleEntryResource` + `Web\ChronicleController::serializeChronicle` (omit them).
- **Impact:** Migrations 2026_06_11_000001/000002 added `start_year`/`end_year`/`impact_score`/`approximate_location` to `chronicles` and `chronicle_entries`; the DTO, actions, models, and an action test support them. But the FormRequests don't list them (Laravel strips them from `validated()`), and all three serializers omit them, so the fields are **write-unreachable and read-invisible** through every HTTP path. (The JSON API has no write endpoint at all — web write + web read + API read are all affected.) Effectively dead through HTTP.
- **Blast radius:** Cross-cutting (FormRequests + 2 Resources + controller serializer); no single enclosing symbol.
- **Fix (prose):** Add the four chronicle-level and four entry-level fields to both FormRequests (integer/min, array for location), include them in all three serializers, and add a round-trip feature test — *if* they are meant to be user-editable (open question 2). Otherwise document them as pipeline-only and have `ImportChroniclesCommand` populate them.

### MQ-4 — `EntityBuilder` bbox/temporal filters use correlated subqueries → full `entities` scan ×2
- **Location:** [EntityBuilder.php:87-127](../../api/app/Builders/EntityBuilder.php#L87) (`inBbox`/`territoryInBbox`/`nearPoint`/`orderByDistanceFrom`), [:135-164](../../api/app/Builders/EntityBuilder.php#L135) (`inTimeRange`/`existsAt`), helpers [:299-332](../../api/app/Builders/EntityBuilder.php#L299).
- **Impact:** Filters put a per-row correlated scalar subquery on the **left** of the `&&`/comparison operator, so Postgres can't use the GiST/btree indexes; it scans all `entities` rows and re-runs the subquery for each, and `paginate()` runs the predicate again for COUNT. `GET /v1/entities` with bbox/near/temporal degrades linearly with table size regardless of bbox selectivity. *(Reported; corroborated by laravel-core's correlated-subquery finding and the confirmed alias-subquery MQ-5. Performance, not correctness.)*
- **Blast radius:** `impact(ListEntitiesAction)` LOW, 2 direct dependents; also `GenerateEntityEmbeddingJob` uses `withGeoJson`.
- **Fix (prose):** Rewrite as `EXISTS (… WHERE el.geom && ST_MakeEnvelope(...))`/`JOIN LATERAL` with the indexed column on the operator's left; convert `withGeoJson`'s six per-row subqueries to laterals. Add the partial `is_primary` indexes first (plan 10, P4–P5).

### MQ-5 — Per-row correlated alias subquery, unindexed (planner-level N+1)
- **Location:** [MapEntitiesByYearAction.php:32-42](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L32) and [MapEntitiesAction.php:46-56](../../api/app/Actions/Entity/MapEntitiesAction.php#L46).
- **Impact:** Both map actions compute `display_name` via `(SELECT name … WHERE entity_id=… AND is_primary ORDER BY updated_at DESC, created_at DESC LIMIT 1)`. `entity_aliases` has no index covering `is_primary`/the sort, so Postgres re-runs an index scan + in-memory sort per output row — up to ~100 000 on `/map/year`. Correct results, but the dominant latency cost. *(Confirmed; verifier corrected high→medium: perf, not wrong behavior.)*
- **Blast radius:** `impact` LOW on both actions, 1 caller each.
- **Fix (prose):** Replace with one `LEFT JOIN LATERAL` for the primary alias and add a partial covering index on `entity_aliases(entity_id) WHERE is_primary` (include `name`, order by `updated_at/created_at`); or denormalize `display_name` onto `entities` via trigger. (Plan 10, P5.)

### MQ-6 — No zoom-keyed simplification; full-resolution polygons at every zoom
- **Location:** [MapEntitiesAction.php:62](../../api/app/Actions/Entity/MapEntitiesAction.php#L62) and [MapEntitiesByYearAction.php:48](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L48).
- **Impact:** Geometry is serialized with `ST_AsGeoJSON(COALESCE(territory_geom, geom), 5)` — 5-decimal coordinate rounding, **no vertex reduction** (`ST_Simplify`/`ST_AsMVT` appear nowhere). OHM border polygons (thousands of vertices) ship at full resolution even at world zoom, and the bbox endpoint doesn't clip to the envelope. Up to 100 000 such features on `/map/year`. *(Confirmed; perf, not correctness → medium.)*
- **Blast radius:** `impact` LOW, controller-only; output shape unchanged → frontend untouched.
- **Fix (prose):** Wrap geometry in `ST_SimplifyPreserveTopology(geom, tolerance)` with tolerance derived from zoom, reduce `ST_AsGeoJSON` digits by band, and clip to the bbox envelope on the spatial endpoint; longer-term expose `ST_AsMVT` tiles. Add a `zoom_level`/tolerance param to `/map/year`. (Plan 10, P2/P10.)

### MQ-7 — Scalar temporal predicate can't use the dedicated GiST range index (dead index)
- **Location:** [MapEntitiesByYearAction.php:52-56](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L52) and [MapEntitiesAction.php:66-70](../../api/app/Actions/Entity/MapEntitiesAction.php#L66); index `gp_active_range_gist_idx` ([migration 2026_04_06_000001:73-74](../../api/database/migrations/2026_04_06_000001_create_geometry_periods_table.php#L73)).
- **Impact:** The year overlap is expressed as scalar `start_year <= :y AND (end_year IS NULL OR end_year >= :y)`. The schema ships a purpose-built GiST index on `int4range(start_year, CASE WHEN end_year IS NULL THEN NULL ELSE end_year+1 END, '[)')`, but GiST range indexes serve only range operators (`@>`, `&&`), so it is **dead** for this query; the same applies to `etr_active_range_gist_idx`. *(Confirmed; perf → medium.)*
- **Blast radius:** `impact` LOW, both map actions; must preserve identical result semantics (covered by `MapEntitiesYearFilteringTest`, `GeometryPeriodPrecedenceTest`).
- **Fix (prose):** Rewrite the predicate as `int4range(start_year, end_year+1, '[)') @> :year` (and `&&` for ranges), matching the indexed expression; or add a stored generated `active_range` column + GiST. (Plan 10, P6.)

### MQ-8 — Over-fetched columns + map feature-contract drift
- **Location:** [MapEntitiesByYearAction.php:103-115](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L103) (11 properties emitted) vs [dashboard.tsx:21-35](../../api/resources/js/pages/dashboard.tsx#L21) (`MapFeature` type) and [historical-map-viewer.tsx:618-624](../../api/resources/js/components/historical-map-viewer.tsx#L618) (popup).
- **Impact:** The action emits `display_priority`/`icon_class`/`period_type`/`geometry_period_id`/`start_year`/`end_year` that the map never uses for rendering (only `id`/`name`/`entity_type`/`entity_group`/`impact_score` are consumed), multiplying payload across up to 100 000 features. Meanwhile the `MapFeature` TS type declares `temporal_start`/`temporal_end`/`entity_color` that the API **never sends** (so `entity_color` is always undefined → hardcoded `#2563eb`), and the popup reads `summary`/`year_start`/`year_end` — a third naming variant that never matches. The test fixture mirrors the wrong shape. *(Confirmed; this is the frontend FE-12 bug and the map-query contract-drift bug — the same defect.)*
- **Blast radius:** `impact` LOW, controller-only; trimming is safe for the current consumer (it ignores extras).
- **Fix (prose):** Trim to the consumed fields, emit `entity_color` from `attributes->>'entity_color'` in SQL, realign the `MapFeature` type and popup keys, and add a feature-shape contract test. (Plan 10, P8.)

### MQ-9 — OR-of-two-geometry-columns bbox predicate weakens GiST use + select/serialize mismatch
- **Location:** [MapEntitiesAction.php:126-130](../../api/app/Actions/Entity/MapEntitiesAction.php#L126).
- **Impact:** `(territory_geom && env OR geom && env)` spans two separately-indexed columns, so the planner must BitmapOr two GiST scans rather than one probe. Worse, the filter tests both columns independently while serialization/ordering prefer `COALESCE(territory_geom, geom)`: a row can be **selected by its point `geom` but rendered from an off-viewport `territory_geom`** (edge case: both columns populated, territory outside the bbox). *(Confirmed; perf + narrow correctness edge → medium. Latent until the bbox endpoint gets a consumer.)*
- **Blast radius:** `impact(MapEntitiesAction)` LOW, controller-only; no live consumer today.
- **Fix (prose):** Filter and serialize a single resolved geometry `COALESCE(territory_geom, geom)` and build a functional GiST index on that expression; or maintain a stored `map_geom` column. See open question 7.

### MQ-11 — `ResolveOhmFeatureAction` excludes open-ended periods (`end_year IS NULL`)
- **Location:** [ResolveOhmFeatureAction.php:76](../../api/app/Actions/EntityGeoRef/ResolveOhmFeatureAction.php#L76) and [:94](../../api/app/Actions/EntityGeoRef/ResolveOhmFeatureAction.php#L94) (`end_year >= target_year`, no NULL branch).
- **Impact:** Both period lookups require `end_year >= target_year`, so ongoing periods (`end_year IS NULL`, which the map renders as active) never match. Clicking such an entity skips the period geometry and falls back to a point or 404s — the highlight doesn't match the rendered border. *(Reported.)*
- **Blast radius:** `impact(ResolveOhmFeatureAction)` LOW, 1 caller.
- **Fix (prose):** Mirror the map predicate `(end_year IS NULL OR end_year >= target_year)` in both queries; add a regression test with an open-ended period. (Folded into plan 10, P3.)

### MQ-12 — `GeoJson` cast fallback does one DB round trip per geometry attribute (latent N+1 engine)
- **Location:** [GeoJson.php:54-57](../../api/app/Casts/GeoJson.php#L54).
- **Impact:** When a model is loaded without a precomputed `<key>_geojson` alias, `get()` issues `SELECT ST_AsGeoJSON(?)` per attribute access. Any loop touching `geom`/`territory_geom` silently becomes N+1 (2N+1 for both). Active offenders: `ResolveOhmFeatureAction` (MQ-3), `EntityResource` via `primaryLocation`, admin `EntityController::show`, `EntityTimelineController::show`, geometry-period CRUD, `BackfillGeometryPeriodsAction`. List endpoints are safe only because they precompute aliases — a discipline every new call site must remember. *(Cast mechanism confirmed by laravel-core; the per-call-site N+1 is reported.)*
- **Blast radius:** `impact(GeoJson, Class)` MEDIUM, 4 direct importers, 35 symbols across 3 depths.
- **Fix (prose):** Convert WKB→GeoJSON in PHP without a DB hop (parse the EWKB), or default models to select `ST_AsGeoJSON` aliases via a global scope; at minimum log/deprecate the fallback so per-row usage is visible.

### MQ-13 — Validated `group` filter silently ignored by both map actions
- **Location:** [MapEntitiesRequest.php:46](../../api/app/Http/Api/V1/Requests/MapEntitiesRequest.php#L46) (validated) vs [MapEntitiesAction.php](../../api/app/Actions/Entity/MapEntitiesAction.php) (never reads `$filters['group']`). *(Author-confirmed: the action reads `type`/`types`/`min_confidence`/`min_impact`/bbox/temporal but never `group`.)*
- **Impact:** Clients filtering the map by `group=POLITY` receive the unfiltered set with no error — a silent no-op filter. `MapEntitiesByYearAction` has no group support at all.
- **Blast radius:** `impact(MapEntitiesAction)` LOW, 1 caller.
- **Fix (prose):** Apply an `entity_group` equality predicate when present (the column is btree-indexed), and either add group support to the by-year action or drop the rule from the request.

### MQ-14 — `?parent_id=`/`include_children` 500 (`childrenOf` scope + `children` relation don't exist)
- **Location:** [ListEntitiesAction.php:86](../../api/app/Actions/Entity/ListEntitiesAction.php#L86) (`$query->childrenOf(...)`); [EntityResource.php:88-90](../../api/app/Http/Api/V1/Resources/EntityResource.php#L88); [EntityController.php:118-119](../../api/app/Http/Api/V1/Controllers/EntityController.php#L118). *(Author-confirmed: grep shows only these call sites — no `childrenOf`/`scopeChildrenOf` definition and no `Entity::children` relation.)*
- **Impact:** `ListEntitiesRequest` validates `parent_id`, and the action then calls the undefined `childrenOf` → `BadMethodCallException`; `include_children` eager-loads a non-existent `children` relation → `RelationNotFoundException`. Any request using the documented hierarchy params returns **HTTP 500**.
- **Blast radius:** `impact(ListEntitiesAction)` LOW, 2 direct dependents.
- **Fix (prose):** Either implement the hierarchy (a `children()` relation + `childrenOf` scope via the relationships table or a `parent_id` column) or remove `parent_id`/`include_children` from the request, action, and resource until it exists.

### MQ-15 — `ORDER BY display_priority DESC` puts NULL-priority rows first (curation inverted)
- **Location:** [MapEntitiesAction.php:135](../../api/app/Actions/Entity/MapEntitiesAction.php#L135) and [MapEntitiesByYearAction.php:95](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L95). *(Author-confirmed: `orderByDesc('entities.display_priority')`, column nullable, Postgres DESC defaults NULLS FIRST.)*
- **Impact:** Within the same territory class, un-prioritized entities outrank curated ones. When more rows match than the LIMIT, the visible feature set is the opposite of the curation intent.
- **Blast radius:** `impact` LOW, both actions.
- **Fix (prose):** Use explicit `display_priority DESC NULLS LAST` (with `impact_score DESC NULLS LAST` as tiebreaker) in both actions. (Plan 10, P7.)

### MQ-19 — Backfill/import ping-pong geometry through PHP in per-row loops
- **Location:** [BackfillGeometryPeriodsAction.php:22-23,59-69,130-181](../../api/app/Actions/Entity/BackfillGeometryPeriodsAction.php#L22); [ImportBorderEntityJob.php:320-356](../../api/app/Jobs/ImportBorderEntityJob.php#L320).
- **Impact:** Backfill reads `primaryLocation` geometry through the cast (round trips), holds it as a PHP array, and re-inserts per range and per relationship via `create()`/`update()`, each re-encoding with `ST_GeomFromGeoJSON`. Scales as O(entities × ranges × relationships) round trips with redundant WKB→JSON→WKB conversions. Not request-path, but it populates the map tables. *(Reported.)*
- **Blast radius:** `impact` LOW; `BackfillEntityCommand`, `ImportBorderEntityJob`.
- **Fix (prose):** Rewrite as `INSERT … SELECT` copying geometry column-to-column inside Postgres (no GeoJSON intermediate); batch period upserts with `INSERT … ON CONFLICT`. (Plan 10, P12.)

### FE-4 — Out-of-order OHM click-resolution responses (last to arrive wins)
- **Location:** [historical-map-viewer.tsx:1302-1353](../../api/resources/js/components/historical-map-viewer.tsx#L1302), invoked from handleClick at [:1167-1172](../../api/resources/js/components/historical-map-viewer.tsx#L1167).
- **Impact:** Each basemap click POSTs to `/map/resolve-ohm-feature` with no AbortController/sequence token and no latest-click check before `setOhmHighlightFeature`/`onFeatureClick`. Two rapid clicks can resolve B-then-A, leaving A highlighted and A selected though the user last clicked B.
- **Blast radius:** `impact(resolveClickedOhmFeature)` LOW, 1 caller; contained to the viewer.
- **Fix (prose):** Track a monotonic click sequence (or per-click AbortController that cancels the previous), apply only the latest response, and abort on unmount.

### FE-5 — Highlight selection change re-pushes the entire base FeatureCollection
- **Location:** [historical-map-viewer.tsx:485-586](../../api/resources/js/components/historical-map-viewer.tsx#L485) (single data-apply effect; `ohmHighlightData` in deps).
- **Impact:** The one effect lists `ohmHighlightData` in its deps and unconditionally `setData`s all three sources with freshly cloned arrays. Toggling one highlight feature re-serializes/re-tiles the full base-geometry source (potentially thousands of multipolygons), plus the defensive cloning doubles GC per run → frame hitches on dense years.
- **Blast radius:** `impact(HistoricalMapViewer)` — 9 indexed processes; props contract unchanged.
- **Fix (prose):** Split into one effect per source keyed on its own data (base/overlay/highlight), keeping fitBounds with the base/overlay effect; drop the cloning once each effect fires only on its own identity change.

### FE-7 — `normalizeToFeatures` mangles Features with null geometry
- **Location:** [geojson.ts:31-51](../../api/resources/js/lib/geojson.ts#L31).
- **Impact:** `{type:'Feature', geometry:null}` fails the `type==='Feature' && geometry` check, skips the GeometryCollection branch, and lands in the bare-geometry fallback, producing `{type:'Feature', geometry:<the original Feature>, properties:{}}` — invalid GeoJSON to `setData`, and its bogus nested coordinates can poison `computeBoundsFromFeatures`. Latent today (the year endpoint returns only non-null geometry) but the `MapFeature` type declares geometry nullable and overlay data passes arbitrary shapes through the same function.
- **Blast radius:** `impact(normalizeToFeatures)` 1 caller, 7 impacted across the Components module.
- **Fix (prose):** Explicitly return `[]` for any `Feature`/`FeatureCollection`/`GeometryCollection` candidate before the bare-geometry fallback, so null-geometry Features are dropped, not mangled.

### PP-8 — Brittle LLM JSON parsing; a schema-invalid item crashes the whole run
- **Location:** [parse_sequence.py:43](../../pipeline/agent/graph/nodes/parse_sequence.py#L43) (and the same pattern in `extract_candidates`, `generate_content`).
- **Impact:** Nodes `json.loads` after stripping only a leading ```json fence, then build all models in one comprehension inside a `try` that catches `(JSONDecodeError, TypeError)`. Prose-wrapped or differently-fenced output → empty list + one error. **But** a single schema-invalid item raises a pydantic `ValidationError` (a `ValueError`, **not** caught) which propagates uncaught out of `workflow.invoke` and **aborts the whole run** (no surrounding try/except). With non-tool-calling free fallback models, both failure modes are realistic. *(Confirmed; the verifier corrected the mechanism — invalid items crash rather than silently empty.)*
- **Blast radius:** String-wired nodes on the critical path; everything downstream depends on parsed output.
- **Fix (prose):** Use structured/JSON-mode output (response_format or tool calling) where supported; add tolerant extraction (locate the JSON object, strip arbitrary fences); validate items individually so one bad record is dropped with a warning; consider a bounded re-ask. (Plan 11.)

### PP-9 — No graph-level error handling / checkpointing
- **Location:** [workflow.py:65](../../pipeline/agent/graph/workflow.py#L65) (`compile()` with no checkpointer); `run_agent` calls `invoke` directly.
- **Impact:** A strictly linear 15-node graph with no error-routing edges, no checkpointer/thread_id, and node `llm.invoke()`/`subprocess.run` calls outside the narrow JSON try blocks. One transient failure (all LLM fallbacks down, Docker absent, an uncaught `ValidationError`) raises out of `invoke`, loses all in-memory state, and forces a restart from scratch. *(Confirmed; resilience gap → medium.)*
- **Blast radius:** Architectural; affects all agent runs.
- **Fix (prose):** Add a checkpointer (e.g. `SqliteSaver`) + `thread_id` for resumable partial progress, and wrap node bodies (or use a decorator) to convert exceptions into `PipelineError` state with an error-routing edge to a terminal audit node. (Plan 11.)

---

## Low

### LC-7 — `GeoJson` cast builds geometry SQL by string interpolation, not a bound parameter
- **Location:** [GeoJson.php:89](../../api/app/Casts/GeoJson.php#L89). *(Verdict: uncertain — the literal claim is true, but the injection/breakage risk is not reachable.)*
- **Impact:** `set()` returns `DB::raw("ST_SetSRID(ST_GeomFromGeoJSON('{$escaped}'),4326)")`, inlining JSON rather than binding it. Every real caller passes a PHP array, `json_encode` + single-quote-doubling with `standard_conforming_strings=on` is complete escaping, and the same expression is parameterized correctly in `HydrateEntityGeometryFromGeoRefAction` — so the inconsistency is real but no injection/crash is currently reachable. Hygiene/defense-in-depth.
- **Blast radius:** Applied via attribute casting (no CALLS edge); affects `EntityLocation`/`GeometryPeriod`/`EntityTimelineEntry`/`GeographicRegion` geometry columns.
- **Fix (prose):** Use a bound placeholder (`ST_GeomFromGeoJSON(?)`) integrated with query bindings, and reject non-array input + `json_encode` unconditionally so only controlled JSON is emitted.

### MQ-16 — Duplicate features per entity when multiple periods cover the year
- **Location:** [MapEntitiesAction.php:139-157](../../api/app/Actions/Entity/MapEntitiesAction.php#L139), [MapEntitiesByYearAction.php:99-117](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L99). *(Author-confirmed: one feature per `geometry_periods` row, `feature.id = entity_id`, no dedup.)*
- **Impact:** An entity with overlapping periods (territory + relationship-derived presence, or overlapping imports) yields multiple Features sharing one id; the territory-first ORDER BY sorts but doesn't collapse them. Stacked fills double-darken, feature-id interactions get ambiguous, duplicates consume LIMIT slots.
- **Blast radius:** `impact` LOW, both actions.
- **Fix (prose):** `DISTINCT ON (entity_id)` ordered by the territory-first/recency keys (or an opt-out param for callers wanting all periods). (Plan 10, P7.)

### MQ-17 — Antimeridian-crossing viewports rejected or invert the envelope
- **Location:** [MapEntitiesRequest.php:32-35](../../api/app/Http/Api/V1/Requests/MapEntitiesRequest.php#L32) (`between:-180,180`) + [MapEntitiesAction.php:119-130](../../api/app/Actions/Entity/MapEntitiesAction.php#L119) (single envelope). *(Reported.)*
- **Impact:** Across the dateline, MapLibre `getBounds()` yields lng outside ±180 or `min>max`; validation 422s or a degenerate envelope matches nothing. Invisible today only because the live consumer never sends a bbox.
- **Blast radius:** `impact(MapEntitiesAction)` LOW, 1 caller.
- **Fix (prose):** Normalize longitudes and, when `min_lng>max_lng`, OR two envelopes (`[min,180]` and `[-180,max]`); relax validation to accept wrapped values. See open question (antimeridian).

### MQ-18 — Validated `include_territories` parameter is dead
- **Location:** [MapEntitiesRequest.php:54](../../api/app/Http/Api/V1/Requests/MapEntitiesRequest.php#L54). *(Author-confirmed: never read; the action always serializes `COALESCE(territory_geom, geom)`.)*
- **Impact:** Consumers can't opt out of heavy territory polygons (e.g. points-only for low-bandwidth); the parameter silently does nothing.
- **Blast radius:** `impact(MapEntitiesAction)` LOW.
- **Fix (prose):** Implement it (serialize `geom` only / skip territory rows when false) or delete the rule.

### FE-6 — `ResizeObserver` effect never attaches
- **Location:** [historical-map-viewer.tsx:593-608](../../api/resources/js/components/historical-map-viewer.tsx#L593).
- **Impact:** Runs once with `[]` deps and returns early because `mapRef.current` is still null (the map is created async). The observer is never created; cleanup is dead code. Masked today by MapLibre's own `trackResize` default.
- **Blast radius:** Internal to the component; no contract change.
- **Fix (prose):** Delete the dead effect (documenting reliance on `trackResize`) or add `mapReady` to its deps so it attaches once the map exists.

### FE-8 — `fitBounds` math ignores antimeridian crossing
- **Location:** [geojson.ts:80-113](../../api/resources/js/lib/geojson.ts#L80) (`computeBoundsFromFeatures`).
- **Impact:** Naive min/max longitudes; any data straddling ±180° yields near-global bounds and `fitBounds` zooms out to the whole world. For the global-extent dashboard this mostly degrades fit quality.
- **Blast radius:** `impact(computeBoundsFromFeatures)` 1 caller, 3 impacted; viewer flows only.
- **Fix (prose):** Detect antimeridian spans (lng range > 180) and compute bounds in a shifted domain, or skip auto-fit beyond a span threshold.

### FE-9 — Empty/invalid year snaps to 100 and fetches; input diverges from rendered year
- **Location:** [dashboard.tsx:328-336](../../api/resources/js/pages/dashboard.tsx#L328) (`clampYear`) + [:150-165](../../api/resources/js/pages/dashboard.tsx#L150).
- **Impact:** `clampYear` returns 100 for any non-numeric string, including the empty string when the user clears the field — so clearing fires a fetch for year 100 and overwrites sessionStorage. Separately, `yearInput` holds raw text while `selectedYear` is clamped, so typing 5000 shows "5000" while the map renders 3000.
- **Blast radius:** `impact(clampYear)` 2 callers; keep `getInitialDashboardYear`'s default-on-missing semantics.
- **Fix (prose):** Treat empty/unparsable input as "no committed year" (keep previous, disable fetch) and reflect clamping back into the input.

### FE-10 — Hover popup goes stale on pan/zoom; reads property names the API never emits
- **Location:** [historical-map-viewer.tsx:1224-1231](../../api/resources/js/components/historical-map-viewer.tsx#L1224) (position captured once), [:619-639](../../api/resources/js/components/historical-map-viewer.tsx#L619) (`year_start/year_end` vs the API's `start_year/end_year`).
- **Impact:** Popup screen x/y is computed once at mouseenter and never updated on `move`, so panning leaves it floating; and it reads `year_start/year_end` while the endpoint emits `start_year/end_year`, so the intended From/To rows never render (the years fall into the generic key/value dump).
- **Blast radius:** `impact(bindOverlayInteractionHandlers)` 1 caller; shared by dashboard/edit/history-panel popups.
- **Fix (prose):** Store the feature's lngLat and re-project on `move` (or close on `movestart`); align the property names with the payload (and MQ-8).

### FE-11 — Debug `console.log` of up to 10 candidate features on every basemap click
- **Location:** [historical-map-viewer.tsx:1115-1133](../../api/resources/js/components/historical-map-viewer.tsx#L1115).
- **Impact:** Production code logs identifiers, scoring metadata, full properties, and entire feature objects for the top-10 candidates per click — console noise plus retained references (delayed GC) every session; leaks internal scoring.
- **Blast radius:** Behavior-neutral removal.
- **Fix (prose):** Remove or gate behind `import.meta.env.DEV`.

### PP-10 — `approval_gate` appends a plain dict where a `PipelineError` model is expected
- **Location:** [approval_gate.py:16](../../pipeline/agent/graph/nodes/approval_gate.py#L16). *(Confirmed; downgraded high→low — the branch is unreachable today.)*
- **Impact:** When `proposed_diff` is None, the node appends a raw dict; `audit_logger` runs `.model_dump()` and the CLI reads `.node`/`.error_type`, which would `AttributeError`. But `build_diff` unconditionally sets `proposed_diff`, so the branch is dead defensive code today; it becomes live under a future refactor.
- **Blast radius:** On the linear path between `build_diff` and `commit_writer`; 0 static callers (string-wired).
- **Fix (prose):** Append a `PipelineError` instance (standardize on it everywhere), or have consumers coerce dicts via `PipelineError(**e)`.

### PP-11 — `resolve_wikidata` overwrites `wikidata_match`, dropping the `existing_entity` dedup flag
- **Location:** [resolve_wikidata.py:22](../../pipeline/agent/graph/nodes/resolve_wikidata.py#L22). *(Confirmed; downgraded medium→low — currently unreachable + import-layer dedup backstops it.)*
- **Impact:** `db_lookup` stores the existing-DB marker inside `wikidata_match`; when a candidate also carries `wikidata_id`, `resolve_wikidata` reassigns `wikidata_match = full.get(qid, {})`, discarding `existing_entity`, so `build_diff` treats an existing entity as new. But **no agent code path populates `candidate.wikidata_id` today**, and the Laravel importer's `isDuplicate` (run by default) catches the QID and skips it — so no duplicate row results; the effect is a wasted import attempt. A latent foot-gun for a future change.
- **Blast radius:** String-wired node; feeds `build_diff` reuse-vs-create.
- **Fix (prose):** Keep `existing_entity` in a dedicated `EnrichedCandidate` field, or preserve it when overwriting `wikidata_match`.

### PP-12 — In-place mutation of shared state lists under a no-reducer `TypedDict`
- **Location:** [preprocess_transcript.py:68](../../pipeline/agent/graph/nodes/preprocess_transcript.py#L68) and the same `state[...].append(...)` + `return state` pattern across all nodes; `AgentRunState` has no `Annotated` reducers ([state.py:12-29](../../pipeline/agent/graph/state.py#L12)). *(Confirmed; benign today → low.)*
- **Impact:** Works only because the graph is strictly linear and nodes mutate the same channel-held list object. Introducing any parallel/fan-out/`Send` node, partial-update returns, or a checkpointer would cause lost/doubled appends and break replay — the canonical LangGraph foot-gun. Prerequisite for safe parallelism/checkpointing (PP-9).
- **Blast radius:** Cross-cutting; all nodes.
- **Fix (prose):** Move append-style fields (`errors`, `audit_log`, `committed`) to `Annotated` reducers (`operator.add`/custom merger) and have nodes return small partial-update dicts instead of mutating + returning the whole state. (Plan 11.)

---

## Appendix — Refuted during verification

- **Pipeline: "Re-running the same `run_id` is non-idempotent (duplicate imports/chronicle rows)"** — *Refuted.* Every write layer dedups: `ImportEntityJob`/`ImportEntitiesCommand.isDuplicate` (run by default, no `--force`), `ResolveRelationshipsJob.relationshipExists` (incl. symmetric reverse), and chronicle slug-dedup with a non-force no-op — all covered by passing tests. `chronicles:import` isn't even called by the pipeline. The only residual is a missing run-level short-circuit (redundant work on retry) — hygiene, downgraded to low; **not** the asserted duplicate-data bug.
- **Pipeline: "Default/fallback model IDs are hallucinated/typoed"** — *Refuted.* The flagged IDs (`google/gemma-4-*:free`, `openai/gpt-oss-20b/120b:free`, `x-ai/grok-4.20`) are **real** OpenRouter models released after the auditor's Jan-2026 knowledge cutoff; the fallback chain does not 404 on the live OpenRouter config. A narrower real issue remains (low): the **primary** defaults `gpt-4o-mini`/`gpt-4o` are bare OpenAI names that OpenRouter rejects without the `openai/` prefix, wasting ~2 retries per node before the valid fallbacks succeed, and model names aren't env-overridable.
- **Pipeline (partial): "Chronicle secondary-entity `entity_id` label fallback dangles/fails FK"** — *Refuted half of PP-6.* The importer (`syncSecondaryEntities`) intentionally consumes the label, looks entities up **by name**, and skips-with-warning on miss — the label is the expected input, never used as a raw FK. Only the `primary_relationship_id` half (PP-6) is a real bug.

---

## Notes on coverage and confidence
- **Authorization/security was not in scope.** The map endpoints are public/unauthenticated; the Chronicle write FormRequests only check `user() !== null` (no policy/ownership). A deliberately large, no-bbox, `min_impact`-free `/map/year` request is an unauthenticated, uncached DoS lever worth a follow-up.
- **No queries were `EXPLAIN`ed and no test suites were run.** All planner/index claims (BitmapOr, dead GiST index, the alias N+1) and "tests are mocked / no test exercises X" statements are reasoned from source, not measured.
- **Map-query coverage came from two auditor passes** (a comprehensive 14-finding pass whose verifiers were lost, and a focused 5-finding pass that verified cleanly). They were merged here; items marked *reported* are the ones only the first pass produced and that I did not personally re-read.

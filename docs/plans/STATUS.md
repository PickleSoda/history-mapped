# Plan Status Index

> **Verified:** 2026-06-15, by reading each plan against the live codebase (`api/`, `web/`, `pipeline/`).
> Plan checkboxes/headers are not authoritative — this index reflects what actually exists in code.
>
> Legend: ✅ Executed · 🟡 Partial (work remains) · ⬜ Not started · 🗄️ Archived (done/superseded, moved to `../archive/`)

## How to read this

- **`docs/plans/NN-*.md`** — the numbered product roadmap (foundation → API → OHM phases → hardening).
- **`docs/superpowers/plans/*.md`** — dated agent-driven implementation plans, each paired with a design spec in `docs/superpowers/specs/`.
- Fully-executed *historical* plans (April–May cycle) and superseded ones were moved to `docs/archive/superpowers-plans/`. The current cycle (June) stays here so this folder reads as the live backlog.

---

## Numbered roadmap (`docs/plans/`)

| Plan | Status | Notes |
|------|--------|-------|
| 01-foundation-setup | ✅ | Docker stack, workspace, env all present. |
| 02-app-scaffolding | ✅ | `api/` Laravel + `web/` SPA both far exceed scaffold. |
| 03-runtime-and-client-alignment | ✅ | `/api/v1` prefix, health route, Sanctum group, web client. |
| 04-entity-data-model | ✅ | Migrations `2026_03_18_*`, 13 models, PostGIS/pgvector indexes. |
| 05-api-layer | ✅ | DTO/Action/Resource V1 layer; live API grown past the doc. |
| 06-entity-model-simplification | ✅ | Dead columns absent; simplification folded into base schema. |
| 07-geoshape-territory-auto-population | ✅ | `pipeline/wikidata/scraper/geoshape.py` → `territory_geom`. |
| 08-ohm-phase-0-stabilize-rendering | ✅ | Shared viewer + `lib/geojson.ts` normalization. |
| 09-ohm-phase-1-ohm-basemap-and-timeframe | ✅ | Basemap + `ohm-date`/`ohm-layer-date-filter`. (Admin FE-1 padding still open — see 12-bug-report; `web/` already pads.) |
| 10-map-query-optimization | 🟡 | Index/payload plumbing shipped; see superpowers map-bbox plan for the live remainder (resolver, spatial builder, MVT/caching, MQ-2 dashboard fetch). |
| 10-ohm-phase-2-timeline-map-interaction | 🟡 | Selection + relationship-geometry done; UI extraction (2.1), source/target distinction (2.4), FE interaction tests (2.5) remain. |
| 11-agentic-pipeline-improvements | 🟡 | Write-path (PP-1/2/3/4/7) fixed; confidence rework (PP-5) + structured I/O, checkpointing, observability, caching not started. |
| 11-ohm-phase-3-reference-existing-ohm-objects | 🟡 | Backend (`entity_geo_refs`, resolve-ohm-feature) done; editor attach/search/remove UI + OHM retrieval expansion remain. |
| 12-bug-report | 🟡 | ~70% fixed (LC-1/2/3/4/5/6, MQ-7/8/11/13/14/15/16, PP-1/2/3/4/7). Open: **backend** MQ-2 (dashboard repoint), MQ-3/4/5/12/19 (perf rewrites, risky); **admin FE** FE-1/2/3/4/5/6/7/8/9/10/11; **pipeline** PP-5/8/9/10/11/12. |
| 12-ohm-phase-4-ohm-id-editor-integration | ⬜ | No iD editor surface / postMessage bridge yet. |
| 13-ohm-phase-5-change-requests-and-contribution-pipeline | ⬜ | No change_requests tables/models; depends on Phase 4. |
| 14-experimental-inferred-boundary-fallback-pipeline | ⬜ | Explicitly experimental; no `pipeline/inference/` yet. |
| 15-ohm-bulk-border-ingestion | ✅ | `pipeline/ohm_borders/*`, `ImportBordersCommand`, OHM-draft constraints. |
| 16-openapi-docs-exposure | ⬜ | No Scramble config/UI; was blocked on RBAC (17), now unblocking. |
| 17-rbac-write-authorization | 🟡 | **In progress (concurrent work):** `permission:` middleware on write routes + `Gate::before` admin super-user landed in `routes/api.php` / `AppServiceProvider`; verify PermissionSeeder, Policies, and tests to close out. |

## Active agent-driven plans (`docs/superpowers/plans/`)

| Plan | Status | Remaining |
|------|--------|-----------|
| 2026-04-08-entity-show-edit-crud-alignment | 🟡 | Geometry-period CRUD + timeline reads shipped; **hierarchy controls** (`parent_entity_id`/`successor_entity_id` in `entity-form.tsx`) not built. |
| 2026-06-02-ohm-border-event-extraction | 🟡 | Extractor/scan/build + CLI exist; **enrich path is a stub** (`search_event_by_title` raises `NotImplementedError`, no `run_event_enrich_stage`). |
| 2026-06-09-historical-entity-agentic-pipeline | ✅ | LangGraph agent shipped (`pipeline/agent/`, 15-node graph). |
| 2026-06-10-chronicle-model-implementation | ✅ | Chronicle tables/models/API + agent nodes. |
| 2026-06-11-chronicle-id-resolution | ✅ | `resolve_entity_ids` node + maps wired into workflow. |
| 2026-06-11-chronicle-model-extension | ✅ | start/end_year, impact_score, approximate_location + enum-based seeder. |
| 2026-06-12-agentic-pipeline-write-path | 🟡 | Write-path gating + error capture + dead-code removal done; **state reducers (T10) and SqliteSaver checkpointer (T12)** deliberately not adopted; verify T4/T9/T13/T15. |
| 2026-06-12-chronicle-data-model-completion | ✅ | source_evidence jsonb, slug-unique-ignore fix, import persists new fields. |
| 2026-06-12-confidence-scoring-rework | ⬜ | Entire plan open — `validate.py` still seeds flat `0.95`; no weights/flags/scorer/hard-block. Depends on write-path sub-project. |
| 2026-06-12-map-bbox-query-optimization | 🟡 | Phases 1–3 shipped (see below). **Remaining:** single-statement `ResolveOhmFeatureAction` (T12), EntityBuilder spatial EXISTS/LATERAL rewrite (T13), destructive borders-from-OHM storage migration (T15–17), admin dashboard FE (T10/11, intentionally skipped). |
| 2026-06-12-temporal-semantics-unification | ✅ | LC-3 fix, int4range temporal scopes, timeline observers + bulk-import suppression, OHM ref on timeline entries. *Known deferral:* admin `entity-history-panel.tsx` OHM-highlight wiring skipped. |

### Recently executed slices (this cycle)

`map-bbox-query-optimization` Phases 1–3 + `temporal-semantics-unification` shipped on `main`:
ConfidenceLevel::atLeast, int4range temporal predicate, DISTINCT-ON dedup, ZoomSimplification, COALESCE bbox + antimeridian, trimmed payload + entity_color + OHM ref, ETag/Cache-Control, OHM ref on `/entities/map/year` and timeline entries, timeline observers, and removal of the broken `parent_id`/`include_children` params. Migration `2026_06_14_000001_map_optimization_indexes`.

---

## What still needs execution (priority view)

**Pipeline / data quality**
- `confidence-scoring-rework` (⬜) — replace the flat 0.95 floor with weighted scoring + hard-blocks. Highest-leverage data-quality gap.
- `ohm-border-event-extraction` enrich stub (🟡) — wire live Wikidata event search.
- `11-agentic-pipeline-improvements` P3+ (🟡) — structured LLM I/O, checkpointing, observability.

**Map / API performance (superpowers map-bbox remainder)**
- Single-statement `ResolveOhmFeatureAction` (T12), EntityBuilder spatial EXISTS/LATERAL (T13) — perf, optional.
- Borders-from-OHM storage cleanup (T15–17) — destructive; serving path already correct, so low urgency.
- MQ-2 (dashboard unbounded `/entities/map/year` fetch) + MQ-15 (display_priority NULLS ordering).

**Frontend (admin)**
- FE-1 admin date padding, FE-5/7/10/11 viewer bugs (12-bug-report).
- Entity-form hierarchy controls (2026-04-08 plan).
- Phase 2 UI extraction + interaction tests.

**Editorial / contribution program (OHM phases 4–5)**
- iD editor integration (12), change-requests pipeline (13) — large, not started.
- OpenAPI docs (16) + RBAC completion (17, concurrent).

**Experimental**
- Inferred-boundary fallback pipeline (14) — explicitly experimental, no code.

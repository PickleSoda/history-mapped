# Plan Status Index

> **Verified:** 2026-06-15 against the live codebase (`api/`, `web/`, `pipeline/`); structure refreshed 2026-06-18.
> Plan checkboxes/headers are not authoritative — this index reflects what actually exists in code.
>
> Legend: ✅ Executed · 🟡 Partial (work remains) · ⬜ Not started

## How to read this

- **`docs/plans/*.md`** — the live product backlog. The OHM program keeps its `ohm-phase-N-*` names; cross-cutting efforts are named by topic. Fully-executed roadmap plans were moved to [`../archive/plans/`](../archive/plans/).
- **`docs/superpowers/plans/*.md`** — dated agent-driven implementation plans, each paired with a design spec in `docs/superpowers/specs/`. Completed plans + their specs were moved to [`../archive/superpowers-plans/`](../archive/superpowers-plans/) and [`../archive/superpowers-specs/`](../archive/superpowers-specs/).
- Only **in-progress / not-started** work remains in the live folders, so they read as the backlog.

---

## Live product backlog (`docs/plans/`)

| Plan | Status | Notes |
|------|--------|-------|
| [map-query-optimization](map-query-optimization.md) | 🟡 | Index/payload plumbing shipped; live remainder tracked in the superpowers map-bbox plan (resolver, spatial builder, MVT/caching, MQ-2 dashboard fetch). |
| [agentic-pipeline-improvements](agentic-pipeline-improvements.md) | 🟡 | Write-path (PP-1/2/3/4/7) fixed; confidence rework (PP-5) + structured I/O, checkpointing, observability, caching not started. |
| [bug-report](bug-report.md) | 🟡 | ~70% fixed. Open: **backend** MQ-2 (dashboard repoint), MQ-3/4/5/12/19 (perf rewrites, risky); **admin FE** FE-1…FE-11; **pipeline** PP-5/8/9/10/11/12. |
| [ohm-phase-2-timeline-map-interaction](ohm-phase-2-timeline-map-interaction.md) | 🟡 | Selection + relationship-geometry done; UI extraction (2.1), source/target distinction (2.4), FE interaction tests (2.5) remain. |
| [ohm-phase-3-reference-existing-ohm-objects](ohm-phase-3-reference-existing-ohm-objects.md) | 🟡 | Backend (`entity_geo_refs`, resolve-ohm-feature) done; editor attach/search/remove UI + OHM retrieval expansion remain. |
| [ohm-phase-4-ohm-id-editor-integration](ohm-phase-4-ohm-id-editor-integration.md) | ⬜ | No iD editor surface / postMessage bridge yet. |
| [ohm-phase-5-change-requests-and-contribution-pipeline](ohm-phase-5-change-requests-and-contribution-pipeline.md) | ⬜ | No change_requests tables/models; depends on Phase 4. |
| [experimental-inferred-boundary-fallback-pipeline](experimental-inferred-boundary-fallback-pipeline.md) | ⬜ | Explicitly experimental; no `pipeline/inference/` yet. |

### Executed roadmap (archived → [`../archive/plans/`](../archive/plans/))

`01-foundation-setup` · `02-app-scaffolding` · `03-runtime-and-client-alignment` · `04-entity-data-model` · `05-api-layer` · `06-entity-model-simplification` · `07-geoshape-territory-auto-population` · `08-ohm-phase-0-stabilize-rendering` · `09-ohm-phase-1-ohm-basemap-and-timeframe` · `15-ohm-bulk-border-ingestion` · `16-openapi-docs-exposure` (commit `fd6b69f`) · `17-rbac-write-authorization` (commit `7190bb2`) — all ✅ verified shipped.

---

## Active agent-driven plans (`docs/superpowers/plans/`)

| Plan | Status | Remaining |
|------|--------|-----------|
| [2026-04-08-entity-show-edit-crud-alignment](../superpowers/plans/2026-04-08-entity-show-edit-crud-alignment.md) | 🟡 | Geometry-period CRUD + timeline reads shipped; **hierarchy controls** (`parent_entity_id`/`successor_entity_id` in `entity-form.tsx`) not built. |
| [2026-06-02-ohm-border-event-extraction](../superpowers/plans/2026-06-02-ohm-border-event-extraction.md) | 🟡 | Extractor/scan/build + CLI exist; **enrich path is a stub** (`search_event_by_title` raises `NotImplementedError`). |
| [2026-06-12-agentic-pipeline-write-path](../superpowers/plans/2026-06-12-agentic-pipeline-write-path.md) | 🟡 | Write-path gating + error capture + dead-code removal done; **state reducers (T10) and SqliteSaver checkpointer (T12)** deliberately not adopted; verify T4/T9/T13/T15. |
| [2026-06-12-confidence-scoring-rework](../superpowers/plans/2026-06-12-confidence-scoring-rework.md) | ⬜ | Entire plan open — `validate.py` still seeds flat `0.95`; no weights/flags/scorer/hard-block. Depends on the write-path sub-project. |
| [2026-06-12-map-bbox-query-optimization](../superpowers/plans/2026-06-12-map-bbox-query-optimization.md) | 🟡 | Phases 1–3 shipped. **Remaining:** single-statement `ResolveOhmFeatureAction` (T12), EntityBuilder spatial EXISTS/LATERAL rewrite (T13), destructive borders-from-OHM storage migration (T15–17), admin dashboard FE (T10/11, intentionally skipped). |

### Completed this cycle (archived → [`../archive/superpowers-plans/`](../archive/superpowers-plans/))

`2026-06-09-historical-entity-agentic-pipeline` · `2026-06-10-chronicle-model-implementation` · `2026-06-11-chronicle-id-resolution` · `2026-06-11-chronicle-model-extension` · `2026-06-12-chronicle-data-model-completion` · `2026-06-12-temporal-semantics-unification` — all ✅. Their design specs moved to [`../archive/superpowers-specs/`](../archive/superpowers-specs/).

### Design specs without an active plan (`docs/superpowers/specs/`)

Forward-looking / partial design material kept live for direction:
- **Web/Atlas frontend** (unbuilt): `2026-06-12-web-interaction-model-design`, `2026-06-12-web-frontend-design-brief`, `2026-06-13-atlas-frontend-plumbing-design` → see [architecture/frontend-app.md](../architecture/frontend-app.md).
- **`2026-06-02-standalone-relationship-resolution-design`** — partial: the standalone `pipeline:resolve-relationships` / `report-relationship-hints` CLI is **not** implemented (the original plan is archived). Open remainder; no active plan.
- **`2026-06-12-audit-open-questions-decisions`** — cross-cutting decision record.

---

## What still needs execution (priority view)

**Pipeline / data quality**
- `confidence-scoring-rework` (⬜) — replace the flat 0.95 floor with weighted scoring + hard-blocks. Highest-leverage data-quality gap.
- `ohm-border-event-extraction` enrich stub (🟡) — wire live Wikidata event search.
- `agentic-pipeline-improvements` P3+ (🟡) — structured LLM I/O, checkpointing, observability.

**Map / API performance**
- Single-statement `ResolveOhmFeatureAction` (T12), EntityBuilder spatial EXISTS/LATERAL (T13) — perf, optional.
- Borders-from-OHM storage cleanup (T15–17) — destructive; serving path already correct, low urgency.
- MQ-2 (dashboard unbounded `/entities/map/year` fetch) + MQ-15 (display_priority NULLS ordering).

**Frontend (admin)**
- FE-1 admin date padding, FE-5/7/10/11 viewer bugs (bug-report).
- Entity-form hierarchy controls (2026-04-08 plan).
- Phase 2 UI extraction + interaction tests.

**Editorial / contribution program (OHM phases 4–5)**
- iD editor integration (phase 4), change-requests pipeline (phase 5) — large, not started.

**Experimental**
- Inferred-boundary fallback pipeline — explicitly experimental, no code.

# Temporal Semantics Unification — Implementation Plan

> **Status: ✅ Executed** — verified 2026-06-15 against the codebase. See [STATUS.md](../../plans/STATUS.md).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply one consistent rule for unknown/open-ended/BCE temporal bounds end-to-end — fix the timeline open-start crash, include open-ended entities in temporal filters, make sub-1000-CE/BCE years filter the OHM basemap, and keep timelines fresh without rebuild storms.

**Architecture:** A symmetric coalesce in the timeline builder, an index-usable open-ended-aware predicate in `EntityBuilder`, a year-padding fix in the frontend OHM date helper, and new debounced/suppressible observers for relationship/location writes.

**Tech Stack:** Laravel 13 (PHP 8) + PostgreSQL (int4range/GiST), PHPUnit; React/TS (Vitest).

**Spec:** [../specs/2026-06-12-temporal-semantics-unification-design.md](../specs/2026-06-12-temporal-semantics-unification-design.md)

---

## File structure

| File | Change |
|------|--------|
| `api/app/Builders/EntityTimelineEntryBuilder.php` | Symmetric `start_year ?? end_year` coalesce |
| `api/app/Builders/EntityBuilder.php` | Open-ended-aware int4range temporal predicate |
| `api/resources/js/pages/dashboard.tsx` | `yearToTimeframe` pads via `yearToOhmDate` |
| `api/resources/js/lib/ohm-date.ts` | (alt) relax `normalizeOhmDate` regex |
| `api/app/Observers/EntityRelationshipObserver.php`, `EntityLocationObserver.php` | New observers |
| `api/app/Providers/AppServiceProvider.php` | Register observers + suppression flag |
| `api/app/Console/Commands/*Import*` | Set the suppression flag during bulk import |

---

## Task 1: Fix the open-start timeline crash (LC-3)

**Files:** Modify `api/app/Builders/EntityTimelineEntryBuilder.php:66`; Test `api/tests/Feature/TimelineProjectionTest.php` (extend or new)

- [ ] **Step 1: Write the failing test** — an entity whose only `EntityTemporalRange` has `start_year = null, end_year = 1200` and no geometry periods/relationships → `ProjectEntityTimelineAction::rebuildForEntity` succeeds and writes one timeline row with `start_year = 1200`.
- [ ] **Step 2: Run → FAIL** (NOT NULL violation today). `... artisan test --filter=TimelineProjectionTest`
- [ ] **Step 3: Implement** — `'start_year' => $range->start_year ?? $range->end_year` (mirroring the existing end fallback).
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(api): timeline projection no longer crashes on open-start temporal ranges`

## Task 2: Frontend OHM date padding (FE-1)

**Files:** Modify `api/resources/js/pages/dashboard.tsx:348-350`; Test `api/resources/js/lib/__tests__/ohm-date.test.ts` (new) + `dashboard.test.tsx`

- [ ] **Step 1: Write the failing tests** — (a) `normalizeOhmDate(yearToTimeframe(100))` is non-null and equals a padded `"0100-01-01"`; (b) `yearToTimeframe(-500)` → non-null normalized date.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — make `yearToTimeframe` delegate to the existing `yearToOhmDate` helper (zero-pads to ≥4 digits, preserves the BCE minus sign). Update `dashboard.test.tsx` to assert the padded format.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(web): pad OHM timeframe dates so sub-1000-CE/BCE years filter the basemap`

## Task 3: EntityBuilder open-ended semantics + int4range predicate

**Files:** Modify `api/app/Builders/EntityBuilder.php:135-164`; Test `api/tests/Feature/EntityBuilderTemporalTest.php` (new)

- [ ] **Step 1: Write the failing tests** — (a) an entity with `end_year = null` (ongoing) matches `existsAt(1500)` for any year ≥ its start; (b) an `EXPLAIN` test shows `etr_active_range_gist_idx` is used.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — express `inTimeRange`/`existsAt` against `entity_temporal_ranges` using `int4range(start_year, CASE WHEN end_year IS NULL THEN NULL ELSE end_year+1 END, '[)')` with `@>`/`&&`, treating NULL start as `int4range(NULL, ...)` (unbounded below). Preserve existing result semantics for closed ranges.
- [ ] **Step 4: Run → PASS** (existing builder tests + new open-ended cases).
- [ ] **Step 5: Commit** `fix(api): temporal scopes include open-ended ranges and use the GiST range index`

## Task 4: Timeline-freshness observers with bulk-import suppression

**Files:** Create `api/app/Observers/EntityRelationshipObserver.php`, `EntityLocationObserver.php`; Modify `api/app/Providers/AppServiceProvider.php`, the import commands; Test `api/tests/Feature/TimelineFreshnessTest.php` (new)

- [ ] **Step 1: Write the failing tests** — (a) saving an `EntityRelationship` outside `RelationshipController` dispatches `RebuildEntityTimelineJob` for both endpoints; (b) a bulk import wrapped in the suppression flag dispatches **one** batched rebuild, not N.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — observers dispatch `RebuildEntityTimelineJob` on created/updated/deleted, guarded by a static `RebuildEntityTimelineJob::$suppressed` (or a cache flag) that the import commands set around their batch, followed by a single `ProjectEntityTimelineAction()(null)`-style batch rebuild for the touched ids. Register the observers in `AppServiceProvider::boot`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(api): relationship/location timeline observers with bulk-import suppression`

## Task 5: OHM-linked timeline entries highlight the OHM feature (borders-from-OHM follow-up)

**Files:** Create `api/database/migrations/2026_06_12_000004_timeline_ohm_ref.php`; Modify `api/app/Actions/Timeline/ProjectEntityTimelineAction.php`, `api/app/Http/Api/V1/Resources/EntityTimelineEntryResource.php`, `api/resources/js/components/entity-history-panel.tsx`; Test `TimelineOhmRefTest.php` (new), `entity-history-panel.test.tsx`

> Spec §4.1 (OHM-linked timeline highlight) / decision D19. Mirrors plan A Task 9b so OHM borders highlight consistently across the dashboard map and the history panel. Do **after** plan A Task 9b (defines the `ohm_external_id` feature-property contract the panel reuses).

- [ ] **Step 1: Write the failing tests** — (a) a rebuilt timeline entry for an OHM-linked entity carries its `ohm_external_id` in the read model / resource; (b) `entity-history-panel` highlights the OHM feature (calls the OHM-highlight path) when an active entry has `ohm_external_id` and null `territory_geom`, instead of pushing a polygon into the overlay source.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** —
  - Migration: add nullable `ohm_external_id` (+ `ohm_provider`/`ohm_external_type`) to `entity_timeline_entries`.
  - `ProjectEntityTimelineAction`: project the entity's active `ohm` geo-ref `external_id` onto the inserted rows (join `entity_geo_refs` where provider=ohm, is_active). (Alternative if a column is undesirable: expose it via a join in `EntityTimelineEntryResource` instead — pick one and keep it consistent.)
  - `EntityTimelineEntryResource`: include `ohm_external_id` (+ provider/type).
  - `entity-history-panel.tsx`: when an active entry has `ohm_external_id` and no `territory_geom`, call the shared OHM-highlight helper (same mechanism the dashboard map uses with the `ohm_external_id` property) rather than enriching a polygon into the overlay; keep rendering point `geom` markers for app-owned geometry.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat: OHM-linked timeline entries highlight the OHM basemap feature`

---

## Self-review (coverage)

- LC-3 → T1. FE-1 → T2. open-ended semantics + MQ-7 (etr index) → T3. timeline freshness → T4. OHM-linked timeline
  highlight (D19) → T5. The geometry-period `int4range` predicate (MQ-7) is implemented in sub-project A; this plan covers
  the `entity_temporal_ranges` sibling. All spec requirements mapped.

## Execution handoff

Subagent-driven recommended. Task 1 (the crash) first; Task 4 (observers) last, with the bulk-import suppression test as the guardrail against rebuild storms.

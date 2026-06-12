# Temporal Semantics Unification — Design Spec

> **Date:** 2026-06-12
> **Status:** Design (approved) — ready for implementation planning
> **Area:** `api/` (EntityBuilder temporal scopes, timeline projection, migrations, observers) + `api/resources/js` (OHM date helper).
> **Source:** bug report LC-3, FE-1, MQ-7 (predicate form), and the cross-cutting "temporal-edge handling" theme.
> **Sub-project:** E of the audit-remediation set.

## 1. Problem

Unknown/open-ended/BCE temporal bounds are mishandled inconsistently at every layer: the timeline fallback crashes on
open-start ranges (LC-3); `EntityBuilder` temporal scopes exclude open-ended entities; the frontend OHM date filter
silently fails for sub-4-digit and BCE years (FE-1); and timeline freshness depends on the write path (only `GeometryPeriod`
/`EntityTemporalRange` observers exist). One consistent ruling closes all of these.

## 2. Goals / Non-goals

**Goals**
- A single, documented rule for unknown bounds applied end-to-end.
- The timeline projection never crashes on open-start ranges.
- Open-ended entities are included (not silently excluded) by temporal filters and the map/click paths.
- Sub-1000-CE and BCE years filter the OHM basemap correctly.
- Timelines stay fresh regardless of write path, without rebuild storms.

**Non-goals**
- The map query's bbox/zoom/payload work (sub-project A) — this spec only covers the *temporal* predicate form and semantics.
- New temporal data model columns — years are already signed integers; no schema change beyond optional helper indexes.

## 3. Accepted decision — the rule

**Unknown bounds are unbounded, never excluded. BCE is a negative signed year. Pad years on display.**

- `start_year IS NULL` ⇒ −∞ for overlap; `end_year IS NULL` ⇒ +∞ (ongoing). Both NULL ⇒ always overlapping.
- Timeline projection coalesces `start ?? end` (and `end ?? start`) symmetrically so an end-only range projects a span,
  not a NULL crash.
- Map and `ResolveOhmFeatureAction` treat `end_year IS NULL` as ongoing (the map already does; the click path is fixed in
  sub-project A / cross-referenced).
- BCE years are stored as negative integers (already true); the only BCE/early-year bug is display-side date formatting.

## 4. Architecture

### 4.1 Components

**`EntityTimelineEntryBuilder::fromPrimaryTemporalRange` (LC-3).** Set `start_year => $range->start_year ?? $range->end_year`
(mirroring the existing `end_year ?? start_year`), so an open-start range never inserts NULL into the NOT NULL
`entity_timeline_entries.start_year`.

**`EntityBuilder::inTimeRange`/`existsAt` (semantics).** Confirm NULL bounds are treated as ±∞ so open-ended entities
*match* an overlapping query window rather than being excluded. Express the predicate in `int4range … && / @>` form so the
`etr_active_range_gist_idx` is usable (parallels MQ-7's geometry-period fix; here for `entity_temporal_ranges`).

**Frontend `yearToTimeframe` / `normalizeOhmDate` (FE-1).** Pad years to ≥4 digits via the existing `yearToOhmDate`
helper (`100 → "0100-01-01"`, `-500 → "-0500-01-01"`), OR relax `normalizeOhmDate` to accept 1–4-digit years consistent
with `dateRangeFromISODate`'s `\d{1,4}` regex (the two currently disagree). Choose padding (dashboard-local, lower blast radius).

**Timeline freshness observers.** Add `EntityRelationship` and `EntityLocation` observers that dispatch
`RebuildEntityTimelineJob` for the affected entity id(s), guarded by a "suppress during bulk import" flag the importers set
(then one batch rebuild at the end), or per-entity debouncing — to avoid rebuild storms.

## 5. Data flow

Timeline projection: canonical tables → `ProjectEntityTimelineAction` (now crash-safe on open-start) → `entity_timeline_entries`.
Temporal filters: `EntityBuilder` scopes use index-usable range predicates and include open-ended rows. Frontend: padded
ISO dates flow into `applyOhmLayerDateFilter` so the basemap filters at all eras.

## 6. Error handling

- Open-start range → projects a valid span (no NOT NULL violation, no failed queued job).
- Sub-4-digit/BCE year → a valid normalized date (basemap filters), not a silent all-eras fallback.
- Bulk import → batched/suppressed rebuilds, not a storm of queued jobs.

## 7. Testing

- LC-3: rebuilding the timeline for an entity whose only range is end-only (NULL start) succeeds and projects a span at `end_year`.
- Open-ended inclusion: an entity with `end_year IS NULL` matches an `existsAt(year)` for any year ≥ its start.
- FE-1: `yearToTimeframe(100)` / `(-500)` produce non-null normalized dates and the basemap filter is applied (assert via a non-mocked `normalizeOhmDate` test).
- Observers: saving an `EntityRelationship` outside the controller dispatches a rebuild; a bulk import dispatches a single batched rebuild, not N.

## 8. Sequencing (feeds the plan)

1. LC-3 timeline coalesce (stops the crash).
2. Frontend date padding (FE-1).
3. EntityBuilder open-ended semantics + int4range predicate.
4. Observers + bulk-import suppression.

## 9. Risks

- **Observer rebuild storms** — the suppression/batching flag is the critical mitigation; test the bulk-import path explicitly.
- **Predicate parity** — the `int4range` rewrite for `entity_temporal_ranges` must preserve existing `inTimeRange`/`existsAt`
  results; guard with the existing builder tests plus new open-ended cases.

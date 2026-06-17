# Chronicle Display on the Dashboard — Design Spec

> **Date:** 2026-06-12
> **Status:** Design (proposed — new feature, not from the audit). Design decisions below are mine; flag any you'd change on review.
> **Area:** `api/resources/js` (Inertia admin dashboard) + the existing public Chronicle API.
> **Related:** [chronicle-data-model-completion-design](2026-06-12-chronicle-data-model-completion-design.md) (D — enhances this), entity-model [attributes.md §6](../../entity-model/attributes.md).

## 1. Problem / intent

Chronicles (ordered narrative sequences over entities + relationships) exist in the data model and have a public read API,
but they are **invisible on the map dashboard**. We want to surface them so a reviewer can browse chronicles and step
through a chronicle's entries, with each entry jumping the map to that moment in time and place — turning a chronicle into
a guided tour over the existing year-driven map.

## 2. Goals / Non-goals

**Goals**
- A chronicles panel on the dashboard: searchable list → select a chronicle → see its ordered entries.
- Selecting an entry drives the existing dashboard state: sets the year (which refreshes the map + OHM date filter) and
  selects the entry's primary entity (which populates the existing Selection panel and highlights the map feature).
- Lightweight "step through" (prev/next entry) so a chronicle reads as a narrative walk.
- Reuse the existing year + entity-selection machinery — no parallel map state.

**Non-goals (this iteration)**
- Editing chronicles on the dashboard (CRUD already lives in the admin Chronicle pages).
- A full bottom-timeline scrubber or cinematic "story mode" (future; see Approaches B/C).
- Server-side "chronicles active in year N" filtering — depends on sub-project D exposing entry/chronicle years on the
  index endpoint; this spec works without it and adopts it when available.

## 3. Current surfaces (grounding)

- `GET /api/v1/chronicles` — paginated **summaries** (`chronicle_id`, `title`, `slug`, `source_type`, `status`,
  `entry_count`, timestamps); supports `search`/`status`/`per_page`/`page`. Does **not** return entries or temporal fields.
- `GET /api/v1/chronicles/{slug}` — full chronicle with entries eager-loaded
  (`entries.primaryRelationship.sourceEntity/targetEntity`, `entries.secondaryEntities`); `ChronicleEntryResource` exposes
  a derived **`timestamp`** per entry (from the primary relationship or earliest secondary entity), so each entry has a
  usable year today even before D serializes explicit `start_year`.
- Dashboard layout (`api/resources/js/pages/dashboard.tsx`): a header (year input) + a `[map | 22rem aside]` grid where the
  aside is the entity **Selection** panel. Year state (`selectedYear`) drives the map query; `selectedEntityId` drives the
  Selection panel + (via `onFeatureClick`) map highlight.

## 4. Approaches considered

- **A — Chronicles tab in the right aside + entry drill-down that drives the map (recommended).** The 22rem aside becomes a
  two-tab panel: **Chronicles** (searchable list → entries) and **Selection** (existing entity detail). Selecting an entry
  sets year + entity selection. Lowest complexity; reuses all existing state; ships value immediately.
- **B — Bottom timeline track with chronicle bars.** Chronicles as horizontal bars on a year scrubber; click to scrub.
  More immersive but needs a timeline component that doesn't exist yet — larger, and better built on top of A.
- **C — Full "story mode" overlay.** A chronicle becomes a step-through narrative that advances year + camera with
  transitions. Highest polish, most work; a natural follow-on once A exists.

**Recommendation: A**, designed so B and C can build on the same data hooks and entry-step logic later.

## 5. Architecture (Approach A)

```
 dashboard.tsx
   ├─ state: selectedYear, selectedEntityId  (existing)
   ├─ state: selectedChronicleSlug, activeEntryId  (new)
   └─ right aside = Tabs[ "Chronicles" | "Selection" ]
        ├─ <ChroniclePanel>             ── useChronicles({search})  → GET /v1/chronicles
        │     └─ list rows (title, source_type badge, entry_count)
        │           └─ onSelect(slug) → setSelectedChronicleSlug
        ├─ <ChronicleDetail slug>       ── useChronicle(slug)       → GET /v1/chronicles/{slug}
        │     └─ entries (sequence_order): narrative, year(timestamp), entities
        │           └─ onSelectEntry(entry) ──► applyEntry(entry)
        │     └─ prev/next stepper
        └─ <SelectionPanel>             (existing entity detail)

 applyEntry(entry):
   setSelectedYear(entryYear(entry))            // drives the existing map query + OHM date filter
   setSelectedEntityId(entryPrimaryEntityId(entry))  // drives Selection + map highlight
   (optional) viewer.flyTo(entry.approximate_location)  // enhancement
```

### 5.1 Components (new)

- **`api/resources/js/types/chronicle.ts`** — `Chronicle`, `ChronicleSummary`, `ChronicleEntry` TS types matching the API
  resources (the existing `web/src/types/chronicle.ts` is in the other SPA; the Inertia app needs its own).
- **`useChronicles(params)`** / **`useChronicle(slug)`** — TanStack Query hooks wrapping the two endpoints.
- **`ChroniclePanel`** — search box + scrollable summary list + pagination/"load more"; emits `onSelect(slug)`.
- **`ChronicleDetail`** — renders the selected chronicle's entries in `sequence_order` (narrative snippet, derived year,
  involved entity chips), a prev/next stepper, and a "back to list" affordance; emits `onSelectEntry(entry)`.
- **Aside tab wrapper** in `dashboard.tsx` — switches between Chronicles and Selection (auto-focus Selection when an entry
  selects an entity, with a visible way back to the chronicle).

### 5.2 Helpers

- **`entryYear(entry)`** — `entry.start_year ?? entry.timestamp-derived year ?? chronicle.start_year`. (Uses the derived
  `timestamp` today; prefers the explicit field once D lands.)
- **`entryPrimaryEntityId(entry)`** — `entry.primaryRelationship?.source_entity_id ?? entry.secondaryEntities?.[0]?.entity_id`.

### 5.3 Optional viewer enhancement
Add an optional `flyTo?: {lng,lat}` (or `focusKey`) prop to `HistoricalMapViewer` so `applyEntry` can pan to
`entry.approximate_location` when present. If omitted, selection-driven highlight (existing) is the fallback — so this is
not a blocker.

## 6. Data flow

Browse: `ChroniclePanel` → `GET /v1/chronicles?search=` (cached by query key). Select chronicle → `ChronicleDetail` →
`GET /v1/chronicles/{slug}` (cached). Select entry → `applyEntry` sets `selectedYear` (same value → map cache hit; new
value → the existing year query refetches the map and re-applies the OHM date filter) and `selectedEntityId` (existing
entity query + map highlight). Stepping prev/next just calls `applyEntry` on the adjacent entry.

## 7. Error / edge handling

- Entry with no resolvable year → keep the current year; still select the entity and show the narrative.
- Entry with no primary entity → no selection; show the narrative only.
- `approximate_location` null → no fly-to; rely on selection highlight.
- Empty chronicle list / search miss → empty state. Index `per_page` 20 → "load more" (or a small pager).
- Re-selecting the same year must not thrash the map (the existing year query key handles this — assert in tests).

## 8. Testing

- `useChronicles`/`useChronicle` fetch + cache (mocked fetch).
- `ChroniclePanel`: renders summaries, search filters the request, select emits the slug.
- `ChronicleDetail`: entries render in `sequence_order`; selecting an entry calls `applyEntry` with the derived year +
  primary entity id; prev/next steps correctly.
- Dashboard integration: selecting an entry updates `selectedYear` + `selectedEntityId`; a same-year entry does not refetch
  the map (cache hit); the Selection tab shows the entity.
- Edge: entry without year/entity degrades gracefully (no crash).

## 9. Sequencing (feeds the plan)

1. Types + query hooks.
2. `ChroniclePanel` (list + search).
3. `ChronicleDetail` (entries + stepper) + the `entryYear`/`entryPrimaryEntityId` helpers.
4. Aside tab wrapper + `applyEntry` wiring in `dashboard.tsx`.
5. (Optional) viewer `flyTo` prop + map pan.

## 10. Dependencies & risks

- **Works today** on the existing index/show endpoints using the derived `timestamp`. **Enhanced by sub-project D**: once
  entry/chronicle `start_year`/`end_year`/`impact_score`/`approximate_location` are serialized (and the index supports a
  year filter), `entryYear` uses the explicit field, the list can filter to "chronicles active in year N", and entries can
  fly to `approximate_location`. Adopt those when D lands; do not block on it.
- **Aside width (22rem)** is tight for a list + entries; tabs keep it usable. If it feels cramped, a collapsible left rail
  (Approach A variant) is a small change — flag on review.
- **Map refetch coupling:** entry-stepping that changes the year inherits the dashboard's map fetch cost — the map-query
  optimization (sub-project A) and debounce make this cheap; until then, stepping across many distinct years is as
  expensive as typing those years.

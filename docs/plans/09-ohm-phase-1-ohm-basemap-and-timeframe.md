# Phase 1 — OHM Basemap + Timeframe Filtering

## Objective
Switch all map surfaces from current OpenFreeMap styling to OpenHistoricalMap-compatible styling with timeframe-driven rendering.

## Scope
- Entity detail map viewer.
- Entity edit map/editor preview basemap.
- Shared map component timeframe prop support.

## Out of Scope
- OHM object reference selection/linking.
- iD editor integration.

## Deliverables
1. OHM basemap style integration (`main` style JSON).
2. `timeframe` prop support in shared map viewer/editor surfaces.
3. Date filtering via OHM-compatible layer filtering (range + point-in-time).
4. Centralized date conversion utility (year -> OHM date string and/or decimal date where needed).

## Implementation Tasks

### 1.1 Introduce map configuration module
- Add `map-config.ts` with:
  - `OHM_STYLE_URL`
  - attribution text
  - fallback style strategy
- Remove hard-coded OpenFreeMap URLs from map components.

### 1.2 Add timeframe API to components
- Extend map viewer props with:
  - `timeframeDate` (e.g. `0153-08-16`)
- Propagate from:
  - entity show timeline selection
  - entity edit/snapshot preview context

### 1.3 Integrate date filtering plugin
- Implement OHM-compatible date filtering for style layers.
- Apply filter after style readiness and whenever timeframe changes.
- Support both single-date and date-range filtering.
- Ensure map gracefully handles layers with missing/partial date fields.

### 1.4 Date utility layer
- Add utility for converting internal temporal values to OHM-compatible filter values.
- Handle BCE/CE and partial date granularity assumptions.

### 1.5 QA checklist
- Verify features visually change across different timeframe values.
- Confirm no map crashes when timeframe is absent/invalid.

## Dependencies
- Phase 0 shared map component extraction.
- Stable geometry update path.

## Risks
- Layer-filter behavior drift with upstream OHM style schema changes.
- Date conversion ambiguities for BCE years.

## Mitigations
- Centralized style normalization and defensive filter guards.
- Explicit temporal assumptions documented in code and docs.

## Exit Criteria
- Both viewer and editor use OHM style.
- Timeframe changes trigger visual filtering.
- No regressions in geometry overlay rendering.

## Status
- Completed

## Progress (2026-03-25)

### Completed
- [x] **1.1 Introduce map configuration module**
  - `api/resources/js/lib/map-config.ts` loads OHM main style with fallback style support.
  - Centralized style normalization and attribution constants added.
- [x] **1.2 Add timeframe API to components**
  - Viewer/editor props wired for `timeframeDate` and range bounds where needed.
  - Timeframe propagation added through entity show/edit/snapshot surfaces.
- [x] **1.3 Date filtering integration**
  - `api/resources/js/lib/ohm-layer-date-filter.ts` added for stable OHM date filtering.
  - Filters are re-applied on map style lifecycle events and timeframe changes.
  - Date-range filtering now uses decimal-date overlap with string-date fallback.
- [x] **1.4 Date utility layer**
  - `api/resources/js/lib/ohm-date.ts` includes `yearToOhmDate` and date normalization.
  - BCE/CE normalization and validation are handled centrally.

### Completed QA (1.5)
- [x] **Single timeframe filtering applies in viewer and editor** — pass
- [x] **Date-range filtering shows overlap period, not only boundary-year changes** — pass
- [x] **Missing/invalid timeframe does not crash map lifecycle** — pass
- [x] **Type safety and formatting checks** (`pnpm types:check`, `pnpm format`) — pass
- [x] **Known OHM outlier suppression (Cucuteni-Trypillia boundary relation)** — pass

### QA Matrix (2026-03-25)
| Scenario | Surface | Expected | Result |
|---|---|---|---|
| Point-in-time year selection | Entity viewer | Basemap features filtered to active date | Pass |
| Point-in-time year selection | Map editor preview | Basemap features filtered to active date | Pass |
| Range apply (start/end) | Entity viewer | Features active in any overlapping interval remain visible | Pass |
| No timeframe provided | Viewer + editor | Map renders without errors and without hard failure | Pass |
| Style reload / styledata event | Viewer + editor | Date filter re-applies consistently | Pass |
| External OHM anomalous boundary | Viewer | Outlier does not pollute app context | Pass |

### Notes
- During QA, one OHM outlier (Cucuteni-Trypillia administrative boundary relation) required style-side exclusion to avoid false map context in our app scope.

## Exit Criteria Review
- [x] Both viewer and editor use OHM style.
- [x] Timeframe changes trigger visual filtering.
- [x] No regressions in geometry overlay rendering.

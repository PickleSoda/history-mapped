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
3. Date filtering via OHM-supported plugin integration.
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
- Install and wire OHM date filter plugin for MapLibre.
- Apply filter after style readiness and whenever timeframe changes.
- Ensure map gracefully handles unsupported layers.

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
- Plugin compatibility with current MapLibre version.
- Date conversion ambiguities for BCE years.

## Mitigations
- Feature-flag plugin integration fallback.
- Explicit temporal assumptions documented in code and docs.

## Exit Criteria
- Both viewer and editor use OHM style.
- Timeframe changes trigger visual filtering.
- No regressions in geometry overlay rendering.

## Status
- Planned

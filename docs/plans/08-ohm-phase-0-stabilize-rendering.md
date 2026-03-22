# Phase 0 — Stabilize Geometry Rendering Pipeline

## Objective
Ensure geometry and territory data reliably render immediately after load/save in all relevant admin surfaces.

## Scope
- Entity detail map rendering (`show` page).
- Entity edit map preview and snapshot map preview.
- Snapshot selection behavior and map overlay updates.

## Out of Scope
- OHM basemap/date filtering migration.
- OHM reference linking and contribution workflows.

## Current Problem Statement
- Users report "map has no data" and "saved features are not rendered".
- Rendering currently depends on mixed component-level state and ad-hoc geometry normalization.
- Debug visibility into source/layer/data update failures is limited.

## Deliverables
1. Shared map-viewer core component for read-only rendering.
2. Unified geometry normalization utility reused by viewer + history panel.
3. Deterministic map source update lifecycle (`map loaded` -> `sources ready` -> `data pushed`).
4. Render diagnostics (feature counts and state transitions in dev logs).
5. Focused tests for geometry payload shapes (`Geometry`, `Feature`, `FeatureCollection`, `GeometryCollection`).

## Implementation Tasks

### 0.1 Extract shared viewer foundation
- Create `HistoricalMapViewer` component with props:
  - `baseGeometry`
  - `overlayGeometry`
  - `fitBoundsMode` (`none | base | all`)
  - `onRenderStateChange` (optional)
- Move map source/layer creation out of timeline component.

### 0.2 Consolidate normalization
- Introduce utility module for flattening GeoJSON into renderable features.
- Handle mixed input formats:
  - raw geometry objects
  - single feature
  - feature collections
  - geometry collections
- Guarantee output is always `FeatureCollection`.

### 0.3 Harden data update flow
- Guard against updates before style/source readiness.
- Make update path idempotent when switching snapshots quickly.
- Ensure post-save state updates force viewer refresh from latest payload.

### 0.4 Add diagnostics
- In development mode, log:
  - input payload types
  - normalized feature counts
  - source update success/failure
- Add fallback empty-state message only when features are truly empty.

### 0.5 Validation and tests
- Add unit tests for geometry normalization utility.
- Add integration-level frontend test coverage where feasible.
- Verify existing snapshot API tests remain green.

## Dependencies
- Existing snapshot API payload contract.
- Existing timeline fetch behavior in entity detail page.

## Risks
- Hidden mismatches between server resource fields and frontend expectations.
- Race conditions around map style load and source updates.

## Mitigations
- Strict TypeScript types for geometry props.
- Single source of truth for normalization logic.
- Structured render-state logging in dev.

## Exit Criteria
- Saved snapshot geometry appears without page hard refresh.
- Point/line/polygon features all render reliably.
- Snapshot toggling updates map consistently.
- No regressions in existing geometry snapshot feature tests.

## Status
- In progress

## Progress Notes
- Shared read-only viewer extraction completed.
- GeoJSON normalization utility extracted and reused.
- Shared map style/config loading introduced for editor + viewer alignment.
- Preview initial-load rendering race fixed in shared viewer:
  - Removed brittle `isStyleLoaded()` gate from data-application path.
  - Added source-readiness application with `idle` fallback retry.
  - Added resize hardening to reduce first-paint blank states.
- Validation updates:
  - User confirmed preview now renders on initial load.
  - `GeometrySnapshotControllerTest` focused suite passes (25 tests).
  - Type diagnostics for map viewer/editor/edit/snapshot files are clean.

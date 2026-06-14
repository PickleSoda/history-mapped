# Phase 2 — Timeline-to-Map Interaction (Snapshots + Relationships)

> **Status: 🟡 Partial** — verified 2026-06-15; remaining work tracked in [STATUS.md](STATUS.md).

## Objective
Implement the target UX: map on the left, timeline on the right; clicking snapshots or relationships applies corresponding geometry context to the map.

## Scope
- Entity detail page timeline and map composition.
- Interaction model for timeline item selection and map updates.
- Relationship selection behavior and geometry application path.

## Out of Scope
- OHM external reference storage model.
- OHM iD editing and upload pipeline.

## Deliverables
1. Refactored `EntityHistoryPanel` composition (map left, timeline right).
2. Unified selected-item state (`snapshot | relationship`).
3. Relationship geometry retrieval strategy implemented.
4. Interaction and selection visual states.

## Data Contract Changes
- Extend relationship response to include map-applicable geometry context, either:
  - embedded related-entity geometry, or
  - lightweight reference requiring on-click fetch.

## Implementation Tasks

### 2.1 Refactor UI composition
- Split into:
  - `EntityHistoryTimeline`
  - `HistoricalMapViewer` usage container
- Preserve existing loading/error/empty states.

### 2.2 Selection state machine
- Implement selected item model:
  - `none`
  - `snapshot:<id>`
  - `relationship:<id>`
- Snapshot click:
  - apply snapshot geometry overlays
- Relationship click:
  - apply related entity geometry overlays (with direction context)

### 2.3 Backend/API extension for relationship mapping
- Update relationship endpoints/resources to provide geometry linkage.
- Add optional query flag for geometry payload enrichment if needed.

### 2.4 Map overlay semantics
- Base entity: persistent reference layer.
- Selected item: highlighted overlay layer.
- Relationship mode: include source/target visual distinction.

### 2.5 Validation
- Feature tests for relationship payload enrichment.
- Frontend interaction tests for click-to-apply behavior.

## Dependencies
- Phase 0 and Phase 1 complete.
- Relationship controller/resource updates.

## Risks
- Payload bloat if relationship geometry is fully embedded for all rows.
- UX confusion if relationship direction isn’t clearly represented.

## Mitigations
- Add lightweight mode + on-demand fetch option.
- Explicit labels and badge indicators for direction and applied layer.

## Exit Criteria
- Timeline is right-side, map is left-side.
- Clicking snapshot updates map immediately.
- Clicking relationship updates map immediately.
- Applied state is visible and reversible.

## Status
- In progress

## Progress (2026-03-25)

### Completed
- [x] **2.2 Selection state machine (core)**
  - Unified selected timeline item state (`snapshot | relationship | none`) implemented in `EntityHistoryPanel`.
  - Clicking a snapshot applies snapshot geometry overlays.
  - Clicking a relationship applies related-entity geometry overlays.
  - Clicking an already-selected item clears selection (reversible applied state).
- [x] **2.3 Backend/API extension for relationship mapping (lightweight embedded mode)**
  - `RelationshipController` now includes `related_entity.geojson` and `related_entity.territory_geojson` in list/store payloads.
  - Frontend relationship type updated to consume optional geometry payload fields.
- [x] **2.5 Validation (backend slice)**
  - Added feature coverage: relationship index returns related entity geometry payload.
  - `tests/Feature/Admin/RelationshipControllerTest.php` passing.

### In Progress
- [ ] **2.1 Refactor UI composition**
  - Existing layout already renders map left / timeline right; extraction into a dedicated timeline subcomponent is still pending.
- [ ] **2.4 Map overlay semantics**
  - Base + selected overlay behavior is active.
  - Source/target visual distinction for relationship mode still pending.
- [ ] **2.5 Validation (frontend slice)**
  - Frontend interaction tests for click-to-apply behavior still pending.

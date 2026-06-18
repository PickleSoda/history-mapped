# Phase 4 — Integrate OpenHistoricalMap iD Editor Surface

> **Status: ⬜ Not started** — as of 2026-06-15. See [STATUS.md](STATUS.md).

## Objective
Provide a comprehensive OHM-native editing experience by integrating `@openhistoricalmap/id` as a dedicated editing surface while preserving app-level workflow control.

## Scope
- Dedicated OHM iD integration surface (route/component).
- Session/context handoff between app and iD.
- Feature selection/export bridge back into app.

## Out of Scope
- Fully automated direct publishing to OHM in this phase.

## Key Finding
`@openhistoricalmap/id` is packaged primarily as a full editor application bundle, not a small composable React widget. Integration should be treated as embedded surface/micro-frontend behavior.

## Deliverables
1. New "Edit in OHM" workflow entry from entity/snapshot editors.
2. Hosted/embedded iD surface with map/date/context prefill.
3. Communication bridge for selected OHM objects and geometry extraction.
4. Fallback path to internal lightweight editor.

## Implementation Tasks

### 4.1 Integration architecture decision
- Choose one:
  - iframe integration against controlled iD deployment URL
  - internal hosted static iD app route
- Document tradeoffs (security, maintenance, upgrade cadence).

### 4.2 Context handoff contract
- Pass map center/zoom/date/presets through URL hash params.
- Include entity/snapshot context identifiers for round-trip mapping.

### 4.3 Bridge protocol
- Define `postMessage` schema:
  - `ready`
  - `selectionChanged`
  - `exportGeometry`
  - `error`
- Add origin validation and message versioning.

### 4.4 UX and fallback
- Add explicit "Open in OHM iD" CTA.
- Preserve current internal editor as fallback when bridge unavailable.

### 4.5 Operational readiness
- Pin tested iD version.
- Add integration smoke tests and error telemetry.

## Dependencies
- Phase 3 OHM reference model for storing chosen IDs.

## Risks
- iD app internals may change between versions.
- Cross-window security and compatibility concerns.

## Mitigations
- Stable wrapper contract and strict version pinning.
- Feature flag rollout.

## Exit Criteria
- Users can open OHM iD with relevant context from entity/snapshot workflow.
- Selected OHM objects can be captured and persisted back in app.
- Fallback path remains functional.

## Status
- Planned

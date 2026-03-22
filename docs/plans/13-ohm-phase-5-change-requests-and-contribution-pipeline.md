# Phase 5 — OHM Change Requests + Contribution Pipeline

## Objective
Enable users to draft, review, and eventually submit change requests to OpenHistoricalMap from within the application with traceability and governance.

## Scope
- Internal change request queue.
- Validation/review workflow.
- Export/adaptation to OHM-compatible change formats.
- Foundation for future direct OHM API submission.

## Out of Scope
- Fully unattended auto-publishing to OHM.

## Deliverables
1. Change request domain model and queue UI.
2. Review/approval workflow with audit trail.
3. Export pipeline to OHM-compatible payloads (`osmChange` / OSM XML as needed).
4. Submission adapter abstraction for future direct API integration.

## Proposed Workflow
1. User proposes geometry/tag update from entity/snapshot context.
2. System creates `change_request` item with source references and diffs.
3. Reviewer validates temporal/source/licensing criteria.
4. Approved requests enter export/submission queue.
5. Submission result linked back to local entities and OHM object IDs.

## Implementation Tasks

### 5.1 Data model
- `change_requests`
- `change_request_items`
- `change_request_reviews`
- statuses: `draft -> pending_review -> approved -> queued -> submitted -> failed`.

### 5.2 Queue and processing
- Queue jobs for transformation/validation/submission.
- Retry/backoff and dead-letter handling.

### 5.3 Validation rules
- Temporal completeness checks.
- Source/citation completeness checks.
- License/attribution checks aligned with OHM guidance.

### 5.4 Export/submission adapters
- Adapter interface:
  - `toOsmXml()`
  - `toOsmChange()`
  - `submit()` (future)
- Keep adapter implementation isolated for future OHM auth flows.

### 5.5 Review UI
- Dedicated admin queue view with:
  - diff preview
  - geometry preview on map
  - approve/reject/comment actions

## Dependencies
- Phase 3 reference model.
- Phase 4 editor integration bridge.

## Risks
- OHM API auth/submission constraints may evolve.
- Data quality/legal requirements for external publishing.

## Mitigations
- Keep submission optional and gated.
- Start with export-only mode before enabling direct submission.

## Exit Criteria
- Change requests can be created, reviewed, and queued.
- System can export approved requests in OHM-compatible format.
- Submission adapter boundary is production-ready for later activation.

## Status
- Planned

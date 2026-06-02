# Standalone Relationship Resolution and Reporting Design

> **Date:** 2026-06-02
> **Status:** Approved
> **Related plans:** `2026-04-08-event-relationship-pipeline-stabilization.md`

## Problem

`ResolveRelationshipsJob` currently marks ALL hints as `resolved=true` — including `target_not_found`. Once a target entity is missing, the hint becomes terminal and can never be retried even if the target entity is imported later. This forces operators to either:
- run relationship resolution inline during import (which fails for async batches)
- manually delete and re-stage hints
- lose relationship edges silently

Additionally, there is no CLI visibility into how many hints are stuck, why they are stuck, or which target entities are missing.

## Goal

1. Make `target_not_found` retryable so operators can re-run resolution after importing missing target entities.
2. Add a standalone `pipeline:resolve-relationships` command that resolves hints for a specific batch or all unresolved hints.
3. Add a `pipeline:report-relationship-hints` command that audits hint state and surfaces actionable summary counts.

## Non-Goals

- No new database tables or schema migrations.
- No change to the `relationships` table or relationship creation logic.
- No change to the pipeline Python code.
- No full audit trail or retry counter per hint.

## Architecture

### Retryability Fix

Change `ResolveRelationshipsJob::markHint()` so only terminal outcomes set `resolved=true`:

| Outcome | `resolved` | `resolution_note` | Retryable? |
|---------|-----------|-------------------|------------|
| `created` | `true` | `created` | No |
| `already_exists` | `true` | `already_exists` | No |
| `unknown_type` | `true` | `unknown_type` | No |
| `self_reference` | `true` | `self_reference` | No |
| `target_not_found` | `false` | `target_not_found` | **Yes** |

This requires updating the existing `ResolveRelationshipsJobTest` expectations for `target_not_found` from `resolved=true` to `resolved=false`.

### Command: `pipeline:resolve-relationships`

Signature:
```text
pipeline:resolve-relationships
  {batchId? : Resolve hints for this batch; omit to resolve all unresolved hints}
  {--sync : Run synchronously instead of dispatching a job}
  {--dry-run : Show counts without creating relationships}
```

Behavior:
- If `batchId` is provided: dispatch `ResolveRelationshipsJob($batchId)`
- If `batchId` is omitted: collect all distinct `batch_id` values where `resolved=false`, then dispatch one job per batch
- `--dry-run`: query counts per batch and resolution class, print table, exit without touching relationships
- `--sync`: call `handle()` directly instead of dispatching

Output:
```
Resolving relationships for 3 batches...
  Batch: pipeline-20260530-120000  → 12 created, 3 target_not_found (retryable)
  Batch: border-relations-20260531  →  5 created, 1 target_not_found (retryable)
  Batch: egypt-patch-20260531       →  0 created, 7 target_not_found (retryable)
Done. 17 created, 11 retryable.
```

### Command: `pipeline:report-relationship-hints`

Signature:
```text
pipeline:report-relationship-hints
  {batchId? : Report for this batch only; omit for all batches}
  {--limit=10 : Sample size per class}
```

Behavior:
- Print summary table: batch, total hints, created, already_exists, unknown_type, self_reference, target_not_found (retryable)
- Print sample rows for each retryable class (`target_not_found`)
- Print sample entities whose `attributes` JSONB still contains `_relationship_hints` (embedded-hint fallback path)

Output:
```
┌──────────────────────────┬───────┬─────────┬──────────────┬─────────────┬───────────────┬──────────────────┐
│ Batch                    │ Total │ Created │ Already Exists│ Unknown Type│ Self Reference│ Target Not Found │
├──────────────────────────┼───────┼─────────┼──────────────┼─────────────┼───────────────┼──────────────────┤
│ pipeline-20260530-120000 │    15 │      12 │            0 │           0 │             0 │                3 │
│ border-relations-20260531│     6 │       5 │            0 │           0 │             0 │                1 │
│ egypt-patch-20260531     │     7 │       0 │            0 │           0 │             0 │                7 │
└──────────────────────────┴───────┴─────────┴──────────────┴─────────────┴───────────────┴──────────────────┘

Retryable samples (target_not_found):
  - Q9999 (source: Roman Empire) → type: part_of
  - Q8888 (source: Battle of Gaugamela) → type: fought_at

Embedded hints still in attributes:
  - Entity: Q2277 (Roman Empire) → 2 hints
```

## Data Flow

```
ImportEntitiesCommand --skip-relationships
    → entities imported, hints staged as resolved=false

pipeline:resolve-relationships
    → ResolveRelationshipsJob($batchId) or ResolveRelationshipsJob per batch
    → relationships created for found targets
    → target_not_found hints remain resolved=false

pipeline:report-relationship-hints
    → read-only audit of staging table + embedded hints

(repeat after importing missing targets)
pipeline:resolve-relationships
    → previously target_not_found hints may now resolve
```

## Error Handling

- Missing `pipeline_relationship_hints` table → fall back to embedded-hint path (existing behavior in the job)
- Empty batch → print "No unresolved hints found" and exit 0
- Invalid `batchId` → warn and skip (do not fail the whole run when resolving all batches)
- `--dry-run` must never write to the database

## Testing Strategy

1. **Unit tests for retryability**
   - `target_not_found` leaves `resolved=false`
   - Re-running the job after the target entity exists creates the relationship
   - Duplicate reruns remain idempotent

2. **Feature tests for `ResolvePipelineRelationshipsCommand`**
   - Resolves one batch when `batchId` is provided
   - Resolves all unresolved hints when `batchId` is omitted
   - `--dry-run` prints counts without creating relationships
   - `--sync` runs inline
   - Safe to rerun (idempotent)

3. **Feature tests for `ReportPipelineRelationshipHintsCommand`**
   - Reports counts by batch and resolution class
   - Prints sample retryable rows
   - Prints embedded-hint audit
   - Safe to run on empty table

4. **End-to-end test: `PipelineEventHubImportTest`**
   - Seed JSONL records for a battle, two armies, two commanders, and one place
   - Import into one batch with `--skip-relationships`
   - Run `pipeline:resolve-relationships`
   - Assert the final graph contains expected event-centered edges
   - Assert no relationship was lost because a target entity arrived later in the batch

## Components

- `api/app/Console/Commands/ResolvePipelineRelationshipsCommand.php`
- `api/app/Console/Commands/ReportPipelineRelationshipHintsCommand.php`
- `api/app/Jobs/ResolveRelationshipsJob.php` (modify `markHint` + add `resolveAll()`)
- `api/tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php`
- `api/tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php`
- `api/tests/Feature/Feature/PipelineEventHubImportTest.php`

## Migration and Relationship to Existing Plan

This design implements the missing pieces from `2026-04-08-event-relationship-pipeline-stabilization.md`:
- Task 2 steps 6-11 (standalone resolution command)
- Task 4 (reporting command)
- Task 6 (end-to-end verification test)

The existing `ResolveRelationshipsJobTest` coverage remains valid after updating the `target_not_found` assertion.

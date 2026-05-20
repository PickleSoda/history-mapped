# Laravel Implementation Status — Entity Model

This document reflects the current Laravel status of the canonical entity model rather than the original cutover checklist.

Related spec:
- [schema-proposal-strict-write-derived-timeline.md](./schema-proposal-strict-write-derived-timeline.md)

Related plan:
- [2026-04-06-entity-model-migration.md](../superpowers/plans/2026-04-06-entity-model-migration.md)

---

## Completed

- [x] Canonical normalized tables are live: `entity_aliases`, `entity_tags`, `entity_temporal_ranges`, `entity_locations`, `geometry_periods`, and `entity_timeline_entries`.
- [x] Legacy entity temporal/location/geometry columns are removed.
- [x] `geometry_snapshots` storage and public/admin compatibility endpoints are removed.
- [x] `Entity` exposes canonical relations for aliases, tags, temporal ranges, locations, geometry periods, and timeline entries.
- [x] Backfill and timeline rebuild commands exist for canonical data maintenance.
- [x] Timeline projection reads from `geometry_periods`, relationships, and temporal-range fallback.
- [x] Focused tests cover schema constraints, relations, backfill behavior, timeline rebuild behavior, and removed legacy snapshot endpoints.

## Remaining Work

- [ ] Normalize citations into dedicated citation tables. Current live model still uses `source_citations` JSONB.
- [ ] Harden `geometry_periods` lifecycle rules for overlapping periods, provenance completeness, and broader pipeline consistency.
- [ ] Continue pruning leftover legacy naming in historical notes and logs when it creates confusion, without changing the underlying historical record.

## Notes

- No entity-model rollout flags remain in live app config.
- The canonical write path is unconditional.
- Historical migration notes remain useful as implementation history, but this file is the current status summary.

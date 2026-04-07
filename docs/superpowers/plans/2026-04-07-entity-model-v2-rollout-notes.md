# Entity Model V2 Rollout Notes

Date: 2026-04-08

## Required Backfill Order

1. Run core v2 backfill to confirm canonical table idempotency.
2. Run timeline rebuild (`timeline:rebuild`) so `entity_timeline_entries` reflect geometry periods and temporal fallback.
3. Re-run targeted integrity checks for geo refs and timeline counts.
4. Confirm no legacy-table/column references remain in app and test paths.

Suggested command order:

```bash
docker compose -f docker/docker-compose.yml exec app php artisan entity-model-v2:backfill
docker compose -f docker/docker-compose.yml exec app php artisan timeline:rebuild
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/BackfillEntityModelV2CommandTest.php tests/Feature/Feature/RebuildEntityTimelineCommandTest.php tests/Feature/Feature/EntityGeoRefIntegrityTest.php
```

## Safe Rollback Point

Safe rollback point is immediately before applying migration `2026_04_08_000002_drop_legacy_entity_fields_and_snapshot_table`.

Rollback procedure:

1. Restore DB from backup or run migration rollback to re-add legacy columns.
2. Re-run `timeline:rebuild` for consistency if period writes were made while transitioning.

## Compatibility Flags Used

- `ENTITY_MODEL_V2_WRITE_ENABLED`: retained for rollout safety but write paths are now v2-only.
- `GEOMETRY_SNAPSHOT_COMPAT_READ_ENABLED`: no longer used; geometry snapshot compatibility surface has been removed.

## Data Audit Queries (Manual Geometry Periods)

Find manual geometry periods by entity and year range:

## Legacy Erasure Inventory

- See `docs/superpowers/plans/2026-04-07-legacy-erasure-inventory.md` for the full Task 10 Step 1 usage inventory and removal ordering.

```sql
SELECT entity_id, period_type, start_year, end_year, provenance_mode, relationship_id, source_event_id
FROM geometry_periods
WHERE provenance_mode = 'manual'
ORDER BY entity_id, start_year, end_year;
```

Find invalid manual presence rows (should be zero):

```sql
SELECT geometry_period_id, entity_id, period_type, provenance_mode, relationship_id
FROM geometry_periods
WHERE provenance_mode = 'manual' AND period_type = 'presence';
```

Find entities with no timeline entries despite having periods:

```sql
SELECT gp.entity_id, COUNT(*) AS period_count
FROM geometry_periods gp
LEFT JOIN entity_timeline_entries ete ON ete.entity_id = gp.entity_id
GROUP BY gp.entity_id
HAVING COUNT(ete.timeline_entry_id) = 0;
```

Find orphan geometry-period scoped geo refs that should be pruned:

```sql
SELECT geo_ref_id, entity_id, external_id, source_meta, is_active
FROM entity_geo_refs
WHERE COALESCE(source_meta->>'origin', '') = 'geometry_period'
  AND is_active = false;
```

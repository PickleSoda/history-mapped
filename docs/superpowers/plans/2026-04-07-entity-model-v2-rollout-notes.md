# Entity Model V2 Rollout Notes

Date: 2026-04-07

## Required Backfill Order

1. Run core v2 backfill to seed normalized tables from legacy entity fields.
2. Run timeline rebuild (`timeline:rebuild`) so `entity_timeline_entries` reflect geometry periods and temporal fallback.
3. Re-run targeted integrity checks for geo refs and timeline counts.
4. Keep compatibility endpoints enabled until client consumers are migrated.

Suggested command order:

```bash
docker compose -f docker/docker-compose.yml exec app php artisan entity-model-v2:backfill
docker compose -f docker/docker-compose.yml exec app php artisan timeline:rebuild
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/BackfillEntityModelV2CommandTest.php tests/Feature/Feature/RebuildEntityTimelineCommandTest.php tests/Feature/Feature/EntityGeoRefIntegrityTest.php
```

## Safe Rollback Point

Safe rollback point is immediately before enabling `ENTITY_MODEL_V2_WRITE_ENABLED=true` in production.

Rollback procedure:

1. Set `ENTITY_MODEL_V2_WRITE_ENABLED=false`.
2. Keep `GEOMETRY_SNAPSHOT_COMPAT_READ_ENABLED=true`.
3. Re-run `timeline:rebuild` for consistency if period writes were made while transitioning.

## Compatibility Flags Used

  - `false`: legacy entity temporal/location writes still active.
  - `true`: legacy entity temporal/location writes disabled; legacy geometry-snapshot write endpoints return HTTP 410.

  - `true`: compatibility read endpoints remain available during migration.
  - `false`: disable compatibility read path after all clients switch to v2/timeline reads.

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

-- Shrinks a TEMPLATE copy of the full benchmark database to :n entities: all
-- 36,266 curated entities plus the first (n - 36,266) bulk entities in md5
-- order, so every smaller set is contained in every larger one. Foreign-key
-- triggers are off (session_replication_role) and each dependent table is
-- cleaned with one set-based statement instead (per-row cascades from 600k
-- relationships took over 12 minutes). See docs/architecture/scalability.md.
\set ON_ERROR_STOP 1
\timing on
-- Hash the 600k-id sets instead of rescanning them per row.
SET work_mem = '512MB';

CREATE TEMP TABLE keep AS
  SELECT entity_id FROM entities WHERE NOT (attributes ? '_bulk')
  UNION ALL
  (SELECT entity_id FROM entities WHERE attributes ? '_bulk' ORDER BY md5(entity_id::text) LIMIT greatest(:n - 36266, 0));
CREATE UNIQUE INDEX ON keep (entity_id);
CREATE TEMP TABLE gone AS SELECT entity_id FROM entities e WHERE NOT EXISTS (SELECT 1 FROM keep k WHERE k.entity_id = e.entity_id);
CREATE UNIQUE INDEX ON gone (entity_id);
ANALYZE keep; ANALYZE gone;

CREATE TEMP TABLE grel AS
  SELECT r.relationship_id FROM relationships r JOIN gone g ON g.entity_id = r.source_entity_id
  UNION
  SELECT r.relationship_id FROM relationships r JOIN gone g ON g.entity_id = r.target_entity_id;
CREATE UNIQUE INDEX ON grel (relationship_id);
CREATE TEMP TABLE gper AS
  SELECT p.geometry_period_id FROM geometry_periods p JOIN gone g ON g.entity_id = p.entity_id
  UNION
  SELECT p.geometry_period_id FROM geometry_periods p JOIN grel r ON r.relationship_id = p.relationship_id;
CREATE UNIQUE INDEX ON gper (geometry_period_id);
CREATE TEMP TABLE gref AS
  SELECT x.geo_ref_id FROM entity_geo_refs x JOIN gone g ON g.entity_id = x.entity_id
  UNION
  SELECT x.geo_ref_id FROM entity_geo_refs x JOIN gper p ON p.geometry_period_id = x.geometry_period_id;
ANALYZE grel; ANALYZE gper; ANALYZE gref;

SET session_replication_role = replica;
UPDATE entities SET primary_geo_ref_id = NULL WHERE primary_geo_ref_id IN (SELECT geo_ref_id FROM gref);
DELETE FROM entity_geo_refs WHERE geo_ref_id IN (SELECT geo_ref_id FROM gref);
UPDATE chronicle_entries SET primary_relationship_id = NULL WHERE primary_relationship_id IN (SELECT relationship_id FROM grel);
DELETE FROM geometry_periods WHERE geometry_period_id IN (SELECT geometry_period_id FROM gper);
UPDATE geometry_periods SET source_event_id = NULL WHERE source_event_id IN (SELECT entity_id FROM gone);
DELETE FROM relationships WHERE relationship_id IN (SELECT relationship_id FROM grel);
DELETE FROM pipeline_relationship_hints WHERE source_entity_id IN (SELECT entity_id FROM gone);
DELETE FROM entity_timeline_entries WHERE entity_id IN (SELECT entity_id FROM gone);
UPDATE entity_timeline_entries SET location_entity_id = NULL WHERE location_entity_id IN (SELECT entity_id FROM gone);
UPDATE entity_timeline_entries SET related_entity_id = NULL WHERE related_entity_id IN (SELECT entity_id FROM gone);
DELETE FROM entity_aliases WHERE entity_id IN (SELECT entity_id FROM gone);
DELETE FROM entity_tags WHERE entity_id IN (SELECT entity_id FROM gone);
DELETE FROM entity_temporal_ranges WHERE entity_id IN (SELECT entity_id FROM gone);
DELETE FROM entity_locations WHERE entity_id IN (SELECT entity_id FROM gone);
DELETE FROM chronicle_entry_entities WHERE entity_id IN (SELECT entity_id FROM gone);
DELETE FROM map_stories WHERE entity_id IN (SELECT entity_id FROM gone);
DELETE FROM entities WHERE entity_id IN (SELECT entity_id FROM gone);
SET session_replication_role = origin;

SELECT count(*) AS entities FROM entities;
-- Compaction (VACUUM FULL), the tile-table refresh and ANALYZE run afterwards,
-- one database at a time: a concurrent long transaction elsewhere in the
-- cluster keeps VACUUM FULL from dropping the deleted rows.

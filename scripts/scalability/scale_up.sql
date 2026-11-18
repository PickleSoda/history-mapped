-- Doubles a benchmark database: one synthetic copy of every entity with its
-- aliases, location, dates, tags, map periods, relationships and timeline
-- entries (not OHM refs, hints or chronicle links). Copies keep names, types,
-- importance and dates; points move by up to ±0.5° so they do not stack on
-- their originals. Run on a TEMPLATE copy; run twice for 4x.
-- See docs/architecture/scalability.md.
\set ON_ERROR_STOP 1
\timing on

CREATE TEMP TABLE m AS
SELECT entity_id AS old, gen_random_uuid() AS new,
       (('x' || substr(md5(entity_id::text), 1, 8))::bit(32)::int)::float8 / 4294967296.0 AS dx,
       (('x' || substr(md5(entity_id::text), 9, 8))::bit(32)::int)::float8 / 4294967296.0 AS dy
FROM entities;
CREATE UNIQUE INDEX ON m (old);
ANALYZE m;

CREATE TEMP TABLE rm AS SELECT relationship_id AS old, gen_random_uuid() AS new FROM relationships;
CREATE UNIQUE INDEX ON rm (old);
ANALYZE rm;

-- Point jitter (dx, dy in [-0.5, 0.5)), clamped to the valid range.
CREATE OR REPLACE FUNCTION pg_temp.jitter(g geometry, dx float8, dy float8) RETURNS geometry
LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE
    WHEN g IS NULL THEN NULL
    WHEN GeometryType(g) = 'POINT' THEN ST_SetSRID(ST_MakePoint(
      least(179.999, greatest(-179.999, ST_X(g) + dx)),
      least(89.999, greatest(-89.999, ST_Y(g) + dy))), ST_SRID(g))
    ELSE g
  END
$$;

INSERT INTO entities (entity_id, name, wikidata_id, summary, significance, impact_score, attributes, reviewer_id,
  review_date, source_citations, embedding, display_priority, created_by, created_at, updated_at, entity_type,
  entity_group, location_confidence, location_method, date_method, date_confidence, duration_type,
  verification_status, confidence, icon_class, primary_geo_ref_id, description)
SELECT m.new, e.name, e.wikidata_id, e.summary, e.significance, e.impact_score, e.attributes || '{"_synthetic": true}',
  e.reviewer_id, e.review_date, e.source_citations, e.embedding, e.display_priority, 'scalability-copy', e.created_at,
  e.updated_at, e.entity_type, e.entity_group, e.location_confidence, e.location_method, e.date_method,
  e.date_confidence, e.duration_type, e.verification_status, e.confidence, e.icon_class, NULL, e.description
FROM entities e JOIN m ON m.old = e.entity_id;

INSERT INTO entity_aliases (alias_id, entity_id, name, language, source, is_primary, created_at, updated_at)
SELECT gen_random_uuid(), m.new, a.name, a.language, a.source, a.is_primary, a.created_at, a.updated_at
FROM entity_aliases a JOIN m ON m.old = a.entity_id;

INSERT INTO entity_locations (location_id, entity_id, location_name, geom, territory_geom, location_method,
  location_confidence, is_primary, notes, created_at, updated_at)
SELECT gen_random_uuid(), m.new, l.location_name, pg_temp.jitter(l.geom, m.dx, m.dy), l.territory_geom,
  l.location_method, l.location_confidence, l.is_primary, l.notes, l.created_at, l.updated_at
FROM entity_locations l JOIN m ON m.old = l.entity_id;

INSERT INTO entity_temporal_ranges (temporal_range_id, entity_id, range_type, start_year, end_year, start_date,
  end_date, duration_type, date_method, date_confidence, is_primary, notes, created_at, updated_at)
SELECT gen_random_uuid(), m.new, t.range_type, t.start_year, t.end_year, t.start_date, t.end_date, t.duration_type,
  t.date_method, t.date_confidence, t.is_primary, t.notes, t.created_at, t.updated_at
FROM entity_temporal_ranges t JOIN m ON m.old = t.entity_id;

INSERT INTO entity_tags (entity_tag_id, entity_id, tag, created_at, updated_at, source)
SELECT gen_random_uuid(), m.new, t.tag, t.created_at, t.updated_at, t.source
FROM entity_tags t JOIN m ON m.old = t.entity_id;

INSERT INTO relationships (relationship_id, source_entity_id, target_entity_id, temporal_start, temporal_end,
  description, source_citations, created_at, created_by, start_year, end_year, derive_geometry_period,
  relationship_type, confidence)
SELECT rm.new, ms.new, mt.new, r.temporal_start, r.temporal_end, r.description, r.source_citations, r.created_at,
  'scalability-copy', r.start_year, r.end_year, r.derive_geometry_period, r.relationship_type, r.confidence
FROM relationships r
JOIN rm ON rm.old = r.relationship_id
JOIN m ms ON ms.old = r.source_entity_id
JOIN m mt ON mt.old = r.target_entity_id;

INSERT INTO geometry_periods (geometry_period_id, entity_id, period_type, start_year, end_year, geom, territory_geom,
  description, provenance_mode, relationship_id, source_event_id, created_by, created_at, updated_at, confidence)
SELECT gen_random_uuid(), m.new, g.period_type, g.start_year, g.end_year, pg_temp.jitter(g.geom, m.dx, m.dy),
  g.territory_geom, g.description, g.provenance_mode, rm.new, me.new, 'scalability-copy', g.created_at,
  g.updated_at, g.confidence
FROM geometry_periods g
JOIN m ON m.old = g.entity_id
LEFT JOIN rm ON rm.old = g.relationship_id
LEFT JOIN m me ON me.old = g.source_event_id;

INSERT INTO entity_timeline_entries (timeline_entry_id, entity_id, entry_kind, start_year, end_year, title,
  description, location_entity_id, geom, territory_geom, source_table, source_id, relationship_type,
  related_entity_id, related_entity_name, derived_at, created_at, updated_at)
SELECT gen_random_uuid(), m.new, t.entry_kind, t.start_year, t.end_year, t.title, t.description, ml.new,
  pg_temp.jitter(t.geom, m.dx, m.dy), t.territory_geom, t.source_table, t.source_id, t.relationship_type, mr.new,
  t.related_entity_name, t.derived_at, t.created_at, t.updated_at
FROM entity_timeline_entries t
JOIN m ON m.old = t.entity_id
LEFT JOIN m ml ON ml.old = t.location_entity_id
LEFT JOIN m mr ON mr.old = t.related_entity_id;

REFRESH MATERIALIZED VIEW tiles.atlas_features;
VACUUM ANALYZE;
SELECT count(*) AS entities FROM entities;
SELECT pg_size_pretty(pg_database_size(current_database())) AS size;

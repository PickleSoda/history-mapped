# Entity Attributes — Current Reference

> Status: current live model after the normalized entity-model cutover.
> An entity is no longer a single wide row. The live surface is split across `entities`, normalized companion tables, and a few controller-level helper fields.

---

## 1. Canonical `entities` Columns

These are the current first-class fields on the `entities` table.

| Field | Meaning |
|---|---|
| `entity_id` | UUID primary key |
| `name` | Primary display name |
| `entity_type` | Concrete entity type enum |
| `entity_group` | Top-level group enum |
| `wikidata_id` | Optional linked-data identifier |
| `summary` | Short descriptive summary |
| `significance` | Longer historical significance text |
| `impact_score` | Numeric prioritization / ranking signal |
| `attributes` | JSONB spillover for type-specific fields and a few presentation helpers |
| `verification_status` | Workflow state such as `pipeline_draft`, `needs_review`, `human_verified` |
| `confidence` | Overall confidence enum |
| `date_method` | How the canonical date was resolved |
| `date_confidence` | Confidence in the canonical date |
| `duration_type` | Point / period / ongoing / uncertain |
| `location_method` | How the canonical location was resolved |
| `location_confidence` | Confidence in the canonical location |
| `display_priority` | Display ordering / importance hint |
| `icon_class` | Enum used for iconography |
| `source_citations` | JSONB citation payload still used in the live model |
| `embedding` | pgvector embedding used for semantic search |
| `reviewer_id` | Reviewer foreign key |
| `review_date` | Review timestamp |
| `created_by` | Import or authoring provenance string |
| `primary_geo_ref_id` | Optional canonical external georef pointer |
| `created_at` / `updated_at` | Timestamps |

### What `attributes` is for right now

`attributes` is still part of the live write model. It currently carries:

- type-specific fields that are not worth dedicated columns yet
- some presentation helpers surfaced by the admin controller, including values such as `date_raw`, `temporal_display_range`, `era_label`, `confidence_notes`, and `entity_color`

It should not be treated as the place for canonical aliases, tags, temporal rows, base locations, or time-varying geometries. Those live in dedicated tables.

---

## 2. Canonical Companion Tables

### `entity_aliases`

Canonical storage for alternative names.

| Field | Meaning |
|---|---|
| `alias_id` | UUID primary key |
| `entity_id` | Owning entity |
| `name` | Alias text |
| `language` | Optional language marker |
| `source` | Optional provenance note |
| `is_primary` | Primary alias flag |

### `entity_tags`

Canonical storage for free-form tags.

| Field | Meaning |
|---|---|
| `entity_tag_id` | UUID primary key |
| `entity_id` | Owning entity |
| `tag` | One normalized tag string |

### `entity_temporal_ranges`

Canonical storage for entity date ranges.

| Field | Meaning |
|---|---|
| `temporal_range_id` | UUID primary key |
| `entity_id` | Owning entity |
| `range_type` | `primary`, `secondary`, or `disputed` |
| `start_year` / `end_year` | Normalized integer years |
| `start_date` / `end_date` | ISO-style source strings preserved for display |
| `duration_type` | Duration enum value stored with the range |
| `date_method` | Resolution method for this range |
| `date_confidence` | Confidence for this range |
| `is_primary` | Primary range flag |
| `notes` | Editorial notes |

### `entity_locations`

Canonical storage for base locations and base geometry.

| Field | Meaning |
|---|---|
| `location_id` | UUID primary key |
| `entity_id` | Owning entity |
| `location_name` | Human-readable location label |
| `geom` | Base point or line geometry |
| `territory_geom` | Base polygon / multipolygon geometry |
| `location_method` | Resolution method |
| `location_confidence` | Confidence enum |
| `is_primary` | Primary location flag |
| `notes` | Editorial notes |

### `entity_geo_refs`

Canonical storage for external geospatial matches.

| Field | Meaning |
|---|---|
| `geo_ref_id` | UUID primary key |
| `entity_id` | Owning entity |
| `provider` | `ohm`, `wikidata`, `geonames`, `pleiades`, or `custom` |
| `external_type` | `node`, `way`, `relation`, `feature`, or `qid` |
| `external_id` | Provider-native identifier |
| `match_role` | `primary`, `candidate`, `fallback`, or `rejected` |
| `retrieval_method` | `overpass`, `nominatim`, `rest`, or `manual` |
| `temporal_start` / `temporal_end` | Optional textual temporal bounds |
| `temporal_start_year` / `temporal_end_year` | Normalized year helpers |
| `external_tags` | Raw provider metadata |
| `source_meta` | Lookup provenance metadata |
| `match_score` | Match strength |
| `is_active` | Active georef flag |

### `geometry_periods`

Canonical storage for time-varying geometry.

| Field | Meaning |
|---|---|
| `geometry_period_id` | UUID primary key |
| `entity_id` | Owning entity |
| `period_type` | `territory`, `route`, `spread_zone`, `movement_path`, or `presence` |
| `start_year` / `end_year` | Valid year range |
| `geom` | Time-scoped point or line geometry |
| `territory_geom` | Time-scoped polygon / multipolygon geometry |
| `description` | Why this period exists |
| `provenance_mode` | Live DB supports `manual`, `derived`, and `ohm_import` |
| `relationship_id` | Optional relationship source |
| `source_event_id` | Optional event source |
| `confidence` | Geometry confidence |
| `created_by` | Provenance string |

### `entity_timeline_entries`

Derived read model for timelines. This is rebuilt projection data, not hand-authored source of truth.

| Field | Meaning |
|---|---|
| `timeline_entry_id` | UUID primary key |
| `entity_id` | Owning entity |
| `entry_kind` | Projection kind |
| `start_year` / `end_year` | Timeline span |
| `title` / `description` | Read-model text |
| `location_entity_id` | Optional related place/event pointer |
| `geom` / `territory_geom` | Projected geometry for map/timeline use |
| `source_table` / `source_id` | Canonical origin of the row |
| `relationship_type` | Optional copied relationship metadata |
| `related_entity_id` / `related_entity_name` | Optional related-entity helpers |
| `derived_at` | Projection timestamp |

---

## 3. Flattened Helper Fields Exposed to the UI

The admin controller and some API payloads still surface a flattened entity shape for convenience.
These fields are live, but they are not all dedicated columns on `entities`.

| Exposed field | Backing store |
|---|---|
| `alternative_names` | `entity_aliases` |
| `tags` | `entity_tags` |
| `temporal_start` / `temporal_end` | Primary `entity_temporal_ranges` row |
| `location_name` | Primary `entity_locations` row |
| `geojson` or `geom` | Primary `entity_locations.geom` |
| `territory_geojson` or `territory_geom` | Primary `entity_locations.territory_geom` |
| `date_raw` | Currently surfaced from `attributes` |
| `temporal_display_range` | Currently surfaced from `attributes` or computed from the primary range |
| `era_label` | Currently surfaced from `attributes` |
| `confidence_notes` | Currently surfaced from `attributes` |
| `entity_color` | Currently surfaced from `attributes` |

This is the main reason older docs drifted: helper fields looked like table columns even after persistence moved to normalized tables.

---

## 4. Relationship Fields Relevant to Entity Pages

Relationships are stored in the `relationships` table, not on `entities`.
The current live fields are:

- `relationship_id`
- `source_entity_id`
- `target_entity_id`
- `relationship_type`
- `temporal_start`
- `temporal_end`
- `start_year`
- `end_year`
- `description`
- `confidence`
- `source_citations`
- `derive_geometry_period`
- `created_at`
- `created_by`

That `derive_geometry_period` flag matters because some relationship types can create derived presence geometry periods.

---

## 5. Fields That Are Not Live in the Current Model

These names appeared in older docs and diagrams, but they are not current live fields in the canonical model:

- `parent_entity_id`
- `successor_entity_id`
- direct `alternative_names` array storage on `entities`
- direct `tags` array storage on `entities`
- direct `temporal_start`, `temporal_end`, `geom`, and `territory_geom` columns on `entities` as canonical persistence
- `confidence_breakdown`
- `validation_flags`
- `source_diversity_score`
- `media_refs`
- `relationship_summary`
- `nearby_entity_count`
- `cluster_id`
- `embedding_version`
- `geometry_snapshots`

When you need the live schema, prefer the migrations and models in `api/` over older planning docs.

---

## 6. Practical Reading Guide

Use this mental model when working with an entity today:

1. `entities` holds identity, status, scoring, and shared metadata.
2. aliases, tags, dates, and base locations live in dedicated companion tables.
3. time-varying geometry lives in `geometry_periods`.
4. timeline rows live in `entity_timeline_entries` and can be rebuilt.
5. some convenience fields in UI payloads are still derived from JSON or companion tables for ease of editing.

For editing guidance, see `for-historians.md` and `for-geodata-contributors.md`.

# Plan 06 — Entity Model Simplification

## Goal

Reduce the `entities` table from ~45 columns to ~30 by dropping dead columns and
migrating display/provenance metadata into the existing JSONB `attributes` column.

## Motivation

Many columns were added speculatively during the initial schema design and have
never been populated by any pipeline or admin action. Others carry low-cardinality
display metadata that belongs inside the flexible `attributes` JSONB rather than
occupying first-class column slots with their own casts, fillables and validation.

A leaner table means:

- Smaller row width → faster sequential scans and HOT updates.
- Fewer model fillables/casts → less cognitive overhead.
- DTO, request, resource and factory surface area shrinks proportionally.

## Columns to DROP (6 — never populated, no consumer)

| Column | Type | Reason |
|---|---|---|
| `relationship_summary` | jsonb | Placeholder for cached counts — never computed |
| `nearby_entity_count` | integer | Placeholder for PostGIS proximity cache — never computed |
| `cluster_id` | integer | Placeholder for HDBSCAN output — never computed |
| `confidence_breakdown` | jsonb | Placeholder for per-axis confidence — never computed |
| `source_diversity_score` | integer | Placeholder for source analysis — never computed |
| `embedding_version` | text | Hidden from serialization, never set; can live in `attributes` if ever needed |

## Columns to MOVE into `attributes` JSONB (8)

### Display metadata (3)

| Column | Type | New `attributes` key | Notes |
|---|---|---|---|
| `entity_color` | text | `entity_color` | Hex color; map path reads from attributes |
| `era_label` | text | `era_label` | Derived from temporal range via era ref table |
| `temporal_display_range` | text | `temporal_display_range` | Formatted display string |

### Provenance metadata (5)

| Column | Type | New `attributes` key | Notes |
|---|---|---|---|
| `date_raw` | text | `date_raw` | Original source date string |
| `confidence_notes` | text | `confidence_notes` | LLM-identified uncertainties |
| `validation_flags` | text[] | `validation_flags` | Stage-7 pipeline results → stored as JSON array |
| `media_refs` | jsonb | `media_refs` | `[{type, url, caption}]` |
| `confidence_breakdown` | — | — | *(dropped, not moved — never populated)* |

## Migration strategy

A single migration that:

1. Backfills existing non-null values from columns into `attributes` JSONB using
   `jsonb_build_object()` + `jsonb_strip_nulls()` + `||` merge.
2. Drops the 14 columns (6 dead + 8 moved).
3. Drops the `source_citations_gin_idx` index that covered `source_citations`
   *(column remains, but index was deleted in an earlier plan — verify)*.

The `down()` method re-adds the columns and copies values back out of `attributes`.

## Code changes

| File | Action |
|---|---|
| **Migration** | New migration (backfill → drop cols) |
| `Entity.php` | Remove from fillable, casts, hidden |
| `EntityBuilder.php` | `selectForMap()` reads `entity_color` from `attributes->>'entity_color'` |
| `EntityResource.php` | Remove dead fields; read moved fields from `$this->attributes[…]` |
| `EntitySummaryResource.php` | Same |
| `EntityMapResource.php` | Read `entity_color` from attributes |
| `EntityData.php` | Remove moved fields from constructor; fold into `attributes` in `toModelArray()` |
| `StoreEntityRequest.php` | Move validation rules under `attributes.*` |
| `UpdateEntityRequest.php` | Same |
| `EntityFactory.php` | Move generated values into `attributes` array |
| `EntitySeeder.php` | Move values into `attributes` key for every seed row |

## Resulting column list (~30)

```
entity_id          (uuid PK)
name               (text)
entity_type        (enum)
entity_group       (enum)
alternative_names  (text[])
wikidata_id        (text)
summary            (text)
significance       (text)
tags               (text[])
impact_score       (integer)
attributes         (jsonb)          ← absorbs 8 former columns
temporal_start     (text)
temporal_end       (text)
temporal_start_year (integer)
temporal_end_year  (integer)
date_method        (enum)
date_confidence    (enum)
duration_type      (enum)
location_name      (text)
location_confidence (enum)
location_method    (enum)
geom               (geometry)
territory_geom     (geometry)
parent_entity_id   (uuid FK)
successor_entity_id (uuid FK)
verification_status (enum)
confidence         (enum)
display_priority   (integer)
icon_class         (enum)
source_citations   (jsonb)
embedding          (vector)
reviewer_id        (bigint FK)
review_date        (timestamp)
created_by         (text)
created_at         (timestamp)
updated_at         (timestamp)
```

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Seeder uses moved columns directly | Refactor seeder to embed values in `attributes` |
| Map hot-path performance for `entity_color` | Covered by existing GIN index on `attributes`; also add expression index `(attributes->>'entity_color')` if needed |
| API consumers expect top-level keys | Resources continue exposing them at the same JSON path by reading from attributes |

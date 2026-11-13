# Pipeline entity record

The JSONL record the Python pipeline writes and `php artisan pipeline:import` reads: one entity per
line. The importer maps the public keys into `EntityData` and handles the private `_` keys itself.

> **Audience:** developers, data contributors · **Use:** reference · **Last reviewed:** 2026-11-14 ·
> **Code:** `pipeline/wikidata/mapper/entity_mapper.py` (writer), `api/app/Jobs/ImportEntityJob.php`
> and `api/app/DTOs/EntityData.php` (reader) · **How-to:** [Importing data](../implementation-docs/data-contributor-guide.md)

## Schema

```jsonc
{
  // Required identity
  "name": "Roman Empire",
  "entity_type": "political_entity",
  "entity_group": "POLITY",

  // Recommended identifiers
  "wikidata_id": "Q2277",

  // Core narrative
  "summary": "An imperial polity.",
  "significance": null,
  "alternative_names": ["Imperium Romanum"],

  // Temporal
  "temporal_start": "-0027",
  "temporal_end": "0476",
  "duration_type": "period",             // point | period | ongoing | uncertain
  "date_method": "source_database",
  "date_confidence": "medium",

  // Spatial hints from Wikidata-side extraction
  "location_name": "Rome",
  "location_method": "wikidata",
  "location_confidence": "medium",
  "geojson": {
    "type": "Point",
    "coordinates": [12.5, 41.9]
  },
  "territory_geojson": {
    "type": "Polygon",
    "coordinates": [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]]
  },

  // Derived enrichment
  "attributes": {},
  "tags": ["polity", "political_entity", "ancient"],
  "impact_score": 76,

  // Pipeline state
  "verification_status": "pipeline_draft",
  "confidence": "medium",
  "source_citations": [
    {
      "source_type": "reference",
      "title": "Wikidata:Q2277",
      "url": "https://www.wikidata.org/wiki/Q2277",
      "reliability": "reference"
    }
  ],

  // Pipeline-private payloads consumed by Laravel import
  "_relationship_hints": [],
  "_geo_resolution": {}
}
```

## Required fields

- `name`
- `entity_type`
- `entity_group`

Import skips records missing any of these.

## Pipeline-private keys

The importer reads these and strips them before building `EntityData`.

| Key | Shape | What the importer does |
|---|---|---|
| `_relationship_hints` | `[{relationship_type, target_wikidata_id, target_label, temporal_start, temporal_end, confidence, source}]` | Stages each hint in `pipeline_relationship_hints`. They become relationships once both ends exist (`ResolveRelationshipsJob`) |
| `_geo_resolution` | `{status, geo_ref: {provider, external_type, external_id, match_role, retrieval_method, match_score, …}, provenance, geometry}` | Only when `status` is `"matched"` and `geo_ref.external_id` is set: writes an `entity_geo_refs` row |
| `_identity_span` | `[start_year, end_year]` | The record's era for the namesake guard when it has no dates of its own |
| `_geometry_periods`, `_ohm_relation_id` | See below | OHM border records only (`pipeline:import-borders`) |

## OHM borders contract

The OHM borders pipeline uses `_geometry_periods[*].geojson` as its importer-facing spatial field.

In the current first pass, that payload is point-only:

```jsonc
{
  "_ohm_relation_id": "100",
  "_geometry_periods": [
    {
      "ohm_relation_id": "100",
      "external_type": "relation",
      "start_year": 1900,
      "end_year": 1950,
      "start_date": "1900",
      "end_date": "1950",
      "geojson": {
        "type": "Point",
        "coordinates": [12.48, 41.89]
      },
      "label": "Testland (1900-1950)",
      "external_tags": {
        "name": "Testland"
      }
    }
  ]
}
```

Rationale:

- final JSONL stays lightweight even when OHM source geometry is large
- OHM feature identity still lives in `entity_geo_refs`
- representative points still support markers, timeline entries, and reverse lookup
- `territory_geom` remains available for manual or curated local boundary authoring outside this import path

Full OHM polygons may still exist transiently inside pipeline parse/build stages for representative-point derivation, but they are not persisted through the final OHM border importer contract.

## Notes

- The importer sets `verification_status` to `pipeline_draft`. It uses `needs_review` instead when the
  record asks for it, when a namesake is suspected, or when a person's dates span more than 110 years.
- `tags` are written as manual tags. A value that matches no tag slug or name becomes a new `topic` tag.
- `_infobox` inside `attributes` is preserved in JSONL but stripped in import.
- Unknown extra fields are tolerated but should be avoided in canonical output.

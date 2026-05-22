# Pipeline Entity Record Schema

> Canonical JSONL record schema emitted by the Python pipeline for import into Laravel.

## Purpose

Each line in `*.jsonl` is a single entity record. Laravel import reads this shape and maps it into `EntityData`, then handles optional pipeline-private keys.

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

## Required Fields

- `name`
- `entity_type`
- `entity_group`

Import skips records missing any of these.

## Optional Pipeline-Private Keys

- `_relationship_hints`: staged for relationship resolution jobs.
- `_geo_resolution`: consumed by import georef action.
- `_geometry_periods`: importer-facing temporal geometry payload used by the OHM borders pipeline.

These keys are stripped before constructing Laravel `EntityData`.

## OHM Borders Contract

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

- `verification_status` is forced to `pipeline_draft` during import.
- `_infobox` inside `attributes` is preserved in JSONL but stripped in import.
- Unknown extra fields are tolerated but should be avoided in canonical output.

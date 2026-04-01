# Relationship Hints Manifest Schema

> Schema for `_relationship_hints` emitted in pipeline JSONL records.

## Purpose

Hints are unresolved relationship candidates derived from Wikidata properties. They are staged during import and resolved later against actual entity IDs.

## Schema

```jsonc
"_relationship_hints": [
  {
    "relationship_type": "capital_of",
    "target_wikidata_id": "Q220",
    "target_label": "Rome",
    "confidence": "medium",         // low | medium | high
    "source": "wikidata:P36"
  }
]
```

## Field Definitions

- `relationship_type` (required): target relationship enum key used by the app.
- `target_wikidata_id` (required): Wikidata QID of the related entity.
- `target_label` (optional): human-readable label for diagnostics.
- `confidence` (optional): hint confidence (defaults to `medium` in importer fallback behavior).
- `source` (optional): property provenance, typically `wikidata:P###`.

## Import Behavior

- Hints are inserted into `pipeline_relationship_hints` with:
  - `source_entity_id`
  - `relationship_type`
  - `target_wikidata_id`
  - `target_label`
  - `confidence`
  - `wikidata_property`
  - `batch_id`
  - `resolved=false`
- If the staging table is unavailable, importer stores hints under `entities.attributes._relationship_hints`.

## Validation Guidance

- Do not emit hints without `target_wikidata_id`.
- Prefer stable relationship keys over free text.
- Keep `source` machine-readable for traceability.

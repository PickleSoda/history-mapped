# Entity Georef Write Request Schema

> API request schema for manual georef attach in entity edit flows.

Endpoint:

- `POST /api/v1/entities/{entity}/geography-references`

## Schema

```jsonc
{
  "provider": "ohm",                 // enum: ohm | wikidata | geonames | pleiades | custom
  "external_type": "relation",       // enum: node | way | relation | feature | qid
  "external_id": "1880",
  "match_role": "primary",           // enum: primary | candidate | fallback | rejected
  "retrieval_method": "rest",        // enum: overpass | nominatim | rest | manual

  "temporal_start": "-0027",
  "temporal_end": "0476",

  "external_tags": {
    "historic": "empire"
  },
  "source_meta": {
    "display_name": "Roman Empire"
  },

  "match_score": 1.0,
  "is_active": true
}
```

## Validation Rules (Laravel)

- Required:
  - `provider`
  - `external_type`
  - `external_id`
  - `match_role`
  - `retrieval_method`
- Optional:
  - temporal fields
  - metadata fields (`external_tags`, `source_meta`)
  - `match_score` in range `[0,1]`
  - `is_active` boolean
- Constraint:
  - Temporal ranges must be coherent (`temporal_end` not earlier than `temporal_start`) when both are present.

## Notes

- Manual entity edit uses app-side attach/search endpoints and remains independent of pipeline import flow.
- For `provider=ohm`, backend enrichment may fetch additional metadata/geometry before persistence.

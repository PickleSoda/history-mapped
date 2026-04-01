# Geo-Resolution Manifest Schema

> Canonical schema for the `_geo_resolution` key emitted by the Python pipeline in each JSONL entity record.

## Design Principle

The pipeline is the **sole decision-maker** for automatic geo-resolution. It queries OHM Nominatim (and future fallback sources), evaluates matches, and emits a deterministic verdict. Laravel **consumes** this manifest as-is — it never second-guesses the pipeline's decision.

## Schema

```jsonc
"_geo_resolution": {
  // Pipeline's verdict
  "status": "matched",         // "matched" | "no_match" | "skipped"

  // Present when status == "matched"
  "geo_ref": {
    "provider":         "ohm",         // matches GeoRefProvider enum: ohm | wikidata | geonames | pleiades | custom
    "external_type":    "relation",    // matches GeoRefExternalType enum: node | way | relation | feature | qid
    "external_id":      "1880",        // string — OHM osm_id, Wikidata QID, etc.
    "match_role":       "primary",     // matches GeoRefMatchRole enum: primary | candidate | fallback | rejected
    "retrieval_method": "nominatim",   // matches GeoRefRetrievalMethod enum: overpass | nominatim | rest | manual
    "match_score":      1.0,           // 0.0–1.0 confidence in name match
    "external_tags":    {},            // OHM extratags passthrough (JSONB)
    "source_meta":      {}             // raw API response metadata (JSONB)
  },

  // Present when geo_ref includes geometry
  "geometry": {
    "type": "Polygon",                 // GeoJSON type
    "coordinates": [[[...]]]           // GeoJSON coordinates
  },

  // How the pipeline arrived at this decision
  "provenance": {
    "resolver":    "ohm_nominatim",    // which resolver produced this: ohm_nominatim | wikidata_coords | inferred_boundary
    "query":       "Roman Empire Rome",// the search query used
    "candidates":  2,                  // how many candidates the resolver found
    "reason":      "exact_name_match"  // why this candidate was selected (or why no match)
  }
}
```

## Status Values

- `matched`: Pipeline found a confident match and recommends attaching (`geo_ref` must be present).
- `no_match`: Pipeline searched but found no acceptable match (`geo_ref` must be absent).
- `skipped`: Pipeline intentionally skipped resolution (`geo_ref` must be absent).

## Laravel Consumption Rules

1. **`status == "matched"`**: Create `EntityGeoRef` row using `geo_ref` fields, hydrate geometry if `geometry` is present, set `location_method` based on `provenance.resolver`.
2. **`status == "no_match"`**: Do nothing. Entity has no auto-resolved georef.
3. **`status == "skipped"`**: Do nothing.
4. **`_geo_resolution` key absent**: Treat as `skipped` — legacy JSONL records without the key are safe.

## Mapping to Laravel Enums

- `geo_ref.provider` -> `GeoRefProvider` -> `provider`
- `geo_ref.external_type` -> `GeoRefExternalType` -> `external_type`
- `geo_ref.match_role` -> `GeoRefMatchRole` -> `match_role`
- `geo_ref.retrieval_method` -> `GeoRefRetrievalMethod` -> `retrieval_method`
- `provenance.resolver` -> `LocationResolutionMethod` -> `entities.location_method`

### `provenance.resolver` -> `LocationResolutionMethod` mapping

- `ohm_nominatim` -> `ohm_nominatim`
- `wikidata_coords` -> `wikidata`
- `inferred_boundary` -> `(future)`

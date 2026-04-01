# Inferred Geometry Snapshot Schema

> Experimental schema for non-canonical inferred boundary output (Plan 14).

## Status

Draft proposal for fallback/inference pipelines. Not part of canonical import geometry writes.

## Schema

```jsonc
{
  "entity_id": "uuid",
  "snapshot_date_start": "-0700-01-01",
  "snapshot_date_end": "-0680-12-31",
  "geom": {
    "type": "Polygon",
    "coordinates": [[[...]]]
  },
  "geometry_origin": "inferred",               // required invariant
  "confidence_score": 0.87,
  "confidence_band": "inferred_high_confidence", // inferred_high_confidence | inferred_candidate_only
  "inference_method": "region_occupancy_model",
  "model_version": "v0.1.0",
  "source_bundle": ["ohm", "wikidata", "open_hydro"],
  "topology_metrics": {
    "valid": true,
    "component_count": 1,
    "sliver_count": 0
  },
  "evidence_summary": {
    "anchors": 12,
    "cross_method_agreement": 0.74,
    "temporal_support": 0.81
  },
  "generated_at": "2026-04-01T12:00:00Z",
  "invalidated_at": null,
  "do_not_merge_canonical": true
}
```

## Hard Rules

- Inferred records are non-canonical and must not overwrite canonical entity geometry by default.
- `geometry_origin` must be `inferred`.
- `do_not_merge_canonical` should remain `true` until explicit promotion policy exists.

## Serving Guidance

- Only `inferred_high_confidence` records are eligible for default serving.
- Inferred layers should render only when canonical/OHM-backed geometry is unavailable.
- Client should style inferred geometry as uncertain (visual distinction required).

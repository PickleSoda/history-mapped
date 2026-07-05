# Schemas

Schema specifications for pipeline payloads, import contracts, and georef API requests.

## Core

- [pipeline-entity-record.md](pipeline-entity-record.md) — the JSONL entity record the pipeline emits and `pipeline:import` consumes.
- [geo-resolution-manifest.md](geo-resolution-manifest.md) — geo-resolution manifest contract.
- [relationship-hints-manifest.md](relationship-hints-manifest.md) — staged relationship-hint records.
- [ref-table-record.md](ref-table-record.md) — reference-table (calendar systems, periods, regions, …) records.

## API

- [entity-georef-write-request.md](entity-georef-write-request.md) — georef write-request payload.

## Experimental

- [inferred-geometry-snapshot.md](inferred-geometry-snapshot.md) — draft contract for the
  [inferred-boundary fallback pipeline plan](../plans/experimental-inferred-boundary-fallback-pipeline.md) (⬜ not started).

## Notes

- Core schemas describe currently used payloads.
- Experimental schemas are draft contracts; check [../plans/STATUS.md](../plans/STATUS.md) before relying on them.

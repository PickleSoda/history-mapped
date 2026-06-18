# OHM Borders Staged Parallel Design

## Goal

Replace the current single-pass `py -m pipeline borders` flow with a staged, file-backed workflow that maximizes single-machine throughput while keeping every stage restartable from durable intermediate artifacts.

## Current Problem

The existing `borders` command performs fetch, parse, enrich, map, and final write in one process. That creates three concrete problems:

1. A failure late in the pipeline forces a full refetch and reparse.
2. Parse and enrichment work cannot be parallelized independently.
3. There is no manifest or stage-level state that explains which step completed successfully.

## Proposed Architecture

The OHM borders workflow will be split into five explicit stages:

1. `fetch`: execute the Overpass query and persist the raw response JSON.
2. `parse`: turn raw Overpass elements into normalized OHM polity shard files.
3. `enrich`: batch Wikidata QIDs from parsed shards and write enrichment shard files.
4. `build`: merge parsed shards with enrichment results and emit final JSONL shards plus the merged JSONL.
5. `run`: convenience wrapper that executes the full staged workflow in order.

Each run will write to a deterministic artifact directory, for example:

`output/ohm_borders/<run_id>/`

`run_id` defaults to a UTC timestamp in `YYYYMMDD-HHMMSS` format and may be overridden explicitly.

That directory will contain:

- `manifest.json`
- `raw/overpass.json`
- `parsed/parsed-00001.jsonl` ... `parsed-*.jsonl`
- `enriched/enriched-qids-00001.json` ... `enriched-qids-*.json`
- `built/built-00001.jsonl` ... `built-*.jsonl`
- `final/ohm_borders.jsonl`

## Data Model And File Contracts

### Raw fetch output

- A single JSON file containing the Overpass response exactly as returned.
- Metadata in `manifest.json` records the query source, fetch timestamp, and element count.

### Parsed shard output

- JSONL where each line is a parsed polity object containing OHM tags, relation id, and stage geometry payloads.
- Parsing does not depend on Wikidata.
- Shards are created by splitting parsed polities into fixed-size chunks so they can be processed independently.

### Enrichment shard output

- JSON files keyed by QID with the same metadata shape currently returned by `batch_enrich_qids`.
- Enrichment shards are always bounded QID chunks, not parsed-shard mirrors.
- File naming is deterministic, for example `enriched-qids-00001.json`.
- The build stage loads every successful enrichment shard into one in-memory QID index keyed by Wikidata id, then maps parsed shards against that index.

### Built shard output

- JSONL using the current Laravel import contract.
- Invalid stage periods are filtered during mapping so malformed OHM stages do not poison downstream imports.

### Manifest

The manifest records:

- `run_id`
- stage status per step: `pending`, `running`, `completed`, `failed`
- declared inputs and outputs per stage
- shard counts and chunk sizes
- worker counts used for parse and enrich
- summary counters such as `elements_returned`, `polities_parsed`, `qids_requested`, `qids_enriched`, `records_written`

The manifest should use one top-level object with a stable shape:

- `run_id`
- `artifact_dir`
- `options`
- `summary`
- `stages`

Each entry in `stages` uses this shape:

- `status`
- `inputs`
- `outputs`
- `started_at`
- `finished_at`
- `failed_shards`

For `enrich`, `failed_shards` is a list of enrichment shard filenames such as `enriched-qids-00007.json`.

Manifest writes will use a single-writer temp-file replacement strategy: write the full next manifest state to `manifest.json.tmp`, flush it, and then replace `manifest.json` atomically with `os.replace`.

## Concurrency Model

### Parse stage

- Parse the raw Overpass response once to extract polity objects.
- Partition the polity list into shards.
- Use a bounded worker pool to serialize shard files in parallel.
- Default `--parsed-shard-size` is `100` polity records.
- Default `--parse-workers` is `max(1, cpu_count() - 1)`.

### Enrich stage

- Read parsed shards, extract unique QIDs, and partition them into batches.
- Execute SPARQL enrichment concurrently with a configurable worker cap.
- Persist successful shard outputs independently so a failed batch can be retried without redoing successful batches.
- Default `--enrich-batch-size` remains `50` QIDs to match the current batcher.
- Default `--enrich-workers` is `4`.
- No auto-tuning is planned in the first iteration; operator-supplied flags are the tuning mechanism.

### Build stage

- Build final JSONL shard-by-shard by combining parsed shard inputs with the enrichment index.
- Merge built shards into the final JSONL in a deterministic order: parsed shard number ascending, then record order within each parsed shard.

The default should favor throughput, but all worker counts must remain configurable to avoid overwhelming Overpass, Wikidata, or low-memory developer machines.

## CLI Surface

The existing `borders` entrypoint will become a group with subcommands:

- `py -m pipeline borders fetch`
- `py -m pipeline borders parse`
- `py -m pipeline borders enrich`
- `py -m pipeline borders build`
- `py -m pipeline borders run`

Compatibility requirement:

- `py -m pipeline borders --output ...` should continue to work, either as an alias to `borders run` or via a compatibility shim, so current docs and scripts do not break immediately.

Core shared options:

- `--run-id`
- `--artifact-dir`
- `--query-file`
- `--parsed-shard-size`
- `--enrich-batch-size`
- `--parse-workers`
- `--enrich-workers`
- `--resume`
- `--force`
- `--no-enrich`

`--artifact-dir` is the canonical option. No separate `--workspace` option is planned in v1.

If `--query-file` is omitted, fetch uses the existing built-in `GLOBAL_QUERY` constant.

`--no-enrich` behavior:

- `borders run --no-enrich` skips the enrich stage entirely.
- `borders build --no-enrich` builds from parsed shards with an empty Wikidata index.
- The resulting JSONL keeps the same schema, but Wikidata-derived fields remain absent or `null`, matching current no-enrichment behavior.

## Failure Handling And Resume Rules

- `fetch` can be skipped if `raw/overpass.json` already exists and `--force` is not set.
- `parse` can skip completed shard outputs recorded in the manifest.
- `enrich` retries only failed or missing enrichment shard files.
- `build` rebuilds only missing or forced shard outputs.
- `run --resume` walks the manifest and continues from the first incomplete stage.

`--force` semantics:

- `fetch --force` refetches raw Overpass data and rewrites `raw/overpass.json`.
- `parse --force` rewrites all parsed shard outputs.
- `enrich --force` reruns all enrichment shards, not just missing or failed ones.
- `build --force` rewrites all built shard outputs and the merged final JSONL.
- `run --force` applies forced behavior to every stage it executes.

Enrichment failure policy:

- Failed QID batches are recorded in the manifest with their shard ids.
- Successful enrichment shards remain usable.
- `build` is allowed to proceed with partial enrichment by default, preserving the current tolerant behavior where missing Wikidata metadata does not block record emission.
- A future strict mode is out of scope for this change.

Manifest updates should be written atomically so an interrupted run does not leave ambiguous stage state.

## Validation Rules

- Mapper output must not contain geometry periods where `start_year > end_year`.
- In v1, a malformed stage period means both years are parseable and `start_year > end_year`; those stages are dropped during build.
- Stages with missing or unparsable years are allowed to pass through unchanged, matching current importer expectations.
- Import-facing JSONL must preserve the existing schema expected by Laravel.
- Final merged JSONL ordering should be deterministic across reruns with the same inputs.
- Stage-level counters in the manifest should match the produced artifact counts.

## Testing Strategy

### Python tests

- Unit tests for artifact-path planning and manifest updates.
- Unit tests for parse sharding and enrichment batch planning.
- Regression tests confirming invalid stage periods are dropped during build.
- End-to-end staged test using a small synthetic OHM payload that runs `fetch` fixture replacement, `parse`, `enrich`, and `build` with multiple shards.

### Laravel tests

- Keep the current importer regression coverage for malformed stage periods.
- No schema changes are expected for Laravel import consumers.

## Documentation Changes

- Update `pipeline/README.md` with staged command examples and resume flows.
- Document the artifact directory structure and when to reuse existing artifacts versus forcing a fresh run.

## Non-Goals

- No workflow engine or external queue system.
- No change to the Laravel import JSONL schema.
- No attempt to parallelize the Laravel import in this change.

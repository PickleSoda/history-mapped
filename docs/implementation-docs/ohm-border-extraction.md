# OHM Border Extraction Step By Step

This document explains how the history-mapped OHM border extraction pipeline works from the first Overpass query to the final Laravel import.

It describes the staged workflow currently implemented in the repository, not the older single-pass version.

## Purpose

The OHM border pipeline exists to:

- fetch all OpenHistoricalMap `admin_level=2` administrative boundary relations
- normalize chronology relations and standalone relations into one internal polity shape
- optionally enrich those polities from Wikidata using the OHM `wikidata` tag
- build importer-ready JSONL records for Laravel
- import entities, OHM geo refs, and geometry periods into Postgres

The pipeline is designed to be restartable. Each stage writes its own artifacts, and a manifest records what has completed.

## High-Level Flow

The full workflow is:

1. `fetch` downloads raw OHM Overpass JSON.
2. `parse` converts raw Overpass elements into normalized polity shards.
3. `enrich` batches unique Wikidata QIDs and writes enrichment shards.
4. `build` maps parsed polities into importer-facing JSONL shards and merges them.
5. `pipeline:import-borders` reads the merged JSONL and writes data into Laravel models.

The main CLI entrypoint for the complete extraction is:

```powershell
py -m pipeline borders run --run-id global-2026-04-11 --output output/ohm_borders_global.jsonl
```

The legacy compatibility form still works and routes through the same staged code path:

```powershell
py -m pipeline borders --run-id global-2026-04-11 --output output/ohm_borders_global.jsonl
```

## Step 1: Start A Run And Create The Artifact Layout

When you run any OHM borders stage, the pipeline resolves a run id and an artifact directory.

- If you pass `--run-id`, that value is used.
- If you pass `--artifact-dir`, that directory is used directly.
- Otherwise the pipeline derives `output/ohm_borders/<run_id>/`.

Artifact directories are created up front so every stage writes into a predictable location.

Expected layout:

```text
output/ohm_borders/<run_id>/
├── manifest.json
├── raw/
│   └── overpass.json
├── parsed/
│   └── parsed-00001.jsonl
├── enriched/
│   └── enriched-qids-00001.json
├── built/
│   └── built-00001.jsonl
└── final/
    └── ohm_borders.jsonl
```

The relevant path helpers live in [pipeline/ohm_borders/artifacts.py](/history-mapped/pipeline/ohm_borders/artifacts.py).

## Step 2: Initialize Or Reuse The Manifest

Every run uses a manifest file at `manifest.json`.

The manifest stores:

- `run_id`
- `artifact_dir`
- `options`
- `summary`
- `stages`

Each stage entry tracks:

- `status`
- `inputs`
- `outputs`
- `started_at`
- `finished_at`
- `failed_shards`

Manifest writes are atomic: the pipeline writes `manifest.json.tmp` and then replaces the real manifest. This avoids leaving a half-written manifest if the process is interrupted.

Implementation lives in [pipeline/ohm_borders/manifest.py](/history-mapped/pipeline/ohm_borders/manifest.py).

## Step 3: Fetch Raw OHM Data

The `fetch` stage sends an Overpass request to the OHM endpoint:

- endpoint: `https://overpass-api.openhistoricalmap.org/api/interpreter`
- default query: all relations where `boundary=administrative` and `admin_level=2`
- output mode: `out geom;`

Default query:

```overpass
[out:json][timeout:1800];
relation["boundary"="administrative"]["admin_level"="2"];
out geom;
```

This request is implemented in [pipeline/ohm_borders/fetcher.py](/history-mapped/pipeline/ohm_borders/fetcher.py).

What happens during fetch:

1. The query text is loaded from `--query-file` or the built-in global query.
2. The pipeline posts the query to the OHM Overpass API.
3. The returned JSON is written exactly once to `raw/overpass.json`.
4. The manifest is updated with fetch status and raw element count.

If `--resume` is set and `raw/overpass.json` already exists, fetch is skipped unless `--force` is also set.

## Step 4: Parse Raw Overpass Elements Into Polities

The `parse` stage reads `raw/overpass.json` and transforms raw OHM relations into normalized polity objects.

This logic is also implemented in [pipeline/ohm_borders/fetcher.py](/history-mapped/pipeline/ohm_borders/fetcher.py), inside `parse_elements()`.

The parser handles two OHM shapes:

### 4.1 Chronology Relations

If a relation has `type=chronology`, it is treated as the root polity. Its member relations become dated stages.

For each chronology:

1. The chronology relation becomes the polity root.
2. Each member relation is looked up by relation id.
3. Each member relation becomes one stage with:
   - `relation_id`
   - `tags`
   - assembled geometry

### 4.2 Standalone Administrative Relations

If a relation is not a chronology and is not already a member of one, it becomes a standalone polity.

In that case the parser creates a single-stage polity where the root relation and the only stage share the same relation id and tags.

### 4.3 Geometry Assembly

For each stage, the parser extracts outer member ways and stitches their coordinates into polygon rings.

- If Shapely is available, it uses `Polygon` and `MultiPolygon` assembly.
- If Shapely fails or is unavailable, it falls back to a simple `MultiPolygon` coordinate structure.

If no usable rings are found, the geometry for that stage is `null`.

### 4.4 Parsed Shards

After parsing all polities, the pipeline splits them into shards.

- default shard size: `100` polities
- default parse workers: `max(1, cpu_count() - 1)`

Each shard is written as JSONL to `parsed/parsed-00001.jsonl`, `parsed/parsed-00002.jsonl`, and so on.

The staged orchestration is implemented in [pipeline/ohm_borders/stages.py](/history-mapped/pipeline/ohm_borders/stages.py).

If `--resume` is set, existing parsed shard files are skipped unless `--force` is set.

## Step 5: Collect Unique Wikidata QIDs

The `enrich` stage is optional. It is skipped entirely if you run with `--no-enrich`.

If enrichment is enabled, the pipeline reads every parsed shard and extracts the `tags.wikidata` value from each parsed polity.

Important details:

- duplicate QIDs across shards are deduplicated
- QIDs are sorted for deterministic batching
- missing QIDs are ignored

The result is one sorted list of unique Wikidata ids for the run.

## Step 6: Enrich QIDs In Batches

The enrichment stage batches QIDs and fetches metadata from Wikidata.

Defaults:

- batch size: `50`
- workers: `4`

Each successful batch is written to a file such as:

- `enriched/enriched-qids-00001.json`
- `enriched/enriched-qids-00002.json`

Each enrichment shard is a JSON object keyed by QID. Values contain the metadata used later by the mapper, such as name, aliases, description, and temporal hints.

The stage is tolerant of partial failure:

1. successful shards stay on disk
2. failed shards are recorded in `manifest.json`
3. the build stage can still proceed with incomplete enrichment

This behavior is implemented in [pipeline/ohm_borders/stages.py](/history-mapped/pipeline/ohm_borders/stages.py).

If `--resume` is set, existing enrichment shard files are skipped unless `--force` is set.

## Step 7: Build Importer-Facing JSONL Records

The `build` stage converts parsed polity objects into the final JSONL schema consumed by Laravel.

It does this shard by shard:

1. load parsed shard records
2. load all available enrichment shards into one Wikidata index
3. map each parsed polity into one final record
4. write one built shard per parsed shard
5. merge all built shards into `final/ohm_borders.jsonl`

Built shard outputs are written to:

- `built/built-00001.jsonl`
- `built/built-00002.jsonl`

The merged final output is:

- `final/ohm_borders.jsonl`

If you pass `--output`, the CLI also copies `final/ohm_borders.jsonl` to the path you requested.

## Step 8: Map Parsed Polities Into Final Records

The final mapping logic lives in [pipeline/ohm_borders/mapper.py](/history-mapped/pipeline/ohm_borders/mapper.py).

For each polity, the mapper:

1. reads the OHM tags and stage list
2. looks up Wikidata metadata if a `wikidata` tag exists
3. chooses a final display name
4. resolves top-level temporal bounds
5. emits `_geometry_periods` from valid stages
6. returns a JSON record matching the Laravel import contract

### 8.1 Name Selection

Name selection is:

1. Wikidata English label, if available
2. OHM `name:en`
3. OHM `name`
4. `Unknown`

### 8.2 Temporal Bound Resolution

Top-level `temporal_start` and `temporal_end` are chosen carefully.

Priority is:

- root OHM tag dates first
- otherwise earliest and latest valid stage dates
- otherwise Wikidata temporal hints

This matters because the repository previously hit real data where Wikidata dates represented a modern administrative region while OHM stages represented the historical polity. The current mapper prefers OHM stage chronology for the extraction output.

### 8.3 Invalid Stage Filtering

Before a stage becomes a geometry period, the mapper checks whether both parsed years exist and whether `start_year <= end_year`.

If a stage has reversed years, it is dropped.

This protects the downstream import from malformed OHM chronology members.

### 8.4 Final Record Shape

Each final JSONL line includes fields like:

- `name`
- `entity_type=political_entity`
- `entity_group=POLITY`
- `wikidata_id`
- `alternative_names`
- `summary`
- `temporal_start`
- `temporal_end`
- `verification_status=ohm_draft`
- `_ohm_relation_id`
- `_geometry_periods`

`_geometry_periods` contains one entry per valid dated stage with:

- OHM relation id
- start and end dates
- start and end years
- GeoJSON geometry
- a human-readable label
- passthrough OHM tags

## Step 9: Merge Built Shards Deterministically

After all built shards are written, the build stage assembles the final merged JSONL.

The merge order is deterministic:

1. built shard order follows parsed shard number ascending
2. record order inside each shard is preserved

This makes reruns stable as long as the inputs are the same.

## Step 10: Review The Manifest And Artifacts

At the end of a successful run, you can inspect:

- `manifest.json` for stage state and counters
- `raw/overpass.json` for the raw OHM response
- `parsed/*.jsonl` for normalized polity objects
- `enriched/*.json` for Wikidata batch responses
- `built/*.jsonl` for importer-facing shard output
- `final/ohm_borders.jsonl` for the merged import file

Useful summary fields in the manifest include:

- `raw_elements`
- `parsed_polities`
- `parsed_shards`
- `enrich_unique_qids`
- `enrich_shards`
- `build_records`

## Step 11: Import The Final JSONL Into Laravel

Once the Python pipeline has produced the final JSONL, Laravel imports it with:

```powershell
Copy-Item output/ohm_borders_global.jsonl api/storage/app/ohm_borders_global.jsonl
docker compose -f docker/docker-compose.yml exec app php -d memory_limit=1024M artisan pipeline:import-borders /var/www/html/storage/app/ohm_borders_global.jsonl --sync --batch-id=global-2026-04-11
```

The import command is implemented in [api/app/Console/Commands/ImportBordersCommand.php](/history-mapped/api/app/Console/Commands/ImportBordersCommand.php).

What the command does:

1. opens the JSONL file line by line
2. trims empty lines
3. decodes each line as JSON
4. skips malformed lines
5. either dispatches `ImportBorderEntityJob` or runs it synchronously with `--sync`

For large full exports, `--sync` is preferred because the records can be very large and queue payload serialization is expensive.

The higher PHP memory limit is also important because some OHM records contain very large geometries.

## Step 12: Import One Record Into The Domain Model

Each JSONL record is handled by [api/app/Jobs/ImportBorderEntityJob.php](/history-mapped/api/app/Jobs/ImportBorderEntityJob.php).

For each record, the job:

1. validates required fields like `name`, `entity_type`, and `entity_group`
2. extracts `_geometry_periods`
3. filters invalid reversed geometry periods
4. sorts geometry periods chronologically
5. removes import-only helper fields from the entity payload
6. forces `verification_status` to `ohm_draft`
7. builds an `EntityData` DTO
8. looks for an existing entity by Wikidata id, OHM relation id, or name/type

Then it takes one of three paths:

- create a new entity
- update an existing entity if `--force` is set
- skip entity creation and only upsert geometry periods if it already exists

## Step 13: Create The OHM Geo Ref

If `_ohm_relation_id` is present, the job creates or reuses an OHM geo reference.

That geo ref is stored with:

- `provider=ohm`
- `external_type=relation`
- `external_id=<ohm relation id>`
- `retrieval_method=overpass`
- `match_role=primary`

The geo ref’s temporal bounds come from the first and last sorted geometry period.

This is why ordering geometry periods correctly matters: the importer uses the sorted first and last period when setting geo ref temporal metadata.

## Step 14: Hydrate Entity Geometry

After creating the geo ref, the importer looks for the first geometry period that actually contains GeoJSON and hydrates the entity geometry from it.

This gives the entity a usable current geometry record in addition to the historical `geometry_periods` timeline.

## Step 15: Create Geometry Periods

Finally, the job upserts one `geometry_periods` row for each valid period that has:

- GeoJSON
- a start year
- an end year

Each row is written with:

- `period_type=territory`
- `provenance_mode=ohm_import`
- `confidence=medium`
- `created_by=borders:<batchId>`

If a geometry period with the same entity, years, and OHM import provenance already exists, the job skips it.

## Resume And Force Behavior

The staged pipeline is built to tolerate reruns.

### `--resume`

Use `--resume` when you want to continue an interrupted run.

- fetch skips existing `raw/overpass.json`
- parse skips existing parsed shard files
- enrich skips existing enrichment shard files
- build skips existing built shard files when possible

### `--force`

Use `--force` when you want to rewrite stage outputs.

- fetch refetches raw OHM data
- parse rewrites parsed shards
- enrich reruns all enrichment batches
- build rewrites built shards and the merged final file

### `--no-enrich`

Use `--no-enrich` if you want to build importer-ready JSONL using OHM data only.

In that mode:

- the enrich stage is skipped
- the build stage uses an empty Wikidata index
- the final schema stays the same
- Wikidata-derived fields are simply absent or `null`

## Practical Commands

### Full staged run

```powershell
py -m pipeline borders run --run-id global-2026-04-11 --output output/ohm_borders_global.jsonl
```

### Resume an interrupted run

```powershell
py -m pipeline borders run --run-id global-2026-04-11 --resume --output output/ohm_borders_global.jsonl
```

### Run stage by stage

```powershell
py -m pipeline borders fetch --run-id global-2026-04-11
py -m pipeline borders parse --run-id global-2026-04-11 --resume
py -m pipeline borders enrich --run-id global-2026-04-11 --resume
py -m pipeline borders build --run-id global-2026-04-11 --resume
```

### Build without Wikidata enrichment

```powershell
py -m pipeline borders run --run-id global-2026-04-11 --no-enrich --output output/ohm_borders_global.jsonl
```

### Import into Laravel

```powershell
$batchId = "global-$(Get-Date -Format 'yyyy-MM-dd')"
Copy-Item output/ohm_borders_global.jsonl api/storage/app/ohm_borders_global.jsonl
docker compose -f docker/docker-compose.yml exec app php -d memory_limit=1024M artisan pipeline:import-borders /var/www/html/storage/app/ohm_borders_global.jsonl --sync "--batch-id=$batchId"
```

## Files To Read If You Need To Trace The Pipeline In Code

- [pipeline/__main__.py](/history-mapped/pipeline/__main__.py)
- [pipeline/ohm_borders/fetcher.py](/history-mapped/pipeline/ohm_borders/fetcher.py)
- [pipeline/ohm_borders/stages.py](/history-mapped/pipeline/ohm_borders/stages.py)
- [pipeline/ohm_borders/mapper.py](/history-mapped/pipeline/ohm_borders/mapper.py)
- [pipeline/ohm_borders/manifest.py](/history-mapped/pipeline/ohm_borders/manifest.py)
- [api/app/Console/Commands/ImportBordersCommand.php](/history-mapped/api/app/Console/Commands/ImportBordersCommand.php)
- [api/app/Jobs/ImportBorderEntityJob.php](/history-mapped/api/app/Jobs/ImportBorderEntityJob.php)

## Key Operational Notes

- The global OHM Overpass query can take a long time.
- Full imports should use `php -d memory_limit=1024M`.
- `--sync` is safer for very large JSONL records than pushing everything through the queue.
- Invalid reversed stage periods are filtered in both the Python mapper and the Laravel importer.
- The final output schema is stable even when enrichment is skipped or partially missing.

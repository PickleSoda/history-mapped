# OHM Borders Pipeline

Fetches all `admin_level=2` relations from [OpenHistoricalMap](https://www.openhistoricalmap.org/), parses them into polity records, optionally enriches them with Wikidata metadata, and produces an importer-ready JSONL file.

Can be run as a standalone CLI (`python -m pipeline.ohm_borders`) or via the top-level dispatcher (`python -m pipeline borders`).

## Staged pipeline

Each stage writes artifacts under `output/ohm_borders/<run_id>/` and records progress in `manifest.json`, so any stage can be resumed without redoing finished work.

```text
output/ohm_borders/<run_id>/
├── manifest.json
├── raw/
│   ├── overpass.json          # full Overpass payload (may be several GB)
│   └── raw-NNNNN.jsonl        # relation-only shards for parallel parse
├── parsed/
│   └── parsed-NNNNN.jsonl     # polity records, 100 per shard by default
├── enriched/
│   └── enriched-NNNNN.jsonl   # polities with Wikidata metadata hydrated
├── built/
│   └── built-NNNNN.jsonl      # mapper output, ready for import
└── final/
    └── ohm_borders.jsonl      # merged output file

output/ohm_borders/<run_id>/
├── relations_candidates/
│   └── relations-candidates-NNNNN.jsonl
├── relations_enriched/
│   └── relations-enriched-NNNNN.json
├── relations_built/
└── relations_final/
  ├── ohm_relation_entities.jsonl
  └── ohm_relation_hints.jsonl
```

## Stage breakdown

| Stage | Command | What it does |
| --- | --- | --- |
| `extract_subgraph` | `borders extract-subgraph` | Reads an existing global `overpass.json`, extracts a seed-centered OHM relation subgraph, and materializes a reduced `raw/overpass.json` plus raw shards |
| `fetch` | `borders fetch` | Downloads the Overpass payload and splits it into raw relation shards |
| `parse` | `borders parse` | Parses each raw shard into polity records (`ProcessPoolExecutor`) |
| `enrich` | `borders enrich` | Resolves Wikidata QIDs via SPARQL; optionally also searches by name |
| `build` | `borders build` | Maps each parsed/enriched shard through the polity mapper and merges to `final/` |
| `run` | `borders run` | Convenience: runs all four stages in sequence |

Relation stages are tracked separately in `manifest.json` under `relation_stages`:

| Relation stage | Command | What it does |
| --- | --- | --- |
| `scan` | `borders relations-scan` | Extracts predecessor, successor, and event relation candidates from parsed shards |
| `enrich` | `borders relations-enrich` | Enriches relation targets with Wikidata and Wikipedia metadata |
| `build` | `borders relations-build` | Emits importer-ready relation entity and hint JSONL files |
| full run | `borders relations-run` | Convenience: runs relation scan, enrich, and build in sequence |

`--resume` skips any artifact that already exists on disk.  
`--force` overwrites existing artifacts for the current stage.

## Country subgraph extraction

Use `extract-subgraph` when you already have a global OHM dump and want a smaller country-centered relation graph for downstream parse, enrich, build, and relation stages.

```powershell
py -m pipeline borders extract-subgraph \
  --input output/ohm_borders/global-2026-04-14/raw/overpass.json \
  --seed-name "Roman Empire" \
  --run-id roman-empire-subgraph \
  --max-depth 3 \
  --max-nodes 400 \
  --resume

py -m pipeline borders parse --run-id roman-empire-subgraph --resume
py -m pipeline borders enrich --run-id roman-empire-subgraph --resume --enrich-names
py -m pipeline borders build --run-id roman-empire-subgraph --resume
py -m pipeline borders relations-run --run-id roman-empire-subgraph --resume
```

Subset runs also write:

```text
output/ohm_borders/<run_id>/subgraph/
├── seed.json
├── graph_edges.jsonl
└── closure_report.json
```

See `docs/implementation-docs/ohm_country_subgraph_runbook.md` for the full first-run and second-run workflow.

## Running the full pipeline

```powershell
# 1. Fetch — downloads ~3 GB Overpass payload and shards it (~14 min on first run)
py -m pipeline borders fetch --run-id global-2026-04-15

# 2. Parse — CPU-bound, runs shards in parallel (~90 min for 18 shards on 8 cores)
py -m pipeline borders parse --run-id global-2026-04-15 --resume --parse-workers 8

# 3. Enrich — resolves Wikidata QIDs; --enrich-names also searches by name
py -m pipeline borders enrich --run-id global-2026-04-15 --enrich-names

# 4. Build — I/O-bound, very fast
py -m pipeline borders build --run-id global-2026-04-15 --resume

# Or run all stages at once
py -m pipeline borders run --run-id global-2026-04-15 --parse-workers 8 --enrich-names

# 5. Build relation outputs after country entities exist
py -m pipeline borders relations-run --run-id global-2026-04-15 --resume
```

To resume after an interruption, pass `--resume` to any stage — already-written shards are skipped.  
If Wikidata enrichment is not needed, skip the enrich step and go straight from parse to build.

## Name-based enrichment

The `--enrich-names` flag in the `enrich` stage searches Wikidata by `name` for any polity records that still lack a `wikidata_id` after SPARQL matching. Matched records are hydrated through the normal SPARQL enrichment path and tagged with `_wikidata_match_source: "name_search"` for audit purposes.

You can also run name enrichment as a post-processing step on any existing output file:

```powershell
py -m pipeline borders enrich-output-names \
  --input  output/ohm_borders/global-2026-04-15/final/ohm_borders.jsonl \
  --output output/ohm_borders_enriched.jsonl
```

## Key CLI options

| Flag | Default | Description |
| --- | --- | --- |
| `--run-id ID` | auto | Deterministic run ID used as the artifact directory name |
| `--artifact-dir PATH` | `output/ohm_borders/<run_id>` | Override artifact root |
| `--query-file PATH` | bundled query | Override the Overpass QL query file |
| `--raw-shard-size N` | `200` | Relations per raw fetch shard |
| `--parsed-shard-size N` | `100` | Polities per parsed shard |
| `--parse-workers N` | `cpu_count() - 1` | Parallel parse processes |
| `--build-workers N` | `cpu_count() - 1` | Parallel build processes |
| `--enrich-workers N` | `4` | Parallel Wikidata enrichment threads |
| `--enrich-batch-size N` | `50` | QIDs per SPARQL batch |
| `--enrich-names` | off | Also search Wikidata by name for missing QIDs |
| `--resume` | off | Skip artifacts that already exist |
| `--force` | off | Overwrite existing artifacts |

## Importing into Laravel

```powershell
$batchId = "global-$(Get-Date -Format 'yyyy-MM-dd')"
$jsonl    = "output/ohm_borders/$batchId/final/ohm_borders.jsonl"

Copy-Item $jsonl api/storage/app/ohm_borders_global.jsonl

docker compose -f docker/docker-compose.yml exec app `
  php -d memory_limit=1024M artisan pipeline:import-borders `
    /var/www/html/storage/app/ohm_borders_global.jsonl `
    --sync "--batch-id=$batchId"
```

Drop `--sync` to process the import asynchronously via the queue.

## Importing relation outputs into Laravel

Run the relation import only after the country/entity import has completed for the same batch.

```powershell
$batchId = "global-$(Get-Date -Format 'yyyy-MM-dd')"
$relationsDir = "output/ohm_borders/$batchId/relations_final"

docker compose -f docker/docker-compose.yml exec app `
  php -d memory_limit=1024M artisan pipeline:import-border-relations `
    /var/www/html/$relationsDir `
    --sync "--batch-id=$batchId"
```

Use `--skip-resolve` to stage hints during large loads and run one resolver pass later.

## Full OHM import runbook

```powershell
# 1. Produce country/entity outputs.
py -m pipeline borders run --run-id global-2026-04-15 --parse-workers 8 --enrich-names

# 2. Import country entities into Laravel.
docker compose -f docker/docker-compose.yml exec app `
  php -d memory_limit=1024M artisan pipeline:import-borders `
    /var/www/html/output/ohm_borders/global-2026-04-15/final/ohm_borders.jsonl `
    --sync --batch-id=global-2026-04-15

# 3. Produce relation outputs from the same run.
py -m pipeline borders relations-run --run-id global-2026-04-15 --resume

# 4. Import relation entities and resolve relationships.
docker compose -f docker/docker-compose.yml exec app `
  php -d memory_limit=1024M artisan pipeline:import-border-relations `
    /var/www/html/output/ohm_borders/global-2026-04-15/relations_final `
    --sync --batch-id=global-2026-04-15
```

Optional verification after import:

```bash
docker compose -f docker/docker-compose.yml exec app \
  php artisan tinker --execute "echo App\Models\Entity::query()->where('created_by', 'borders:global-' . now()->format('Y-m-d'))->count() . PHP_EOL;"
```

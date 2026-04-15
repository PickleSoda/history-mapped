# WikiGlobe Data Pipeline

Wikipedia / Wikidata scraper and data population tool for the WikiGlobe historical atlas.

## Quick Start

```bash
cd pipeline
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env       # fill in API keys
```

## How It Works (Two Phases)

**Phase 1 — Python scraper → JSONL files (local, no DB).** Scrapes Wikidata/Wikipedia and writes `.jsonl` files to `pipeline/output/`. Nothing touches Postgres.

**Phase 2 — Laravel import → Postgres.** An artisan command reads the JSONL files, dispatches queued jobs that create entities/relationships in the database.

## Usage

### 1a. Scrape by type / group

```bash
# Scrape a single entity type (outputs JSONL to output/)
python -m pipeline scrape --type political_entity --limit 100

# Scrape all types in a group
python -m pipeline scrape --group POLITY --limit 50

# Scrape with time range filter
python -m pipeline scrape --type event_battle --start-year -500 --end-year 1500
```

### 1b. Scrape by topic (graph walk)

Scrape a specific subject and everything connected to it, across all entity types:

```bash
# Search by name — resolves to a Wikidata QID automatically
python -m pipeline topic "Late Bronze Age Collapse"

# Or pass a QID directly
python -m pipeline topic Q484954

# Control walk depth and entity limit
python -m pipeline topic "Roman Empire" --depth 3 --limit 500

# Skip Wikipedia enrichment for a faster run
python -m pipeline topic "Silk Road" --skip-wikipedia

# Skip entities that don't map to any of the 30 types
python -m pipeline topic Q484954 --skip-untyped
```

The topic command starts from a seed entity and follows linked Wikidata
properties (participants, locations, causes, effects, parts, etc.) via BFS.
Each discovered item is classified into one of three buckets:

- Regular entities (30 WikiGlobe types) → `output/topic_<slug>.jsonl`
- Reference-table items (eras, broad regions, seas, etc.) → `output/topic_<slug>_ref.jsonl`
- Truly unclassified items → `output/topic_<slug>_untyped.jsonl`

When importing with `php artisan pipeline:import ... --all`, Laravel skips both
`*_ref.jsonl` and `*_untyped.jsonl` so only canonical entities are created.

### 2. Import Wikidata entities into Laravel

```bash
# Copy output to api storage
cp output/*.jsonl ../api/storage/app/pipeline/

# Import a single file
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:import storage/app/pipeline/political_entity.jsonl

# Import all files
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:import storage/app/pipeline/ --all
```

### 3. OHM Borders

The borders pipeline fetches all `admin_level=2` relations from OpenHistoricalMap,
parses them into polity records, and produces an importer-ready JSONL file.

The pipeline is split into discrete stages. Each stage writes artifacts under
`output/ohm_borders/<run_id>/` and records progress in `manifest.json`, so a
partially completed run can be resumed without redoing finished work.

```text
output/ohm_borders/<run_id>/
├── manifest.json
├── raw/
│   ├── overpass.json          # full Overpass payload (may be several GB)
│   └── raw-NNNNN.jsonl        # relation-only shards split for parallel parse
├── parsed/
│   └── parsed-NNNNN.jsonl     # polity records, 100 per shard by default
├── built/
│   └── built-NNNNN.jsonl      # mapper output, ready for import
└── final/
    └── ohm_borders.jsonl      # merged output file
```

#### Stage breakdown

| Stage | Command | What it does |
|---|---|---|
| `fetch` | `borders fetch` | Downloads the Overpass payload and splits it into raw relation shards |
| `parse` | `borders parse` | Parses each raw shard into polity records using a `ProcessPoolExecutor` |
| `build` | `borders build` | Maps each parsed shard through the polity mapper and merges to `final/` |
| `enrich` | `borders enrich` | Resolves Wikidata QIDs via SPARQL metadata enrichment; with `--enrich-names` also searches by name for missing QIDs |

`--resume` skips any artifact that already exists on disk.  
`--force` overwrites existing artifacts for the current stage.

**Name-based enrichment (optional):** To also back-fill missing Wikidata IDs by name search during the enrich stage:

```powershell
py -m pipeline borders enrich --run-id global-2026-04-15 --enrich-names
```

This searches Wikidata by `name` for any records still lacking a `wikidata_id`, hydrates matched QIDs through normal SPARQL enrichment, and writes a `_wikidata_match_source` field for audit purposes.

#### Key CLI options

| Flag | Default | Description |
|---|---|---|
| `--parse-workers N` | `cpu_count() - 1` | Parallel parse processes |
| `--parsed-shard-size N` | `100` | Polities per parsed shard |
| `--raw-shard-size N` | `200` | Relations per raw shard |
| `--build-workers N` | `cpu_count() - 1` | Parallel build processes |
| `--enrich-workers N` | `4` | Parallel Wikidata enrichment threads |
| `--enrich-batch-size N` | `50` | QIDs per SPARQL batch |

#### Running the full pipeline

```powershell
# 1. Fetch — downloads ~3 GB Overpass payload and shards it (~14 min on first run)
py -m pipeline borders fetch --run-id global-2026-04-15

# 2. Parse — CPU-bound, runs shards in parallel across all cores (~90 min for 18 shards on 8 cores)
py -m pipeline borders parse --run-id global-2026-04-15 --resume --parse-workers 8

# 3. Entrich - Resolves Wikidata QIDs via SPARQL metadata enrichment
py -m pipeline borders enrich --run-id global-2026-04-15 --enrich-names

# 4. Build — I/O-bound, very fast
py -m pipeline borders build --run-id global-2026-04-15 --resume --build-workers 8
```

To resume after an interruption, pass `--resume` to any stage — already-written
shards are skipped automatically.

If Wikidata enrichment is not needed, simply skip the enrich step and proceed directly from parse to build.

#### Importing into Laravel

```powershell
$batchId = "global-$(Get-Date -Format 'yyyy-MM-dd')"
$jsonl    = "output/ohm_borders/$batchId/final/ohm_borders.jsonl"

Copy-Item $jsonl api/storage/app/ohm_borders_global.jsonl

docker compose -f docker/docker-compose.yml exec app `
  php -d memory_limit=1024M artisan pipeline:import-borders `
    /var/www/html/storage/app/ohm_borders_global.jsonl `
    --sync "--batch-id=$batchId"
```

Drop `--sync` to process the import asynchronously via the queue instead.

Optional verification after import:

```bash
docker compose -f docker/docker-compose.yml exec app \
  php artisan tinker --execute "echo App\Models\Entity::query()->where('created_by', 'borders:global-' . now()->format('Y-m-d'))->count() . PHP_EOL;"
```

### 4. Generate embeddings

```bash
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:embeddings --pending --chunk=50
```

## Environment settings

```dotenv
OPENAI_SUMMARY_MODEL=gpt-4o-mini
SUMMARY_USE_LLM=false          # set true to use LLM for summary truncation
SUMMARY_MAX_CHARS=420
WIKIPEDIA_EXTRACT_MAX_CHARS=8000
```

## Architecture

See [docs/data_pipeline_architecture.md](../docs/data_pipeline_architecture.md) for the full design.

```text
pipeline/
├── __init__.py
├── __main__.py           # CLI entry point
├── config.py             # Settings, env loading
├── requirements.txt
├── .env.example
├── scraper/
│   ├── __init__.py
│   ├── wikidata.py       # SPARQL queries against Wikidata
│   ├── wikipedia.py      # Wikipedia API content extraction
│   └── topic.py          # BFS graph-walk scraper from a seed QID
├── mapper/
│   ├── __init__.py
│   ├── entity_mapper.py  # Raw wiki data → entity schema
│   ├── relationship_mapper.py  # Wikidata properties → 76 relationship types
│   └── type_configs.py   # Per-entity-type field mappings
├── dedup/
│   ├── __init__.py
│   └── deduplicator.py   # Wikidata ID + fuzzy name dedup
├── embeddings/
│   ├── __init__.py
│   └── generator.py      # Standalone embedding generator (optional Python-side)
├── ohm_borders/          # OHM borders pipeline (fetch/parse/build/enrich)
├── queries/
│   ├── polity.sparql
│   ├── place.sparql
│   ├── event.sparql
│   ├── economy.sparql
│   └── culture.sparql
└── output/               # Generated JSONL files (gitignored)
    └── .gitkeep
```

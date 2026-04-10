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

**Example: Late Bronze Age Collapse** would discover:

- The collapse event itself (`event_war` or untyped)
- Sea Peoples, Hittite Empire, Mycenaean Greece (`political_entity`)
- Troy, Ugarit, Hattusa (`city`)
- Related battles (`event_battle`)
- Trade routes that were disrupted (`trade_route`)
- Key persons like Ramesses III (`person`)

When importing with `php artisan pipeline:import ... --all`, Laravel skips both
`*_ref.jsonl` and `*_untyped.jsonl` so only canonical entities are created.

## Structured Extraction Enhancements

The mapper now preserves more high-value structured fields from Wikidata:

- **Temporal fields**: uses `P571/P576` plus `P580/P582/P585` fallbacks to populate `temporal_start` / `temporal_end` with normalized year strings.
- **Location name**: resolves from explicit fields or linked location properties (`P276`, then `P131`, then `P17`).
- **Geometry fallback**: uses direct `P625` coordinates first, then falls back to coordinates of linked location entities when available.
- **Territory geometry**: if Wikidata provides `P3896` geoshape data, the pipeline fetches the linked Commons `Data:*.map` file and converts it into GeoJSON for `territory_geom`.
- **Long text retention**: stores richer article text in `attributes._wikipedia_extract` while keeping `summary` short.

## Summary Shortening Strategy (Rule-first + Optional LLM)

The pipeline now uses a hybrid summarization approach:

1. **Rule-based shortening (default)** — sentence-aware truncation to `SUMMARY_MAX_CHARS`.
2. **Optional LLM fallback** — only used when `SUMMARY_USE_LLM=true` and `OPENAI_API_KEY` is set.

This keeps ingestion deterministic and low-cost by default, while allowing
higher-quality compression for very long extracts when needed.

### New environment settings

```dotenv
OPENAI_SUMMARY_MODEL=gpt-4o-mini
SUMMARY_USE_LLM=false
SUMMARY_MAX_CHARS=420
WIKIPEDIA_EXTRACT_MAX_CHARS=8000
```

### 2. Import into Laravel (from host or inside Docker)

```bash
# Copy output to api storage
cp output/*.jsonl ../api/storage/app/pipeline/

# Run the Laravel import command
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:import storage/app/pipeline/political_entity.jsonl

# Or import all files
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:import storage/app/pipeline/ --all
```

### 2a. Full OHM border fetch and Laravel import

Use these commands to run the full OHM `admin_level=2` border extract and then populate the Laravel app.

```bash
# From the repo root, create the full OHM border JSONL.
# This is a large Overpass query and can take a long time to finish.
py -m pipeline borders --output output/ohm_borders_global.jsonl

# Make the JSONL visible inside the Laravel Docker container.
Copy-Item output/ohm_borders_global.jsonl api/storage/app/ohm_borders_global.jsonl

# Import synchronously into Laravel from the container-visible path.
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:import-borders \
    /var/www/html/storage/app/ohm_borders_global.jsonl \
    --sync \
    --batch-id=global-$(Get-Date -Format yyyy-MM-dd)
```

If you want the queue to process the import asynchronously instead, drop `--sync`:

```bash
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:import-borders \
    /var/www/html/storage/app/ohm_borders_global.jsonl \
    --batch-id=global-$(Get-Date -Format yyyy-MM-dd)
```

Optional verification after import:

```bash
docker compose -f docker/docker-compose.yml exec app \
  php artisan tinker --execute "echo App\\Models\\Entity::query()->where('created_by', 'borders:global-' . now()->format('Y-m-d'))->count() . PHP_EOL;"
```

### 3. Generate embeddings

```bash
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:embeddings --pending --chunk=50
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
├── queries/
│   ├── polity.sparql
│   ├── place.sparql
│   ├── event.sparql
│   ├── economy.sparql
│   └── culture.sparql
└── output/               # Generated JSONL files (gitignored)
    └── .gitkeep
```

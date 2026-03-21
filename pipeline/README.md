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

## Usage

### 1. Scrape entities from Wikidata + Wikipedia

```bash
# Scrape a single entity type (outputs JSONL to output/)
python -m pipeline.scrape --type political_entity --limit 100

# Scrape all types in a group
python -m pipeline.scrape --group POLITY --limit 50

# Scrape with time range filter
python -m pipeline.scrape --type event_battle --start-year -500 --end-year 1500
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

### 3. Generate embeddings

```bash
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:embeddings --pending --chunk=50
```

## Architecture

See [docs/data_pipeline_architecture.md](../docs/data_pipeline_architecture.md) for the full design.

```
pipeline/
├── __init__.py
├── __main__.py           # CLI entry point
├── config.py             # Settings, env loading
├── requirements.txt
├── .env.example
├── scraper/
│   ├── __init__.py
│   ├── wikidata.py       # SPARQL queries against Wikidata
│   └── wikipedia.py      # Wikipedia API content extraction
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

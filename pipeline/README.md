# WikiGlobe Data Pipeline

Wikidata/Wikipedia scraper and OHM borders pipeline for the WikiGlobe historical atlas.

## Quick Start

```bash
cd pipeline
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env       # fill in API keys
```

## How It Works

**Phase 1 — Python scraper → JSONL files (local, no DB).** Scrapes Wikidata/Wikipedia and writes `.jsonl` files to `pipeline/output/`. Nothing touches Postgres.

**Phase 2 — Laravel import → Postgres.** An artisan command reads the JSONL files and creates entities/relationships in the database.

## Typical commands

### Scrape Wikidata entities

```bash
python -m pipeline scrape --type political_entity --limit 100
python -m pipeline topic "Late Bronze Age Collapse"
```

→ See [wikidata/README.md](wikidata/README.md) for full usage, all options, and import steps.

### OHM Borders (full run)

```powershell
py -m pipeline borders fetch  --run-id global-2026-04-15
py -m pipeline borders parse  --run-id global-2026-04-15 --resume --parse-workers 8
py -m pipeline borders enrich --run-id global-2026-04-15 --enrich-names
py -m pipeline borders build  --run-id global-2026-04-15 --resume
```

→ See [ohm_borders/README.md](ohm_borders/README.md) for stage breakdown, options, and import steps.

### Generate embeddings

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

## Folder structure

```text
pipeline/
├── __init__.py
├── __main__.py           # Unified CLI dispatcher (backward-compat entry point)
├── config.py             # Settings and env loading
├── requirements.txt
├── .env.example
├── wikidata/             # Wikidata/Wikipedia scraping module
│   ├── README.md
│   ├── __main__.py       # CLI: scrape / topic / dedup
│   ├── scraper/          # SPARQL, Wikipedia API, topic BFS walker
│   ├── mapper/           # entity_mapper, relationship_mapper, type_configs
│   ├── dedup/            # Wikidata ID + fuzzy name deduplicator
│   ├── resolver/         # OHM geo-resolver
│   ├── embeddings/       # Optional Python-side embedding generator
│   └── queries/          # Per-type SPARQL templates
├── ohm_borders/          # OHM borders fetch / parse / enrich / build pipeline
│   └── README.md
└── output/               # Generated JSONL files (gitignored)
    └── .gitkeep
```

See [docs/data_pipeline_architecture.md](../docs/data_pipeline_architecture.md) for the full design.

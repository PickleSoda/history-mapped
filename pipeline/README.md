# history-mapped Data Pipeline

Wikidata/Wikipedia scraper and OHM borders pipeline for history-mapped.

All commands below assume your current working directory is the repository root. The top-level `python -m pipeline` entry point works from the repo root; it does not work from inside the `pipeline/` directory unless you adjust `PYTHONPATH` yourself.

## Quick Start

```powershell
py -m venv pipeline/.venv
.\pipeline\.venv\Scripts\Activate.ps1
pip install -r pipeline/requirements.txt
Copy-Item pipeline/.env.example pipeline/.env
```

On macOS or Linux:

```bash
python -m venv pipeline/.venv
source pipeline/.venv/bin/activate
pip install -r pipeline/requirements.txt
cp pipeline/.env.example pipeline/.env
```

## How It Works

**Phase 1 — Python pipeline → JSONL and OHM artifacts.** The pipeline scrapes Wikidata/Wikipedia, builds topic files, and runs staged OHM borders processing. With the default `pipeline/.env`, artifacts are written to the repository-level `output/` directory when commands are run from the repo root.

**Phase 2 — Laravel import → PostgreSQL.** Artisan commands read the generated files and create entities, stage relationship hints, resolve relationships, and generate embeddings.

## Typical Commands

### Wikidata and topic extraction

```powershell
py -m pipeline scrape --type political_entity --limit 100
py -m pipeline topic "Late Bronze Age Collapse"
py -m pipeline dedup output/political_entity.jsonl --check-db
```

See [wikidata/README.md](wikidata/README.md) for full usage, output buckets, and import steps.

### OHM borders full run

```powershell
py -m pipeline borders fetch  --run-id global-2026-04-15
py -m pipeline borders parse  --run-id global-2026-04-15 --resume --parse-workers 8
py -m pipeline borders enrich --run-id global-2026-04-15 --enrich-names
py -m pipeline borders build  --run-id global-2026-04-15 --resume
py -m pipeline borders relations-run --run-id global-2026-04-15 --resume
```

See [ohm_borders/README.md](ohm_borders/README.md) for stage breakdown, subgraph extraction, and Laravel import steps.

### OHM historical collections

```powershell
py -m pipeline collections build-xml-index --input output/map.xml --index-path output/ohm_collections/map.sqlite3 --force
py -m pipeline collections egypt-build --xml-index-path output/ohm_collections/map.sqlite3 --ohm-index-path output/ohm_borders/indexes/global-2026-04-14.sqlite3 --run-id egypt-historical-collection --force
py -m pipeline collections egypt-relations-run --run-id egypt-historical-collection --resume
```

See [../docs/implementation-docs/ohm-egypt-collection-runbook.md](../docs/implementation-docs/ohm-egypt-collection-runbook.md) for the streaming XML index workflow, point precedence rules, and Laravel import steps.

### Laravel-side import and embeddings

```bash
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:import storage/app/pipeline/ --all

docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:embeddings --pending --chunk=50
```

## Environment Settings

```dotenv
OPENAI_SUMMARY_MODEL=gpt-4o-mini
SUMMARY_USE_LLM=false
SUMMARY_MAX_CHARS=420
WIKIPEDIA_EXTRACT_MAX_CHARS=8000
OUTPUT_DIR=output
```

`OUTPUT_DIR` is resolved relative to the current working directory. In the repo's default workflow that means artifacts land in the root `output/` directory.

## Module Layout

```text
pipeline/
├── __init__.py
├── __main__.py           # Unified CLI dispatcher
├── config.py             # Settings and env loading
├── requirements.txt
├── .env.example
├── tests/                # Python tests for the pipeline
├── wikidata/             # scrape / topic / dedup pipeline
│   ├── README.md
│   ├── __main__.py
│   ├── dedup/
│   ├── embeddings/
│   ├── mapper/
│   ├── queries/
│   ├── resolver/
│   └── scraper/
└── ohm_borders/          # staged OHM borders and relations pipeline
    ├── README.md
    ├── artifacts.py
    ├── enricher.py
    ├── fetcher.py
    ├── index_builder.py
    ├── stage_*.py
    └── subgraph_extractor.py
```

See [../docs/implementation-docs/data_pipeline_architecture.md](../docs/implementation-docs/data_pipeline_architecture.md) for the current end-to-end pipeline architecture.

# history-mapped

An interactive historical atlas and editorial platform for mapping entities, events, relationships, and time-aware geography. The monorepo combines a Laravel backend and admin surface, a separate React customer SPA, and a Python pipeline for Wikidata and OpenHistoricalMap ingestion.

---

## Architecture

| Layer | Current Stack |
|-------|---------------|
| **API + Admin** | Laravel 13, PHP 8.4 container runtime, Inertia.js + React, PostgreSQL 16 with PostGIS + pgvector |
| **Customer Web** | React 19, Vite, TanStack Query, Axios |
| **Data Pipeline** | Python CLI for Wikidata/Wikipedia scraping, topic extraction, and staged OHM borders processing |
| **Infrastructure** | Docker Compose, Nginx, Redis, Mailpit, CloudBeaver, RedisInsight |

```text
history-mapped/
├── api/          # Laravel app, REST API, Inertia admin, queue and scheduler code
├── web/          # Standalone React SPA served by Vite
├── pipeline/     # Python scrape and OHM processing pipeline
├── output/       # Generated JSONL files and OHM pipeline artifacts
├── docker/       # Dockerfiles and docker-compose.yml
└── docs/         # Architecture, runbooks, schemas, plans, and model docs
```

---

## Prerequisites

- **Docker Desktop** (or Docker Engine + Compose v2)
- **pnpm** >= 10
- **Python 3.10+** if you plan to run anything under `pipeline/`
- **Git**

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/PickleSoda/history-mapped.git && cd history-mapped

# 2. Copy env files
cp api/.env.example api/.env

# Optional: only needed if you plan to run the Python pipeline
cp pipeline/.env.example pipeline/.env

# 3. Start the local stack
pnpm dev
```

This runs `docker compose -f docker/docker-compose.yml up`, which:
- installs Composer and pnpm dependencies via one-shot init containers
- starts PostgreSQL 16 with PostGIS and pgvector
- starts the Laravel app, Nginx, queue worker, and scheduler
- starts the Vite dev servers for the admin frontend and customer SPA
- starts Redis, Mailpit, CloudBeaver, and RedisInsight

If you need to rebuild images, run:

```bash
pnpm dev:build
```

### Service URLs

| Service | URL |
|---------|-----|
| **Laravel app / Admin panel** | http://localhost:8000 |
| **Customer web SPA** | http://localhost:5173 |
| **Admin Vite HMR** | http://localhost:5174 |
| **Mailpit** | http://localhost:8025 |
| **CloudBeaver** | http://localhost:8978 |
| **RedisInsight** | http://localhost:5540 |

The admin UI is served at `http://localhost:8000`. `http://localhost:5174` is the HMR server only.

### First-Run Setup

After containers are up, run migrations and seed the database:

```bash
docker compose -f docker/docker-compose.yml exec app php artisan migrate --seed
```

### Stopping

```bash
pnpm dev:down
```

---

## Common Commands

```bash
# Run the Laravel test suite
docker compose -f docker/docker-compose.yml exec app php artisan test

# Run a filtered Laravel test
docker compose -f docker/docker-compose.yml exec app php artisan test --filter=EntityControllerTest

# Type-check the frontend packages from Docker
pnpm typecheck

# List API routes
pnpm api:routes

# Run any artisan command
docker compose -f docker/docker-compose.yml exec app php artisan <command>

# Fresh database reset
docker compose -f docker/docker-compose.yml exec app php artisan migrate:fresh --seed
```

---

## Data Pipeline

All `python -m pipeline ...` examples assume your current working directory is the repository root.

```powershell
py -m venv pipeline/.venv
.\pipeline\.venv\Scripts\Activate.ps1
pip install -r pipeline/requirements.txt
```

Main entry points:

```powershell
py -m pipeline scrape --type political_entity --limit 100
py -m pipeline topic "Late Bronze Age Collapse"
py -m pipeline borders run --run-id global-2026-04-15 --parse-workers 8 --enrich-names
py -m pipeline borders relations-run --run-id global-2026-04-15 --resume
```

With the default `pipeline/.env`, pipeline outputs go to the repository-level `output/` directory when commands are run from the repo root.

Pipeline-specific docs:
- [pipeline/README.md](pipeline/README.md)
- [pipeline/wikidata/README.md](pipeline/wikidata/README.md)
- [pipeline/ohm_borders/README.md](pipeline/ohm_borders/README.md)

## OHM Borders Import Workflow

Run the country/entity import first, then the relation import for the same `run_id`.

```powershell
# 1. Build importer-ready country/entity output
py -m pipeline borders run --run-id global-2026-04-15 --parse-workers 8 --enrich-names

# 2. Import country entities into Laravel
docker compose -f docker/docker-compose.yml exec app `
  php -d memory_limit=1024M artisan pipeline:import-borders `
  /var/www/html/output/ohm_borders/global-2026-04-15/final/ohm_borders.jsonl `
  --sync --batch-id=global-2026-04-15

# 3. Build importer-ready relation outputs
py -m pipeline borders relations-run --run-id global-2026-04-15 --resume

# 4. Import relation entities, stage hints, and resolve relationships
docker compose -f docker/docker-compose.yml exec app `
  php -d memory_limit=1024M artisan pipeline:import-border-relations `
  /var/www/html/output/ohm_borders/global-2026-04-15/relations_final `
  --sync --batch-id=global-2026-04-15
```

For larger imports, replace the final step with `--skip-resolve`, then run one resolver pass after all relation hints are staged.

---

## Environment Variables

Docker Compose defaults are defined in `docker/docker-compose.yml`. Override them via a project-root `.env` file or exported environment variables.

| Variable | Default | Description |
|----------|---------|-------------|
| `FORWARD_NGINX_PORT` | `8000` | Laravel app and admin panel port |
| `FORWARD_WEB_PORT` | `5173` | Customer web port |
| `FORWARD_ADMIN_PORT` | `5174` | Admin Vite HMR port |
| `FORWARD_DB_PORT` | `5432` | PostgreSQL port |
| `FORWARD_REDIS_PORT` | `6379` | Redis port |
| `FORWARD_MAILPIT_PORT` | `8025` | Mailpit UI port |
| `FORWARD_CLOUDBEAVER_PORT` | `8978` | CloudBeaver port |
| `FORWARD_REDISINSIGHT_PORT` | `5540` | RedisInsight port |
| `HISTORY_MAPPED_DB_IMAGE` | `history-mapped-db:16-pgvector-v0.8.2` | Optional prebuilt DB image tag to skip local pgvector compilation |
| `POSTGRES_DB` | `history-mapped` | Database name |
| `POSTGRES_USER` | `history-mapped` | Database user |
| `POSTGRES_PASSWORD` | `secret` | Database password |

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/README.md](docs/README.md) | Documentation index and guidance on which docs describe current state |
| [docs/architecture/system-overview.md](docs/architecture/system-overview.md) | Runtime surfaces, routing, and repository architecture |
| [docs/implementation-docs/setup.md](docs/implementation-docs/setup.md) | Local setup and development workflow |
| [pipeline/README.md](pipeline/README.md) | Python pipeline overview and command entry points |
| [docs/architecture/data-pipeline.md](docs/architecture/data-pipeline.md) | Detailed scrape, OHM, import, and embedding pipeline architecture |
| [docs/entity-model/README.md](docs/entity-model/README.md) | Entity model overview and companion references |
| [docs/schemas/README.md](docs/schemas/README.md) | Pipeline and API schema documentation |
| [docs/implementation-docs/ohm-country-subgraph-runbook.md](docs/implementation-docs/ohm-country-subgraph-runbook.md) | OHM country subgraph extraction workflow |
| [docs/TODO.md](docs/TODO.md) | Current task backlog |

---

## Project Structure Details

### `api/` — Laravel Backend and Admin

- REST API lives under `/api/v1`
- Inertia admin UI is served from Laravel at `http://localhost:8000`
- Admin-side React includes the richer historical map, timeline, relationship, and reference-table tooling

### `web/` — Standalone Customer SPA

- Vite + React 19 app with TanStack Query and Axios
- Current implementation is a small bootstrap client that checks `GET /api/v1/health`
- Prepared for cookie-based Laravel auth with `withCredentials: true` and CSRF helper support

### `pipeline/` — Python Ingestion and Processing

- `wikidata/` handles `scrape`, `topic`, and `dedup`
- `ohm_borders/` handles staged OHM fetch, parse, enrich, build, and relation generation
- Laravel consumes generated artifacts through `pipeline:import`, `pipeline:import-borders`, `pipeline:import-border-relations`, and `pipeline:embeddings`

### `output/` — Generated Artifacts

- Topic and type-based JSONL output from the Wikidata pipeline
- `ohm_borders/<run_id>/...` artifacts for staged OHM processing and import

---

## License

Private repository.

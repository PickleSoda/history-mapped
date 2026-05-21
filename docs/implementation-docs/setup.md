# history-mapped Setup Guide

This guide describes how to run the existing monorepo locally. It is not a scaffold-from-scratch guide.

## Prerequisites

- Docker Desktop or Docker Engine with Compose v2
- pnpm >= 10
- Python 3.10+ for the `pipeline/` workflow
- Git

## Repository Layout

```text
history-mapped/
├── api/          # Laravel app, REST API, Inertia admin, queue and scheduler code
├── web/          # Standalone React SPA served by Vite
├── pipeline/     # Python scrape and OHM processing pipeline
├── output/       # Generated JSONL files and OHM stage artifacts
├── docker/       # Dockerfiles and docker-compose.yml
└── docs/         # Architecture, runbooks, schemas, plans, and model docs
```

## 1. Boot the Local Stack

From the repository root:

```bash
cp api/.env.example api/.env

# Optional: only needed if you plan to run the Python pipeline
cp pipeline/.env.example pipeline/.env

pnpm dev
```

This starts the full Docker-based app stack and leaves logs attached to the terminal.

If you need image rebuilds, run:

```bash
pnpm dev:build
```

After the containers are healthy, run the initial database setup:

```bash
docker compose -f docker/docker-compose.yml exec app php artisan migrate --seed
```

To stop the stack:

```bash
pnpm dev:down
```

## 2. Docker Services

File: `docker/docker-compose.yml`

| Service | Port | Purpose |
|---------|------|---------|
| **`composer-install`** | - | One-shot Composer install init container |
| **`app`** | - | PHP-FPM runtime for Laravel |
| **`nginx`** | `8000` | HTTP entry point for Laravel and the admin UI |
| **`pnpm-install`** | - | One-shot pnpm install init container |
| **`web`** | `5173` | Customer SPA Vite dev server |
| **`vite-admin`** | `5174` | Admin HMR server |
| **`db`** | `5432` | PostgreSQL with PostGIS + pgvector |
| **`redis`** | `6379` | Cache, sessions, and queues |
| **`queue`** | - | `php artisan queue:work` |
| **`scheduler`** | - | Laravel scheduler loop |
| **`mailpit`** | `8025` | Mail testing UI |
| **`cloudbeaver`** | `8978` | Database inspection UI |
| **`redisinsight`** | `5540` | Redis inspection UI |

Important runtime notes:

- Open the admin UI at `http://localhost:8000`.
- `http://localhost:5174` is only the admin HMR server, not the admin UI entry point.
- Day-to-day PHP and Node work should run through Docker. The Python pipeline is the main host-side workflow.

## 3. Day-to-Day Commands

From the repository root:

```bash
# Laravel tests
docker compose -f docker/docker-compose.yml exec app php artisan test

# Filtered Laravel test
docker compose -f docker/docker-compose.yml exec app php artisan test --filter=EntityControllerTest

# Workspace type checks
pnpm typecheck

# Route list
pnpm api:routes

# Any artisan command
docker compose -f docker/docker-compose.yml exec app php artisan <command>

# Fresh database reset
docker compose -f docker/docker-compose.yml exec app php artisan migrate:fresh --seed
```

## 4. Route Layout

The repo currently uses these route files:

| File | Responsibility |
|------|----------------|
| **`api/routes/web.php`** | Welcome page, dashboard, entity CRUD pages, relationship routes, geometry-period routes, reference-table pages |
| **`api/routes/api.php`** | `/api/v1` JSON API including health check, public reads, and Sanctum-protected writes |
| **`api/routes/settings.php`** | Authenticated profile, security, and appearance pages |
| **`api/routes/console.php`** | Console route definitions |

Laravel Fortify registers the auth endpoints; there is no separate `routes/auth.php` file in this repository.

## 5. Frontend Surfaces

### `api/` admin frontend

- Inertia.js + React rendered by Laravel
- Richer implementation surface today: historical map viewer, geometry editing, timelines, entity relationships, and reference tables
- Served at `http://localhost:8000`

### `web/` standalone SPA

- React 19 + Vite + TanStack Query + Axios
- Current implementation is intentionally small: a single home route that checks `GET /api/v1/health`
- Prepared for cookie-based Laravel auth via `withCredentials: true` and a Sanctum CSRF helper
- Served at `http://localhost:5173`

## 6. Python Pipeline Workflow

Create and activate a virtual environment, then run all pipeline commands from the repository root:

```powershell
py -m venv pipeline/.venv
.\pipeline\.venv\Scripts\Activate.ps1
pip install -r pipeline/requirements.txt
```

Typical commands:

```powershell
py -m pipeline scrape --type political_entity --limit 100
py -m pipeline topic "Late Bronze Age Collapse"
py -m pipeline borders run --run-id global-2026-04-15 --parse-workers 8 --enrich-names
py -m pipeline borders relations-run --run-id global-2026-04-15 --resume
```

With the default `pipeline/.env`, `OUTPUT_DIR=output`, so running from the repo root writes artifacts into the repository-level `output/` directory.

Pipeline verification should use the Python test runner directly:

```powershell
py -m pytest pipeline/tests
```

## 7. Generated Artifacts

Generated data is not confined to the `pipeline/` directory.

- Topic and type-based JSONL files are written under `output/`.
- OHM staged runs are written under `output/ohm_borders/<run_id>/`.
- Laravel import commands read those artifacts back from mounted paths such as `/var/www/html/output/...` inside the `app` container.

## 8. Current Working Conventions

- Use Docker for Laravel, Composer, pnpm, Vite, queue, and scheduler work.
- Use repo-root `pnpm` scripts for workspace-level tasks.
- Use repo-root `py -m pipeline ...` commands for the Python pipeline.
- Prefer the docs in [../../README.md](../../README.md), [../architecture_overview.md](../architecture_overview.md), and [../../pipeline/README.md](../../pipeline/README.md) over older planning docs when there is a discrepancy.
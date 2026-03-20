# WikiGlobe

An interactive historical atlas mapping entities, events, and relationships across time and geography. Built on open infrastructure — PostgreSQL/PostGIS/pgvector, MapLibre GL JS, and OpenHistoricalMap.

---

## Architecture

| Layer | Stack |
|-------|-------|
| **API** | Laravel 13, PHP 8.4, PostgreSQL 16 (PostGIS + pgvector) |
| **Admin Panel** | Inertia.js + React (inside Laravel) |
| **Web Frontend** | React SPA, MapLibre GL JS, TanStack Query |
| **Infrastructure** | Docker Compose, Redis, Nginx |

```
wikiglobe/
├── api/          # Laravel backend — REST API + Inertia admin panel
├── web/          # React SPA — customer-facing map interface
├── docker/       # Docker Compose + Dockerfiles
└── docs/         # Architecture docs and specs
```

---

## Prerequisites

- **Docker Desktop** (or Docker Engine + Compose v2)
- **pnpm** ≥ 10 (`npm install -g pnpm`)
- **Git**

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/PickleSoda/WG.git && cd WG

# 2. Copy env file
cp api/.env.example api/.env

# 3. Start all services (builds images, installs deps, starts containers)
pnpm dev
```

This runs `docker compose -f docker/docker-compose.yml up --build`, which:
- Installs Composer and pnpm dependencies (one-shot init containers)
- Starts PostgreSQL 16 with PostGIS + pgvector extensions
- Starts the Laravel app (PHP-FPM + Nginx), queue worker, and scheduler
- Starts Vite dev servers for the admin panel and web frontend
- Starts Redis, Mailpit, CloudBeaver, and RedisInsight

### Service URLs

| Service | URL |
|---------|-----|
| **API / Admin Panel** | http://localhost:8000 |
| **Web Frontend** | http://localhost:5173 |
| **Admin Vite HMR** | http://localhost:5174 |
| **Mailpit** | http://localhost:8025 |
| **CloudBeaver (DB UI)** | http://localhost:8978 |
| **RedisInsight** | http://localhost:5540 |

### First-Run Setup

After containers are up, run migrations and seed the database:

```bash
docker exec wikiglobe-app-1 php artisan migrate
docker exec wikiglobe-app-1 php artisan db:seed
```

### Stopping

```bash
pnpm dev:down
```

---

## Common Commands

```bash
# Run tests
docker exec wikiglobe-app-1 php artisan test

# Run a specific test file
docker exec wikiglobe-app-1 php artisan test --filter=EntityControllerTest

# List API routes
pnpm api:routes

# Artisan commands
docker exec wikiglobe-app-1 php artisan <command>

# Tinker (Laravel REPL)
docker exec -it wikiglobe-app-1 php artisan tinker

# Fresh migrate + seed
docker exec wikiglobe-app-1 php artisan migrate:fresh --seed
```

---

## Environment Variables

Docker Compose defaults are defined in `docker/docker-compose.yml`. Override via a `.env` file in the project root or by setting env vars.

| Variable | Default | Description |
|----------|---------|-------------|
| `FORWARD_NGINX_PORT` | `8000` | API / admin panel port |
| `FORWARD_WEB_PORT` | `5173` | Web frontend port |
| `FORWARD_ADMIN_PORT` | `5174` | Admin Vite HMR port |
| `FORWARD_DB_PORT` | `5432` | PostgreSQL port |
| `FORWARD_REDIS_PORT` | `6379` | Redis port |
| `FORWARD_MAILPIT_PORT` | `8025` | Mailpit UI port |
| `FORWARD_CLOUDBEAVER_PORT` | `8978` | CloudBeaver port |
| `FORWARD_REDISINSIGHT_PORT` | `5540` | RedisInsight port |
| `POSTGRES_DB` | `wikiglobe` | Database name |
| `POSTGRES_USER` | `wikiglobe` | Database user |
| `POSTGRES_PASSWORD` | `secret` | Database password |

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/setup.md](docs/setup.md) | Full setup guide — repo structure, Docker services, artisan workflows |
| [docs/architecture_overview.md](docs/architecture_overview.md) | Foundational architecture — three-layer model, tech stack rationale |
| [docs/entity_specification.md](docs/entity_specification.md) | Entity data model — 30 types, 5 groups, enums, JSONB attribute schemas |
| [docs/web_implementation_architecture.md](docs/web_implementation_architecture.md) | Web frontend architecture — MapLibre, data fetching, rendering strategy |
| [docs/game_inspired_ui_ux.md](docs/game_inspired_ui_ux.md) | UI/UX design guide — Civ VI and Total War patterns |
| [docs/reference_tables.md](docs/reference_tables.md) | Historical periods, regions, calendars, writing systems |
| [docs/TODO.md](docs/TODO.md) | Current task backlog |
| [docs/plans/](docs/plans/) | Implementation plans for upcoming features |

---

## Project Structure Details

### `api/` — Laravel Backend

- **Actions** (`app/Actions/`) — Domain logic (list, create, update entities)
- **Builders** (`app/Builders/`) — Custom Eloquent query builders (spatial, temporal, JSONB)
- **DTOs** (`app/DTOs/`) — Data transfer objects for validation and transformation
- **Models** (`app/Models/`) — Eloquent models with PostGIS and pgvector casts
- **Enums** (`app/Enums/`) — PHP-backed enums matching PostgreSQL enum types

### `web/` — React SPA

- MapLibre GL JS with OpenHistoricalMap base tiles
- TanStack Query for server state
- Zustand for UI state
- shadcn/ui + Tailwind CSS

---

## License

Private repository.

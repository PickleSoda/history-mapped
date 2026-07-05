# api — Laravel Backend & Inertia Admin

Laravel 13 / PHP 8.4 application serving two surfaces behind Nginx:

- **JSON REST API** — `routes/api.php`, versioned under `/api/v1`, controllers in
  `app/Http/Api`. Consumed by the public Atlas SPA (`../web`).
- **Inertia.js + React admin** — `routes/web.php`, controllers in `app/Http/Controllers`,
  React app under `resources/js`. Entity/relationship/chronicle editors, map editor, and the
  route-bound AI editing agent.

Persistence is PostgreSQL 16 with PostGIS (geometry) and pgvector (embeddings).

## Running

Everything runs in Docker — **no host-local PHP/Composer**. From the repo root:

```bash
pnpm dev                                                  # whole stack
docker compose -f docker/docker-compose.yml exec app php artisan <cmd>
```

Admin + API: `http://localhost:8000` · admin Vite HMR: `http://localhost:5174`.

## Commands (inside the `app` container)

```bash
php artisan test                        # PHPUnit suite
composer ci:check                       # JS lint + prettier + tsc + tests (mirrors CI)
composer lint                           # Pint (PHP) autofix
npm run lint && npm run types:check     # admin frontend (resources/js)
php artisan wayfinder:generate --with-form   # regen TS route/action helpers
```

## Architecture conventions

- **Write/business logic lives in Action classes** (`app/Actions/{Entity,Relationship,Chronicle,Source,Timeline,EntityGeoRef}`) — controllers stay thin.
- Supporting layers: `app/Services`, `app/Builders`, `app/DTOs`, `app/Casts`, `app/Observers`,
  `app/Jobs` (async via the `queue` container; cron via `scheduler`).
- `resources/js/actions/**` and `resources/js/routes/**` are **generated** by Wayfinder — regenerate, never hand-edit.
- Pipeline artifacts are ingested via `pipeline:import*` artisan commands; embeddings via `pipeline:embeddings`.

## Docs

- [docs/architecture/system-overview.md](../docs/architecture/system-overview.md) — runtime surfaces and routing
- [docs/architecture/admin-map-editor.md](../docs/architecture/admin-map-editor.md) — admin editor and map UI
- [docs/implementation-docs/admin-ai-agent.md](../docs/implementation-docs/admin-ai-agent.md) — AI editing agent runbook
- [docs/entity-model/entity-specification.md](../docs/entity-model/entity-specification.md) — canonical data model

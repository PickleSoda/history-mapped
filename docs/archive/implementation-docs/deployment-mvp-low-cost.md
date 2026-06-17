# MVP Deployment (Low Cost, Minimal Hassle)

## Goal

Ship fast with low monthly cost while keeping a clean path to scale later.

## Recommended Stack

- Backend runtime: managed container app service running Docker image from `docker/api/Dockerfile`
- Process model:
  - `app` service (HTTP)
  - `queue` worker service
  - `scheduler` service (single replica)
- Database: managed PostgreSQL (start small)
- Cache/queue/session: managed Redis (small tier)
- Frontend (`web/`): static hosting + CDN
- Object storage: S3-compatible bucket for uploads/artifacts

This keeps your current Docker-based boundaries and avoids manually managing Compose in production.

## Why Not VPS + Docker Compose for MVP?

A single VPS with Compose is cheap, but you will manually own:

- service restarts and crash recovery
- SSL and reverse proxy hardening
- rolling deploys/rollback
- host patching and security updates
- scaling during traffic spikes

For very low traffic, it is still viable. If you choose VPS temporarily, treat it as a short-lived bridge and keep the same image boundaries so migration to managed runtime stays simple.

## Database Choice for Your Requirements

Your app depends on PostGIS and pgvector (see `docker/db/Dockerfile` and extension init scripts). Before selecting Neon or any provider, validate extension support in your target region/tier.

Verification checklist:

1. Confirm `postgis` extension is available and enabled.
2. Confirm `vector` (pgvector) extension is available and enabled.
3. Validate creating GIST indexes for spatial columns.
4. Validate creating vector indexes and running nearest-neighbor queries.
5. Run a representative migration in staging.

If either extension is not fully supported, pick a managed PostgreSQL provider with explicit support for both extensions.

## Minimal Production Topology

1. `web` static build deployed to CDN.
2. `api` container for Laravel HTTP.
3. `queue` container for jobs.
4. `scheduler` container for scheduled tasks.
5. Managed PostgreSQL.
6. Managed Redis.
7. Secret manager for app credentials.

## Scaling Strategy (MVP)

- `api`: min 1 replica, scale to 2-3 on CPU/concurrency.
- `queue`: min 1 replica, scale based on queue depth/latency.
- `scheduler`: exactly 1 replica.
- Database: start with one primary instance and automated backups.

## CI/CD Pipeline (MVP)

### Trigger Rules

- Pull request: run checks only.
- Push to `main`: build image and deploy to staging.
- Manual approval: promote to production.

### CI Steps

1. Checkout and install dependencies (`pnpm`, Composer).
2. Lint and type checks (`api` + `web`).
3. Run Laravel tests in containerized environment.
4. Build production images.
5. Publish image with immutable tag (commit SHA).

### CD Steps

1. Deploy new image to staging (`api`, `queue`, `scheduler`).
2. Run migrations as one-off job.
3. Run smoke tests (`/api/v1/health`, DB and Redis checks).
4. Manual approval gate.
5. Deploy production with rolling strategy.
6. Auto-rollback on failed health checks.

## Environment and Secrets

Keep secrets out of repo and inject at deploy time:

- `APP_KEY`, `APP_ENV`, `APP_URL`
- `DB_*`
- `REDIS_*`
- `QUEUE_CONNECTION=redis`
- `CACHE_STORE=redis`
- `SESSION_DRIVER=redis`
- object storage credentials

## Operations Baseline

- Enable centralized logs for `api`, `queue`, `scheduler`.
- Alert on: API 5xx rate, queue lag, DB storage/CPU, Redis memory.
- Daily automated DB backup with restore test at least monthly.

## Estimated Cost Shape (Relative)

- Lowest: single VPS + Compose (highest ops effort, weakest scaling).
- Balanced MVP: managed containers + small managed DB/Redis (recommended).
- Highest initial cost: full HA production footprint.

## 30-Day Implementation Plan

1. Week 1: add staging environment, registry, secrets, and CI image publish.
2. Week 2: deploy staging runtime (`api`, `queue`, `scheduler`) and run migrations.
3. Week 3: deploy `web` static build to CDN and wire env vars.
4. Week 4: production cutover with rollback plan and monitoring alerts.

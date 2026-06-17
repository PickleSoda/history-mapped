# Production Deployment (Optimal for This Architecture)

## Goal

Run a resilient, autoscaling, low-ops platform optimized for your current monorepo and service split.

## Target Architecture

- Frontend (`web/`): static hosting behind global CDN
- Backend compute:
  - `api` service (Laravel HTTP)
  - `queue` service (workers)
  - `scheduler` service (single active instance)
- Data:
  - managed PostgreSQL with PostGIS + pgvector
  - managed Redis (cache, sessions, queues)
- Storage: S3-compatible object store
- Observability: centralized logs, metrics, tracing, alerting
- Secrets: managed secret store with rotation

This directly mirrors the service boundaries already present in `docker/docker-compose.yml`, but on managed infrastructure.

## Platform Characteristics to Require

Choose a cloud/runtime that supports:

1. container autoscaling by CPU/memory and HTTP concurrency
2. background worker autoscaling by queue depth
3. zero-downtime rolling deployments
4. private networking between app and data services
5. managed TLS certificates
6. managed cron or job scheduling

## Data Layer Design

### PostgreSQL

- Single primary with PITR backups from day one
- Read replicas when analytics/read load grows
- Connection pooling (PgBouncer or provider equivalent)
- Extensions required:
  - `postgis`
  - `vector` (pgvector)

### Redis

- Separate logical DBs or namespaces for cache/session/queues
- Persistence and eviction policies tuned by workload
- HA tier once queue workload is critical

## Autoscaling Policy

### API

- Min replicas: 2
- Max replicas: 10-20 (initial)
- Scale out triggers:
  - CPU > 65% for 5 minutes
  - p95 latency or concurrency threshold exceeded

### Queue

- Min replicas: 2
- Max replicas: 20+
- Scale out triggers:
  - queue depth threshold
  - oldest job age threshold

### Scheduler

- Exactly 1 replica
- No horizontal scaling

## Release Strategy

Use blue/green or canary for production:

1. Build immutable image with commit SHA.
2. Deploy to green/canary slice.
3. Run post-deploy health + migration compatibility checks.
4. Shift traffic gradually.
5. Roll back automatically if SLOs degrade.

## Migration Strategy

- Run schema migrations in a pre-traffic deployment job.
- Use backward-compatible migration patterns:
  - expand schema first
  - deploy app
  - backfill async
  - remove old fields in later release
- Never couple destructive migrations with same-release app cutover.

## CI/CD Pipeline (Production Grade)

## 1. Pull Request Pipeline

1. dependency install and caching
2. lint/type checks (`api`, `web`)
3. unit/feature tests
4. build validation (`web`, Laravel assets)
5. container build smoke test

## 2. Main Branch Build Pipeline

1. build image once
2. generate SBOM
3. image vulnerability scan
4. sign image/provenance metadata
5. push to registry with immutable tags

## 3. Staging Deploy Pipeline

1. deploy `api`, `queue`, `scheduler`
2. run migrations
3. execute smoke tests and synthetic checks
4. publish release notes and metrics snapshot

## 4. Production Deploy Pipeline

1. required manual approval
2. progressive rollout (canary or blue/green)
3. SLO/health gate checks
4. automated rollback on failure
5. post-deploy verification and incident hooks

## SRE Baseline

Define and monitor SLOs:

- API availability
- API latency (p95)
- queue processing delay
- DB error rate

Alerting priorities:

1. customer-impacting failures (5xx spikes, total outage)
2. queue backlog and stuck workers
3. DB saturation and storage growth
4. Redis memory pressure

## Security and Compliance Baseline

- private networking for DB/Redis
- least-privilege IAM for runtime and CI
- image scanning and patch cadence
- WAF/rate limits on public API
- audit logs for deployment actions
- secret rotation policy

## Disaster Recovery

- RPO target: <= 15 minutes (PITR + frequent backups)
- RTO target: <= 60 minutes for full-region incident (initial)
- quarterly restore drills from production backup snapshots

## Recommended Phased Rollout

1. Phase 1: staging parity and baseline CI/CD
2. Phase 2: production with rolling deploys and autoscale
3. Phase 3: canary/blue-green and SLO-driven rollback automation
4. Phase 4: multi-zone hardening and read replica strategy

## Decision Summary

- Keep Docker images as deployment artifact.
- Do not use Docker Compose as production orchestrator.
- Use managed container runtime + managed Postgres/Redis.
- Enforce extension validation (PostGIS + pgvector) before provider lock-in.

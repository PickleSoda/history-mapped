# Plan 01 - Foundation Setup

> **Status: ✅ Executed** — verified 2026-06-15 against the codebase. See [STATUS.md](STATUS.md).

## Goal

Create the monorepo foundation so Laravel, the customer app, and the shared package can all run in a fully dockerized workspace.

## Scope

- Add root workspace files and Docker-oriented scripts.
- Add the initial Docker Compose stack and base images.
- Create the real `@history-mapped/shared` package with a build pipeline.
- Keep `api/` and `web/` app scaffolding for the next phase.

## Deliverables

- Root `package.json`, `pnpm-workspace.yaml`, `.env.example`, and `.gitignore`
- `docker/docker-compose.yml`
- Base Dockerfiles for PHP-FPM, nginx, Node Vite services, and the shared watcher
- Initial `shared/` workspace package with buildable TypeScript output

## Verification

- `docker compose -f docker/docker-compose.yml config` succeeds
- `pnpm --filter @history-mapped/shared build` works inside Docker
- The repo is ready for Laravel and Vite scaffolding without host toolchains

## Notes

- The first commit optimizes for repeatable plumbing, not finished product behavior.
- Queue, scheduler, and Vite services are defined now so the next commit can plug real apps into the same runtime model.
- **Update (post-commit):** The `@history-mapped/shared` package was removed in a later commit. The Inertia admin panel receives data via Inertia props (no API client needed), and the web SPA will generate its own OpenAPI client directly. The `shared/` directory, its Docker service, and all workspace references have been deleted.

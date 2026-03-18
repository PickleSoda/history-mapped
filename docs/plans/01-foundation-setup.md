# Plan 01 - Foundation Setup

## Goal

Create the monorepo foundation so Laravel, the customer app, and the shared package can all run in a fully dockerized workspace.

## Scope

- Add root workspace files and Docker-oriented scripts.
- Add the initial Docker Compose stack and base images.
- Create the real `@wikiglobe/shared` package with a build pipeline.
- Keep `api/` and `web/` app scaffolding for the next phase.

## Deliverables

- Root `package.json`, `pnpm-workspace.yaml`, `.env.example`, and `.gitignore`
- `docker/docker-compose.yml`
- Base Dockerfiles for PHP-FPM, nginx, Node Vite services, and the shared watcher
- Initial `shared/` workspace package with buildable TypeScript output

## Verification

- `docker compose -f docker/docker-compose.yml config` succeeds
- `pnpm --filter @wikiglobe/shared build` works inside Docker
- The repo is ready for Laravel and Vite scaffolding without host toolchains

## Notes

- The first commit optimizes for repeatable plumbing, not finished product behavior.
- Queue, scheduler, and Vite services are defined now so the next commit can plug real apps into the same runtime model.

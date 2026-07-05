# Contributing to history-mapped

Thanks for contributing! This guide covers the **code** workflow. To contribute historical
**data** (entities, relationships, borders, geometry), start with
[docs/implementation-docs/data-contributor-guide.md](docs/implementation-docs/data-contributor-guide.md)
and the audience guides in [docs/entity-model/](docs/entity-model/)
([for-historians.md](docs/entity-model/for-historians.md),
[for-geodata-contributors.md](docs/entity-model/for-geodata-contributors.md)).

## Getting set up

Follow the [Quick Start in README.md](README.md#quick-start). Everything backend runs in
Docker Compose — **do not run host-local PHP/Composer/PHPUnit**; use the containers:

```bash
pnpm dev                                                  # bring up the whole stack
docker compose -f docker/docker-compose.yml exec app php artisan migrate --seed
```

Full setup detail: [docs/implementation-docs/setup.md](docs/implementation-docs/setup.md).

## Branches & flow

- `main` — stable; release PRs target this branch.
- `develop` — integration branch; day-to-day work merges here first.
- Feature branches: `feat/<topic>` (or `fix/`, `docs/`, `ci/` as appropriate), branched from `develop`.

## Commit messages

Conventional-commit style, imperative mood, with a scope where it helps:

```
feat(web): timeline v2 — real periods gantt, expand-to-scrub
fix(ai): WikidataService 403 (missing User-Agent)
docs(plans): archive shipped web-pwa-caching plan + spec
```

Common types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`.
Common scopes: `api`, `web`, `admin`, `pipeline`, `ai`, `geo`, `deps`, `plans`, `specs`.

## Before you open a PR

Run the checks for every surface you touched:

**Backend (Laravel — inside the `app` container):**

```bash
docker compose -f docker/docker-compose.yml exec app composer ci:check   # lint + prettier + tsc + tests (mirrors CI)
# or piecemeal:
docker compose -f docker/docker-compose.yml exec app php artisan test
docker compose -f docker/docker-compose.yml exec app composer lint       # Pint autofix
```

**Admin frontend (`api/resources/js` — inside the `app` container):**

```bash
docker compose -f docker/docker-compose.yml exec app npm run lint
docker compose -f docker/docker-compose.yml exec app npm run types:check
```

**Public SPA (`web/`):**

```bash
pnpm --filter @history-mapped/web lint
pnpm --filter @history-mapped/web types:check
pnpm --filter @history-mapped/web build
```

**Pipeline (Python):**

```bash
python -m pytest pipeline/tests/
python -m pytest pipeline/agent/tests/
```

## Gotchas

- **Wayfinder TS is generated.** Never hand-edit `api/resources/js/actions/**` or
  `api/resources/js/routes/**` — regenerate with
  `php artisan wayfinder:generate --with-form` (in the `app` container).
- **Write/business logic lives in Action classes** (`api/app/Actions/**`), not controllers.
  Keep controllers thin.
- The canonical entity model is
  [docs/entity-model/entity-specification.md](docs/entity-model/entity-specification.md) —
  schema changes must stay consistent with it (or change it in the same PR).
- Pipeline artifacts must match the contracts in [docs/schemas/](docs/schemas/).

## Documentation rules

Docs live under [docs/](docs/) — see [docs/README.md](docs/README.md) for the map.

- New design specs → `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`;
  implementation plans → `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.
- When a plan ships: move the plan **and its spec** to `docs/archive/` and update
  [docs/plans/STATUS.md](docs/plans/STATUS.md).
- Filenames are kebab-case. Precedence when things disagree: code → the relevant doc →
  `STATUS.md`.

## Questions / bugs

Open a GitHub issue. For known problem areas, check
[docs/plans/bug-report.md](docs/plans/bug-report.md) and [docs/TODO.md](docs/TODO.md) first.

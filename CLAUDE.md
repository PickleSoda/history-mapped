# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`history-mapped` is a pnpm monorepo for an interactive historical atlas. Three runtime surfaces:

- **`api/`** — Laravel 13 / PHP 8.4. Serves both the **JSON REST API** (`routes/api.php`, versioned under `/api/v1`, controllers in `app/Http/Api`) **and** the **Inertia.js + React admin** (`routes/web.php`, `app/Http/Controllers`, React under `api/resources/js`). Fronted by Nginx.
- **`web/`** — standalone **React 19 + Vite** public Atlas SPA (`@history-mapped/web`). TanStack Query + Axios against the API. Independent of the Inertia admin.
- **`pipeline/`** — **Python** ingestion: Wikidata/Wikipedia scraping, topic extraction, OpenHistoricalMap (OHM) border processing, and a LangGraph **agentic** extraction pipeline (`pipeline/agent`).

Generated artifacts (JSONL, OHM borders) land in `output/`. Persistence is **PostgreSQL 16 with PostGIS (geometry) + pgvector (embeddings)**.

## Everything runs in Docker Compose

Do **not** run host-local PHP/Composer/PHP-unit — use the containers, or you'll hit host/container drift. The stack is `docker/docker-compose.yml`, project name `history-mapped`. Services: `app` (PHP), `nginx`, `web` (SPA Vite), `vite-admin` (admin Vite), `db`, `redis`, `queue`, `scheduler`, `mailpit`, `cloudbeaver`, `redisinsight`; `composer-install` / `pnpm-install` are one-shot init containers.

```bash
pnpm dev            # docker compose -f docker/docker-compose.yml up  (whole stack)
pnpm dev:build      # ...up --build  (rebuild images)
pnpm dev:down       # ...down --remove-orphans
```

Dev URLs (override with `FORWARD_*_PORT` in `.env`): API+admin via Nginx → `:8000`, public SPA → `:5173`, admin Vite → `:5174`, Postgres → `:5432`, Mailpit → `:8025`, CloudBeaver → `:8978`, RedisInsight → `:5540`.

Run backend commands inside `app` (this prefix is assumed below):

```bash
docker compose -f docker/docker-compose.yml exec app php artisan <cmd>
```

## Common commands

**Backend (Laravel, in `app`):**

```bash
php artisan test                       # full PHPUnit suite
php artisan test --filter EntityTest   # single test class / method
php artisan test tests/Feature/Foo.php # single file
composer test                          # config:clear + pint --test + artisan test
composer ci:check                      # JS lint + prettier + tsc + tests (mirrors CI)
composer lint                          # Pint (PHP) autofix; composer lint:check to verify
php artisan wayfinder:generate --with-form  # regen TS route/action helpers (see Gotchas)
php artisan route:list                 # or: pnpm api:routes  (from host)
```

The admin frontend (`api/resources/js`) uses npm scripts run in `app`: `npm run lint` / `format` / `types:check`, `npm run build`.

**Public SPA (`web/`, pnpm):** `pnpm lint`, `pnpm types:check`, `pnpm build` (= `tsc -b && vite build`). From host root, `pnpm typecheck` typechecks workspaces via the `web` service.

**Pipeline (Python):**

```bash
python -m pipeline scrape --type political_entity   # Wikidata scrape
python -m pipeline topic "Roman Empire"             # topic extraction
python -m pipeline borders fetch                     # OHM borders
python -m pytest pipeline/tests/                     # pipeline tests
python -m pytest pipeline/agent/tests/test_graph.py  # agentic-pipeline tests
```

The LangGraph agent graph is `pipeline/agent/graph/workflow.py:build_workflow` (registered in `langgraph.json`); pipeline config/secrets come from `pipeline/.env`.

## Architecture notes (the non-obvious parts)

- **`Entity` is the domain hub.** 30 entity types across 5 groups (the canonical model is `docs/entity-model/entity-specification.md`). Around it: `EntityRelationship` (typed links), `Chronicle`/`ChronicleEntry` (narrative), time-aware geography via `GeometryPeriod` + `EntityGeoRef`/`EntityLocation` (PostGIS), `EntityTimelineEntry`, plus reference tables (`CalendarSystem`, `HistoricalPeriod`, `GeographicRegion`, `WritingSystem`, …).
- **Write/business logic lives in Action classes**, not controllers: `app/Actions/{Entity,Relationship,Chronicle,Source,Timeline,EntityGeoRef}`. Controllers stay thin. Supporting layers: `app/Services`, `app/Builders` (query builders), `app/DTOs`, `app/Casts`, `app/Observers`, `app/Jobs` (async via the `queue` worker), and the `scheduler` container for cron tasks.
- **Data flows pipeline → app.** The pipeline scrapes/fetches and writes JSONL + OHM artifacts to `output/` (contracts in `docs/schemas/`); a Laravel import layer ingests them into Postgres; embeddings are generated into pgvector; the API then serves entities/timeline/map to the SPA and admin. End-to-end flow: `docs/architecture/data-pipeline.md`.
- **OHM integration**: historical borders/geometry come from OpenHistoricalMap and render via MapLibre — see `docs/architecture/ohm-integration.md`.

## Gotchas

- **Wayfinder TS is generated**, not hand-written: `api/resources/js/actions/**` and `api/resources/js/routes/**` come from `php artisan wayfinder:generate`. Regenerate rather than editing; if a run hits `Permission denied`, the target tree was left root-owned by an earlier run — `chown` it back to your user on the host.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **history-mapped** (9921 symbols, 18824 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/history-mapped/context` | Codebase overview, check index freshness |
| `gitnexus://repo/history-mapped/clusters` | All functional areas |
| `gitnexus://repo/history-mapped/processes` | All execution flows |
| `gitnexus://repo/history-mapped/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

# Documentation Map

Project docs live under [`docs/`](docs/) and are kept tidy — start at [`docs/README.md`](docs/README.md),
the master index. Layout:

| Folder | What's there |
|--------|--------------|
| [`docs/architecture/`](docs/architecture/) | How it's built: `system-overview`, `frontend-app`, `data-pipeline`, `admin-map-editor`, `ohm-integration`. |
| [`docs/implementation-docs/`](docs/implementation-docs/) | Operator runbooks: setup, deployment, agentic + OHM pipelines, data contribution. |
| [`docs/entity-model/`](docs/entity-model/) | Canonical data model — `entity-specification.md` is the single source of truth for the 30 types / 5 groups. |
| [`docs/schemas/`](docs/schemas/) | Pipeline-artifact and API payload contracts. |
| [`docs/plans/`](docs/plans/) | Live roadmap/backlog. [`docs/plans/STATUS.md`](docs/plans/STATUS.md) is the **verified** per-plan status index. |
| [`docs/superpowers/`](docs/superpowers/) | Agent-driven design `specs/` + implementation `plans/` (current cycle only). |
| [`docs/reference/`](docs/reference/) | Forward-looking design references — **not** the live app. |
| [`docs/archive/`](docs/archive/) | Completed/superseded docs; history only, not source of truth. |
| [`docs/TODO.md`](docs/TODO.md) | Fine-grained engineering backlog not owned by a plan. |

Conventions when writing docs here:

- New design specs → `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`; implementation plans → `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` (per the `brainstorming` / `writing-plans` skills).
- When a plan ships, move it (and its spec) to `docs/archive/` and update `docs/plans/STATUS.md`.
- Filenames are kebab-case. Code is the source of truth; then the relevant doc; then `STATUS.md`.

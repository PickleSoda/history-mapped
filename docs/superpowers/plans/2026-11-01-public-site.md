# Public site: landing, browse and docs — implementation plan

Spec: [`../specs/2026-11-01-public-site-design.md`](../specs/2026-11-01-public-site-design.md). Branch `feat/public-site`
(worktree `.claude/worktrees/public-site`), skeleton committed first; four tracks on their own branches, merged back in
the order A, B, C, D by the integrator, who runs the integration checks below.

## Skeleton (integrator, before the tracks)

- `web/src/app/router.tsx` with the full route tree of D1 and lazy placeholder pages under `routes/site`, `routes/browse`,
  `routes/docs`; `SiteLayout` placeholder with `<Outlet/>`; `/` + query → `/app` redirect.
- Labelled empty blocks in `hooks/index.ts` (`// Public site (track B)`, `// Browse (track D)`).
- `pnpm exec eslint .`, `tsc -b`, `vitest run` green.

## Track A — backend

1. `GET /api/v1/map-stories` index (`MapStoryController@index`, `ListMapStoriesRequest`, `MapStorySummaryResource`):
   fields, `kind`, `sort`, pagination per D4. Tests.
2. `collections`: migration, `Collection` model (uuid pk, `items` cast), `api/resources/collections/*.json` (JSON schema in
   `docs/schemas/collections.md`), `CollectionsSyncCommand` (`collections:sync {--path=}`, upsert by slug, deletes nothing,
   prints a two-column result per file), `CollectionController@index/show`, `CollectionResource` resolving items in one
   query per kind. Tests: sync (create/update/draft hidden/unknown ref dropped), index, show, 404.
3. Five to eight seed sets from the real data (`docker compose exec app php artisan tinker` or SQL to find slugs and ids),
   committed under `api/resources/collections/`. Run `collections:sync` on the dev DB.
4. D7 link changes with tests.
5. `composer lint` (Pint) + the PHPUnit suite on a dedicated test DB (see "How to run checks").

## Track B — shell

1. `SiteLayout` (header, outlet, footer, mobile menu), `NotFoundPage`, `lib/site-links.ts` (+ tests), `lib/document-meta.ts`.
2. `/app` move: `vite.config.ts` manifest `start_url: '/app'`; `atlas-links.ts` → `/app?…`; legacy redirect rule in
   `lib/legacy-redirect.ts` (pure, tested) used by the index route; check every internal `to="/"` / `href="/"` in `web/src`
   (account pages' "back to atlas", login redirects `safeNext`, NavBreadcrumb) and point them at `/app` or `/` as appropriate.
3. Link mode (D3): `components/atlas/link-mode.tsx`, `usePageNav()`, switch the call sites in `EntityPage`, `ChroniclePage`
   and their helpers; `PageFrame` `variant: 'site'`; pure policy in `lib/page-nav.ts` with tests.
4. `routes/site/EntityRoute.tsx`, `ChronicleRoute.tsx` (breadcrumb, "Open on the globe", document title, loading/404 states).
5. `routes/site/LandingPage.tsx` per D6 (featured sets and stories through the hooks track D adds; until merge, use
   `useChronicleList` and a placeholder for stories, and leave a `// TODO(track D)` where the collection hooks go).
6. Update the Routing section of `docs/architecture/frontend-app.md`. Checks: eslint, `tsc -b`, vitest.

## Track C — docs

1. `web/package.json`: `react-markdown`, `remark-gfm`, `rehype-slug`, `mermaid` (exact versions, `pnpm install` inside the
   web container so the lockfile updates). Keep the renderer and mermaid in lazy chunks.
2. `content/docs/manifest.ts` per D5 + `lib/docs/` (`loadDoc(slug)`, `rewriteDocLink()`, `docTitleFromMarkdown()`), tests.
3. `routes/docs/DocsLayout.tsx` (sidebar by section, mobile select), `DocPage.tsx` (renderer, TOC, prev/next, "Edit on
   GitHub"), styles for prose (`@tailwindcss/typography` or hand-written prose classes consistent with the site).
4. `docker/web/Dockerfile.prod`: `COPY docs/ ./docs/` before the build; confirm the image builds
   (`docker build -f docker/web/Dockerfile.prod --build-arg VITE_API_URL=https://api.example.org -t hm-web-test .` from the
   worktree root, then remove the image).
5. Checks: eslint, `tsc -b`, vitest, `pnpm build` in the web container.

## Track D — browse

1. Schemas + API clients + hooks for collections and the map-stories index per D4 (zod, `queryKeys`, 5-minute staleTime),
   written to the contract in the spec; unit tests with fixtures.
2. `routes/browse/BrowseIndexPage.tsx` (curated sets, facet grids from `useTags`, recent chronicles, battle maps),
   `BrowseFacetPage.tsx` (tag header, child chips, chronicles + entities with "load more"), `CollectionPage.tsx`,
   `StoriesPage.tsx`; cards reuse `StoryCard`, `GroupBadge`, `TagPills`, `EntityImage` where they fit.
3. Every item links to the standalone pages (`site-links`), with an "Open on the globe" secondary action.
4. Document titles through `lib/document-meta.ts` (track B's; until merge, a local no-op is acceptable).
5. Checks: eslint, `tsc -b`, vitest.

## Integration (integrator)

1. Merge A; run its PHPUnit suite once more; `php artisan collections:sync` + `migrate` on the dev DB; serve the branch API
   on a free port (`php artisan serve` in a one-off container) for the web checks.
2. Merge B, C, D; resolve `hooks/index.ts` / `router.tsx` conflicts (append-only blocks).
3. Web checks: eslint, `tsc -b`, vitest, `pnpm build`; the web image builds with `docs/` copied.
4. Manual pass against the branch API: `/` (landing + redirect `/?sel=…`), `/app` deep links, `/browse`, a facet, a set,
   stories, an entity page, a chronicle page, `/docs` + two pages, 404; mobile widths.
5. Pint, PHPUnit, Python unaffected. Update `docs/plans/STATUS.md`; move spec + plan to the archive when shipped.

## How to run checks from a worktree (containers mount the main checkout, so use one-off containers)

```bash
WT=$PWD   # the track's worktree root
# web: lint, types, unit tests
docker run --rm -v "$WT":/workspace -v history-mapped_root_node_modules:/workspace/node_modules \
  -v history-mapped_web_node_modules:/workspace/web/node_modules -v history-mapped_pnpm_store:/pnpm/store \
  -w /workspace/web history-mapped-web sh -c 'pnpm exec eslint . && pnpm exec tsc -b && pnpm exec vitest run'
# api: Pint + PHPUnit on a dedicated DB (create it once with the four extensions)
docker compose -f /home/pickle/code/history-mapped/docker/docker-compose.yml exec -T db psql -U history-mapped -d history-mapped \
  -c 'CREATE DATABASE "history-mapped_test_<track>"'
for ext in hstore pg_trgm postgis vector; do docker compose -f /home/pickle/code/history-mapped/docker/docker-compose.yml exec -T db \
  psql -U history-mapped -d "history-mapped_test_<track>" -c "CREATE EXTENSION IF NOT EXISTS \"$ext\""; done
docker run --rm --network history-mapped_default -v "$WT/api":/var/www/html -v history-mapped_api_vendor:/var/www/html/vendor \
  -w /var/www/html -e DB_DATABASE="history-mapped_test_<track>" history-mapped-app sh -c 'vendor/bin/pint --test && php artisan test'
```

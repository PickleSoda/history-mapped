# Public site: landing, browse and docs — design

**Status:** approved 2026-11-01 (user decisions in chat). Branch `feat/public-site` off `main` b9875b8.
**Plan:** [`../plans/2026-11-01-public-site.md`](../plans/2026-11-01-public-site.md).

## Why

historymapped.org is one page: the globe. People who arrive from a search or a link have no way in except the
map, and nothing explains what the project is. The site should work two ways: as an encyclopedia you browse
(landing → collections → chronicle, entity and battle-map pages) and as the globe. The globe keeps everything it
has; it moves under `/app`.

## Decisions

**D1. Route tree.** One SPA (`web/`), react-router v7, two frames.

```
/                         landing (SiteLayout)
/app                      the atlas shell, unchanged: ?sel ?chron&step ?story&sstep ?full ?bbox ?y ?g ?q ?view ?basemap
/browse                   collections index: curated sets, era / region / theme / type grids, chronicles, battle maps
/browse/stories           battle maps (map stories) list
/browse/collections/:slug a curated set
/browse/:facet/:tag       everything carrying a tag, e.g. /browse/era/medieval
/entities/:id             standalone entity page
/chronicles/:slug         standalone chronicle page (?step=n optional)
/docs                     docs index
/docs/:slug               one rendered markdown page
/login /register /saved /contributions   unchanged (AccountLayout)
*                         not-found page (SiteLayout)
```

- `/` **with any query string** redirects to `/app` with the same query (`replace`), so every shared link made before
  this change (`/?sel=…&full=1`, `/?chron=…`, `/?story=…`) keeps working. The landing has no query params of its own.
- The PWA manifest `start_url` becomes `/app`. The service worker scope stays `/`.
- `lib/atlas-links.ts`: `entityHref` / `chronicleHref` now point at `/app?…` (they are "open on the globe" links);
  new `lib/site-links.ts` builds the site paths (`entityPagePath(id)`, `chroniclePagePath(slug, step?)`,
  `collectionPath(slug)`, `facetPath(facet, tag)`, `storiesPath()`, `docPath(slug)`, `atlasHref(params)`).

**D2. Two frames, one design.** `SiteLayout` (header: wordmark → `/`, Browse, Docs, "Open the globe" → `/app`,
sign-in / account; `<Outlet/>`; footer: GitHub, docs, sign in) wraps every page except `/app` and the account pages.
Site pages are ordinary scrolling documents, mobile-first, built with the existing tokens (`font-heading` Fraunces,
Geist, the shadcn/base-ui components in `components/ui`, `page-kit` where it fits). No map on site pages; the
globe is one click away everywhere ("Open on the globe").

**D3. One detail page, two homes (link mode).** `EntityPage` and `ChroniclePage` already render from an id prop
(`variant: 'page' | 'sheet'`). They stay the single source for both the in-atlas full page and the standalone
routes. Their navigation goes through the atlas hooks (`useSelection().select`, `useChronicleNav().enter`,
`useStoryNav().enter`, `useFullPage().collapse/closeEntity/collapseChronicle/closeChronicle`,
`useTimeState().setInstant` + `useMapFocus()` for "show on map"). A **link-mode context** decides what those do:

| Action in the page | atlas mode (`/app`, today's behaviour) | site mode (`/entities/:id`, `/chronicles/:slug`) |
|---|---|---|
| open another entity | `select(id)` (push `sel`) | navigate to `/entities/:id` |
| open a chronicle (step) | `enter(slug, step)` | navigate to `/chronicles/:slug?step=n` |
| open a battle map (step) | `enter(slug, step)` | navigate to `/app?story=slug&sstep=n` (needs the map) |
| show on map / set year | map focus + `setInstant` | navigate to `/app?sel=id&y=…` (open on the globe at that year) |
| Collapse / Close | collapse / clear `sel` | hidden; the header shows "Open on the globe" (`/app?sel=id&full=1`) |

Implementation: `components/atlas/link-mode.tsx` exports `LinkModeProvider({ mode })` and `usePageNav()`, which
returns `{ openEntity, openChronicle, openStory, showOnMap, collapse, close, mode }`. Every call site above in
`EntityPage.tsx`, `ChroniclePage.tsx` (and the small components they use: `TagPills`, `RelationshipTimeline`, the
graph click handlers if they select) switches to `usePageNav()`. Default mode is `atlas`, so nothing in `/app`
changes. `PageFrame` gets `variant: 'page' | 'sheet' | 'site'`: `site` renders no sticky collapse/close bar, full
width up to `max-w-3xl`, and the page title is the document title. The standalone routes render
`<LinkModeProvider mode="site"><EntityPage id variant="site"/></LinkModeProvider>` with a breadcrumb
(Browse › Entity) and the "Open on the globe" action. Selection in site mode must never write `sel` to the URL.

**D4. Collections** (three kinds, one index page):
- *Facet collections* are the tag vocabulary (`GET /api/v1/tags`: `era`, `region`, `theme`, `type`, `topic`, with
  counts). `/browse` shows the era, region, theme and type tags as cards (name, description, counts; era cards show
  their years). `/browse/:facet/:tag` lists the chronicles (`GET /chronicles?tags=`) and entities
  (`GET /entities?tags=&sort=impact`) carrying that tag, each linking to its standalone page, with child tags
  (`parent`) as chips.
- *Curated sets* are editorial, file-authored and DB-served, like map stories: `api/resources/collections/<slug>.json`,
  synced by `php artisan collections:sync` (upsert by slug; `--path=`; no admin editing in v1), table `collections`:
  `collection_id uuid pk, slug unique, title, subtitle null, description text null (markdown), cover_entity_id uuid null
  (fk entities, null on delete), items jsonb (ordered), status enum draft|published default published, sort_order int,
  timestamps`. An item is `{kind: "entity"|"chronicle"|"story"|"tag", ref: <uuid|slug>, note?: string}`.
  API: `GET /api/v1/collections` → `{data: [{slug,title,subtitle,description,cover (entity summary|null),
  item_count, items_by_kind: {entity,chronicle,story,tag}}]}` (published only, by sort_order, then title);
  `GET /api/v1/collections/{slug}` → the same plus `items: [{kind, note, entity?|chronicle?|story?|tag?}]` resolved
  through the existing summary resources (`EntitySummaryResource`, `ChronicleResource` without entries, the map-story
  summary, the tag row from the tags index). Unresolvable refs are dropped with a log line, never a 500.
  Five to eight seed sets drawn from the real content ship with the feature (e.g. the Roman world, the Silk Roads,
  great battles, medieval Europe, the age of empires), each with a two-sentence description.
- *Battle maps*: new `GET /api/v1/map-stories` index: `{data: [{id, slug, kind, title, year, step_count,
  entity: {id, name, entity_type} | null, chronicle: {slug, title} | null}], meta: pagination}`, `kind=` filter,
  `sort=year|title`, `per_page` ≤ 100. `/browse/stories` lists them as cards (StoryCard exists) linking to
  `/app?story=slug` and, when the story has an entity, to `/entities/:id`.

**D5. Docs rendered from the repo.** A manifest, `web/src/content/docs/manifest.ts`, lists sections and pages:
`{ slug, title, section, path }` with `path` relative to the repo root. Pages are imported at build time with
`import.meta.glob('../../../../docs/**/*.md', { query: '?raw', import: 'default' })` (only manifest paths are
loaded, lazily). The production image copies `docs/` into the build context (`docker/web/Dockerfile.prod`).
Renderer: `react-markdown` + `remark-gfm` + `rehype-slug` in a lazy chunk; `mermaid` fenced blocks render with
`mermaid` loaded on demand (fall back to the code block on error); tables scroll horizontally; headings get
anchors and a desktop table of contents. Relative links between docs are rewritten to `/docs/<slug>` when the
target is in the manifest, otherwise to `https://github.com/PickleSoda/history-mapped/blob/main/<path>`. First
manifest: Overview (`docs/README.md` as the index text, `docs/architecture/system-overview.md`), Architecture
(`frontend-app`, `data-pipeline`, `ohm-integration`, `tags`, `entity-images`, `admin-map-editor`), Data model
(`entity-model/entity-specification`, `for-historians`, `diagrams`), Guides (`implementation-docs/setup`,
`data-contributor-guide`, `map-story-authoring`), Contracts (`schemas/atlas-tiles`). Runbooks, plans and the
archive are not published. The university report (PDF) is deferred.

**D6. Landing.** Hero: the name, one sentence on what it is, two calls to action (Open the globe → `/app`,
Browse → `/browse`). "Why" (motivation, three short paragraphs), "How it works" (Wikidata and OpenHistoricalMap
data, an editorial layer, chronicles, battle maps, the time-aware map), "Start here" (three curated sets and three
battle maps, live from the API), footer. Copy is drafted from `README.md` and `docs/architecture/system-overview.md`
and marked for the user to refine.

**D7. Backend links that assume the atlas is at `/`.** `DescribeContributionTargetsAction::atlas()` builds
`/app?…`; the admin map-story editor's `preview_url` (`Admin\MapStoryController@edit`) becomes
`frontend_url . '/app'`; `SendsNonStaffToAtlas` keeps `/` (the landing is the right place for a non-staff user).

**D8. Document titles and SEO.** Every site page sets `document.title` ("Battle of Cannae · History Mapped") and a
meta description through a small `useDocumentMeta()` hook. No prerendering in v1; it is a follow-up for the
landing, docs and browse pages (entity pages would need server rendering).

**D9. Tests.** vitest (`src/**/*.test.ts`): legacy redirect rule, `site-links`, link-mode policy (pure), docs
manifest + link rewriting, browse view-model mapping. PHPUnit: `collections:sync` (create, update, drop a missing
ref, draft hidden), collections API, map-stories index (filters, pagination), the `/app` links.

**D10. Out of scope.** Admin UI for curated sets; server rendering / prerendering; the PDF; a site-wide search page
(the command palette stays in `/app`); redesign of the atlas shell.

## Ownership (parallel tracks)

| Track | Branch | Owns |
|---|---|---|
| A backend | `feat/public-site-backend` | `api/` (collections, map-stories index, D7), `docs/schemas/collections.md` |
| B shell | `feat/public-site-shell` | `web/src/app/router.tsx`, `routes/site/*`, `lib/site-links.ts`, `lib/document-meta.ts`, `components/atlas/link-mode.tsx`, edits to `EntityPage`, `ChroniclePage`, `page-kit`, `atlas-links`, `vite.config.ts` (start_url), `docs/architecture/frontend-app.md` routing section |
| C docs | `feat/public-site-docs` | `routes/docs/*`, `content/docs/*`, `lib/docs/*`, `docker/web/Dockerfile.prod`, `web/package.json` deps for markdown |
| D browse | `feat/public-site-browse` | `routes/browse/*`, `lib/api/collections.ts`, `lib/api/map-stories.ts` (add `mapStoryList`), `lib/schemas/collection.ts`, `lib/schemas/map-story-list.ts`, hooks `useCollections`, `useCollection`, `useMapStoryList`, the labelled block in `hooks/index.ts` and `lib/query/queryKeys.ts` |

The route skeleton (every route with a placeholder page) is committed before the tracks start, so no track edits
another track's files. A track that needs a change outside its list reports it instead of making it.

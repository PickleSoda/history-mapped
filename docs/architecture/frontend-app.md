# Frontend App Architecture — Historical Atlas (`web/`)

> Architecture reference for the Atlas SPA. Companion to the plumbing spec at
> [`docs/superpowers/specs/2026-06-13-atlas-frontend-plumbing-design.md`](../superpowers/specs/2026-06-13-atlas-frontend-plumbing-design.md).
> Describes the **current intended state** of the frontend foundation.

## What this app is

A single-page application that renders historical entities on a map, filtered by a
**bounding box** (where), a **time** instant or range (when), and a **selection** (what).
Everything else — the browse list, detail panel, search, chronicles — is derived from those
three inputs. The map is a persistent WebGL surface that never unmounts.

## Stack

| Layer | Technology |
|---|---|
| Framework | React 19 + Vite 7 (TypeScript, bundler module resolution) |
| Routing | react-router-dom v7 — one route (`/`); everything else is URL search params |
| URL state | nuqs (typed, validated, per-key search-param hooks) |
| Server cache | TanStack Query v5 |
| Ephemeral state | zustand (selector reads) + `useRef` |
| Validation | zod (API response schemas + URL parsers) |
| Map | MapLibre GL (WebGL, globe projection, imperative feature-state) |
| UI | shadcn/ui (base-nova on @base-ui/react) on Tailwind v4, vaul (mobile sheet) |
| Graphs | cytoscape + cytoscape-fcose, lazy-loaded (`components/graph`) |
| HTTP | axios (`src/lib/api/client.ts`) |

## The core principle

> **The URL is the query input. TanStack Query is the data. The map and gestures are the
> only things allowed to live outside React.**

```
URL search params → snapScope() → TanStack query keys → cached data → render
```

If you can answer *"what re-fetches and what re-renders when the user pans?"* you
understand the whole architecture. The answer, by design, is: **panning within a tile
re-fetches nothing and re-renders nothing** (URL `replace` only); panning across a tile
boundary re-fetches once and re-renders the map pins + list.

## State model — three layers, one home each

Every piece of state belongs to **exactly one** layer. Duplicated state is the root cause
of desync bugs, so this boundary is enforced, not advisory.

```
┌─────────────────────────────────────────────────────────────────┐
│ URL layer (nuqs)            survives refresh · shareable          │
│   bbox · t · g · sel · q · chron · step · full · view             │
└───────────────┬───────────────────────────────────────────────────┘
                │ snapScope()  (snap bbox→tile grid, time→resolution)
                ▼
┌─────────────────────────────────────────────────────────────────┐
│ Server cache (TanStack Query)   cache only · re-derivable         │
│   entitiesInView · entity · connections · entityTimeline ·        │
│   entityGraph · search · highlights · density · chronicle ·       │
│   chronicleGraph                                                  │
└───────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│ Ephemeral (zustand + useRef)    interaction-only · lost on refresh│
│   liveScrub · hover · palette open · sheet height · map ref       │
└───────────────────────────────────────────────────────────────────┘
```

**The one boundary that matters:** continuous gestures (drag-pan, scrub) write to the
**ephemeral** layer at 60fps and commit to the **URL** layer only on gesture end. That
single debounce is what stops history spam and re-fetch storms.

## Directory layout (`web/src/`)

```
app/
  providers.tsx     QueryClientProvider + NuqsAdapter + BrowserRouter
  router.tsx        the single `/` route → AtlasLayout
  routes/AtlasLayout.tsx  picks DesktopShell or MobileShell by breakpoint
lib/
  api/              typed endpoint fns (entitiesInView, entity, entityTimeline,
                    fetchEntityGraph, fetchChronicleGraph, search, …) over axios
  query/
    client.ts       QueryClient config (staleTime, gcTime defaults)
    queryKeys.ts    the `qk` key factory — single source of truth for keys
  url/              nuqs parsers/serializers per param (bbox, time, groups, sel, q, …)
  scope/            snapScope, snapBboxToTiles (quadkey), snapTime
  schemas/          zod schemas (API responses; graph.ts = relation-graph payloads)
  graph/            pure relation-graph logic: model (merge/collapse/paths),
                    filters, chronicle step slicing — Vitest-covered
  full-page.ts      pure `full` page / page-stack / mobile-sheet policy
  chronicle-page.ts pure chronicle-page logic (external default, step rows, mount hysteresis)
  entity-format.ts  date + free-form JSON (citations, media, attributes) display
  utils.ts          cn() etc. (shadcn)
hooks/              the hook inventory (URL-state, derived, server-cache, ephemeral)
stores/             zustand ephemeral store (slices: scrub, hover, palette, sheet, mapRef)
components/
  ui/               shadcn primitives
  atlas/            shells, panels, sheet, EntityPage, ChroniclePage, FullPage host,
                    page-kit (shared page frame / sections / stats ledger)
  graph/            RelationGraph (cytoscape canvas + filter bar, info card, legend)
  map/              MapCanvas (persistent, imperative)
types/              shared domain types
```

## The hook seam

Components never touch the router or query client directly — they go through hooks. This
keeps the three-layer boundary enforceable in one place.

- **URL-state hooks** — `useViewport`, `useTimeState`, `useFilters`, `useSelection`,
  `useSearchQuery`, `useChronicleNav`, `useFullPage`. Each subscribes only to the keys it
  needs, so moving bbox cannot wake `useSelection`.
- **Derived** — `useScope()` returns the memoized snapped `{ bbox, z, time, groups }` that
  every viewport query keys on.
- **Server-cache hooks** — `useEntitiesInView`, `useEntity`, `useEntityConnections`,
  `useEntityTimeline`, `useEntityGraph`, `useChronicleGraph`, `useFetchNeighbourhood`
  (imperative "expand node" fetch through the same cache key), `useSearch`,
  `useHighlights`, `useTimelineDensity`, `useChronicle`, `usePrefetchEntity`.
- **DOM** — `useNearViewport(ref, scrollRoot)` (IntersectionObserver with hysteresis; lazily
  mounts the chronicle page's step graphs).
- **Ephemeral/imperative** — `useMapInstance`, `useLiveScrub`, `useHover`, `useSheet`,
  `useCommandPalette`.

## Routing

There is **one route**, `/` → `AtlasLayout`, which mounts `DesktopShell` (≥ `md`) or
`MobileShell` (below it). There is no `<Outlet/>` and no per-panel routes: browse,
chronicles, selection, search, time, bbox and the full page are all **search params**
read through the hooks above.

```
/                      AtlasLayout → DesktopShell | MobileShell
  ?sel=<uuid>          entity detail (desktop right panel / mobile sheet)
  ?chron=<slug>&step=n chronicle tour (desktop left panel / mobile sheet)
  ?full=1              expand the focus into its full page (see below)
```

The map is persistent: the shells overlay panels on it instead of swapping it out.

**History hygiene:** pan/zoom/scrub/filter-toggle use `replace`; entity select, chronicle
step and `full` use `push` (so the back button deselects / walks steps / collapses the page).

### The full page (`full`)

`full` is a nuqs boolean (`parseAsFull`, serialised as `1`, cleared when false). It
expands the current *focus* — `sel` wins over `chron`, as everywhere — into a scrollable
page. Policy lives in `lib/full-page.ts` (pure, tested); `useFullPage()` exposes
`expand` / `collapse` / `closeEntity` and, for chronicles, `expandChronicle` (drops any
`sel` so the chronicle page is on top) / `collapseChronicle(step)` / `closeChronicle`.

- **Desktop:** `FullPageHost` (in `components/atlas/FullPage.tsx`) slides pages up over
  the map and timeline with a CSS transform transition (instant under
  `prefers-reduced-motion`); the TopBar stays. `BehindPage` makes the covered shell
  `inert`. A page keeps rendering while it slides away, then unmounts. Escape collapses.
  There are two layers (`openPageStack`): the chronicle page, and the entity page above
  it. An entity opened from the chronicle page slides up over it; the chronicle page stays
  mounted (inert) underneath, so closing the entity page uncovers it with its scroll
  position and graph state intact. A covered layer never mounts fresh.
- **Mobile:** the vaul sheet's `full` snap *is* the page. `full=1` snaps to full (deep
  link, Expand, Back); dragging onto full pushes `full=1`; leaving the full snap removes it.
  Peek/half behave as before. At the full snap `SheetContent` renders the page in place of
  the detail body.
- **Collapse** removes `full`; **Close** clears `sel` (and `full`, unless a chronicle is
  active — then you drop back to the chronicle page beneath). On the chronicle page,
  Collapse returns to the tour **at the step last in focus** (writes `step`), and Close
  ("Exit tour") clears `chron`, `step` and `full`. The mobile sheet swaps pages rather
  than stacking them, so the chronicle page remounts after an entity page closes there.
- Pages register by kind in `FULL_PAGES` (`entity`, `chronicle`); a kind with no renderer
  never opens. Page modules are `React.lazy` chunks (prefetched when an Expand button is
  hovered: DetailPanel, ChroniclePlayer, the sheet bars), so they stay out of the entry
  bundle. Both pages are built from `page-kit.tsx` (`PageFrame` = scroll container +
  sticky header that names the page once its `PageTitle` scrolls away; `Section`,
  `StatGrid`/`Stat`, `ImpactMeter`).

### EntityPage

`components/atlas/EntityPage.tsx`, taking the entity id as a prop (`variant: 'page' |
'sheet'`). In order: header (type, name, alternative names, dates with `date_raw` on hover,
location, Wikidata link) and a stats ledger (began / ended / span / impact meter /
confidence signal / verification ladder); **summary and significance** as separate
sections; the relation graph (1 or 2 hops); attributes and tags; chronicle chips; the
relationship timeline (the accessible list view of the graph) beside the derived timeline
entries (`GET /entities/{id}/timeline`); sources (`source_citations`) and media. The
free-form JSON fields are flattened defensively by `lib/entity-format.ts`.

### ChroniclePage

`components/atlas/ChroniclePage.tsx` (`?chron=<slug>&full=1`), from `useChronicle` (the
entries' narrative) and `useChronicleGraph` (the graph + per-step membership), joined by
`entry_id` (`stepRows`; the row index is the `step` param).

- **Header:** chronicle / source-type / status badges, title, span, step count, and a
  ledger (began, ended, steps, entities, relations, impact). "About this chronicle" at the
  bottom shows `source_reference` (a link, or the transcript excerpt) and `metadata`.
- **Whole-chronicle graph:** chronicle entities solid, externals dimmed (`dimmedNodes`),
  primary relations heavy (`emphasisedEdges`). Externals are toggled by the filter bar's
  "outside the chronicle" chip and start **off above 400 edges** (`defaultShowExternal`):
  fcose lays out Imperial Rome (221–402 nodes) in ~150 ms and the 621-node
  age-of-revolutions chronicle in ~470 ms either way, but past ~400 edges the external
  fringe buries the chronicle's own structure. A step scrubber (slider + prev/next +
  "Show all") highlights a step's subgraph in place (`stepHighlight`) and frames it
  (`fitHighlight`), with the step's primary edge labelled and its narrative under the
  slider. It starts on the tour's current step when opened mid-tour, else on "all".
- **Step list:** every step shows its year, narrative, the primary relation (`WhatChanged`,
  shared with the player), "Focus in the main graph" (sets the scrubber and scrolls up),
  and its own compact graph (`stepSubgraph`, primary emphasised and labelled) with a
  per-step "+ N external" switch (`external` prop). Step graphs mount through
  `useNearViewport` — within 300 px of the page viewport, unmounted beyond 1200 px — over
  a fixed-height placeholder, so the list never jumps. Measured on the 123-step Imperial
  Rome chronicle (headless Chrome, 1440×900): at most 9 cytoscape instances alive while
  scrolling (6 at rest), p95 frame 16.8 ms and no long tasks at ~2,200 px/s.
- Clicking a node's Open (or any entity in a step) selects it, which opens the entity
  page on top.

### RelationGraph and `lib/graph`

`components/graph/RelationGraph.tsx` is the shared graph view (entity page and chronicle
page). Contract: `docs/schemas/relation-graph-api.md`.

- **Engine:** cytoscape + fcose, loaded by dynamic import on first mount
  (`cytoscape-loader.ts`) — separate chunks, never in the atlas entry bundle.
- **Props:** `nodes`, `edges` (memoised — a new identity resets the graph), `rootId`,
  `expandable`, `highlight` (`{nodes, edges?}` to fade the rest, e.g. a step scrubber),
  `fitHighlight` (frame the highlight when it changes), `emphasisedEdges` (heavy),
  `labelledEdges` (always labelled), `dimmedNodes` (e.g. chronicle externals, edges
  included), `compact`, `initialFilter`, `externalToggle` (the chip) or `external`
  (controlled switch), `onOpen` (default: select the entity), `height`, `truncated`,
  `label`.
- **Encoding:** colour = entity-group token (resolved from CSS variables per theme, so
  light/dark both work), size = `impact_score` (1–100), arrows = direction, edge label =
  relationship type on hover/selection, double ring = expanded, heavy ring = root.
- **Interaction:** clicking a node opens an info card (relation to the root — direct edges,
  else the shortest path in view — plus Open / Expand / Collapse); clicking an edge shows
  its description. Expand fetches the node's depth-1 neighbourhood and lays out **only the
  new nodes** around it with every other node pinned (`fixedNodeConstraint`). Filters
  (relationship-type chips with counts, entity-group chips, year range, chronicle-external
  toggle) toggle visibility and never refetch. Layouts only run over visible elements;
  a node a filter later reveals is placed beside its visible neighbours with the rest
  pinned (`placeNodes`), so toggling never moves what was already on screen. Plain wheel scrolls the page; Ctrl/⌘ +
  wheel or pinch zooms. Controls (zoom, fit, reset, legend, filters) are focusable buttons.
- **Pure logic** (`lib/graph/`, Vitest): `createGraphModel` / `mergeNeighbourhood` /
  `collapseExpansion` track which owner (base or expansion) needs each node and edge, so a
  collapse removes only what nothing else needs (cascading into removed nodes'
  expansions); `computeVisibility` + facet helpers implement the filters;
  `stepSubgraph` / `stepHighlight` slice the chronicle graph per step.

## Caching strategy

- **Snap before keying** — raw bbox lives in the URL and drives the camera; the snapped
  scope keys the cache. Sub-tile pans = same key = cache hit, zero fetch.
- **`keepPreviousData`** on the viewport query — old pins stay on screen during refetch,
  no empty-map flash.
- **High `staleTime`** — historical data is immutable (`Infinity` for entity detail and
  chronicles).
- **Structural sharing** keeps untouched entities referentially stable so memoized rows
  and pins don't re-render.
- **Abort on key change** via the query `signal` — fast scrubs cancel in-flight requests.
- **Prefetch on intent** — hover a row/pin warms `useEntity`; chronicles prefetch step
  n+1.

## Re-render budget

The map pins, list, panel, and timeline are independent subscribers. The enforced budget:

| Action | May re-render | Must NOT re-render |
|---|---|---|
| Pan within tile | nothing | list, panel, timeline |
| Pan across tile | map pins, list | panel, timeline, top bar |
| Scrub (drag) | scrubber readout, ghost filter | list, panel, map source |
| Release scrub | map pins, list, density | panel (unless sel left view) |
| Select entity | detail panel + 1 feature-state flag | list, map component, timeline |
| Hover entity | 1 feature-state flag | everything in React |
| Toggle filter | list, map pins, chips | panel, timeline, top bar |

Bought by: per-key URL subscriptions, snap-before-key, gestures outside React, imperative
map (`setFeatureState`), zustand selector reads, memoized/virtualized rows, and
`keepPreviousData`. **Litmus test:** highlight re-renders in DevTools, pan one pixel —
nothing should flash.

## Relationship to the backend

The frontend keys everything on the snapped scope and expects the API to do the
geospatial + temporal filtering server-side in a single query (no PHP↔Postgres round
trips — see the map-query-optimization plan). The viewport endpoint returns
prominence-ranked entities for `{ bbox, time, groups }` with a total count for the
"show all N" affordance. The exact endpoint contract is defined separately; this app
consumes it through `lib/api/` with zod-validated responses.

## Build order

URL schema → scope/snapping → query client + key factory → persistent map shell → browse
list → detail panel → timeline → search → chronicles → mobile/highlights. Each step lands
on finished plumbing. See the spec's §9 for per-step verification checkpoints.

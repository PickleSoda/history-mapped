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
| Routing | react-router-dom v7 (persistent layout route + `<Outlet/>`) |
| URL state | nuqs (typed, validated, per-key search-param hooks) |
| Server cache | TanStack Query v5 |
| Ephemeral state | zustand (selector reads) + `useRef` |
| Validation | zod (API response schemas + URL parsers) |
| Map | MapLibre GL (WebGL, globe projection, imperative feature-state) |
| UI | shadcn/ui on Tailwind v4 |
| HTTP | axios (`src/lib/api.ts`) |

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
│   bbox · t · g · sel · q · chron · step · view                    │
└───────────────┬───────────────────────────────────────────────────┘
                │ snapScope()  (snap bbox→tile grid, time→resolution)
                ▼
┌─────────────────────────────────────────────────────────────────┐
│ Server cache (TanStack Query)   cache only · re-derivable         │
│   entitiesInView · entity · connections · search · highlights ·   │
│   density · chronicle                                             │
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
  router.tsx        route tree (AtlasLayout → BrowsePanel / ChronicleIndex / ChroniclePlayer)
lib/
  api/              typed endpoint fns (entitiesInView, entity, search, …) over axios
  query/
    client.ts       QueryClient config (staleTime, gcTime defaults)
    queryKeys.ts    the `qk` key factory — single source of truth for keys
  url/              nuqs parsers/serializers per param (bbox, time, groups, sel, q, …)
  scope/            snapScope, snapBboxToTiles (quadkey), snapTime
  schemas/          zod schemas (API responses + URL param validation)
  utils.ts          cn() etc. (shadcn)
hooks/              the hook inventory (URL-state, derived, server-cache, ephemeral)
stores/             zustand ephemeral store (slices: scrub, hover, palette, sheet, mapRef)
components/
  ui/               shadcn primitives
  map/              MapCanvas (persistent, imperative)
types/              shared domain types
```

## The hook seam

Components never touch the router or query client directly — they go through hooks. This
keeps the three-layer boundary enforceable in one place.

- **URL-state hooks** — `useViewport`, `useTimeState`, `useFilters`, `useSelection`,
  `useSearchQuery`, `useChronicleNav`. Each subscribes to **one** nuqs key, so moving bbox
  cannot wake `useSelection`.
- **Derived** — `useScope()` returns the memoized snapped `{ bbox, z, time, groups }` that
  every viewport query keys on.
- **Server-cache hooks** — `useEntitiesInView`, `useEntity`, `useEntityConnections`,
  `useSearch`, `useHighlights`, `useTimelineDensity`, `useChronicle`, `usePrefetchEntity`.
- **Ephemeral/imperative** — `useMapInstance`, `useLiveScrub`, `useHover`, `useSheet`,
  `useCommandPalette`.

## Routing

The map is a **persistent layout**, not a page. One layout route mounts the map + timeline
and renders `<Outlet/>` into the side panel; children swap only the panel.

```
/                      AtlasLayout      (map + timeline — always mounted)
  index                BrowsePanel      (notable-here list)
  chronicles           ChronicleIndex
  chronicles/:cid      ChroniclePlayer  (reads ?step=)
```

Selection (`?sel=`), search (`?q=`), filters (`?g=`), time (`?t=`), bbox, and view are all
**search params** layered on any route — never separate route components. Mobile uses the
same routes with the aside re-expressed as a draggable sheet (ephemeral height).

**History hygiene:** pan/zoom/scrub/filter-toggle use `replace`; entity select and
chronicle step use `push` (so the back button deselects / walks steps).

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

# Atlas Frontend Plumbing — Design Spec

> Status: approved 2026-06-13 · Scope: `web/` SPA core (pre-UI plumbing) · Stack decisions locked.

## Purpose

Establish the state model, hooks, data layer, and routing for the Historical Atlas
frontend **before any UI is built**. Everything in the Atlas is a function of three
questions: **where** are we looking (bbox), **when** are we looking (time), and **what**
is selected. Get ownership of those three right and the rest of the app — browse list,
detail, search, chronicles — falls out as derived data.

## The one rule that drives everything

> The URL is the query input. TanStack Query is the data. The map and gestures are the
> only things allowed to live outside React.

```
URL search params → derive scope → TanStack query keys → cached data → render
```

There are three places state can live. The entire goal is to assign each piece of state
to **exactly one** of them — never two. Duplicated state (a year in both the URL and a
store) is the source of every desync bug.

## Stack decisions (locked)

| Concern | Choice | Notes |
|---|---|---|
| Framework | React 19 + Vite 7 | Already present |
| Data cache | TanStack Query v5 | Already present |
| Router | **react-router-dom v7** | Already present; map is a persistent layout route |
| URL state | **nuqs** | Typed/validated per-key search-param hooks with push/replace per key + selective re-renders |
| Validation | **zod** | API response schemas + URL param parsers |
| Ephemeral state | **zustand** + `useRef` | Selector reads only |
| Map | **MapLibre GL only** | WebGL, globe projection, `setFeatureState`. Leaflet rejected (no WebGL feature-state / globe) |
| UI primitives | **shadcn/ui** | On Tailwind v4 (already present); requires `@/` alias |
| HTTP | axios | Already present (`src/lib/api.ts`) |

**Selection routing:** selected entity lives in the URL as the **search param `?sel=`**,
not a nested `/entity/:id` route. The panel is conditional UI reading `sel`; the map stays
a persistent layout and never remounts.

## 1. State taxonomy

Decide which layer a value belongs to by asking: should it survive a refresh? should it
be in a shared link? does it change 60×/second?

| Layer | Owns | Tooling | Survives refresh / shareable |
|---|---|---|---|
| **URL** | bbox, time (instant or range), selected entity id, active group filters, search query, active chronicle + step, panel mode, map vs globe | nuqs search params | **Yes** — the shareable state of the app |
| **Server cache** | entities-in-view, entity detail, connections, search results, highlights, chronicle data, timeline density | TanStack Query | Cache only — re-derivable from URL on cold load |
| **Ephemeral** | live (uncommitted) pan/scrub value, hover target, command-palette open, mobile sheet height, draft filters, map instance ref | zustand + `useRef` | No — interaction-only, lost on refresh |

**The boundary that matters:** during a continuous gesture (drag-pan, scrub) the value
lives in the **Ephemeral** layer and drives the UI at 60fps. It is committed to the **URL**
layer only on gesture end. That single debounce boundary stops history spam and re-fetch
storms.

## 2. URL schema

Design the query string as a real API — typed, validated, minimal. Everything
reconstructable from this string; a pasted link drops another user into the exact view.

```
/?bbox=...&t=...&g=...&sel=...&q=...&chron=...&step=...&view=...

bbox   = "w,s,e,n"      // 4 floats, snapped (see §3). Map viewport.
t      = "-490"         // single year (negative = BCE). The timeline instant.
t      = "-490..-480"   // OR a range, when the scrubber is in window mode.
g      = "polity,event" // active group filters; omitted = all five.
sel    = "e:marathon"   // selected entity, type-prefixed id. Drives the detail panel.
q      = "marathon"     // search query; presence opens the command palette.
chron  = "greco-persian"// active chronicle id.
step   = "3"            // chronicle step index.
view   = "map" | "globe"
```

### Push vs replace — back-button hygiene

| Change | History op | Why |
|---|---|---|
| pan / zoom / scrub time | `replace` | continuous; one entry per gesture, not per frame |
| select an entity | `push` | discrete; back should deselect |
| open chronicle / next step | `push` | back should walk steps backward |
| toggle a group filter | `replace` | refinement of current view, not a destination |

**Why nuqs:** per-key hooks with parsers/serializers and a `history: 'push' | 'replace'`
option per key. Subscribing to `useQueryState('sel')` re-renders only on `sel` changes —
not when bbox moves. That selective subscription is half the re-render budget (§8).

## 3. Scope & snapping — the heart of caching

**Scope** is the derived object `{ bbox, z, time, groups }` that every viewport query
keys on. The raw map bbox changes on every pixel of pan — keying the cache on the raw bbox
gives a fresh fetch and zero cache hits. So we **snap before keying**.

```ts
function snapScope(raw) {
  // 1. Snap zoom to an integer level, then quantize the bbox to that level's
  //    tile grid (quadkey). Panning within a tile = same key.
  const z = Math.round(raw.zoom);
  const bbox = snapBboxToTiles(raw.bbox, z); // → expanded to whole tiles

  // 2. Snap time to the band the timeline can actually resolve. Century-wide
  //    zoom → snap to decade; zoomed in → snap to year.
  const time = snapTime(raw.time, raw.timelineZoom);

  // 3. Sort groups for a stable key regardless of toggle order.
  const groups = [...raw.groups].sort();

  return { bbox, z, time, groups };
}
```

**Two bbox values, on purpose:** the **raw** bbox lives in the URL (so the link restores
the exact view) and drives the map camera. The **snapped** scope is what the query key
uses. Pan a little → URL updates (`replace`) → snapped scope unchanged → cache hit, zero
fetch. Pan past a tile boundary → snapped scope changes → one fetch.

**Over-fetch the viewport:** fetch a bbox slightly larger than screen (~1.3×) so small
pans never trigger a fetch and pins are pre-loaded just off-screen.

## 4. TanStack Query design

One **query-key factory** is the single source of truth for keys. Never hand-write a key
array at a call site — always go through the factory so invalidation and prefetch line up.

```ts
// lib/query/queryKeys.ts
export const qk = {
  entitiesInView: (scope) => ['entities', 'view', scope.z, scope.bbox, scope.time, scope.groups],
  entity:         (id)    => ['entity', id],
  connections:    (id)    => ['entity', id, 'connections'],
  search:         (q, f)  => ['search', q, f.groups, f.time],
  highlights:     (time)  => ['highlights', time],
  density:        (scope) => ['density', scope.bbox, scope.groups],
  chronicle:      (id)    => ['chronicle', id],
};
```

```ts
// the viewport query — runs constantly
function useEntitiesInView() {
  const scope = useScope();                // snapped {bbox, z, time, groups}
  return useQuery({
    queryKey: qk.entitiesInView(scope),
    queryFn:  ({ signal }) => api.entitiesInView(scope, signal),
    placeholderData: keepPreviousData,     // map keeps old pins while next loads, no flash
    staleTime: 5 * 60_000,                 // history is immutable; cache hard
    gcTime:    30 * 60_000,
  });
}
```

**Caching levers that matter:**
- **`keepPreviousData`** — previous result stays on screen until the new one arrives. No
  empty-map flash on pan/scrub. The single most important UX lever.
- **High `staleTime`** — historical data is immutable; `staleTime: Infinity` for entity
  detail and chronicle data.
- **Structural sharing** (default on) — unchanged entities keep referential identity, so
  memoized rows/pins don't re-render when one item changed.
- **Abort on key change** — pass `signal` to fetch; a fast scrub cancels in-flight
  requests instead of racing.
- **Prefetch on intent** — `prefetchQuery` on row/pin hover warms the detail panel before
  the click. For chronicles, prefetch step n+1's entity + scope.

## 5. Core hooks inventory

The seam between the three state layers. Every component reads the app through these;
nothing reaches the router or query client directly.

**URL-state hooks** (read + write search params)

| Hook | Returns / does | Re-renders on |
|---|---|---|
| `useViewport()` | raw bbox + zoom ↔ URL; `replace`, debounced on gesture-end | bbox |
| `useTimeState()` | instant or range ↔ URL; play/pause stepping | t |
| `useFilters()` | active groups set ↔ URL; toggle helpers | g |
| `useSelection()` | selected id ↔ URL (`push`); select / clear | sel |
| `useSearchQuery()` | q ↔ URL; open/close palette | q |
| `useChronicleNav()` | chron + step ↔ URL; next/prev/exit | chron, step |

**Derived**

| Hook | Returns |
|---|---|
| `useScope()` | memoized `snapScope({ bbox, time, groups })` — the query input; stable object so query keys don't thrash |

**Server-cache hooks** (TanStack Query wrappers)

`useEntitiesInView()` · `useEntity(id)` · `useEntityConnections(id)` · `useSearch(q)` ·
`useHighlights(time)` · `useTimelineDensity()` · `useChronicle(id)` · `usePrefetchEntity()`

**Ephemeral / imperative**

`useMapInstance()` (ref to maplibre; imperative `flyTo`, feature-state) ·
`useLiveScrub()` (uncommitted scrub value, commits to `useTimeState` on release) ·
`useHover()` (cross-highlight) · `useSheet()` (mobile sheet height) ·
`useCommandPalette()` (⌘K open state).

## 6. Features (vertical slices)

- **Map canvas** (persistent, imperative) — owns camera, basemap, pins & territory layers.
  Queries `useEntitiesInView()`. React writes data into the map imperatively (set GeoJSON
  source, `setFeatureState` for selected/hover); **never re-render the map to move it**.
  Camera reads bbox from URL on mount + programmatic `flyTo`; gestures write bbox out on
  settle.
- **Time + bbox (scope)** — the spine. Scrubber drag updates `useLiveScrub` (ephemeral) at
  60fps; release commits `t` to URL → one viewport fetch. Playback steps `t` (with
  `replace`); prefetch the next few years during play. Queries `useTimelineDensity()`.
- **Impactful entity listing** — "Notable here" list reads the **same** query as the map
  (one fetch feeds both). Server returns prominence-ranked top-N + total count. Rows
  `React.memo`'d, keyed by id, virtualized past ~50. Row hover → `useHover` → map
  feature-state, no list re-render.
- **Search + filters** — ⌘K palette. Filters (`g`) are URL state (shape both list and
  map). `q` is URL too (shareable search). Debounce input (~200ms), `keepPreviousData` so
  results don't flicker. Select → write `sel` (`push`) + `flyTo`.
- **Detail panel** — pure function of `sel`. Queries `useEntity(sel)` +
  `useEntityConnections(sel)`. Changing selection re-renders only the panel + toggles one
  feature-state flag. `geometry: null` → "not placed" banner + related places. Prefetch on
  hover.
- **Chronicle** (guided / scrollytelling) — while `chron` is set, the active step's
  `{ time, bbox }` drives map and locks the timeline. Step = bump `step` (`push`) →
  `flyTo` + re-filter. Prefetch step n+1. Paged and scrollytelling share state; an
  IntersectionObserver maps scroll → step. Queries `useChronicle(id)` (whole tour, one
  fetch).
- **Period highlights** (transient) — banner on meaningful time jump; dismissable, not in
  URL. Queries `useHighlights(time)`; cards link into `sel`.

## 7. Screens & routing

**The central decision: the map never unmounts.** It is a persistent layout, not a page.
Re-initialising a WebGL map on every navigation is slow and loses camera/cache. "Screens"
are states layered over one shell, expressed mostly as search params, with at most a thin
nested route for the panel.

```
/                      → AtlasLayout  (map + timeline, always mounted)
  index                → BrowsePanel  (notable-here list)
  chronicles           → ChronicleIndex
  chronicles/:cid      → ChroniclePlayer  (reads ?step=)

// selection (?sel=), search (?q=), highlights, filters (?g=), time (?t=), bbox, view
// — all SEARCH PARAMS layered on top of any route.
```

A single layout route mounts the map + timeline and renders an `<Outlet/>` into the
`aside`. Children swap only the panel; the map stays alive underneath. **Selection is a
search param** (`?sel=`), so the detail panel is conditional UI, not a route.

Screen → state map: default browse `/` · search `/?q=` · highlights (transient) ·
selection point `/?sel=e:…` · selection territory `/?sel=p:…` · selection no-geometry
`/?sel=c:…` · chronicle paged `/chronicles/:cid?step=n` · chronicle scrolly
`/chronicles/:cid?step=n&mode=scroll` · mobile sheet (any URL + ephemeral `useSheet`).
Mobile is the **same** routes/params with the aside re-expressed as a draggable sheet — no
separate route tree.

## 8. Re-render budget

What is **allowed** to re-render per action. More than this means something reads state it
shouldn't.

| Action | Allowed to re-render | Must NOT re-render |
|---|---|---|
| Pan within a tile | nothing (URL `replace` only) | list, panel, timeline |
| Pan across tile boundary | map pins layer, list (new data) | panel, timeline, top bar |
| Scrub time (dragging) | scrubber readout, ghost filter | list, panel, map source |
| Release scrub | map pins, list, density | panel (unless `sel` left view) |
| Select entity | detail panel, 1 feature-state flag | list rows, map component, timeline |
| Hover entity | 1 feature-state flag | everything in React |
| Toggle filter | list, map pins, chips | panel, timeline, top bar |

**The seven rules that buy that budget:**
1. **Per-key URL subscriptions** — `useSelection` reads only `sel`; bbox can't wake it.
2. **Snap before keying** (§3) — sub-tile pans don't change the query key.
3. **Gestures live outside React** — live values in refs/zustand; commit on settle.
4. **Drive the map imperatively** — selection/hover = `setFeatureState`, not React state.
5. **Selector reads from zustand** — `useStore(s => s.hoverId)`, never the whole store.
6. **Memoize + key + virtualize list rows** — structural sharing makes `React.memo` pay.
7. **`keepPreviousData` everywhere** — no unmount/remount churn on scope change.

**Litmus test:** with React DevTools "highlight re-renders," pan one pixel → nothing
flashes. Scrub + release → only the map pin layer, the list, and density bars flash. If the
detail panel or top bar lights up, a component is over-subscribed.

## 9. Build order

Build the plumbing bottom-up so every screen lands on a finished foundation:

1. **URL schema + parsers** — `useViewport`, `useTimeState`, `useFilters`, `useSelection`.
   Verify back button + pasted link restore state. No data yet.
2. **Scope + snapping** — `useScope` with tile/time quantization; log key changes while
   panning to confirm cache hits.
3. **Query client + key factory** — `useEntitiesInView` against a mock API; wire
   `keepPreviousData` + `staleTime`.
4. **Persistent map shell + layout route** — map mounts once, reads bbox, writes bbox on
   settle, renders pins from the query.
5. **Browse list** — same query, memoized rows, hover ↔ map feature-state.
6. **Detail panel** — `useEntity` + prefetch-on-hover; selection states
   (point / territory / no-geom).
7. **Timeline** — live scrub → commit; density histogram; playback with look-ahead
   prefetch.
8. **Search** — ⌘K palette, debounced `useSearch`, filters.
9. **Chronicles** — derive scope from step; paged first, then scrollytelling via
   IntersectionObserver.
10. **Mobile sheet + highlights** — re-express the aside; transient banner.

## Out of scope (this pass)

UI/visual design, component styling, the actual screen layouts, and the backend
bounding-box endpoint contract. This spec is plumbing only — it stops at "the hooks exist,
the providers are wired, and a mock viewport query renders pins." The Atlas wireframe
system (Geist · five entity groups) drives the UI in a later pass.

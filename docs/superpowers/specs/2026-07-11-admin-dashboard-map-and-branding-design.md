# Admin Dashboard Map Remake + History Mapped Branding

**Date:** 2026-07-11
**Surface:** Inertia admin app (`api/resources/js`) only. The public `web/` SPA is untouched.
**Status:** Design approved pending user spec review.

## Goal

Two admin improvements in one cycle:

1. **Dashboard map remake** — the admin dashboard's map currently renders every entity as a
   generic blue circle with no labels. Replace it with the web Atlas's entity rendering:
   per-group glyph markers, name labels, group-colored territory fills/outlines, and
   viewport-driven loading. ("Same as web" = the points/markers/behavior — NOT the web's
   woodblock/turquoise basemap or theme; the admin keeps its own basemap config.)
2. **Branding sweep** — replace leftover Laravel-starter-kit wording and links with
   History Mapped branding on the `/` landing page, sidebar, and header.

## Part 1 — Dashboard map

### Decisions (user-confirmed)

- **Scope: dashboard only.** The shared `HistoricalMapViewer` (used by `entities/edit` and
  `entity-history-panel`) is NOT modified. A new dedicated component serves the dashboard.
- **Data: viewport + year, like web.** Use the same `GET /api/v1/entities/map` endpoint the
  SPA uses (`bbox_min_lng`/`bbox_min_lat`/`bbox_max_lng`/`bbox_max_lat`, `zoom_level`,
  `year`, `min_results`, `limit`), re-fetching on debounced pan/zoom. The current
  `/api/v1/entities/map/year` bulk fetch on the dashboard is dropped.
- **Click: keep the side panel.** Clicking a marker/territory selects the entity id; the
  existing dashboard side panel (backed by `GET /api/v1/entities/{id}`) and its
  "open entity" link stay.

### Approach (chosen: dedicated component, port from web)

Port the web's proven pieces into the admin bundle rather than extending the 1,460-line
shared viewer (rejected: high blast radius) or extracting a shared workspace package
(rejected: YAGNI for one consumer each; the admin already maintains its own `map-config.ts`
copy — this follows the same pattern).

### Components

- **`api/resources/js/lib/entity-map-icons.ts`** (new) — port of `web/src/lib/map-icons.ts`:
  per-group SVG disc markers (lucide glyph bodies for POLITY crown / PLACE map-pin /
  EVENT star / ECONOMY coins / CULTURE landmark + DEFAULT dot), registered as map images
  (`marker-<GROUP>`, `marker-DEFAULT`), idempotent registration. The admin has no `--g-*`
  CSS variables, so the group palette is exported constants (web's light values):
  polity `#b4543f`, place `#6b7f4a`, event `#bd8a2c`, economy `#4d6a86`, culture `#8a5673`,
  default `#71717a`.
- **`api/resources/js/components/dashboard-map.tsx`** (new) — self-contained map:
  - MapLibre map on the admin's existing `loadHistoricalBasemapStyle()`; year prop drives
    the admin's existing `applyOhmLayerDateFilter`.
  - `entities` GeoJSON source + three layers exactly like the web's `MapCanvas`:
    `entities-fill` (group color, `fill-opacity` 0.15), `entities-line` (group color,
    width 1), `entities-symbols` (marker icon by group + entity name label, text
    `#2a2722` with `#ffffff` halo, size 11).
  - Group color via a maplibre `match` expression on `entity_group` using the palette
    constants.
  - Debounced (250 ms) `moveend` → bbox state; TanStack Query
    `['dashboard-map', bbox, year]` → the map endpoint with session credentials; result
    FeatureCollection pushed to the source imperatively.
  - Click on symbol/fill → `onSelect(entityId)` prop callback; pointer cursor on hover.
  - Props: `{ year: number; onSelect: (id: string) => void; onCountChange?: (n: number) => void; className?: string }`.
- **`api/resources/js/pages/dashboard.tsx`** (modified) — swap `HistoricalMapViewer` for
  `DashboardMap`; remove the `/entities/map/year` query; keep the year input (wired to the
  `year` prop), the selected-entity query + side panel, and the visible-entity count
  readout (now fed by `onCountChange`). Empty state ("No mapped entities…") keeps working
  off the count.

### Error handling

- Query failures surface as the dashboard's existing muted error text (no crash; map stays).
- The map component guards layer mutations with `map.getLayer(...)` and tolerates unmount
  mid-load (cancellation flag, same pattern as web's `MapCanvas`).

### Testing

- Admin vitest: `entity-map-icons` unit tests (marker image id mapping, palette lookup,
  SVG generation contains the group color, registration idempotence with a fake map).
- `dashboard-map` render test with `maplibre-gl` mocked, following the existing
  `historical-map-viewer.test.tsx` pattern (asserts source/layers added and query URL shape).
- Gates: admin `npm run lint`, `npm run types:check`, `npm test` (run in the `app`
  container per project convention), plus `composer test` untouched-backend sanity.
- Live verification on `:8000/dashboard` (restart `app` container first — stale bind-mount
  gotcha).

## Part 2 — Branding sweep

| Location | Current | New |
|---|---|---|
| `components/app-logo.tsx:11` | `Laravel Starter Kit` | `History Mapped` |
| `components/app-sidebar.tsx` footer items | Repository → `github.com/laravel/react-starter-kit`; Documentation → `laravel.com/docs/starter-kits#react` | Repository → `https://github.com/PickleSoda/history-mapped`; Documentation → `https://github.com/PickleSoda/history-mapped/tree/develop/docs` |
| `components/app-header.tsx` (same two links) | same as above | same as sidebar |
| `pages/welcome.tsx` (the `/` landing) | Laravel starter marketing ("Let's get started", Laravel ecosystem links, Laravel logo SVG) | Minimal History Mapped landing: wordmark, tagline "An interactive historical atlas", the existing auth-aware Log in / Register / Dashboard nav kept as-is, plus the two GitHub links above. Reuses the page's existing utility-class styling; no new design system. |

- No GitHub Pages site exists (probed: 404) — the Documentation link targets the `docs/`
  tree on the `develop` branch; swap to a Pages URL later if one is published.
- The browser-tab title comes from `config('app.name')`; `.env.example` already says
  `history-mapped`. **Operator note:** if the runtime `api/.env` still has `APP_NAME=Laravel`,
  update it manually (not a committed file).

## Non-goals

- No changes to `HistoricalMapViewer`, the entity edit page, or the history panel.
- No basemap/theme changes in the admin (keeps OHM main style).
- No dark-mode work; the admin's existing appearance system is untouched.
- No shared map package extraction.

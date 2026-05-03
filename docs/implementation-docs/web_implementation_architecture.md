# history-mapped — Web Implementation Architecture

**Version 1.0 — March 2026**

Companion to: Data Pipeline and Storage Architecture, Foundational Architecture Document

---

## 1. Purpose and Scope

This document defines the architecture for the customer-facing Historical Atlas web application. It covers the technology stack, rendering strategy, data flow patterns, and feature architecture. It does not cover the admin panel (see companion document) or the data ingestion pipeline (see Data Pipeline Architecture).

The application is an interactive, map-centric tool for exploring historical entities, events, and relationships across time and geography. The primary interface is a full-viewport map with temporal controls, search, and contextual detail panels.

---

## 2. Technology Stack

### 2.1 Core Framework

- **React** as the UI framework
- **Vite** as the build tool and dev server
- **TypeScript** throughout

### 2.2 UI and Component Layer

- **shadcn/ui** as the component library (Tailwind CSS utility classes, Radix UI primitives)
- **Tailwind CSS** for all styling
- Components are feature-scoped, not globally shared unless proven reusable across three or more features

### 2.3 Data Fetching and State

- **TanStack Query (React Query)** for all server state: entity fetching, search results, viewport data, user preferences
- **Zustand** (or React context where trivial) for client-only UI state: selected entity, active time range, open panels, map view state
- No global state management library for server data — TanStack Query is the single source of truth for anything that comes from the API

### 2.4 Map Rendering

- **MapLibre GL JS** as the map rendering engine (WebGL, vector tiles, hardware-accelerated)
- **react-map-gl** (visgl/react-map-gl, MapLibre fork) for idiomatic React integration
- **@openhistoricalmap/maplibre-gl-dates** for filtering OHM vector tiles by historical date
- **@openhistoricalmap/map-styles** for base OHM stylesheets (customizable via Maputnik)

### 2.5 Routing

- **React Router** (or TanStack Router) for client-side routing
- URL state encodes the current map view (center, zoom), selected date, and active entity — enabling shareable deep links

---

## 3. Map Architecture

### 3.1 Layer Composition

The map is composed of three distinct layer groups, rendered in this order (bottom to top):

**Layer 1 — OHM Base Map (historical geography)**
Source: OpenHistoricalMap vector tiles from `vtiles.openhistoricalmap.org`. These provide historical coastlines, borders, cities, rivers, and roads filtered by the currently selected date. The OHM style is loaded as the MapLibre base style. The `maplibre-gl-dates` plugin filters all OHM layers by the active date on the time slider.

**Layer 2 — Entity Data (our data)**
Source: The Historical Atlas API, loaded dynamically per viewport. This is the core data layer — battles, cities, trade routes, empires, people, and all 30 entity types from the database specification. Rendered as a GeoJSON source in MapLibre, updated reactively as the user pans, zooms, or changes the time range.

**Layer 3 — Annotations and Overlays (user/editorial)**
Source: The Historical Atlas API. Bezier curves, relationship arrows, custom labels, and editorial overlays created by editors in the admin panel. Loaded per viewport alongside entity data.

### 3.2 OHM Tile Strategy

OHM vector tiles are consumed directly from the public OHM tile endpoint. No self-hosting of OHM tiles is required initially. If performance or availability becomes a concern, the OHM planet file can be downloaded and served locally via Martin or as a PMTiles archive on MinIO.

The OHM style can be customized to reduce visual weight — stripping unnecessary layers (modern POIs, transit lines) and simplifying the palette so that our entity data layer has visual prominence over the base geography.

### 3.3 Custom Tile Serving (Martin)

For scenarios where entity density is very high (zoomed-out views of well-populated regions/periods), a Martin tile server instance can serve pre-computed entity tiles directly from PostGIS. Martin connects to the same PostgreSQL/PostGIS database used by the API and auto-discovers geometry columns, serving them as MVT vector tiles.

Martin is deployed as a Docker Compose service alongside the existing stack. It serves tiles at a dedicated endpoint (e.g., `/tiles/{table}/{z}/{x}/{y}.pbf`) and is placed behind an nginx reverse proxy with aggressive cache headers.

This is an optimization path — not required for initial launch. The viewport-driven GeoJSON approach (Section 4) handles moderate entity volumes without a tile server.

### 3.4 Static Tilesets (PMTiles)

For curated, read-only datasets that change infrequently (e.g., a "greatest empires" overlay, a pre-built trade routes layer), PMTiles archives can be generated from GeoJSON exports using tippecanoe, stored on MinIO, and loaded client-side via the `pmtiles` protocol plugin for MapLibre. This requires zero server infrastructure — the browser reads tiles directly from the static file via HTTP range requests.

---

## 4. Viewport-Driven Entity Loading

### 4.1 Core Principle

Entity data is never loaded all at once. The application fetches only the entities visible in the current map viewport, at the appropriate level of detail for the current zoom level, filtered by the active time range. This keeps payloads small (typically 10–200 features per request) and rendering fast.

### 4.2 Zoom-Level Tiers

The API returns different response shapes depending on the zoom level:

**Tier 1 — Aggregated clusters (low zoom, z0–z6)**
The server groups entities into spatial grid cells using PostGIS. Each cell is returned as a single point with a count and dominant entity type. The client renders these as cluster markers with counts. No individual entity data is transferred.

**Tier 2 — Centroid markers (mid zoom, z7–z12)**
The server returns individual entity centroids with minimal metadata: id, name, entity type, icon class. No full geometries, no summaries. The client renders these as typed icon markers. Clicking a marker fetches the full entity record on demand.

**Tier 3 — Full geometries (high zoom, z13+)**
The server returns full entity geometries (points, lines, polygons) with enough metadata for hover tooltips and the detail panel. Geometries are simplified server-side using PostGIS `ST_Simplify` proportional to the zoom level.

### 4.3 Query Lifecycle

1. The map fires a `moveend` event after any pan or zoom interaction
2. A debounce timer (150–300ms) prevents rapid successive requests during smooth panning
3. The current bounding box is quantized to a coarser grid (snap coordinates to reduce cache-key entropy) so that small pans reuse cached results
4. A TanStack Query is issued with the key: `[bbox, zoom_tier, date_range, active_filters]`
5. TanStack Query checks its cache — if the same quantized viewport was recently fetched, the cached result is returned instantly
6. `keepPreviousData` is enabled so the map retains the old markers while new data loads, preventing visual flash
7. On success, the GeoJSON source in MapLibre is updated with the new feature collection

### 4.4 Temporal Filtering

The time slider controls two independent systems:

- **OHM base layer:** The `maplibre-gl-dates` plugin filters OHM vector tile features by the selected date, showing only geography that existed at that time
- **Entity data layer:** The selected date range is passed as a query parameter to the viewport API, and the server filters entities using their `temporal_start` and `temporal_end` fields

Both filtering mechanisms are triggered by the same time slider interaction, keeping the base map and entity layer temporally synchronized.

---

## 5. Feature Architecture

The application is organized into features, each owning its own components, hooks, types, and API calls. Features communicate through shared state (Zustand store or URL state) and TanStack Query cache, not through direct imports.

### 5.1 Map Feature

Owns the MapLibre instance, layer management, viewport state, and all map interaction handlers (click, hover, moveend). Exposes the map instance to other features only through a stable ref or context — no direct MapLibre API calls from outside this feature.

### 5.2 Time Control Feature

Owns the time slider UI, date parsing (EDTF format support), playback/animation controls, and the active date state. When the date changes, this feature updates both the OHM date filter and the entity query parameters.

### 5.3 Entity Viewport Feature

Owns the viewport-driven data loading loop described in Section 4. Manages the GeoJSON source lifecycle, zoom-tier switching, bbox quantization, and debouncing. Consumes the active date and filter state from other features.

### 5.4 Entity Detail Feature

Owns the detail panel that appears when an entity is selected. Fetches the full entity record (summary, relationships, source citations, confidence metadata) via a dedicated TanStack Query keyed by entity ID. Displays the entity's full geometry on the map as a highlighted overlay.

### 5.5 Search Feature

Owns the search input, autocomplete dropdown, and search results panel. Supports both keyword search (via the API's text search endpoint) and semantic search (via the pgvector similarity endpoint). Search results are displayed as a list and optionally as markers on the map.

### 5.6 Relationship Feature

Owns the rendering of relationship lines, arrows, and bezier curves between entities on the map. When an entity is selected, this feature fetches its relationships and renders them as a MapLibre layer. Relationships are directional and temporally bounded — they appear and disappear as the time slider moves.

### 5.7 Period Overview Feature

Owns the thematic clustering display described in the Data Pipeline Architecture (Section 12.6). When the user navigates to a time period at low zoom, this feature fetches or displays pre-generated period overview text and thematic cluster summaries, providing narrative context before the user explores individual entities.

### 5.8 Filter and Lens Feature

Owns the entity type filters, map lens toggles (e.g., "military lens" showing only battles and military units, "trade lens" showing only trade routes and resources), and any thematic coloring schemes. Filter state is propagated to the Entity Viewport feature to adjust API queries.

---

## 6. API Contract

### 6.1 Viewport Endpoint

The primary data endpoint. Accepts bounding box, zoom level, date range, and entity type filters. Returns GeoJSON FeatureCollection with content varying by zoom tier.

### 6.2 Entity Detail Endpoint

Returns the full entity record for a single entity by ID. Includes summary, relationships, source citations, confidence metadata, and full geometry.

### 6.3 Search Endpoint

Accepts a text query and optional temporal/spatial bounds. Returns ranked results from both keyword and semantic (pgvector) search. Results include enough metadata for list display and map marker placement.

### 6.4 Relationship Endpoint

Returns relationships for a given entity, including target entity metadata sufficient for rendering connection lines without fetching each target entity individually.

### 6.5 Period Overview Endpoint

Returns thematic cluster summaries and introductory text for a given region and time period.

---

## 7. Performance Strategy

### 7.1 Principles

- The map must feel responsive at 60fps during pan and zoom
- Entity data requests should resolve in under 200ms for cached viewports, under 500ms for uncached
- The OHM base layer and entity layer are independent — one loading does not block the other
- No loading spinners on the map itself; stale data is preferred over blank space

### 7.2 Caching Layers

**Browser tile cache:** MapLibre caches OHM vector tiles in memory and IndexedDB (via service worker, optionally)

**TanStack Query cache:** Viewport entity data is cached by quantized bbox + zoom + date key. The cache is kept warm for recently visited viewports, enabling instant back-navigation.

**CDN / nginx cache:** Martin tile responses and static PMTiles are cached at the reverse proxy level with long TTLs for verified entity tiles that change infrequently.

**Server-side query cache:** The API caches expensive PostGIS aggregation queries (cluster tier) in Redis with time-based expiry.

### 7.3 Progressive Loading

At every zoom level, the application renders *something* immediately — clusters at low zoom, markers at mid zoom, full geometries at high zoom. The user never sees an empty map while data loads.

---

## 8. URL State and Deep Linking

The URL encodes the full application state needed to reproduce a view:

- Map center (lat, lng) and zoom level
- Selected date or date range
- Active entity (by ID, if one is selected)
- Active filters and lens mode
- Search query (if active)

This means any view can be shared as a link. Opening a shared link restores the exact map position, time period, selected entity, and active filters.

---

## 9. Accessibility and Responsiveness

- All interactive panels (detail, search, filters) are keyboard-navigable and screen-reader compatible via shadcn/ui's Radix primitives
- The time slider is operable via keyboard (arrow keys for fine adjustment, page up/down for large jumps)
- The application is responsive: on narrow viewports, the detail panel becomes a bottom sheet, the filter panel becomes a drawer, and the time slider compresses to a minimal control
- Map interactions (click, hover) have touch equivalents (tap, long-press)

---

## 10. Dependencies Summary

| Category | Package | Purpose |
|---|---|---|
| Framework | React, TypeScript, Vite | Core application framework |
| UI | shadcn/ui, Tailwind CSS | Component library and styling |
| Data | TanStack Query | Server state management |
| Client state | Zustand | UI-only state (selected entity, panels, etc.) |
| Map | MapLibre GL JS | WebGL map rendering |
| Map (React) | react-map-gl | React bindings for MapLibre |
| Map (OHM) | @openhistoricalmap/maplibre-gl-dates | Temporal filtering of OHM tiles |
| Map (OHM) | @openhistoricalmap/map-styles | OHM base stylesheets |
| Map (tiles) | pmtiles | Client-side PMTiles protocol for static tilesets |
| Routing | React Router or TanStack Router | Client-side navigation and URL state |

---

*End of Document*
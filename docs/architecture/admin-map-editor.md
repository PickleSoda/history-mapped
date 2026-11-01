# history-mapped — Entity Editor & Map UI Architecture

> Status: current admin implementation in `api/`.
> This document describes what exists today in the Inertia admin app, not an aspirational phase plan.

---

## 1. Scope

This document covers the admin entity authoring surface that is currently implemented under `api/resources/js` and `api/routes/web.php`:

- entity create and edit pages
- the shared entity metadata form
- the embedded map viewer and map editor
- georef-assisted geometry hydration
- geometry period CRUD from the edit page
- relationship editing entry points from the edit page

It does not cover the public `web/` client, the pipeline, or speculative future UX concepts.

---

## 2. Current Stack

| Layer | Current choice | Notes |
|---|---|---|
| Backend | Laravel 13 | Session-authenticated admin app |
| UI transport | Inertia.js v2 | Controllers render React pages directly |
| Frontend | React 19 + TypeScript | Admin bundle lives in `api/resources/js` |
| Component system | shadcn/ui + Tailwind CSS | Existing admin UI kit |
| Entity form state | Inertia `useForm` on create, local React state on edit | Edit page manages geometry outside the form payload |
| Map rendering | MapLibre GL JS | Shared by viewer and editor |
| Geometry drawing | `@mapbox/mapbox-gl-draw` on top of MapLibre | Runtime-compatible with local type shims |
| OHM basemap support | Local style/date helpers | `loadHistoricalBasemapStyle()`, `applyOhmLayerDateFilter()` |

Two statements from older versions of this doc are no longer true:

- MapLibre is already installed and used in the admin app.
- The editor does not use Terra Draw; it uses Mapbox Draw with MapLibre.

---

## 3. Page Structure

### Create page

`entities/create` is currently a metadata-first flow.

- Renders `EntityForm`
- Posts to `EntityController@store`
- Collects `attr_*` inputs into a single `attributes` object before submit
- Splits `tags` and `alternative_names` comma strings into arrays before submit
- Does not yet embed the map editor, georef editor, geometry periods panel, or relationship panel

### Edit page

`entities/{entity}/edit` uses the same metadata form and adds three implemented collapsible panels:

1. `Map Editor`
2. `Geometry Periods`
3. `Relationships`

The edit page keeps geometry in React state so the user can:

- hydrate geometry from a georef match
- preview current and highlighted geometries in the shared map viewer
- manually edit `geojson` and `territory_geojson`
- save geometry together with the rest of the entity payload

### Show page

The entity detail page is the read-side companion to the edit flow.

- Uses `HistoricalMapViewer` and `EntityHistoryPanel`
- Displays current geometry plus timeline/history context
- Reads from the same canonical entity detail payload built by `EntityController`

---

## 4. Form Contract vs Canonical Storage

The admin form still works with a flattened read model, but persistence is now split across canonical tables.

### Fields handled directly in the form payload

Examples:

- `name`
- `entity_type`
- `summary`
- `significance`
- `impact_score`
- `wikidata_id`
- `verification_status`
- `confidence`
- `display_priority`
- `icon_class`
- `date_method`
- `date_confidence`
- `duration_type`
- `location_method`
- `location_confidence`

### Fields exposed as flattened helpers

The form still reads and writes convenience fields such as:

- `temporal_start`
- `temporal_end`
- `location_name`
- `tags`
- `alternative_names`
- `confidence_notes`
- `entity_color`
- `era_label`
- `date_raw`

These are not all first-class `entities` columns anymore.

### Canonical write targets behind the form

The backend actions now persist the admin payload into the normalized model:

- `tags` -> `entity_tags`
- `alternative_names` -> `entity_aliases`
- temporal range values -> `entity_temporal_ranges` (typically the primary row)
- location values and base geometry -> `entity_locations` (typically the primary row)
- time-varying geometry -> `geometry_periods`
- external map matches -> `entity_geo_refs`

`attributes` remains the spillover container for type-specific fields and a few presentation helpers that the current controller still surfaces from JSON.

---

## 5. Map Viewer and Map Editor

### Shared viewer

`HistoricalMapViewer` is the shared admin map surface.

- Renders the OHM basemap in MapLibre
- Applies OHM date filtering when a timeframe is available
- Accepts base geometries and overlay geometries
- Is used on dashboard, entity show, and entity edit pages

### Embedded editor

`MapEditor` is already live on the edit page.

- Uses MapLibre GL JS directly
- Mounts `@mapbox/mapbox-gl-draw`
- Provides separate location and territory editing modes
- Supports point and line editing for `geom`
- Supports polygon and multipolygon editing for `territory_geom`
- Normalizes editor output back to GeoJSON for form submission
- `only="location" | "territory"` shows one panel without the tab bar, and `fitToGeometry` zooms to the initial geometry; the map-story editor uses both to draw a feature's `at` / `line` / `area` (`components/map-story/geometry-dialog.tsx`)

### Georef-assisted hydration

The edit page also includes `EntityGeoRefEditor`.

This panel lets an editor attach or choose a geospatial reference and then hydrate base geometry into the working edit state before making manual adjustments.

This is important because the current admin workflow is not purely manual drawing. It is:

1. resolve or attach a georef when possible
2. hydrate base geometry
3. preview it in the shared viewer
4. refine manually if needed

---

## 6. Geometry Periods

Geometry periods are implemented today and replace the earlier `geometry_snapshots` planning language.

### Admin CRUD surface

The edit page mounts `EntityGeometryPeriodsPanel`, which calls dedicated web routes:

- `GET /entities/{entity}/geometry-periods`
- `POST /entities/{entity}/geometry-periods`
- `PUT /entities/{entity}/geometry-periods/{geometryPeriod}`
- `DELETE /entities/{entity}/geometry-periods/{geometryPeriod}`

### Current editable fields

The admin request objects and controller support:

- `period_type`
- `start_year`
- `end_year`
- `description`
- `provenance_mode`
- `relationship_id`
- `source_event_id`
- `confidence`
- `geom`
- `territory_geom`

### Provenance rules that matter for docs

- Admin validation currently accepts `manual` and `derived` in the request layer.
- The database now also allows `ohm_import` for pipeline-imported border geometry.
- Presence periods require a backing `relationship_id`.
- Derived periods must point back to a relationship or source event.

### Derived presence periods

Derived presence periods are not created by the geometry period panel itself.
They are created from relationship workflows when the relationship type supports derivation and the request opts in with `deriveGeometryPeriod=true`.

---

## 7. Routes and Controllers

The admin authoring flow uses session-authenticated web routes, not the public REST API.

### Entity pages

- `GET /entities/create` -> `EntityController@create`
- `POST /entities` -> `EntityController@store`
- `GET /entities/{entity}` -> `EntityController@show`
- `GET /entities/{entity}/edit` -> `EntityController@edit`
- `PUT /entities/{entity}` -> `EntityController@update`
- `DELETE /entities/{entity}` -> `EntityController@destroy`

### Geometry periods

- `EntityGeometryPeriodController@index`
- `EntityGeometryPeriodController@store`
- `EntityGeometryPeriodController@update`
- `EntityGeometryPeriodController@destroy`

The public `/api/v1/...` endpoints are for consumer-facing API access and should not be treated as the admin write path.

---

## 7a. Map-story editor

`/map-stories/{slug}/edit` (`pages/map-stories/edit.tsx`, controller
`Admin\MapStoryController`) edits a map story document — the schema in
[map-story-authoring.md](../implementation-docs/map-story-authoring.md). It is a
split view: a structured form on the left (Overview, Sides & units, Features,
Steps, JSON; `components/map-story/*`, helpers in `lib/map-story-doc.ts`) and
the **public SPA in an iframe** on the right as the preview, so the story is
drawn by the real player rather than a second renderer.

- The page receives the authored document as a JSON string (`document_json`,
  so key order and empty objects survive), the vocabulary, the live
  warnings, the chronicle's entries, and the atlas entity behind each Q-id.
  Edits change a client-side draft; each change is sent to the preview and,
  debounced, to `POST /map-stories/{slug}/validate` (a dry run) for errors and
  warnings. `PUT /map-stories/{slug}` saves the whole document through
  `SaveMapStoryAction` (422 with the errors, which the form maps to tabs and
  fields by their path). Revisions: `GET /map-stories/{slug}/revisions`,
  `…/revisions/{id}`, `POST …/revisions/{id}/restore`.
- Renaming a side, unit or feature id rewrites every reference to it.
- An approved AI edit reloads the page props; the editor takes the new
  document, or warns when there are unsaved edits.

### Preview bridge

The iframe loads `${FRONTEND_URL}/?story=<slug>&sstep=<n>&preview=1`. In
preview mode the SPA (`web/src/hooks/useStoryPreviewBridge.ts`, protocol in
`web/src/lib/map-story/preview.ts`) talks to the admin over `postMessage`:

| Direction | Message | Meaning |
|---|---|---|
| admin → SPA | `map-story:document {document}` | draw this draft (put in the story's query cache, so the player needs no other change) |
| admin → SPA | `map-story:step {index}` | go to a step |
| admin → SPA | `map-story:pick {mode: point\|path}` / `map-story:pick-cancel` | pick on the map |
| admin → SPA | `map-story:get-camera` | report the current view |
| SPA → admin | `map-story:ready` | the admin then sends the draft and the step |
| SPA → admin | `map-story:step-changed {index}` | the player moved; the form follows |
| SPA → admin | `map-story:picked {at}` or `{path}` / `map-story:pick-cancelled` | a pick's result (double-click or Enter ends a path, Esc cancels) |
| SPA → admin | `map-story:unit-dragged {unit, step, at}` | a unit dropped in a new place; the form moves it and the end of its arrow |
| SPA → admin | `map-story:camera {center, zoom, bearing}` | the answer to `get-camera` |
| SPA → admin | `map-story:document-rejected {issues}` | the SPA's schema refused the draft; it keeps drawing the last good one |

Both sides check origins: the SPA only listens to `VITE_ADMIN_ORIGINS`
(comma-separated; dev default `http://localhost:8000`) and parses every
message with zod; the admin only accepts messages from the iframe's window and
`FRONTEND_URL`'s origin. In preview mode the SPA replaces history entries
instead of pushing them and does not open entity selections.

---

## 8. Current Limitations

The admin editor is live, but a few boundaries are still worth documenting explicitly.

- The create page is still metadata-only; map, georef, geometry-period, and relationship tools are edit-page tools.
- Some helper fields shown in the form are read-model conveniences backed by normalized tables or JSON attributes rather than dedicated `entities` columns.
- The map editor still depends on Mapbox Draw typings that reference `mapbox-gl`; the code uses local type shims because runtime rendering is MapLibre.

---

## 9. Historical Notes

Older copies of this document described a phase where map editing had not yet been implemented and Terra Draw still needed to be added. That is now historical context only.

For current implementation truth, use:

- `api/resources/js/pages/entities/create.tsx`
- `api/resources/js/pages/entities/edit.tsx`
- `api/resources/js/components/map-editor.tsx`
- `api/resources/js/components/historical-map-viewer.tsx`
- `api/app/Http/Controllers/Admin/EntityController.php`
- `api/app/Http/Controllers/Admin/EntityGeometryPeriodController.php`
- `api/resources/js/pages/map-stories/edit.tsx`, `api/app/Http/Controllers/Admin/MapStoryController.php` (map stories)

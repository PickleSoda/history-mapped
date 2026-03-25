# WG — Entity Editor & Map UI Architecture

**Version 2.0 — March 2026**

---

## 1. Scope

This document covers the **entity editor** (create/edit forms) and the **map editing UI** for the admin panel. It does not cover the review queue, pipeline monitoring, user management, or other admin features — those are future work.

---

## 2. Technology Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend framework | Laravel 13 | Inertia server-side rendering |
| SPA bridge | Inertia.js v2 | No separate API; controllers pass props directly |
| Auth | Laravel Fortify (session) | Sanctum token layer is for the public REST API only |
| Frontend | React 19 + TypeScript | Via `@inertiajs/react` |
| UI components | shadcn/ui + Tailwind v4 | Existing component library |
| Forms | Inertia `useForm` | Server-side validation errors surfaced via `errors` |
| Map rendering | MapLibre GL JS | All map interactions |
| Geometry drawing | Terra Draw (`@watergis/maplibre-gl-terradraw`) | Points, lines, polygons |

---

## 3. Entity Form Design

### 3.1 Single-table inheritance + JSONB attributes

All 30 entity types share the `entities` table. Type-specific fields live in the JSONB `attributes` column. The form must:

1. Always show the **core fields** (name, type, group, temporal range, location, summary)
2. Conditionally render **type-specific sections** based on `entity_type` selection

### 3.2 Core fields (all types)

| Field | Input | Notes |
|---|---|---|
| `name` | Text | Required |
| `entity_type` | Select | Drives conditional rendering; changing type resets type-specific fields |
| `entity_group` | Derived | Auto-set from `entity_type` via the `EntityType::group()` method; displayed read-only |
| `summary` | Textarea | |
| `significance` | Textarea | |
| `temporal_start` | Text | Integer year string; negative = BCE (e.g. `"-500"`) |
| `temporal_end` | Text | Integer year string; negative = BCE |
| `date_raw` | Text | Free-text date as it appears in source |
| `location_name` | Text | |
| `tags` | Tag input (comma-separated) | Stored as PG text array |
| `alternative_names` | Tag input | Stored as PG text array |
| `impact_score` | Number (0–100) | |
| `wikidata_id` | Text | Must match `Q\d+` |
| `verification_status` | Select | Controls publish visibility |
| `confidence` | Select | Overall confidence level |
| `confidence_notes` | Textarea | |

### 3.3 Type-specific attribute sections

Entity type determines which additional `attributes` sub-fields are rendered. The form conditionally shows these sections:

| Entity type(s) | Section shown |
|---|---|
| `political_entity` | Government type, succession type, diplomatic status |
| `person` | Role, gender, birth/death year |
| `military_unit` | Unit subtype, composition, size |
| `event_battle` | Battle subtype, outcome, forces involved |
| `event_war` | War subtype, duration type |
| `event_treaty` | Treaty subtype, parties |
| `event_rebellion` | Rebellion subtype |
| `trade_route` | Route subtype, commodities |
| `epidemic_disease` | Disease subtype, severity |
| `natural_resource` | Resource category, renewability, strategic value |
| `cultural_work` | Cultural work subtype |
| `language` | Language status, language role, writing system |
| `religious_movement` | Religious movement subtype |
| `technology` | Technology domain |
| All others | No type-specific section |

All type-specific fields are stored in `attributes` as JSON — not top-level columns.

### 3.4 Validation

Laravel Form Requests handle all server-side validation. Zod is used client-side only for:
- `temporal_start` / `temporal_end`: must be a valid integer string (can be negative)
- `wikidata_id`: must match `Q\d+` or be empty
- `entity_color`: must match `#rrggbb` hex or be empty
- `impact_score`: must be 0–100

All other validation is server-side only — enum values, required fields, FK existence.

---

## 4. Map Editing UI

### 4.1 Geometry types per entity type

| Geometry | Entity types |
|---|---|
| Point | `city`, `person`, `event_battle`, `event_natural_disaster`, `epidemic_disease`, `event_tech_adoption`, `educational_institution`, `extraction_infra`, `infrastructure_monument`, `archaeological_culture` |
| LineString | `trade_route`, `migration` |
| Polygon / MultiPolygon | `political_entity`, `dynasty`, `military_unit`, `natural_resource` |
| Any | All others (editor's discretion) |

Selecting an entity type constrains the available drawing modes in Terra Draw. If a type only allows `Point`, the linestring and polygon tools are disabled.

### 4.2 Two geometry columns

`geom` — point location or primary geometry (where the entity is)
`territory_geom` — territorial extent polygon (only for polities, regions)

The map editor exposes two separate drawing layers. `territory_geom` input only appears for entity types where a territory makes sense (`political_entity`, `dynasty`, `military_unit`).

### 4.3 Editing workflow

**Create:**
1. Fill core metadata form
2. Optionally draw geometry on the map panel
3. Submit — geometry stored via `ST_GeomFromGeoJSON()`

**Edit:**
1. Existing geometry rendered as editable layer on load (fetched as GeoJSON from `geom` / `territory_geom` columns)
2. Editor can drag vertices or redraw
3. Submit — geometry updated in-place

### 4.4 Map panel placement

The map panel is a **right-side panel** on the edit/create page, visible at `lg:` breakpoint and wider. On smaller viewports it collapses to a tab. The left panel holds the metadata form.

Layout:
```
┌─────────────────────┬──────────────────┐
│  Metadata Form      │  MapLibre map    │
│  (scrollable)       │  (fixed height)  │
│                     │  Terra Draw      │
│                     │  toolbar         │
└─────────────────────┴──────────────────┘
```

The map is **not required** — entities can be saved without geometry. The map panel shows a placeholder if the entity type doesn't have a natural geographic component (e.g. `cultural_work`, `language`).

### 4.5 Map implementation notes

- MapLibre is **not yet installed** in the admin app. It must be added before the map panel can be implemented.
- Terra Draw (`@watergis/maplibre-gl-terradraw`) must also be added.
- The map panel is a **phase 2** deliverable. Phase 1 is the metadata form (create + edit) without map editing.
- GeoJSON from Terra Draw is serialized to hidden form fields and submitted with the main form via Inertia `useForm`.

---

## 5. Route and Controller Structure

```
GET    /entities/create       → EntityController@create   (entities.create)
POST   /entities              → EntityController@store    (entities.store)
GET    /entities/{entity}/edit → EntityController@edit    (entities.edit)
PUT    /entities/{entity}     → EntityController@update   (entities.update)
DELETE /entities/{entity}     → EntityController@destroy  (entities.destroy)
```

The Inertia layer uses the existing `CreateEntityAction` and `UpdateEntityAction`. It does **not** call the REST API — it invokes the actions directly, consistent with the existing pattern.

---

## 6. Key Decisions and Rationale

**Why not call `/api/v1/entities` from the admin form?**
The REST API uses token auth (Sanctum) and is designed for external consumers. The Inertia admin layer uses session auth and Inertia Form Requests — a separate code path. Both delegate to the same Action classes. This avoids CSRF complexity and keeps the admin as a traditional server-side app.

**Why is `entity_group` derived, not user-selected?**
`EntityType::group()` is a deterministic mapping — the group is an intrinsic property of the type. Showing both as separate fields would allow invalid combinations. The form sets group automatically when the type changes.

**Why store type-specific fields in `attributes` JSONB, not surfaced as columns?**
The 30 entity types each have different sub-fields. Flattening them into top-level columns would produce a table with ~80+ sparse columns. JSONB is the correct choice for sparse, type-dependent data.

**Why is map editing phase 2?**
MapLibre and Terra Draw are not yet installed. The metadata form provides immediate value and is independently testable. Geometry editing adds significant complexity and should be added once the form layer is stable.

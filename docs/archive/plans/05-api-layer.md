# 05 — Entity REST API Layer

> **Status: ✅ Executed** — verified 2026-06-15 against the codebase. See [STATUS.md](../../plans/STATUS.md).

## Summary

Complete REST API for entities, relationships, sources, and reference data.
17 routes versioned under `/api/v1/`, auto-documented via Scramble at `/docs/api`.

## Architecture

```
HTTP Request
    |
FormRequest (validation, returns validated array)
    |
Controller (thin — DTO::fromArray(), invoke Action)
    |
DTO (readonly class, typed fields, fromArray + toModelArray)
    |
Action (domain logic, DB::transaction, PostGIS raw SQL)
    |
Model + EntityBuilder (typed query methods)
    |
JsonResource (response formatting, conditional eager loading)
    |
HTTP Response
```

### Why this pattern

- **No Spatie Data / Spatie Query Builder** — neither is installed and L13 compatibility is uncertain. Plain readonly DTOs and a custom Eloquent Builder serve the same role with zero dependencies.
- **Actions over service classes** — single-responsibility invokable classes are easier to test and compose than fat services.
- **EntityBuilder over model scopes** — 24 typed, chainable methods replace ad-hoc scope methods. The builder is returned by `Entity::newEloquentBuilder()` so all queries get the typed API.
- **Separate Resources for list vs detail vs map** — `EntitySummaryResource` (list), `EntityResource` (detail), `EntityMapResource` (GeoJSON Feature) keep payloads minimal per use case.

## Files Created (30)

| Layer | Files | Purpose |
|-------|-------|---------|
| Builders | `EntityBuilder.php` | 24 chainable query methods |
| DTOs | 4 files | Entity, EntityFilter, Relationship, Source |
| Actions | 8 files | CRUD + Map + Relationship + Source |
| FormRequests | 6 files | Validation for all write/filter endpoints |
| Resources | 7 files (incl. `ReferenceResource`) | JSON response formatting |
| Controllers | 4 files | Entity, EntityRelationship, Source, Reference |

## Route Table

| Method | URI | Auth | Purpose |
|--------|-----|------|---------|
| GET | `/api/v1/health` | Public | Health check |
| GET | `/api/v1/entities` | Public | Paginated entity list with filters |
| GET | `/api/v1/entities/map` | Public | GeoJSON FeatureCollection (bbox required) |
| GET | `/api/v1/entities/{entity}` | Public | Entity detail with optional relations |
| POST | `/api/v1/entities` | Sanctum | Create entity |
| PUT | `/api/v1/entities/{entity}` | Sanctum | Update entity |
| DELETE | `/api/v1/entities/{entity}` | Sanctum | Delete entity |
| GET | `/api/v1/entities/{entity}/relationships` | Public | Entity relationships |
| POST | `/api/v1/entities/{entity}/relationships` | Sanctum | Create relationship |
| DELETE | `/api/v1/entities/{entity}/relationships/{rel}` | Sanctum | Delete relationship |
| GET | `/api/v1/sources` | Public | Paginated source list |
| GET | `/api/v1/sources/{source}` | Public | Source detail |
| POST | `/api/v1/sources` | Sanctum | Create source |
| GET | `/api/v1/reference` | Public | List 10 reference table slugs |
| GET | `/api/v1/reference/{table}` | Public | Reference table data (cached 24h) |
| POST | `/api/v1/reference/cache/clear` | Sanctum | Clear reference cache |
| GET | `/api/v1/user` | Sanctum | Authenticated user info |

## EntityBuilder Query Methods

Spatial: `inBbox`, `territoryInBbox`, `nearPoint`, `orderByDistanceFrom`
Temporal: `inTimeRange`, `existsAt`, `startingAfter`, `endingBefore`
Type/Status: `ofType`, `ofGroup`, `ofTypes`, `verified`, `withStatus`, `withMinConfidence`
Hierarchy: `childrenOf`, `roots`
Search: `search`, `nameLike`, `hasAttribute`, `hasTag`
Sorting: `orderByImpact`, `orderByRecent`, `orderByChronological`
Map: `selectForMap`

## Key Design Decisions

1. **Reference table caching** — `DB::table()->get()` results are converted to arrays of arrays before Redis cache storage. This avoids PHP serialization issues with `stdClass`/`Collection` objects on deserialization.

2. **PostGIS geometry handling** — Create/update actions use raw `DB::raw("ST_GeomFromGeoJSON(?) ::geometry")` with parameter binding for geometry columns. The GeoJson cast handles read-side conversion via `ST_AsGeoJSON`.

3. **Map endpoint** — Returns a flat GeoJSON `FeatureCollection` with lightweight `selectForMap()` projection (id, name, type, group, geom). Bbox is required to prevent full-table scans. Max 5000 features per request.

4. **Authentication** — `laravel/sanctum` v4.3.1 installed for `statefulApi()` middleware and `auth:sanctum` guard. SPA consumers get cookie-based auth; external consumers use Bearer tokens.

## Dependencies Added

- `laravel/sanctum` v4.3.1 — Required by `$middleware->statefulApi()` in `bootstrap/app.php`. Without it, all API routes fail with `BindingResolutionException`.

## Verified Endpoints

All public read endpoints and auth-guarded write endpoints tested end-to-end via curl on `localhost:8000`.

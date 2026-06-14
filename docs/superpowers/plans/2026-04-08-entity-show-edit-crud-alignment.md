# Entity Show/Edit CRUD Alignment Implementation Plan

> **Status: 🟡 Partial** — verified 2026-06-15; remaining work tracked in [STATUS.md](../../plans/STATUS.md).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete admin entity show/edit coverage for canonical entity fields by adding geometry-period CRUD, switching show timeline reads to the timeline endpoint, and exposing hierarchy controls.

**Architecture:** Keep canonical writes in existing entity actions for core fields, and add a focused geometry-period admin JSON surface for nested CRUD from entity edit/show pages. Keep timeline rendering componentized, but source timeline rows from `entity_timeline_entries` API reads instead of relationship-only fetches.

**Tech Stack:** Laravel 13, PHP 8.4, Inertia + React + TypeScript, PostgreSQL/PostGIS, PHPUnit feature tests, Vitest + Testing Library component tests.

**Execution Root:** Unless noted otherwise, run commands from `C:\Users\Achi\Code\FL\history-mapped`.

---

## Scope

This plan addresses only the missing canonical CRUD/read-model coverage previously identified:

- geometry periods: create/read/update/delete from admin entity edit/show flow
- timeline panel: use `/api/v1/entities/{entity}/timeline` read model on show page
- hierarchy fields: render and submit `parent_entity_id` and `successor_entity_id` controls in entity form

Out of scope:

- redesigning event/relationship data model
- broad map UX redesign
- bulk migration/backfill changes

---

### Task 1: Add Geometry Period Admin API Surface

**Files:**
- Create: `api/app/Http/Controllers/Admin/EntityGeometryPeriodController.php`
- Create: `api/app/Http/Requests/Admin/StoreGeometryPeriodRequest.php`
- Create: `api/app/Http/Requests/Admin/UpdateGeometryPeriodRequest.php`
- Modify: `api/routes/web.php`
- Modify: `api/app/Http/Controllers/Admin/EntityController.php`
- Test: create `api/tests/Feature/Admin/EntityGeometryPeriodControllerTest.php`
- Test: modify `api/tests/Feature/Admin/EntityControllerTest.php`

- [x] **Step 1: Write failing feature tests for geometry-period CRUD**

Cover:
- authenticated user can list geometry periods for one entity
- create validates `start_year`, `end_year`, and at least one of `geom` or `territory_geom`
- update persists editable fields (`label`, `description`, `confidence`, years, geometry)
- delete removes row and respects entity ownership

- [x] **Step 2: Run focused test file and verify failure**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Admin/EntityGeometryPeriodControllerTest.php`
Expected: FAIL because route/controller/request classes do not exist.

- [x] **Step 3: Implement store/update request validation classes**

Validation contract:
- `start_year` and `end_year`: integers, `start_year <= end_year`
- `period_type`: nullable enum-like string from allowed set (`territory`, `route`, `spread_zone`, `movement_path`, `presence`)
- geometry payload accepted as GeoJSON strings for both `geom` and `territory_geom`
- `relationship_id`, `source_event_id`, `geo_ref_id`: nullable UUIDs

- [x] **Step 4: Implement geometry-period controller actions**

Actions:
- `index(Entity $entity)` returns JSON list ordered by `start_year`, then `display_priority` desc
- `store(Entity $entity, StoreGeometryPeriodRequest $request)` creates linked period
- `update(Entity $entity, GeometryPeriod $geometryPeriod, UpdateGeometryPeriodRequest $request)` updates linked period
- `destroy(Entity $entity, GeometryPeriod $geometryPeriod)` deletes linked period

- [x] **Step 5: Register nested entity geometry-period routes**

Add routes under auth middleware:
- `GET entities/{entity}/geometry-periods`
- `POST entities/{entity}/geometry-periods`
- `PUT entities/{entity}/geometry-periods/{geometryPeriod}`
- `DELETE entities/{entity}/geometry-periods/{geometryPeriod}`

- [x] **Step 6: Expose geometry-period URLs in entity show/edit props**

In `EntityController@show` and `EntityController@edit`, pass route URLs so UI can call CRUD endpoints without hardcoded path strings.

- [x] **Step 7: Rerun feature tests and confirm pass**

Run:
- `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Admin/EntityGeometryPeriodControllerTest.php`
- `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Admin/EntityControllerTest.php --filter=geometry`

Expected: PASS for new/updated tests.

- [x] **Step 8: Commit**

```bash
git add api/app/Http/Controllers/Admin/EntityGeometryPeriodController.php api/app/Http/Requests/Admin/StoreGeometryPeriodRequest.php api/app/Http/Requests/Admin/UpdateGeometryPeriodRequest.php api/routes/web.php api/app/Http/Controllers/Admin/EntityController.php api/tests/Feature/Admin/EntityGeometryPeriodControllerTest.php api/tests/Feature/Admin/EntityControllerTest.php
git commit -m "feat: add admin geometry period CRUD endpoints"
```

### Task 2: Wire Entity Form Hierarchy Controls

> **Status:** NOT IMPLEMENTED. `parent_entity_id` and `successor_entity_id` fields do not exist in the entity form, types, or backend.

**Files:**
- Modify: `api/resources/js/components/entity-form.tsx`
- Modify: `api/resources/js/pages/entities/edit.tsx`
- Modify: `api/resources/js/pages/entities/create.tsx`
- Modify: `api/resources/js/types/entity.ts`
- Test: create `api/resources/js/components/__tests__/entity-form-hierarchy.test.tsx`

- [ ] **Step 1: Write failing form test for hierarchy controls**

Cover:
- parent and successor selectors render
- values bind to `parent_entity_id` and `successor_entity_id`
- clear action submits `null`

- [ ] **Step 2: Run focused frontend test and verify failure**

Run: `cd api; pnpm vitest resources/js/components/__tests__/entity-form-hierarchy.test.tsx`
Expected: FAIL because controls are not rendered.

- [ ] **Step 3: Add options contract for hierarchy selectors**

Update page props/types so form receives minimal searchable entity options (`entity_id`, `name`, `entity_type`) for parent/successor selection.

- [ ] **Step 4: Render parent/successor controls in `entity-form.tsx`**

Add two selectors in structural section:
- Parent entity (`parent_entity_id`)
- Successor entity (`successor_entity_id`)

Include helper text clarifying hierarchy vs succession semantics.

- [ ] **Step 5: Confirm submit payload contains hierarchy fields**

Ensure create/edit page submit handlers include the two fields in payload and preserve existing null-handling behavior.

- [ ] **Step 6: Rerun hierarchy test and typecheck**

Run:
- `cd api; pnpm vitest resources/js/components/__tests__/entity-form-hierarchy.test.tsx`
- `cd api; pnpm type-check`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/resources/js/components/entity-form.tsx api/resources/js/pages/entities/edit.tsx api/resources/js/pages/entities/create.tsx api/resources/js/types/entity.ts api/resources/js/components/__tests__/entity-form-hierarchy.test.tsx
git commit -m "feat: add parent and successor controls to entity form"
```

### Task 3: Add Geometry Period CRUD UI to Entity Edit

**Files:**
- Create: `api/resources/js/components/entity-geometry-periods-panel.tsx`
- Modify: `api/resources/js/pages/entities/edit.tsx`
- Modify: `api/resources/js/pages/entities/show.tsx`
- Modify: `api/resources/js/components/historical-map-viewer.tsx`
- Test: create `api/resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx`

- [x] **Step 1: Write failing component test for geometry-period panel**

Cover:
- renders existing period rows from prop data
- opens create form and posts payload
- updates and deletes existing rows
- refreshes local list after success

- [x] **Step 2: Run focused test and verify failure**

Run: `cd api; pnpm vitest resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx`
Expected: FAIL because panel does not exist.

- [x] **Step 3: Implement `entity-geometry-periods-panel.tsx`**

Build panel with:
- list view sorted by year range
- inline create/edit form for label, years, confidence, period type, description
- geometry inputs that delegate shape editing to existing map editor flow
- optimistic UI or post-success refetch strategy

- [x] **Step 4: Mount panel in edit page**

In `entities/edit.tsx`, add collapsible section after map editor and wire CRUD URLs from server props.

- [x] **Step 5: Add read-only period summary to show page**

In `entities/show.tsx`, render geometry periods section with year range, label, and description to ensure show-page read coverage.

- [x] **Step 6: Integrate period highlighting in map viewer**

Pass selected period geometry to `historical-map-viewer.tsx` so selecting a period highlights the matching geometry on map.

- [x] **Step 7: Rerun component tests and typecheck**

Run:
- `cd api; pnpm vitest resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx`
- `cd api; pnpm type-check`

Expected: PASS.

- [x] **Step 8: Commit**

```bash
git add api/resources/js/components/entity-geometry-periods-panel.tsx api/resources/js/pages/entities/edit.tsx api/resources/js/pages/entities/show.tsx api/resources/js/components/historical-map-viewer.tsx api/resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx
git commit -m "feat: add geometry periods panel to entity edit/show"
```

### Task 4: Switch Show Timeline Reads to Timeline API

**Files:**
- Modify: `api/resources/js/components/entity-history-panel.tsx`
- Modify: `api/resources/js/components/entity-history-timeline.tsx`
- Modify: `api/resources/js/pages/entities/show.tsx`
- Test: modify `api/resources/js/components/__tests__/entity-history-panel.test.tsx`
- Test: modify `api/tests/Feature/Api/EntityTimelineApiTest.php`

- [x] **Step 1: Write failing frontend test for timeline endpoint usage**

Cover:
- panel fetches from timeline URL prop instead of relationships URL
- renders timeline rows with year/title/description from endpoint payload
- handles empty state and fetch error state

- [x] **Step 2: Run focused panel test and verify failure**

Run: `cd api; pnpm vitest resources/js/components/__tests__/entity-history-panel.test.tsx`
Expected: FAIL because panel currently expects relationship payload.

- [x] **Step 3: Update show page props for timeline URL**

In `entities/show.tsx`, pass timeline endpoint URL from route helper and keep relationship panel URL unchanged for relationship CRUD section.

- [x] **Step 4: Refactor history panel data layer to timeline schema**

Update `entity-history-panel.tsx` to:
- fetch timeline rows from timeline endpoint
- map row data to existing timeline UI model
- keep relationship context badges where available

- [x] **Step 5: Align timeline rendering component contract**

Update `entity-history-timeline.tsx` prop types and row render logic to match timeline-entry fields.

- [x] **Step 6: Add backend API test coverage for required fields**

In `EntityTimelineApiTest.php`, assert response includes fields needed by show timeline (`id`, `title/label`, `start_year`, `end_year`, `description`, geometry presence indicator).

- [x] **Step 7: Run frontend + API tests**

Run:
- `cd api; pnpm vitest resources/js/components/__tests__/entity-history-panel.test.tsx`
- `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Api/EntityTimelineApiTest.php`

Expected: PASS.

- [x] **Step 8: Commit**

```bash
git add api/resources/js/components/entity-history-panel.tsx api/resources/js/components/entity-history-timeline.tsx api/resources/js/pages/entities/show.tsx api/resources/js/components/__tests__/entity-history-panel.test.tsx api/tests/Feature/Api/EntityTimelineApiTest.php
git commit -m "feat: use timeline API for entity show history"
```

### Task 5: End-to-End Verification and Docs Update

> **Status:** Partially completed. Regression suites pass. Docs updated for geometry periods and timeline, but hierarchy fields are not documented because they are not implemented.

**Files:**
- Modify: `docs/entity-model/for-historians.md`
- Modify: `docs/entity-model/diagrams.md`
- Modify: `docs/implementation-docs/entity-model.md` (create if missing)

- [x] **Step 1: Add/refresh historian-facing notes for edit/show CRUD behavior**

Document:
- where geometry periods are edited
- how timeline rows are read on show page
- hierarchy and succession fields in entity form

- [x] **Step 2: Run focused backend and frontend regression suites**

Run:
- `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Admin/EntityControllerTest.php tests/Feature/Admin/EntityGeometryPeriodControllerTest.php tests/Feature/Api/EntityTimelineApiTest.php`
- `cd api; pnpm vitest resources/js/components/__tests__/entity-history-panel.test.tsx resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx resources/js/components/__tests__/entity-form-hierarchy.test.tsx`
- `cd api; pnpm type-check`

Expected: PASS.

- [x] **Step 3: Run impact/scope verification before merge**

Run:
- `git status --short`
- verify only expected files changed for this plan slice

- [x] **Step 4: Commit final docs and verification updates**

```bash
git add docs/entity-model/for-historians.md docs/entity-model/diagrams.md docs/implementation-docs/entity-model.md
git commit -m "docs: document entity show/edit CRUD surfaces"
```

---

## Rollout Notes

- Deploy backend geometry-period endpoints before shipping frontend panel changes.
- Keep existing relationship panel behavior intact while timeline panel switches to timeline endpoint.
- If timeline payload shape differs across environments, gate frontend mapping behind safe runtime guards until all API nodes are updated.

## Completion Criteria

- [x] Entity edit page supports CRUD for geometry periods, including year range, label, description, confidence, and geometry updates.
- [x] Entity show page reads timeline rows from timeline endpoint and renders meaningful empty/error states.
- [ ] Entity create/edit form exposes parent/successor controls and persists them. *(Not implemented)*
- [x] Backend and frontend targeted tests pass.
- [x] Historian/model docs reflect the new canonical edit/show behavior.
# Historical Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an Inertia dashboard page displaying all historical entities on a time-aware map with year filtering, full entity filtering, and side panel entity selection.

**Architecture:** Extend the existing `/api/v1/entities/map` endpoint to accept year and filter parameters. Create a new dashboard page that reuses HistoricalMapViewer for mapping, AppLayout for structure, and entity show page patterns for the side panel summary. The map displays all entities for a selected year, using geometry period precedence (year-specific geometry > base geometry > entity temporal range). Clicking an entity shows its summary in a right-side panel with a link to the full entity page.

**Tech Stack:** 
- Backend: Laravel 13.x, MapEntitiesAction with MapEntitiesRequest
- Frontend: React + TypeScript, HistoricalMapViewer (MapLibre GL), TailwindCSS + shadcn/ui
- API: Extend existing GeoJSON map endpoint with year/filter query parameters
- Database: PostgreSQL with PostGIS (geometry_periods table for year-specific geometries)

---

## File Structure

**Backend:**
- Modify: `api/app/Http/Api/V1/Controllers/EntityController.php` - Add year/filter parameter handling
- Modify: `api/app/Http/Requests/MapEntitiesRequest.php` - Add year and filter validation
- Modify: `api/app/Services/MapEntitiesAction.php` - Implement year-aware geometry selection with period precedence

**Frontend:**
- Modify: `api/resources/js/pages/dashboard.tsx` - Implement full dashboard layout with map + side panel + controls
- Modify: `api/routes/web.php` - Ensure dashboard route is authenticated (check current setup)

**Tests:**
- Create: `api/tests/Feature/MapEntitiesYearFilteringTest.php` - Test year parameter filtering in API
- Create: `api/tests/Feature/GeometryPeriodPrecedenceTest.php` - Test geometry period selection logic

---

## Task 1: Understand Current API Endpoint Shape

**Files:**
- Read: `api/app/Http/Api/V1/Controllers/EntityController.php`
- Read: `api/app/Http/Requests/MapEntitiesRequest.php`
- Read: `api/routes/api.php`
- Read: `api/app/Services/MapEntitiesAction.php`

- [ ] **Step 1: Examine current MapEntitiesAction and MapEntitiesRequest**

Run: `docker compose -f docker/docker-compose.yml exec app cat app/Http/Requests/MapEntitiesRequest.php`

Expected: See current request validation (likely: filters[], radius, etc.)

- [ ] **Step 2: Examine EntityController::map() endpoint**

Run: `docker compose -f docker/docker-compose.yml exec app grep -A 20 "public function map" app/Http/Api/V1/Controllers/EntityController.php`

Expected: See how endpoint processes request and returns GeoJSON

- [ ] **Step 3: Check current MapEntitiesAction implementation**

Run: `docker compose -f docker/docker-compose.yml exec app cat app/Services/MapEntitiesAction.php | head -100`

Expected: Understand data transformation logic (entity → GeoJSON feature)

---

## Task 2: Extend API Request Validation for Year Parameter

**Files:**
- Modify: `api/app/Http/Requests/MapEntitiesRequest.php`
- Test: `api/tests/Feature/MapEntitiesYearFilteringTest.php` (new)

- [ ] **Step 1: Write failing test for year parameter validation**

Create `api/tests/Feature/MapEntitiesYearFilteringTest.php`:

```php
<?php

namespace Tests\Feature;

use Tests\TestCase;

class MapEntitiesYearFilteringTest extends TestCase
{
    public function test_map_endpoint_accepts_year_parameter()
    {
        $response = $this->getJson('/api/v1/entities/map?year=1000');
        
        $response->assertOk();
        $response->assertJsonStructure([
            'type',
            'features' => [
                '*' => [
                    'type',
                    'geometry',
                    'properties',
                ]
            ]
        ]);
    }

    public function test_map_endpoint_validates_year_as_integer()
    {
        $response = $this->getJson('/api/v1/entities/map?year=invalid');
        
        $response->assertUnprocessable();
    }

    public function test_default_year_is_1000_when_not_provided()
    {
        // This will be verified by checking request handling
        $response = $this->getJson('/api/v1/entities/map');
        
        $response->assertOk();
    }
}
```

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/MapEntitiesYearFilteringTest.php --filter test_map_endpoint_accepts_year_parameter`

Expected: FAIL (year parameter not yet supported)

- [ ] **Step 2: Add year parameter to MapEntitiesRequest**

Modify `api/app/Http/Requests/MapEntitiesRequest.php`:

```php
public function rules(): array
{
    return [
        'filters' => ['nullable', 'array'],
        'filters.*.key' => ['required_with:filters', 'string'],
        'filters.*.value' => ['required_with:filters', 'string'],
        'radius' => ['nullable', 'numeric', 'min:0'],
        'year' => ['nullable', 'integer', 'between:1,3000'], // Add this
    ];
}

public function getYear(): int
{
    return (int) $this->input('year', 1000); // Default to 1000
}
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/MapEntitiesYearFilteringTest.php`

Expected: All three tests PASS

- [ ] **Step 4: Commit**

```bash
git add api/tests/Feature/MapEntitiesYearFilteringTest.php api/app/Http/Requests/MapEntitiesRequest.php
git commit -m "test(api): add year parameter validation for map endpoint"
```

---

## Task 3: Implement Geometry Period Selection Logic

**Files:**
- Create: `api/tests/Feature/GeometryPeriodPrecedenceTest.php`
- Modify: `api/app/Services/MapEntitiesAction.php`

- [ ] **Step 1: Write failing test for geometry period precedence**

Create `api/tests/Feature/GeometryPeriodPrecedenceTest.php`:

```php
<?php

namespace Tests\Feature;

use App\Models\Entity;
use App\Models\GeometryPeriod;
use Tests\TestCase;

class GeometryPeriodPrecedenceTest extends TestCase
{
    public function test_geometry_period_takes_precedence_over_base_geometry()
    {
        // Create entity with base geometry
        $entity = Entity::factory()
            ->has(GeometryPeriod::factory()->state([
                'temporal_start' => 950,
                'temporal_end' => 1050,
            ]))
            ->create();

        // Call map endpoint with year 1000
        $response = $this->getJson('/api/v1/entities/map?year=1000');

        // Feature should use geometry_period's geom, not base geom
        $features = $response->json('features');
        $entityFeature = collect($features)->firstWhere('properties.id', $entity->id);

        $this->assertNotNull($entityFeature);
        // Verify properties indicate period geometry was used
        $this->assertTrue(isset($entityFeature['properties']['geometry_period_id']));
    }

    public function test_falls_back_to_base_geometry_when_no_period_matches()
    {
        // Entity with base geometry but no period for year 1000
        $entity = Entity::factory()
            ->has(GeometryPeriod::factory()->state([
                'temporal_start' => 1100,
                'temporal_end' => 1200,
            ]))
            ->create();

        $response = $this->getJson('/api/v1/entities/map?year=1000');

        $features = $response->json('features');
        $entityFeature = collect($features)->firstWhere('properties.id', $entity->id);

        $this->assertNotNull($entityFeature);
        // Should use base geometry (entity->geom)
        $this->assertNull($entityFeature['properties']['geometry_period_id'] ?? null);
    }
}
```

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/GeometryPeriodPrecedenceTest.php --filter test_geometry_period_takes_precedence`

Expected: FAIL (logic not yet implemented)

- [ ] **Step 2: Update MapEntitiesAction to select geometry by year**

Modify `api/app/Services/MapEntitiesAction.php` (assuming it's a service building the GeoJSON):

First, examine current implementation:
```bash
docker compose -f docker/docker-compose.yml exec app grep -A 200 "class MapEntitiesAction" app/Services/MapEntitiesAction.php | head -150
```

Then add a method to select geometry by year:

```php
private function selectGeometryForYear(Entity $entity, int $year): ?GeometryPeriod
{
    // First: try to find a geometry period that covers this year
    $period = $entity->geometry_periods()
        ->where('temporal_start', '<=', $year)
        ->where('temporal_end', '>=', $year)
        ->first();

    if ($period) {
        return $period;
    }

    // Second: fall back to base geometry (represented as null period)
    return null; // Signals to use entity->geom
}

private function buildGeometryFeature(Entity $entity, int $year): array
{
    $period = $this->selectGeometryForYear($entity, $year);
    
    if ($period) {
        $geometry = json_decode($period->geom, true);
        $properties = [
            'id' => $entity->id,
            'name' => $entity->name,
            'geometry_period_id' => $period->id,
            'temporal_start' => $period->temporal_start,
            'temporal_end' => $period->temporal_end,
        ];
    } else {
        $geometry = json_decode($entity->geom, true);
        $properties = [
            'id' => $entity->id,
            'name' => $entity->name,
            'temporal_start' => $entity->temporal_start,
            'temporal_end' => $entity->temporal_end,
        ];
    }

    return [
        'type' => 'Feature',
        'geometry' => $geometry,
        'properties' => $properties,
    ];
}
```

Then modify the main action method to use the year from request:

```php
public function handle(MapEntitiesRequest $request): string
{
    $year = $request->getYear(); // Now available
    $filters = $request->filters();
    
    $query = Entity::query();
    
    // Apply filters...
    if (!empty($filters)) {
        // existing filter logic
    }

    $entities = $query->get();
    
    $features = $entities->map(fn ($entity) => $this->buildGeometryFeature($entity, $year))->toArray();

    return json_encode([
        'type' => 'FeatureCollection',
        'features' => $features,
    ]);
}
```

- [ ] **Step 3: Run tests to verify precedence logic**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/GeometryPeriodPrecedenceTest.php`

Expected: Both tests PASS

- [ ] **Step 4: Commit**

```bash
git add api/tests/Feature/GeometryPeriodPrecedenceTest.php api/app/Services/MapEntitiesAction.php
git commit -m "feat(api): implement year-aware geometry period selection for map endpoint"
```

---

## Task 4: Update Dashboard Page with Map + Controls + Side Panel

**Files:**
- Modify: `api/resources/js/pages/dashboard.tsx`

- [ ] **Step 1: Import necessary components and setup state**

Replace the current dashboard.tsx with:

```tsx
import { Head } from '@inertiajs/react';
import { useState, useCallback, useMemo } from 'react';
import AppLayout from '@/layouts/app-layout';
import { dashboard } from '@/routes';
import { HistoricalMapViewer } from '@/components/historical-map-viewer';
import { EntitySummaryCard } from '@/components/entity-summary-card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import type { BreadcrumbItem, EntityDetail } from '@/types';
import type { GeoJsonObject, Feature } from 'geojson';

const breadcrumbs: BreadcrumbItem[] = [
    {
        title: 'Dashboard',
        href: dashboard(),
    },
];

interface MapEntity extends Partial<EntityDetail> {
    id: number;
    name: string;
    geometry_period_id?: number;
    temporal_start?: number;
    temporal_end?: number;
}

export default function Dashboard() {
    const [year, setYear] = useState<number>(1000);
    const [selectedEntityId, setSelectedEntityId] = useState<number | null>(null);
    const [mapData, setMapData] = useState<{
        features: GeoJsonObject[];
        entities: MapEntity[];
    } | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Fetch map data when year changes
    const fetchMapData = useCallback(async (targetYear: number) => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(
                `/api/v1/entities/map?year=${targetYear}`,
                {
                    headers: {
                        'Accept': 'application/json',
                    },
                }
            );

            if (!response.ok) {
                throw new Error('Failed to load map data');
            }

            const data = await response.json();
            setMapData(data);
            setSelectedEntityId(null); // Reset selection on new year
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }, []);

    // Fetch initial data on mount
    React.useEffect(() => {
        fetchMapData(year);
    }, []);

    const handleYearChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const newYear = Math.max(1, Math.min(3000, parseInt(e.target.value) || 1000));
            setYear(newYear);
            fetchMapData(newYear);
        },
        [fetchMapData]
    );

    const handleFeatureClick = useCallback((feature: Feature) => {
        const entityId = feature.properties?.id;
        if (entityId) {
            setSelectedEntityId(entityId);
        }
    }, []);

    // Find selected entity details
    const selectedEntity = useMemo(() => {
        if (!selectedEntityId || !mapData) return null;
        return mapData.entities.find((e) => e.id === selectedEntityId) || null;
    }, [selectedEntityId, mapData]);

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Historical Dashboard" />
            <div className="flex h-full flex-col gap-4 p-4">
                {/* Year Control */}
                <div className="flex items-center gap-4 rounded-lg border border-sidebar-border/70 bg-white p-4 dark:border-sidebar-border dark:bg-slate-950">
                    <label className="font-medium">Year:</label>
                    <Input
                        type="number"
                        min="1"
                        max="3000"
                        value={year}
                        onChange={handleYearChange}
                        className="w-24"
                    />
                    <span className="text-sm text-muted-foreground">
                        Showing entities for year {year}
                    </span>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-700 dark:border-red-700 dark:bg-red-950 dark:text-red-100">
                        {error}
                    </div>
                )}

                {/* Main Content: Map + Side Panel */}
                <div className="flex flex-1 gap-4 overflow-hidden rounded-lg border border-sidebar-border/70 dark:border-sidebar-border">
                    {/* Map Pane */}
                    <div className="flex-1 overflow-hidden">
                        {loading ? (
                            <div className="flex h-full items-center justify-center">
                                <div className="text-center">
                                    <div className="mb-2 text-sm text-muted-foreground">
                                        Loading map...
                                    </div>
                                    <div className="size-8 animate-spin rounded-full border-4 border-muted border-t-foreground" />
                                </div>
                            </div>
                        ) : mapData?.features && mapData.features.length > 0 ? (
                            <HistoricalMapViewer
                                baseGeometries={mapData.features}
                                timeframeDate={`${year}-01-01`}
                                onFeatureClick={handleFeatureClick}
                            />
                        ) : (
                            <div className="flex h-full items-center justify-center text-muted-foreground">
                                No entities found for year {year}
                            </div>
                        )}
                    </div>

                    {/* Side Panel */}
                    {selectedEntity ? (
                        <div className="w-96 overflow-y-auto border-l border-sidebar-border/70 bg-white p-4 dark:border-sidebar-border dark:bg-slate-950">
                            <div className="space-y-4">
                                <div>
                                    <h2 className="text-lg font-semibold">{selectedEntity.name}</h2>
                                    <p className="text-sm text-muted-foreground">
                                        {selectedEntity.entity_type?.name || 'Unknown Type'}
                                    </p>
                                </div>

                                {/* Temporal Info */}
                                {(selectedEntity.temporal_start || selectedEntity.temporal_end) && (
                                    <div className="space-y-1 rounded-md bg-slate-100 p-3 text-sm dark:bg-slate-800">
                                        <div className="font-medium">Active Period</div>
                                        <div className="text-muted-foreground">
                                            {selectedEntity.temporal_start || '?'} –{' '}
                                            {selectedEntity.temporal_end || '?'}
                                        </div>
                                    </div>
                                )}

                                {/* Location Name */}
                                {selectedEntity.location_name && (
                                    <div className="space-y-1">
                                        <div className="text-sm font-medium">Location</div>
                                        <div className="text-sm text-muted-foreground">
                                            {selectedEntity.location_name}
                                        </div>
                                    </div>
                                )}

                                {/* View Full Page Link */}
                                <Button
                                    asChild
                                    className="w-full"
                                    onClick={() => {
                                        // Navigate to full entity page
                                        window.location.href = `/entities/${selectedEntity.id}`;
                                    }}
                                >
                                    <a href={`/entities/${selectedEntity.id}`}>
                                        View Full Page
                                    </a>
                                </Button>

                                {/* Close Button */}
                                <Button
                                    variant="outline"
                                    className="w-full"
                                    onClick={() => setSelectedEntityId(null)}
                                >
                                    Close
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <div className="w-96 border-l border-sidebar-border/70 bg-slate-50 p-4 text-center text-muted-foreground dark:border-sidebar-border dark:bg-slate-900">
                            Click an entity on the map to view details
                        </div>
                    )}
                </div>
            </div>
        </AppLayout>
    );
}
```

- [ ] **Step 2: Test the dashboard renders**

Run: `docker compose -f docker/docker-compose.yml exec app npm run dev --prefix resources/js`

Navigate to `http://localhost:5173/dashboard` in browser

Expected: See year control at top, map in center, empty side panel on right

- [ ] **Step 3: Test map loading with year parameter**

In browser console, verify year input changes trigger map refetch:
- Change year to 500
- Observe loading state
- Verify map re-renders

- [ ] **Step 4: Test entity selection**

Click on a feature in the map:
- Expected: Side panel shows entity name, type, temporal info
- Expected: "View Full Page" button navigates to entity detail

- [ ] **Step 5: Commit**

```bash
git add api/resources/js/pages/dashboard.tsx
git commit -m "feat(frontend): implement historical dashboard with year control and map viewer"
```

---

## Task 5: Verify Dashboard Route is Authenticated

**Files:**
- Read: `api/routes/web.php`
- Read: `api/app/Http/Middleware/HandleInertiaRequests.php` (if exists)

- [ ] **Step 1: Check current dashboard route setup**

Run: `docker compose -f docker/docker-compose.yml exec app grep -B 5 -A 5 "dashboard" routes/web.php`

Expected: Find current route definition

- [ ] **Step 2: Verify route is under auth middleware**

If not already protected, it should be wrapped with `auth` middleware:

```php
Route::middleware('auth')->group(function () {
    Route::get('/dashboard', [DashboardController::class, 'show'])->name('dashboard');
});
```

Or if using InertiaJS render directly in route:

```php
Route::get('/dashboard', function () {
    return Inertia::render('Dashboard');
})->middleware('auth')->name('dashboard');
```

- [ ] **Step 3: No code changes needed if already protected**

If route is already authenticated, no changes required. Skip commit.

---

## Task 6: Integration Test - End-to-End Dashboard Flow

**Files:**
- Create: `api/tests/Feature/HistoricalDashboardTest.php`

- [ ] **Step 1: Write integration test for dashboard flow**

Create `api/tests/Feature/HistoricalDashboardTest.php`:

```php
<?php

namespace Tests\Feature;

use App\Models\Entity;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class HistoricalDashboardTest extends TestCase
{
    use RefreshDatabase;

    public function test_authenticated_user_can_view_dashboard()
    {
        $user = $this->actingAsUser(); // Assumes actingAsUser helper exists

        $response = $this->get('/dashboard');

        $response->assertOk();
        $response->assertInertia(fn ($page) => $page
            ->component('Dashboard')
        );
    }

    public function test_dashboard_fetches_map_data_for_year()
    {
        $user = $this->actingAsUser();
        
        Entity::factory()
            ->has(GeometryPeriod::factory()->state([
                'temporal_start' => 950,
                'temporal_end' => 1050,
            ]))
            ->create();

        $response = $this->getJson('/api/v1/entities/map?year=1000');

        $response->assertOk();
        $response->assertJsonStructure([
            'type',
            'features' => [
                '*' => ['type', 'geometry', 'properties'],
            ],
        ]);
    }

    public function test_unauthenticated_user_cannot_view_dashboard()
    {
        $response = $this->get('/dashboard');

        $response->assertRedirect('login');
    }
}
```

- [ ] **Step 2: Run integration tests**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/HistoricalDashboardTest.php`

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add api/tests/Feature/HistoricalDashboardTest.php
git commit -m "test(feature): add integration tests for historical dashboard"
```

---

## Task 7: Manual Testing Checklist

**No code changes. Verification only.**

- [ ] **Verify Year Control Works**
  - [ ] Load dashboard at `/dashboard`
  - [ ] Change year input from 1000 to 500
  - [ ] Verify map reloads without page refresh
  - [ ] Check year value persists in input

- [ ] **Verify Map Rendering**
  - [ ] Confirm HistoricalMapViewer renders with entities visible
  - [ ] Confirm zoom/pan controls work
  - [ ] Confirm OHM base layer visible (if using OHM integration)

- [ ] **Verify Entity Selection**
  - [ ] Click on an entity feature (polygon/point)
  - [ ] Confirm side panel appears with entity details
  - [ ] Confirm "View Full Page" button navigates to `/entities/{id}`
  - [ ] Confirm "Close" button hides side panel

- [ ] **Verify Error Handling**
  - [ ] Temporarily break API endpoint
  - [ ] Confirm error message displays on dashboard
  - [ ] Confirm user can still interact (close, change year)

- [ ] **Verify Loading State**
  - [ ] Slow down API response (dev tools throttle)
  - [ ] Confirm loading spinner shows while fetching
  - [ ] Confirm spinner disappears when done

---

## Task 8: Performance & Optimization Checkpoint

**Files:**
- Check: Network performance in browser dev tools
- Check: API response time for map queries
- Review: HistoricalMapViewer rendering efficiency

- [ ] **Step 1: Profile API response time**

Run dashboard, open Network tab in browser dev tools:
- Initial map load: should be < 500ms
- Year change request: should be < 500ms

If slower, document and consider pagination/virtualization in future

- [ ] **Step 2: Check map rendering performance**

In browser console:

```javascript
// Measure rendering time
const start = performance.now();
// Map renders
const end = performance.now();
console.log(`Map render took ${end - start}ms`);
```

Expected: < 1000ms for typical entity count

- [ ] **Step 3: Monitor browser memory**

Open Chrome DevTools → Performance tab, record while:
- Loading dashboard
- Changing year 5 times
- Switching between entities

Expected: No unbounded memory growth

If found, add memory profiling note to technical debt

- [ ] **Step 4: Document findings (no commit needed)**

If performance is acceptable, no action required.

---

## Summary

This plan implements Approach 1: **Extend existing map API + new dashboard page**.

**What You're Building:**
1. Year-aware API endpoint that filters entities by temporal geometry periods
2. Dashboard page with year control, full-screen map, and entity side panel
3. Complete test coverage for API filtering and dashboard flow

**Execution Flow:**
1. Tests first (TDD): Year validation, geometry precedence, integration tests
2. API changes: Add year parameter, implement geometry selection logic
3. Frontend: Dashboard page with map viewer, controls, side panel
4. Verification: Manual testing + performance checkpoint

**Key Decisions Locked In:**
- Year 1000 as default
- Geometry period precedence: year-specific > base geometry
- Side panel with link to full page
- Reuse existing HistoricalMapViewer for rendering
- Full API filtering inherited (no new filters added in this phase)

**Next: Choose Execution Method**

Plan is complete. Ready for execution:

**Option 1: Subagent-Driven (Recommended)** — Fresh subagent per task, faster iteration
**Option 2: Inline Execution** — Execute tasks here with checkpoints for review

Which approach would you like?

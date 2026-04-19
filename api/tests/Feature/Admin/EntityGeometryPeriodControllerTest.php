<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class EntityGeometryPeriodControllerTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    private Entity $entity;

    private Entity $otherEntity;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = User::factory()->create();
        $this->entity = Entity::factory()->create();
        $this->otherEntity = Entity::factory()->create();
    }

    private function createGeometryPeriod(Entity $entity, int $startYear = 100, int $endYear = 150): string
    {
        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, provenance_mode, description, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'territory', ?, ?,
                ST_SetSRID(ST_MakePoint(12.48, 41.89), 4326), 'manual',
                'Initial period', NOW(), NOW()
            )",
            [$entity->entity_id, $startYear, $endYear],
        );

        return (string) DB::table('geometry_periods')
            ->where('entity_id', $entity->entity_id)
            ->where('start_year', $startYear)
            ->where('end_year', $endYear)
            ->value('geometry_period_id');
    }

    public function test_index_lists_only_entity_geometry_periods(): void
    {
        $this->createGeometryPeriod($this->entity, 120, 160);
        $this->createGeometryPeriod($this->otherEntity, 130, 170);

        $this->actingAs($this->user)
            ->getJson(route('entities.geometry-periods.index', $this->entity))
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.entity_id', $this->entity->entity_id)
            ->assertJsonPath('data.0.start_year', 120)
            ->assertJsonPath('data.0.end_year', 160);
    }

    public function test_store_creates_geometry_period(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.geometry-periods.store', $this->entity), [
                'period_type' => 'territory',
                'start_year' => 300,
                'end_year' => 320,
                'description' => 'Expansion period',
                'provenance_mode' => 'manual',
                'geom' => [
                    'type' => 'Point',
                    'coordinates' => [12.48, 41.89],
                ],
            ])
            ->assertCreated()
            ->assertJsonPath('data.entity_id', $this->entity->entity_id)
            ->assertJsonPath('data.start_year', 300)
            ->assertJsonPath('data.end_year', 320);

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $this->entity->entity_id,
            'period_type' => 'territory',
            'start_year' => 300,
            'end_year' => 320,
            'provenance_mode' => 'manual',
        ]);
    }

    public function test_store_creates_polygon_geometry_period(): void
    {
        $response = $this->actingAs($this->user)
            ->postJson(route('entities.geometry-periods.store', $this->entity), [
                'period_type' => 'territory',
                'start_year' => 300,
                'end_year' => 320,
                'description' => 'Territorial extent',
                'provenance_mode' => 'manual',
                'territory_geom' => [
                    'type' => 'Polygon',
                    'coordinates' => [[[10, 40], [11, 40], [11, 41], [10, 41], [10, 40]]],
                ],
            ]);

        $response
            ->assertCreated()
            ->assertJsonPath('data.entity_id', $this->entity->entity_id)
            ->assertJsonPath('data.territory_geom.type', 'Polygon')
            ->assertJsonPath('data.territory_geom.coordinates.0.0.0', 10)
            ->assertJsonPath('data.territory_geom.coordinates.0.0.1', 40);

        $periodId = (string) $response->json('data.geometry_period_id');

        $territoryGeoJson = DB::table('geometry_periods')
            ->where('geometry_period_id', $periodId)
            ->selectRaw('ST_AsGeoJSON(territory_geom)::jsonb AS territory_geom')
            ->value('territory_geom');

        if (is_string($territoryGeoJson)) {
            $territoryGeoJson = json_decode($territoryGeoJson, true, 512, JSON_THROW_ON_ERROR);
        }

        $this->assertIsArray($territoryGeoJson);
        $this->assertSame('Polygon', $territoryGeoJson['type'] ?? null);
    }

    public function test_store_validates_year_range(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.geometry-periods.store', $this->entity), [
                'period_type' => 'territory',
                'start_year' => 320,
                'end_year' => 300,
                'provenance_mode' => 'manual',
                'geom' => [
                    'type' => 'Point',
                    'coordinates' => [12.48, 41.89],
                ],
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['start_year']);
    }

    public function test_store_requires_at_least_one_geometry(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.geometry-periods.store', $this->entity), [
                'period_type' => 'territory',
                'start_year' => 300,
                'end_year' => 320,
                'provenance_mode' => 'manual',
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['geom']);
    }

    public function test_update_persists_editable_fields(): void
    {
        $periodId = $this->createGeometryPeriod($this->entity, 120, 160);

        $this->actingAs($this->user)
            ->putJson(route('entities.geometry-periods.update', [$this->entity, $periodId]), [
                'period_type' => 'movement_path',
                'start_year' => 121,
                'end_year' => 161,
                'description' => 'Updated period',
                'provenance_mode' => 'manual',
                'geom' => [
                    'type' => 'Point',
                    'coordinates' => [13.41, 52.52],
                ],
            ])
            ->assertOk()
            ->assertJsonPath('data.period_type', 'movement_path')
            ->assertJsonPath('data.start_year', 121)
            ->assertJsonPath('data.end_year', 161)
            ->assertJsonPath('data.description', 'Updated period');

        $this->assertDatabaseHas('geometry_periods', [
            'geometry_period_id' => $periodId,
            'period_type' => 'movement_path',
            'start_year' => 121,
            'end_year' => 161,
            'description' => 'Updated period',
        ]);
    }

    public function test_update_replaces_point_with_polygon_geometry_period(): void
    {
        $periodId = $this->createGeometryPeriod($this->entity, 120, 160);

        $response = $this->actingAs($this->user)
            ->putJson(route('entities.geometry-periods.update', [$this->entity, $periodId]), [
                'period_type' => 'territory',
                'start_year' => 121,
                'end_year' => 161,
                'description' => 'Expanded territory',
                'provenance_mode' => 'manual',
                'territory_geom' => [
                    'type' => 'Polygon',
                    'coordinates' => [[[13, 52], [14, 52], [14, 53], [13, 53], [13, 52]]],
                ],
            ]);

        $response
            ->assertOk()
            ->assertJsonPath('data.period_type', 'territory')
            ->assertJsonPath('data.territory_geom.type', 'Polygon')
            ->assertJsonPath('data.territory_geom.coordinates.0.0.0', 13)
            ->assertJsonPath('data.territory_geom.coordinates.0.0.1', 52);

        $territoryGeoJson = DB::table('geometry_periods')
            ->where('geometry_period_id', $periodId)
            ->selectRaw('ST_AsGeoJSON(territory_geom)::jsonb AS territory_geom')
            ->value('territory_geom');

        if (is_string($territoryGeoJson)) {
            $territoryGeoJson = json_decode($territoryGeoJson, true, 512, JSON_THROW_ON_ERROR);
        }

        $this->assertIsArray($territoryGeoJson);
        $this->assertSame('Polygon', $territoryGeoJson['type'] ?? null);
    }

    public function test_destroy_deletes_geometry_period(): void
    {
        $periodId = $this->createGeometryPeriod($this->entity);

        $this->actingAs($this->user)
            ->deleteJson(route('entities.geometry-periods.destroy', [$this->entity, $periodId]))
            ->assertNoContent();

        $this->assertDatabaseMissing('geometry_periods', [
            'geometry_period_id' => $periodId,
        ]);
    }

    public function test_destroy_returns_404_for_period_not_owned_by_entity(): void
    {
        $periodId = $this->createGeometryPeriod($this->otherEntity);

        $this->actingAs($this->user)
            ->deleteJson(route('entities.geometry-periods.destroy', [$this->entity, $periodId]))
            ->assertNotFound();
    }

    public function test_requires_authentication(): void
    {
        $this->getJson(route('entities.geometry-periods.index', $this->entity))
            ->assertUnauthorized();
    }
}

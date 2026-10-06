<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\EntityLocation;
use App\Models\EntityRelationship;
use App\Models\EntityTemporalRange;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class DeriveLocatedAtGeometryCommandTest extends TestCase
{
    use RefreshDatabase;

    private function entity(EntityType $type, ?int $start = null, ?int $end = null): Entity
    {
        $entity = Entity::factory()->ofType($type)->create();

        if ($start !== null) {
            EntityTemporalRange::query()->create([
                'entity_id' => $entity->entity_id,
                'range_type' => 'primary',
                'start_date' => (string) $start,
                'end_date' => $end !== null ? (string) $end : null,
                'is_primary' => true,
            ]);
        }

        return $entity;
    }

    private function point(Entity $entity, float $lng, float $lat, bool $withQid = true): void
    {
        if ($withQid) {
            $entity->forceFill(['wikidata_id' => 'Q'.random_int(1000, 999999999)])->save();
        }

        EntityLocation::query()->create([
            'entity_id' => $entity->entity_id,
            'location_name' => $entity->name,
            'is_primary' => true,
            'geom' => ['type' => 'Point', 'coordinates' => [$lng, $lat]],
        ]);
    }

    private function locatedAt(Entity $source, Entity $target, ?string $start = null): string
    {
        $id = (string) Str::uuid();
        EntityRelationship::query()->create([
            'relationship_id' => $id,
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'located_at',
            'temporal_start' => $start,
            'description' => "{$source->name} took place at {$target->name}.",
            'created_by' => 'test',
        ]);

        return $id;
    }

    private function periodCoordinates(Entity $entity): array
    {
        $row = DB::selectOne('SELECT ST_X(geom) AS x, ST_Y(geom) AS y FROM geometry_periods WHERE entity_id = ?', [$entity->entity_id]);

        return [(float) $row->x, (float) $row->y];
    }

    public function test_dry_run_reports_and_writes_nothing(): void
    {
        $battle = $this->entity(EntityType::EventBattle, 1121);
        $city = $this->entity(EntityType::City);
        $this->point($city, 44.0, 41.8);
        $this->locatedAt($battle, $city);

        $this->artisan('geometry:derive-located-at')
            ->expectsOutputToContain('[DRY-RUN] located_at geometry derivation: 1 period(s) planned')
            ->assertExitCode(0);

        $this->assertSame(0, GeometryPeriod::query()->count());
    }

    public function test_apply_places_event_at_target_point(): void
    {
        $battle = $this->entity(EntityType::EventBattle, 1121);
        $city = $this->entity(EntityType::City);
        $this->point($city, 44.0, 41.8);
        $relationshipId = $this->locatedAt($battle, $city);

        $this->artisan('geometry:derive-located-at --apply')->assertExitCode(0);

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $battle->entity_id,
            'period_type' => 'presence',
            'provenance_mode' => 'derived',
            'relationship_id' => $relationshipId,
            'start_year' => 1121,
            'end_year' => 1121,  // momentary event: open end collapses to the start
            'confidence' => 'medium',
            'created_by' => 'derive:located_at',
        ]);
        $this->assertSame([44.0, 41.8], $this->periodCoordinates($battle));
        // Additive only: the source's own location row is untouched.
        $this->assertSame(0, EntityLocation::query()->where('entity_id', $battle->entity_id)->count());
    }

    public function test_apply_is_idempotent_and_never_adds_a_second_period(): void
    {
        $battle = $this->entity(EntityType::EventBattle, 1121);
        $city = $this->entity(EntityType::City);
        $this->point($city, 44.0, 41.8);
        $this->locatedAt($battle, $city);

        $this->artisan('geometry:derive-located-at --apply')->assertExitCode(0);
        $this->artisan('geometry:derive-located-at --apply')
            ->expectsOutputToContain('0 period(s) planned')
            ->assertExitCode(0);

        $this->assertSame(1, GeometryPeriod::query()->where('entity_id', $battle->entity_id)->count());
    }

    public function test_skips_mapped_own_point_yearless_and_non_place_targets(): void
    {
        $city = $this->entity(EntityType::City);
        $this->point($city, 10.0, 45.0);

        $mapped = $this->entity(EntityType::EventBattle, 1200);
        GeometryPeriod::query()->create([
            'entity_id' => $mapped->entity_id, 'period_type' => 'territory', 'start_year' => 1200,
            'geom' => ['type' => 'Point', 'coordinates' => [1.0, 1.0]], 'provenance_mode' => 'manual',
        ]);
        $this->locatedAt($mapped, $city);

        $ownPoint = $this->entity(EntityType::EventBattle, 1200);
        $this->point($ownPoint, 2.0, 2.0);
        $this->locatedAt($ownPoint, $city);

        $yearless = $this->entity(EntityType::EventBattle);
        $this->locatedAt($yearless, $city);

        $person = $this->entity(EntityType::Person);
        $this->point($person, 3.0, 3.0);
        $wrongTarget = $this->entity(EntityType::EventBattle, 1200);
        $this->locatedAt($wrongTarget, $person);

        $this->artisan('geometry:derive-located-at --apply')
            ->expectsOutputToContain('skipped: own_point=1 (run entity:backfill) no_year=1')
            ->assertExitCode(0);

        $this->assertSame(1, GeometryPeriod::query()->where('entity_id', $mapped->entity_id)->count());
        foreach ([$ownPoint, $yearless, $wrongTarget] as $entity) {
            $this->assertDatabaseMissing('geometry_periods', ['entity_id' => $entity->entity_id]);
        }
    }

    public function test_polity_target_is_low_confidence_and_excluded_by_precise_only(): void
    {
        $reform = $this->entity(EntityType::EventLegalReform, 1873);
        $country = $this->entity(EntityType::PoliticalEntity);
        $this->point($country, 138.0, 36.0);
        $this->locatedAt($reform, $country);

        $this->artisan('geometry:derive-located-at --apply --precise-only')
            ->expectsOutputToContain('polity_target=1')
            ->assertExitCode(0);
        $this->assertDatabaseMissing('geometry_periods', ['entity_id' => $reform->entity_id]);

        $this->artisan('geometry:derive-located-at --apply')->assertExitCode(0);
        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $reform->entity_id, 'confidence' => 'low', 'created_by' => 'derive:located_at',
        ]);
    }

    public function test_prefers_place_target_and_place_sources_never_take_polity_points(): void
    {
        $battle = $this->entity(EntityType::EventBattle, -490);
        $country = $this->entity(EntityType::PoliticalEntity);
        $this->point($country, 22.0, 39.0);
        $plain = $this->entity(EntityType::City);
        $this->point($plain, 23.96, 38.12);
        $this->locatedAt($battle, $country);
        $this->locatedAt($battle, $plain);

        $temple = $this->entity(EntityType::InfrastructureMonument, -447);
        $this->locatedAt($temple, $country);

        $this->artisan('geometry:derive-located-at --apply')->assertExitCode(0);

        $this->assertSame([23.96, 38.12], $this->periodCoordinates($battle));
        $this->assertDatabaseHas('geometry_periods', ['entity_id' => $battle->entity_id, 'start_year' => -490]);
        $this->assertDatabaseMissing('geometry_periods', ['entity_id' => $temple->entity_id]);
    }

    public function test_place_source_keeps_open_end_and_uses_target_period_point_when_no_location(): void
    {
        $temple = $this->entity(EntityType::InfrastructureMonument, -447);
        $city = $this->entity(EntityType::City);
        $city->forceFill(['wikidata_id' => 'Q1524'])->save();
        GeometryPeriod::query()->create([
            'entity_id' => $city->entity_id, 'period_type' => 'territory', 'start_year' => -1000,
            'geom' => ['type' => 'Point', 'coordinates' => [23.72, 37.97]], 'provenance_mode' => 'ohm_import',
        ]);
        $this->locatedAt($temple, $city);

        $this->artisan('geometry:derive-located-at --apply --group=PLACE')->assertExitCode(0);

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $temple->entity_id, 'start_year' => -447, 'end_year' => null,
        ]);
        $this->assertSame([23.72, 37.97], $this->periodCoordinates($temple));
    }

    public function test_never_spreads_a_point_whose_qid_was_cleared(): void
    {
        $siege = $this->entity(EntityType::EventBattle, 1246);
        $uch = $this->entity(EntityType::City);
        $this->point($uch, 132.66, 33.53, withQid: false);  // residue of a removed wrong QID
        $this->locatedAt($siege, $uch);

        $this->artisan('geometry:derive-located-at --apply')
            ->expectsOutputToContain('0 period(s) planned')
            ->assertExitCode(0);

        $this->assertDatabaseMissing('geometry_periods', ['entity_id' => $siege->entity_id]);
    }

    public function test_falls_back_to_relation_years_and_rejects_unknown_group(): void
    {
        $battle = $this->entity(EntityType::EventBattle);
        $city = $this->entity(EntityType::City);
        $this->point($city, 5.0, 50.0);
        $this->locatedAt($battle, $city, '1815');

        $this->artisan('geometry:derive-located-at --apply --group=EVENT')->assertExitCode(0);
        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $battle->entity_id, 'start_year' => 1815, 'end_year' => 1815,
        ]);

        $this->artisan('geometry:derive-located-at --group=POLITY')->assertExitCode(2);
    }
}

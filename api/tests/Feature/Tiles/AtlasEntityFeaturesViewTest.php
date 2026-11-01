<?php

declare(strict_types=1);

namespace Tests\Feature\Tiles;

use App\Enums\EntityGroup;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class AtlasEntityFeaturesViewTest extends TestCase
{
    use RefreshDatabase;

    public function test_decdate_follows_ohm_convention(): void
    {
        $entity = Entity::factory()->verified()->inGroup(EntityGroup::Polity)->create();

        $bounded = $this->insertPeriod($entity, 1900, 1950);
        $open = $this->insertPeriod($entity, 1900, null);
        $bce = $this->insertPeriod($entity, -2999, -2799);

        $row = $this->featureRow($bounded);
        $this->assertSame(1900.00137, (float) $row->start_decdate);
        $this->assertSame(1950.99863, (float) $row->end_decdate);

        $row = $this->featureRow($open);
        $this->assertSame(1900.00137, (float) $row->start_decdate);
        $this->assertNull($row->end_decdate);

        $row = $this->featureRow($bce);
        $this->assertSame(-2998.99863, (float) $row->start_decdate);
        $this->assertSame(-2798.00137, (float) $row->end_decdate);
    }

    public function test_event_window_is_padded_ten_years_but_display_years_are_exact(): void
    {
        $entity = Entity::factory()->verified()->inGroup(EntityGroup::Event)->create();
        $period = $this->insertPeriod($entity, 1066, 1066);

        $row = $this->featureRow($period);

        $this->assertSame(1066, (int) $row->start_year);
        $this->assertSame(1066, (int) $row->end_year);
        $this->assertSame(1056.00137, (float) $row->start_decdate);
        $this->assertSame(1076.99863, (float) $row->end_decdate);
    }

    public function test_ohm_relation_ref_emits_negative_signed_id_and_point_geometry(): void
    {
        $relationEntity = Entity::factory()->verified()->create();
        $relationPeriod = $this->insertPeriod($relationEntity, 900, 1100, withPolygon: true);
        $this->insertOhmRef($relationEntity, 'relation', '1880');

        $nodeEntity = Entity::factory()->verified()->create();
        $nodePeriod = $this->insertPeriod($nodeEntity, 900, 1100);
        $this->insertOhmRef($nodeEntity, 'node', '42');

        $unlinkedEntity = Entity::factory()->verified()->create();
        $unlinkedPeriod = $this->insertPeriod($unlinkedEntity, 900, 1100, withPolygon: true);

        $row = $this->featureRow($relationPeriod);
        $this->assertSame(-1880, (int) $row->ohm_osm_id);
        $this->assertSame('ST_Point', $row->geom_type);

        $this->assertSame(42, (int) $this->featureRow($nodePeriod)->ohm_osm_id);

        $row = $this->featureRow($unlinkedPeriod);
        $this->assertNull($row->ohm_osm_id);
        // Unlinked entities serve the app-owned territory polygon.
        $this->assertSame('ST_Polygon', $row->geom_type);

        // A zero id is not a valid OSM id (parity with OhmDate::signedOsmId).
        $zeroEntity = Entity::factory()->verified()->create();
        $zeroPeriod = $this->insertPeriod($zeroEntity, 900, 1100, withPolygon: true);
        $this->insertOhmRef($zeroEntity, 'relation', '0');
        $row = $this->featureRow($zeroPeriod);
        $this->assertNull($row->ohm_osm_id);
        $this->assertSame('ST_Polygon', $row->geom_type);
    }

    public function test_primary_alias_wins_over_entity_name(): void
    {
        $entity = Entity::factory()->verified()->create(['name' => 'Entity Name']);
        $period = $this->insertPeriod($entity, 900, 1100);

        DB::statement(
            "INSERT INTO entity_aliases (alias_id, entity_id, name, is_primary, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, 'Secondary Alias', false, NOW(), NOW()),
                    (gen_random_uuid(), ?, 'Primary Alias', true, NOW(), NOW())",
            [$entity->entity_id, $entity->entity_id],
        );

        $this->assertSame('Primary Alias', $this->featureRow($period)->name);
    }

    public function test_rejected_entities_are_excluded(): void
    {
        $rejected = Entity::factory()->create([
            'verification_status' => VerificationStatus::Rejected->value,
        ]);
        $period = $this->insertPeriod($rejected, 900, 1100);

        $this->assertNull($this->featureRow($period, required: false));
    }

    public function test_fid_is_stable_and_fits_52_bits(): void
    {
        $entity = Entity::factory()->verified()->create();
        $period = $this->insertPeriod($entity, 900, 1100);

        $first = (int) $this->featureRow($period)->fid;
        $second = (int) $this->featureRow($period)->fid;

        $this->assertSame($first, $second);
        $this->assertGreaterThanOrEqual(0, $first);
        $this->assertLessThanOrEqual(4503599627370495, $first);
        // The fid is the first 52 bits of md5(geometry_period_id), not a row number.
        $this->assertSame(hexdec(substr(md5($period), 0, 13)), $first);
    }

    public function test_has_map_story_flags_entities_with_a_map_story(): void
    {
        $battle = Entity::factory()->verified()->inGroup(EntityGroup::Event)->create();
        $battlePeriod = $this->insertPeriod($battle, 1066, 1066);
        $this->insertMapStory($battle, 'battle-of-testfield');

        $plain = Entity::factory()->verified()->inGroup(EntityGroup::Event)->create();
        $plainPeriod = $this->insertPeriod($plain, 1066, 1066);

        // Parity with MapEntitiesAction: a boolean on every row, never NULL.
        $this->assertTrue((bool) $this->featureRow($battlePeriod)->has_map_story);
        $this->assertFalse($this->featureRow($plainPeriod)->has_map_story);
    }

    /** Insert a geometry period (point, optionally with a polygon) and return its id. */
    private function insertPeriod(Entity $entity, int $startYear, ?int $endYear, bool $withPolygon = false): string
    {
        $periodId = Str::uuid()->toString();
        $territory = $withPolygon
            ? "ST_SetSRID(ST_GeomFromText('POLYGON((10 40, 11 40, 11 41, 10 41, 10 40))'), 4326)"
            : 'NULL';

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                ?, ?, 'territory', ?, ?,
                ST_SetSRID(ST_Point(10.5, 40.5), 4326), {$territory},
                'manual', 'test', NOW(), NOW()
            )",
            [$periodId, $entity->entity_id, $startYear, $endYear],
        );

        return $periodId;
    }

    private function insertOhmRef(Entity $entity, string $externalType, string $externalId): void
    {
        DB::statement(
            "INSERT INTO entity_geo_refs (
                geo_ref_id, entity_id, external_id, external_type, provider,
                match_role, retrieval_method, is_active, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, ?, ?::geo_ref_external_type, 'ohm', 'primary', 'manual', true, NOW(), NOW()
            )",
            [$entity->entity_id, $externalId, $externalType],
        );
    }

    private function insertMapStory(Entity $entity, string $slug): void
    {
        DB::statement(
            "INSERT INTO map_stories (entity_id, slug, kind, title, year, step_count, document, created_at, updated_at)
             VALUES (?, ?, 'battle', 'Test battle', 1066, 1, '{}'::jsonb, NOW(), NOW())",
            [$entity->entity_id, $slug],
        );
    }

    private function featureRow(string $periodId, bool $required = true): ?object
    {
        $row = DB::selectOne(
            'SELECT f.*, ST_GeometryType(f.geom) AS geom_type
             FROM tiles.atlas_entity_features f
             WHERE f.geometry_period_id = ?',
            [$periodId],
        );

        if ($required) {
            $this->assertNotNull($row, "No feature row for geometry period {$periodId}.");
        }

        return $row;
    }
}

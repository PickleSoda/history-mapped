<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use App\Models\EntityAlias;
use App\Models\EntityLocation;
use App\Models\EntityTag;
use App\Models\EntityTemporalRange;
use App\Models\EntityTimelineEntry;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class EntityModelRelationsTest extends TestCase
{
    use RefreshDatabase;

    private Entity $entity;

    protected function setUp(): void
    {
        parent::setUp();
        $this->entity = Entity::factory()->create();
    }

    // ── Entity → EntityAlias ──────────────────────────────────

    public function test_entity_has_many_aliases(): void
    {
        DB::table('entity_aliases')->insert([
            ['alias_id' => Str::uuid(), 'entity_id' => $this->entity->entity_id, 'name' => 'Alt Name 1', 'created_at' => now(), 'updated_at' => now()],
            ['alias_id' => Str::uuid(), 'entity_id' => $this->entity->entity_id, 'name' => 'Alt Name 2', 'created_at' => now(), 'updated_at' => now()],
        ]);

        $aliases = $this->entity->aliases()->get();

        $this->assertCount(2, $aliases);
        $this->assertInstanceOf(EntityAlias::class, $aliases->first());
    }

    // ── Entity → EntityTag ───────────────────────────────────

    public function test_entity_has_many_entity_tags(): void
    {
        DB::table('entity_tags')->insert([
            ['entity_tag_id' => Str::uuid(), 'entity_id' => $this->entity->entity_id, 'tag' => 'bronze-age', 'created_at' => now(), 'updated_at' => now()],
            ['entity_tag_id' => Str::uuid(), 'entity_id' => $this->entity->entity_id, 'tag' => 'mediterranean', 'created_at' => now(), 'updated_at' => now()],
        ]);

        $tags = $this->entity->entityTags()->get();

        $this->assertCount(2, $tags);
        $this->assertInstanceOf(EntityTag::class, $tags->first());
    }

    // ── Entity → EntityTemporalRange ─────────────────────────

    public function test_entity_has_many_temporal_ranges(): void
    {
        DB::table('entity_temporal_ranges')->insert([
            'temporal_range_id' => Str::uuid(),
            'entity_id' => $this->entity->entity_id,
            'range_type' => 'primary',
            'start_year' => -1200,
            'end_year' => -1150,
            'is_primary' => true,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $ranges = $this->entity->temporalRanges()->get();

        $this->assertCount(1, $ranges);
        $this->assertInstanceOf(EntityTemporalRange::class, $ranges->first());
    }

    // ── Entity → EntityLocation ──────────────────────────────

    public function test_entity_has_many_locations(): void
    {
        DB::table('entity_locations')->insert([
            'location_id' => Str::uuid(),
            'entity_id' => $this->entity->entity_id,
            'location_name' => 'Eastern Mediterranean',
            'is_primary' => true,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $locations = $this->entity->locations()->get();

        $this->assertCount(1, $locations);
        $this->assertInstanceOf(EntityLocation::class, $locations->first());
    }

    // ── Entity → GeometryPeriod ──────────────────────────────

    public function test_entity_has_many_geometry_periods(): void
    {
        DB::table('relationships')->insertGetId([
            'relationship_id' => Str::uuid(),
            'source_entity_id' => $this->entity->entity_id,
            'target_entity_id' => Entity::factory()->create()->entity_id,
            'relationship_type' => 'fought_at',
            'created_at' => now(),
        ], 'relationship_id');

        $relationshipId = DB::table('relationships')
            ->where('source_entity_id', $this->entity->entity_id)
            ->value('relationship_id');

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, provenance_mode, relationship_id, created_at, updated_at
            ) VALUES (?, ?, 'presence', -1200, -1190,
                ST_SetSRID(ST_MakePoint(28.97, 41.01), 4326), 'derived', ?, NOW(), NOW())",
            [Str::uuid()->toString(), $this->entity->entity_id, $relationshipId],
        );

        $periods = $this->entity->geometryPeriods()->get();

        $this->assertCount(1, $periods);
        $this->assertInstanceOf(GeometryPeriod::class, $periods->first());
    }

    public function test_entity_geometry_periods_relation_is_defined(): void
    {
        $this->assertInstanceOf(
            \Illuminate\Database\Eloquent\Relations\HasMany::class,
            $this->entity->geometryPeriods()
        );
    }

    public function test_entity_timeline_entries_relation_is_defined(): void
    {
        $this->assertInstanceOf(
            \Illuminate\Database\Eloquent\Relations\HasMany::class,
            $this->entity->timelineEntries()
        );
    }

    // ── GeometryPeriod → Entity ──────────────────────────────

    public function test_geometry_period_model_belongs_to_entity(): void
    {
        $period = new GeometryPeriod(['entity_id' => $this->entity->entity_id]);

        $this->assertInstanceOf(
            \Illuminate\Database\Eloquent\Relations\BelongsTo::class,
            $period->entity()
        );
    }

    public function test_geometry_period_model_has_optional_relationship_association(): void
    {
        $period = new GeometryPeriod(['relationship_id' => null]);

        $this->assertInstanceOf(
            \Illuminate\Database\Eloquent\Relations\BelongsTo::class,
            $period->relationship()
        );
    }

    public function test_geometry_period_model_has_optional_source_event_association(): void
    {
        $period = new GeometryPeriod(['source_event_id' => null]);

        $this->assertInstanceOf(
            \Illuminate\Database\Eloquent\Relations\BelongsTo::class,
            $period->sourceEvent()
        );
    }

    // ── EntityTimelineEntry → Entity ─────────────────────────

    public function test_timeline_entry_model_belongs_to_entity(): void
    {
        $entry = new EntityTimelineEntry(['entity_id' => $this->entity->entity_id]);

        $this->assertInstanceOf(
            \Illuminate\Database\Eloquent\Relations\BelongsTo::class,
            $entry->entity()
        );
    }
}

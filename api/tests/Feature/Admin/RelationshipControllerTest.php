<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\GeometrySnapshot;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class RelationshipControllerTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    private Entity $source;

    private Entity $target;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = User::factory()->create();
        $this->source = Entity::factory()->create();
        $this->target = Entity::factory()->create();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /**
     * Set a PostGIS point geometry on the given entity (required for auto-snapshot).
     */
    private function giveEntityPointGeom(Entity $entity, float $lng = 28.97, float $lat = 41.01): void
    {
        DB::statement(
            'UPDATE entities SET geom = ST_SetSRID(ST_MakePoint(?, ?), 4326) WHERE entity_id = ?',
            [$lng, $lat, $entity->entity_id],
        );
    }

    /**
     * Create an EntityRelationship row directly (bypassing the action).
     *
     * @param  array<string, mixed>  $overrides
     */
    private function createRelationship(array $overrides = []): EntityRelationship
    {
        $attrs = array_merge([
            'source_entity_id' => $this->source->entity_id,
            'target_entity_id' => $this->target->entity_id,
            'relationship_type' => 'allied_with',
            'created_by' => 'test',
        ], $overrides);

        // Insert via DB to get the DB-generated UUID primary key back
        $id = DB::table('relationships')->insertGetId($attrs, 'relationship_id');

        return EntityRelationship::where('relationship_id', $id)->firstOrFail();
    }

    // ── index ─────────────────────────────────────────────────────────────────

    public function test_index_returns_empty_lists_for_entity_with_no_relationships(): void
    {
        $this->actingAs($this->user)
            ->getJson(route('entities.relationships.index', $this->source))
            ->assertOk()
            ->assertJsonStructure(['outgoing', 'incoming'])
            ->assertJsonCount(0, 'outgoing')
            ->assertJsonCount(0, 'incoming');
    }

    public function test_index_returns_outgoing_relationships(): void
    {
        $this->createRelationship();

        $this->actingAs($this->user)
            ->getJson(route('entities.relationships.index', $this->source))
            ->assertOk()
            ->assertJsonCount(1, 'outgoing')
            ->assertJsonCount(0, 'incoming');
    }

    public function test_index_returns_incoming_relationships(): void
    {
        $this->createRelationship([
            'source_entity_id' => $this->target->entity_id,
            'target_entity_id' => $this->source->entity_id,
        ]);

        $this->actingAs($this->user)
            ->getJson(route('entities.relationships.index', $this->source))
            ->assertOk()
            ->assertJsonCount(0, 'outgoing')
            ->assertJsonCount(1, 'incoming');
    }

    public function test_index_includes_related_entity_summary(): void
    {
        $this->createRelationship();

        $this->actingAs($this->user)
            ->getJson(route('entities.relationships.index', $this->source))
            ->assertOk()
            ->assertJsonPath('outgoing.0.related_entity.id', $this->target->entity_id)
            ->assertJsonPath('outgoing.0.related_entity.name', $this->target->name);
    }

    public function test_index_includes_related_entity_geometry_payload(): void
    {
        $this->giveEntityPointGeom($this->target, 12.48, 41.89);
        $this->createRelationship();

        $this->actingAs($this->user)
            ->getJson(route('entities.relationships.index', $this->source))
            ->assertOk()
            ->assertJsonPath('outgoing.0.related_entity.id', $this->target->entity_id)
            ->assertJsonPath('outgoing.0.related_entity.geojson.type', 'Point')
            ->assertJsonPath('outgoing.0.related_entity.territory_geojson', null);
    }

    public function test_index_requires_authentication(): void
    {
        $this->getJson(route('entities.relationships.index', $this->source))
            ->assertUnauthorized();
    }

    // ── store ─────────────────────────────────────────────────────────────────

    public function test_store_creates_relationship(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'allied_with',
            ])
            ->assertCreated()
            ->assertJsonStructure(['relationship' => ['relationship_id', 'relationship_type', 'related_entity']]);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $this->source->entity_id,
            'target_entity_id' => $this->target->entity_id,
            'relationship_type' => 'allied_with',
        ]);
    }

    public function test_store_persists_optional_fields(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'allied_with',
                'temporal_start' => '1648',
                'temporal_end' => '1700',
                'description' => 'Alliance forged at Westphalia',
                'confidence' => 'high',
            ])
            ->assertCreated()
            ->assertJsonPath('relationship.temporal_start', '1648')
            ->assertJsonPath('relationship.temporal_end', '1700')
            ->assertJsonPath('relationship.description', 'Alliance forged at Westphalia')
            ->assertJsonPath('relationship.confidence', 'high');
    }

    public function test_store_requires_target_entity_id(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'relationship_type' => 'allied_with',
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['target_entity_id']);
    }

    public function test_store_requires_relationship_type(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['relationship_type']);
    }

    public function test_store_rejects_invalid_relationship_type(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'invented_type_xyz',
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['relationship_type']);
    }

    public function test_store_rejects_invalid_confidence_value(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'allied_with',
                'confidence' => 'absolute',
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['confidence']);
    }

    public function test_store_rejects_unknown_target_entity(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => '00000000-0000-0000-0000-000000000000',
                'relationship_type' => 'allied_with',
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['target_entity_id']);
    }

    public function test_store_requires_authentication(): void
    {
        $this->postJson(route('entities.relationships.store', $this->source), [
            'target_entity_id' => $this->target->entity_id,
            'relationship_type' => 'allied_with',
        ])->assertUnauthorized();
    }

    // ── store — auto-snapshot ─────────────────────────────────────────────────

    public function test_store_creates_auto_snapshot_for_auto_snapshot_type_with_geom_and_temporal_start(): void
    {
        $this->giveEntityPointGeom($this->source);

        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'fought_at',
                'temporal_start' => '1453',
                'temporal_end' => '1453',
            ])
            ->assertCreated();

        $this->assertDatabaseHas('geometry_snapshots', [
            'entity_id' => $this->source->entity_id,
            'year_start' => 1453,
            'year_end' => 1453,
        ]);

        $snapshot = GeometrySnapshot::where('entity_id', $this->source->entity_id)->first();
        $this->assertNotNull($snapshot);
        $this->assertStringContainsString($this->target->name, $snapshot->description);
        $this->assertStringContainsString('fought at', $snapshot->description);
    }

    public function test_store_does_not_create_auto_snapshot_for_non_auto_snapshot_type(): void
    {
        $this->giveEntityPointGeom($this->source);

        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'allied_with',
                'temporal_start' => '1648',
            ])
            ->assertCreated();

        $this->assertDatabaseMissing('geometry_snapshots', [
            'entity_id' => $this->source->entity_id,
        ]);
    }

    public function test_store_does_not_create_auto_snapshot_when_source_has_no_geom(): void
    {
        // Source entity has no geom (factory default)
        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'fought_at',
                'temporal_start' => '1453',
            ])
            ->assertCreated();

        $this->assertDatabaseMissing('geometry_snapshots', [
            'entity_id' => $this->source->entity_id,
        ]);
    }

    public function test_store_does_not_create_auto_snapshot_when_no_temporal_start(): void
    {
        $this->giveEntityPointGeom($this->source);

        $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'fought_at',
                // No temporal_start
            ])
            ->assertCreated();

        $this->assertDatabaseMissing('geometry_snapshots', [
            'entity_id' => $this->source->entity_id,
        ]);
    }

    // ── destroy ───────────────────────────────────────────────────────────────

    public function test_destroy_deletes_relationship(): void
    {
        $relationship = $this->createRelationship();
        $url = '/entities/'.$this->source->entity_id.'/relationships/'.$relationship->relationship_id;

        $this->actingAs($this->user)
            ->deleteJson($url)
            ->assertNoContent();

        $this->assertDatabaseMissing('relationships', [
            'relationship_id' => $relationship->relationship_id,
        ]);
    }

    public function test_destroy_404s_when_entity_is_not_source(): void
    {
        // Relationship is $target → $source; attempting delete via $source should 404
        $relationship = $this->createRelationship([
            'source_entity_id' => $this->target->entity_id,
            'target_entity_id' => $this->source->entity_id,
        ]);
        $url = '/entities/'.$this->source->entity_id.'/relationships/'.$relationship->relationship_id;

        $this->actingAs($this->user)
            ->deleteJson($url)
            ->assertNotFound();

        $this->assertDatabaseHas('relationships', [
            'relationship_id' => $relationship->relationship_id,
        ]);
    }

    public function test_destroy_404s_for_unknown_relationship(): void
    {
        $url = '/entities/'.$this->source->entity_id.'/relationships/00000000-0000-0000-0000-000000000000';

        $this->actingAs($this->user)
            ->deleteJson($url)
            ->assertNotFound();
    }

    public function test_destroy_requires_authentication(): void
    {
        $relationship = $this->createRelationship();
        $url = '/entities/'.$this->source->entity_id.'/relationships/'.$relationship->relationship_id;

        $this->deleteJson($url)
            ->assertUnauthorized();
    }
}

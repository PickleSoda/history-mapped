<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Models\Entity;
use App\Models\EntityRelationship;
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

    private function giveEntityPointGeom(Entity $entity, float $lng = 28.97, float $lat = 41.01): void
    {
        DB::table('entity_locations')
            ->where('entity_id', $entity->entity_id)
            ->where('is_primary', true)
            ->delete();

        DB::statement(
            "INSERT INTO entity_locations (
                location_id, entity_id, location_name, geom,
                location_method, location_confidence, is_primary, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, NULL,
                ST_SetSRID(ST_MakePoint(?, ?), 4326),
                'human_assigned'::location_resolution_method,
                'high'::confidence_level,
                true,
                NOW(), NOW()
            )",
            [$entity->entity_id, $lng, $lat],
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

    public function test_index_includes_pipeline_draft_related_entity(): void
    {
        $this->target->update(['verification_status' => 'pipeline_draft']);
        $this->createRelationship();

        $this->actingAs($this->user)
            ->getJson(route('entities.relationships.index', $this->source))
            ->assertOk()
            ->assertJsonPath('outgoing.0.related_entity.id', $this->target->entity_id)
            ->assertJsonPath('outgoing.0.related_entity.verification_status', 'pipeline_draft');
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
            ->assertJsonPath('relationship.start_year', 1648)
            ->assertJsonPath('relationship.end_year', 1700)
            ->assertJsonPath('relationship.description', 'Alliance forged at Westphalia')
            ->assertJsonPath('relationship.confidence', 'high');

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $this->source->entity_id,
            'target_entity_id' => $this->target->entity_id,
            'start_year' => 1648,
            'end_year' => 1700,
        ]);
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

    public function test_store_creates_derived_presence_period_for_auto_snapshot_type_with_geom_and_temporal_start(): void
    {
        $this->giveEntityPointGeom($this->target, 12.48, 41.89);

        $response = $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'fought_at',
                'temporal_start' => '1648',
                'temporal_end' => '1648',
                'description' => 'Battle participation',
            ])
            ->assertCreated();

        $relationshipId = (string) $response->json('relationship.relationship_id');

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $this->source->entity_id,
            'period_type' => 'presence',
            'start_year' => 1648,
            'end_year' => 1648,
            'provenance_mode' => 'derived',
            'relationship_id' => $relationshipId,
        ]);
    }

    public function test_store_creates_only_one_derived_presence_period_for_a_relationship(): void
    {
        $this->giveEntityPointGeom($this->target, 12.48, 41.89);

        $response = $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'fought_at',
                'temporal_start' => '1648',
                'temporal_end' => '1648',
            ])
            ->assertCreated();

        $relationshipId = (string) $response->json('relationship.relationship_id');

        $count = DB::table('geometry_periods')
            ->where('relationship_id', $relationshipId)
            ->where('period_type', 'presence')
            ->where('provenance_mode', 'derived')
            ->count();

        $this->assertSame(1, $count);
    }

    public function test_store_uses_target_primary_location_geometry_for_locative_relationships(): void
    {
        $this->giveEntityPointGeom($this->source, 12.48, 41.89);
        $this->giveEntityPointGeom($this->target, 23.72, 37.98);

        $response = $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'fought_at',
                'temporal_start' => '1648',
                'temporal_end' => '1648',
            ])
            ->assertCreated();

        $relationshipId = (string) $response->json('relationship.relationship_id');

        /** @var object{lon: float, lat: float}|null $geometry */
        $geometry = DB::selectOne(
            'SELECT ST_X(geom::geometry) AS lon, ST_Y(geom::geometry) AS lat
             FROM geometry_periods
             WHERE relationship_id = ?',
            [$relationshipId],
        );

        $this->assertNotNull($geometry);
        $this->assertEqualsWithDelta(23.72, $geometry->lon, 0.0001);
        $this->assertEqualsWithDelta(37.98, $geometry->lat, 0.0001);
    }

    public function test_store_does_not_create_derived_presence_period_for_non_auto_snapshot_type(): void
    {
        $this->giveEntityPointGeom($this->source, 12.48, 41.89);

        $response = $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'allied_with',
                'temporal_start' => '1648',
                'temporal_end' => '1648',
            ])
            ->assertCreated();

        $relationshipId = (string) $response->json('relationship.relationship_id');

        $this->assertDatabaseMissing('geometry_periods', [
            'relationship_id' => $relationshipId,
        ]);
    }

    public function test_store_does_not_create_derived_presence_period_when_source_has_no_geom(): void
    {
        $response = $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'fought_at',
                'temporal_start' => '1648',
                'temporal_end' => '1648',
            ])
            ->assertCreated();

        $relationshipId = (string) $response->json('relationship.relationship_id');

        $this->assertDatabaseMissing('geometry_periods', [
            'relationship_id' => $relationshipId,
        ]);
    }

    public function test_store_does_not_create_derived_presence_period_when_target_has_no_geom(): void
    {
        $this->giveEntityPointGeom($this->source, 12.48, 41.89);

        $response = $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'fought_at',
                'temporal_start' => '1648',
                'temporal_end' => '1648',
            ])
            ->assertCreated();

        $relationshipId = (string) $response->json('relationship.relationship_id');

        $this->assertDatabaseMissing('geometry_periods', [
            'relationship_id' => $relationshipId,
        ]);
    }

    // ── update ───────────────────────────────────────────────────────────────

    public function test_update_updates_outgoing_relationship_fields(): void
    {
        $relationship = $this->createRelationship([
            'relationship_type' => 'allied_with',
            'temporal_start' => '1648',
            'temporal_end' => '1650',
            'start_year' => 1648,
            'end_year' => 1650,
            'description' => 'Original',
            'confidence' => 'low',
        ]);

        $url = '/entities/'.$this->source->entity_id.'/relationships/'.$relationship->relationship_id;

        $this->actingAs($this->user)
            ->putJson($url, [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'at_war_with',
                'temporal_start' => '1651',
                'temporal_end' => null,
                'description' => 'Updated',
                'confidence' => 'high',
            ])
            ->assertOk()
            ->assertJsonPath('relationship.relationship_type', 'at_war_with')
            ->assertJsonPath('relationship.temporal_start', '1651')
            ->assertJsonPath('relationship.temporal_end', null)
            ->assertJsonPath('relationship.start_year', 1651)
            ->assertJsonPath('relationship.end_year', null)
            ->assertJsonPath('relationship.description', 'Updated')
            ->assertJsonPath('relationship.confidence', 'high');

        $this->assertDatabaseHas('relationships', [
            'relationship_id' => $relationship->relationship_id,
            'relationship_type' => 'at_war_with',
            'temporal_start' => '1651',
            'description' => 'Updated',
            'confidence' => 'high',
        ]);
    }

    public function test_update_syncs_and_removes_derived_presence_period_for_type_change(): void
    {
        $this->giveEntityPointGeom($this->source, 12.48, 41.89);
        $this->giveEntityPointGeom($this->target, 23.72, 37.98);

        $response = $this->actingAs($this->user)
            ->postJson(route('entities.relationships.store', $this->source), [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'fought_at',
                'temporal_start' => '1648',
                'temporal_end' => '1648',
                'description' => 'Battle participation',
            ])
            ->assertCreated();

        $relationshipId = (string) $response->json('relationship.relationship_id');
        $url = '/entities/'.$this->source->entity_id.'/relationships/'.$relationshipId;

        $this->assertDatabaseHas('geometry_periods', [
            'relationship_id' => $relationshipId,
            'period_type' => 'presence',
            'provenance_mode' => 'derived',
        ]);

        $this->actingAs($this->user)
            ->putJson($url, [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'allied_with',
                'temporal_start' => '1648',
                'temporal_end' => '1650',
                'description' => 'Now an alliance',
                'confidence' => 'medium',
            ])
            ->assertOk();

        $this->assertDatabaseMissing('geometry_periods', [
            'relationship_id' => $relationshipId,
            'period_type' => 'presence',
            'provenance_mode' => 'derived',
        ]);
    }

    public function test_update_404s_when_entity_is_not_source(): void
    {
        $relationship = $this->createRelationship([
            'source_entity_id' => $this->target->entity_id,
            'target_entity_id' => $this->source->entity_id,
        ]);
        $url = '/entities/'.$this->source->entity_id.'/relationships/'.$relationship->relationship_id;

        $this->actingAs($this->user)
            ->putJson($url, [
                'target_entity_id' => $this->target->entity_id,
                'relationship_type' => 'allied_with',
            ])
            ->assertNotFound();
    }

    public function test_update_requires_authentication(): void
    {
        $relationship = $this->createRelationship();
        $url = '/entities/'.$this->source->entity_id.'/relationships/'.$relationship->relationship_id;

        $this->putJson($url, [
            'target_entity_id' => $this->target->entity_id,
            'relationship_type' => 'allied_with',
        ])->assertUnauthorized();
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

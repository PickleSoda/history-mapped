<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Actions\Relationship\CreateRelationshipAction;
use App\Jobs\ResolveRelationshipsJob;
use App\Models\Entity;
use App\Models\EntityLocation;
use App\Models\EntityRelationship;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * Feature tests for ResolveRelationshipsJob.
 *
 * Covers:
 * - Happy path: hint resolves to a relationship record
 * - Target entity not in DB: hint marked target_not_found, no relationship created
 * - Duplicate hint: existing relationship skipped, marked already_exists
 * - Symmetric dedup: reverse-direction relationship prevents duplicate
 * - Non-symmetric type does not dedup in reverse direction
 * - Self-reference: source == target skipped, marked self_reference
 * - Unknown relationship type: hint marked unknown_type, no relationship created
 * - Null wikidata_property: relationship created without source_citations
 * - Multiple hints in one batch: all resolved correctly
 * - Batch isolation: hints from other batches are not touched
 * - Already-resolved hints are not reprocessed
 */
class ResolveRelationshipsJobTest extends TestCase
{
    use RefreshDatabase;

    private string $batchId;

    protected function setUp(): void
    {
        parent::setUp();
        $this->batchId = 'test-batch-'.uniqid();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /**
     * Insert a row into pipeline_relationship_hints and return its auto-increment id.
     *
     * @param  array<string, mixed>  $overrides
     */
    private function seedHint(Entity $source, string $targetWikidataId, string $type, array $overrides = []): int
    {
        return DB::table('pipeline_relationship_hints')->insertGetId(array_merge([
            'source_entity_id' => $source->entity_id,
            'relationship_type' => $type,
            'target_wikidata_id' => $targetWikidataId,
            'target_label' => 'Some Label',
            'temporal_start' => null,
            'temporal_end' => null,
            'confidence' => 'medium',
            'wikidata_property' => 'P36',
            'batch_id' => $this->batchId,
            'resolved' => false,
        ], $overrides));
    }

    /**
     * Insert a pre-existing relationship row directly, bypassing the action.
     */
    private function insertRelationship(string $sourceId, string $targetId, string $type): void
    {
        DB::table('relationships')->insert([
            'relationship_id' => Str::uuid()->toString(),
            'source_entity_id' => $sourceId,
            'target_entity_id' => $targetId,
            'relationship_type' => $type,
            'created_by' => 'test',
            'created_at' => now(),
        ]);
    }

    private function runJob(): void
    {
        (new ResolveRelationshipsJob($this->batchId))->handle(
            app(CreateRelationshipAction::class)
        );
    }

    // ── Happy path ────────────────────────────────────────────────────────────

    public function test_creates_relationship_when_target_found(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q1']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q2']);

        $this->seedHint($source, 'Q2', 'allied_with', ['wikidata_property' => 'P710']);

        $this->runJob();

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'allied_with',
        ]);

        $this->assertDatabaseHas('pipeline_relationship_hints', [
            'source_entity_id' => $source->entity_id,
            'target_wikidata_id' => 'Q2',
            'resolved' => true,
            'resolution_note' => 'created',
        ]);
    }

    public function test_stores_wikidata_property_in_source_citations(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q10']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q11']);

        $this->seedHint($source, 'Q11', 'part_of', ['wikidata_property' => 'P361']);

        $this->runJob();

        $relationship = EntityRelationship::where('source_entity_id', $source->entity_id)
            ->where('target_entity_id', $target->entity_id)
            ->firstOrFail();

        $citations = $relationship->source_citations;
        $this->assertIsArray($citations);
        $this->assertStringContainsString('P361', $citations[0]['title']);
    }

    public function test_null_wikidata_property_creates_relationship_without_citations(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q20']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q21']);

        $this->seedHint($source, 'Q21', 'caused', ['wikidata_property' => null]);

        $this->runJob();

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'caused',
        ]);

        $relationship = EntityRelationship::where('source_entity_id', $source->entity_id)->firstOrFail();
        $this->assertNull($relationship->source_citations);
    }

    public function test_temporal_hints_create_derived_presence_geometry_period_for_auto_types(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q210']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q211']);

        EntityLocation::query()->create([
            'entity_id' => $source->entity_id,
            'is_primary' => true,
            'location_name' => 'Rome',
            'geom' => [
                'type' => 'Point',
                'coordinates' => [12.5, 41.9],
            ],
        ]);

        $this->seedHint($source, 'Q211', 'fought_at', [
            'temporal_start' => '-0052',
            'temporal_end' => '-0052',
        ]);

        $this->runJob();

        $relationship = EntityRelationship::where('source_entity_id', $source->entity_id)
            ->where('target_entity_id', $target->entity_id)
            ->where('relationship_type', 'fought_at')
            ->firstOrFail();

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $source->entity_id,
            'relationship_id' => $relationship->relationship_id,
            'period_type' => 'presence',
            'start_year' => -52,
            'end_year' => -52,
            'provenance_mode' => 'derived',
        ]);
    }

    // ── Target not found ──────────────────────────────────────────────────────

    public function test_marks_hint_target_not_found_when_wikidata_id_absent(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q3']);

        $id = $this->seedHint($source, 'Q9999', 'part_of');

        $this->runJob();

        $this->assertDatabaseCount('relationships', 0);

        $this->assertDatabaseHas('pipeline_relationship_hints', [
            'id' => $id,
            'resolved' => true,
            'resolution_note' => 'target_not_found',
        ]);
    }

    // ── Deduplication ─────────────────────────────────────────────────────────

    public function test_skips_duplicate_relationship(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q4']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q5']);

        $this->insertRelationship($source->entity_id, $target->entity_id, 'part_of');

        $id = $this->seedHint($source, 'Q5', 'part_of');

        $this->runJob();

        // Still only the pre-existing relationship — no new one
        $this->assertDatabaseCount('relationships', 1);

        $this->assertDatabaseHas('pipeline_relationship_hints', [
            'id' => $id,
            'resolved' => true,
            'resolution_note' => 'already_exists',
        ]);
    }

    public function test_symmetric_type_dedup_checks_reverse_direction(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q6']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q7']);

        // Pre-existing relationship stored in the reverse direction
        $this->insertRelationship($target->entity_id, $source->entity_id, 'married_to');

        $id = $this->seedHint($source, 'Q7', 'married_to');

        $this->runJob();

        // Symmetric dedup: reverse already exists, no new row
        $this->assertDatabaseCount('relationships', 1);

        $this->assertDatabaseHas('pipeline_relationship_hints', [
            'id' => $id,
            'resolved' => true,
            'resolution_note' => 'already_exists',
        ]);
    }

    public function test_non_symmetric_type_does_not_dedup_reverse_direction(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q30']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q31']);

        // Pre-existing relationship in reverse direction (non-symmetric type)
        $this->insertRelationship($target->entity_id, $source->entity_id, 'part_of');

        $this->seedHint($source, 'Q31', 'part_of');

        $this->runJob();

        // Non-symmetric: forward direction is new and should be created
        $this->assertDatabaseCount('relationships', 2);
    }

    // ── Self-reference ────────────────────────────────────────────────────────

    public function test_skips_self_reference_hint(): void
    {
        $entity = Entity::factory()->create(['wikidata_id' => 'Q8']);

        $id = $this->seedHint($entity, 'Q8', 'part_of');

        $this->runJob();

        $this->assertDatabaseCount('relationships', 0);

        $this->assertDatabaseHas('pipeline_relationship_hints', [
            'id' => $id,
            'resolved' => true,
            'resolution_note' => 'self_reference',
        ]);
    }

    // ── Unknown relationship type ─────────────────────────────────────────────

    public function test_skips_hint_with_unknown_relationship_type(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q9']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q10']);

        $id = $this->seedHint($source, 'Q10', 'not_a_real_type');

        $this->runJob();

        $this->assertDatabaseCount('relationships', 0);

        $this->assertDatabaseHas('pipeline_relationship_hints', [
            'id' => $id,
            'resolved' => true,
            'resolution_note' => 'unknown_type',
        ]);
    }

    // ── Multiple hints ────────────────────────────────────────────────────────

    public function test_resolves_multiple_hints_in_one_batch(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q40']);
        $target1 = Entity::factory()->create(['wikidata_id' => 'Q41']);
        $target2 = Entity::factory()->create(['wikidata_id' => 'Q42']);

        $this->seedHint($source, 'Q41', 'allied_with');
        $this->seedHint($source, 'Q42', 'at_war_with');

        $this->runJob();

        $this->assertDatabaseCount('relationships', 2);

        $this->assertDatabaseHas('pipeline_relationship_hints', [
            'target_wikidata_id' => 'Q41',
            'resolved' => true,
            'resolution_note' => 'created',
        ]);
        $this->assertDatabaseHas('pipeline_relationship_hints', [
            'target_wikidata_id' => 'Q42',
            'resolved' => true,
            'resolution_note' => 'created',
        ]);
    }

    // ── Batch isolation ───────────────────────────────────────────────────────

    public function test_only_resolves_hints_for_own_batch(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q50']);
        Entity::factory()->create(['wikidata_id' => 'Q51']);

        // Hint belonging to a different batch
        $this->seedHint($source, 'Q51', 'part_of', ['batch_id' => 'other-batch']);

        $this->runJob();

        // No hints for $this->batchId — nothing created
        $this->assertDatabaseCount('relationships', 0);
    }

    public function test_does_not_re_resolve_already_resolved_hints(): void
    {
        $source = Entity::factory()->create(['wikidata_id' => 'Q60']);
        Entity::factory()->create(['wikidata_id' => 'Q61']);

        $this->seedHint($source, 'Q61', 'part_of', [
            'resolved' => true,
            'resolution_note' => 'created',
        ]);

        $this->runJob();

        // Already resolved — skipped, still 0 new relationships
        $this->assertDatabaseCount('relationships', 0);
    }

    public function test_fallback_resolves_embedded_hints_for_non_pipeline_entities(): void
    {
        Schema::dropIfExists('pipeline_relationship_hints');

        $source = Entity::factory()->create([
            'wikidata_id' => 'Q70',
            'created_by' => 'seeder',
            'attributes' => [
                '_relationship_hints' => [[
                    'relationship_type' => 'part_of',
                    'target_wikidata_id' => 'Q71',
                    'confidence' => 'medium',
                ]],
                '_relationship_hints_batch' => $this->batchId,
            ],
        ]);
        $target = Entity::factory()->create(['wikidata_id' => 'Q71']);

        $this->runJob();

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'part_of',
        ]);

        $source->refresh();
        $this->assertArrayNotHasKey('_relationship_hints', $source->attributes ?? []);
        $this->assertArrayNotHasKey('_relationship_hints_batch', $source->attributes ?? []);
    }
}

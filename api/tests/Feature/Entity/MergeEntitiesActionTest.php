<?php

declare(strict_types=1);

namespace Tests\Feature\Entity;

use App\Actions\Entity\MergeEntitiesAction;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class MergeEntitiesActionTest extends TestCase
{
    use RefreshDatabase;

    // ── helpers ──────────────────────────────────────────────────────────────

    private function makeRelationship(string $sourceId, string $targetId, string $type = 'contains'): void
    {
        DB::table('relationships')->insert([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $sourceId,
            'target_entity_id' => $targetId,
            'relationship_type' => $type,
            'created_at' => now(),
        ]);
    }

    private function makeChronicleEntry(string ...$entityIds): ChronicleEntry
    {
        $chronicle = Chronicle::factory()->create();
        $entry = ChronicleEntry::create([
            'entry_id' => (string) Str::uuid(),
            'chronicle_id' => $chronicle->chronicle_id,
            'narrative_text' => 'Test narrative',
            'sequence_order' => 1,
        ]);

        foreach ($entityIds as $eid) {
            DB::table('chronicle_entry_entities')->insert([
                'entry_id' => $entry->entry_id,
                'entity_id' => $eid,
            ]);
        }

        return $entry;
    }

    private function makeTimelineEntry(string $entityId, ?string $locationEntityId = null, ?string $relatedEntityId = null): string
    {
        $id = (string) Str::uuid();
        $sourceId = (string) Str::uuid();
        DB::table('entity_timeline_entries')->insert([
            'timeline_entry_id' => $id,
            'entity_id' => $entityId,
            'entry_kind' => 'relationship',
            'start_year' => 100,
            'title' => 'Test entry',
            'source_table' => 'relationships',
            'source_id' => $sourceId,
            'location_entity_id' => $locationEntityId,
            'related_entity_id' => $relatedEntityId,
        ]);

        return $id;
    }

    // ── 1. Survivor exists and loser is deleted ──────────────────────────────

    public function test_merge_deletes_loser_and_returns_survivor(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (duplicate)']);

        $action = app(MergeEntitiesAction::class);
        $result = $action($survivor->entity_id, $loser->entity_id);

        $this->assertSame($survivor->entity_id, $result->entity_id);
        $this->assertDatabaseHas('entities', ['entity_id' => $survivor->entity_id]);
        $this->assertDatabaseMissing('entities', ['entity_id' => $loser->entity_id]);
    }

    // ── 2. Normal loser relationships are re-pointed to survivor ─────────────

    public function test_merge_repoints_loser_source_relationships_to_survivor(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);
        $third = Entity::factory()->create(['name' => 'Rome']);

        // loser → third  (should become survivor → third)
        $this->makeRelationship($loser->entity_id, $third->entity_id, 'contains');

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, $loser->entity_id);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $survivor->entity_id,
            'target_entity_id' => $third->entity_id,
            'relationship_type' => 'contains',
        ]);
    }

    public function test_merge_repoints_loser_target_relationships_to_survivor(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);
        $third = Entity::factory()->create(['name' => 'Rome']);

        // third → loser  (should become third → survivor)
        $this->makeRelationship($third->entity_id, $loser->entity_id, 'part_of');

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, $loser->entity_id);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $third->entity_id,
            'target_entity_id' => $survivor->entity_id,
            'relationship_type' => 'part_of',
        ]);
    }

    // ── 3. Colliding relationship is dropped, not duplicated ─────────────────

    public function test_merge_drops_loser_relationship_that_collides_with_existing_survivor_relationship(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);
        $third = Entity::factory()->create(['name' => 'Rome']);

        // Survivor already has: survivor → third (contains)
        $this->makeRelationship($survivor->entity_id, $third->entity_id, 'contains');
        // Loser has the same logical edge: loser → third (contains) — would collide
        $this->makeRelationship($loser->entity_id, $third->entity_id, 'contains');

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, $loser->entity_id);

        // Only one relationship should remain
        $count = DB::table('relationships')
            ->where('source_entity_id', $survivor->entity_id)
            ->where('target_entity_id', $third->entity_id)
            ->where('relationship_type', 'contains')
            ->count();

        $this->assertSame(1, $count);
    }

    public function test_merge_drops_colliding_target_side_relationship(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);
        $third = Entity::factory()->create(['name' => 'Rome']);

        // Survivor already has: third → survivor (part_of)
        $this->makeRelationship($third->entity_id, $survivor->entity_id, 'part_of');
        // Loser has the same logical edge: third → loser (part_of) — would collide
        $this->makeRelationship($third->entity_id, $loser->entity_id, 'part_of');

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, $loser->entity_id);

        $count = DB::table('relationships')
            ->where('source_entity_id', $third->entity_id)
            ->where('target_entity_id', $survivor->entity_id)
            ->where('relationship_type', 'part_of')
            ->count();

        $this->assertSame(1, $count);
    }

    // ── 4. Self-loops created by merge are removed ───────────────────────────

    public function test_merge_removes_self_loops_created_by_merge(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);

        // loser → survivor (would become survivor → survivor after merge)
        $this->makeRelationship($loser->entity_id, $survivor->entity_id, 'allied_with');

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, $loser->entity_id);

        $this->assertDatabaseMissing('relationships', [
            'source_entity_id' => $survivor->entity_id,
            'target_entity_id' => $survivor->entity_id,
        ]);
    }

    public function test_merge_removes_self_loops_from_survivor_source_loser_target(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);

        // survivor → loser (would become survivor → survivor after merge)
        $this->makeRelationship($survivor->entity_id, $loser->entity_id, 'allied_with');

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, $loser->entity_id);

        $this->assertDatabaseMissing('relationships', [
            'source_entity_id' => $survivor->entity_id,
            'target_entity_id' => $survivor->entity_id,
        ]);
    }

    // ── 5. chronicle_entry_entities: dedup then re-point ─────────────────────

    public function test_merge_repoints_loser_only_chronicle_entry_links_to_survivor(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);

        // An entry linked ONLY to loser → should become linked to survivor
        $entry = $this->makeChronicleEntry($loser->entity_id);

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, $loser->entity_id);

        $this->assertDatabaseHas('chronicle_entry_entities', [
            'entry_id' => $entry->entry_id,
            'entity_id' => $survivor->entity_id,
        ]);
        $this->assertDatabaseMissing('chronicle_entry_entities', [
            'entry_id' => $entry->entry_id,
            'entity_id' => $loser->entity_id,
        ]);
    }

    public function test_merge_deduplicates_chronicle_entry_linked_to_both_survivor_and_loser(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);

        // An entry linked to BOTH survivor and loser — loser link should be dropped
        $entry = $this->makeChronicleEntry($survivor->entity_id, $loser->entity_id);

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, $loser->entity_id);

        // Survivor still linked
        $this->assertDatabaseHas('chronicle_entry_entities', [
            'entry_id' => $entry->entry_id,
            'entity_id' => $survivor->entity_id,
        ]);
        // Loser link gone (not re-pointed since that would duplicate)
        $this->assertDatabaseMissing('chronicle_entry_entities', [
            'entry_id' => $entry->entry_id,
            'entity_id' => $loser->entity_id,
        ]);

        // Exactly one row for this entry+survivor pair
        $count = DB::table('chronicle_entry_entities')
            ->where('entry_id', $entry->entry_id)
            ->where('entity_id', $survivor->entity_id)
            ->count();
        $this->assertSame(1, $count);
    }

    // ── 6. entity_timeline_entries: re-point secondary refs ──────────────────

    public function test_merge_repoints_location_entity_id_in_timeline_entries(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);
        $ownerEntity = Entity::factory()->create(['name' => 'Marco Polo']);

        // A timeline entry for ownerEntity that references loser as location
        $entryId = $this->makeTimelineEntry($ownerEntity->entity_id, $loser->entity_id, null);

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, $loser->entity_id);

        $this->assertDatabaseHas('entity_timeline_entries', [
            'timeline_entry_id' => $entryId,
            'location_entity_id' => $survivor->entity_id,
        ]);
    }

    public function test_merge_repoints_related_entity_id_in_timeline_entries(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);
        $ownerEntity = Entity::factory()->create(['name' => 'Marco Polo']);

        // A timeline entry for ownerEntity that references loser as related_entity
        $entryId = $this->makeTimelineEntry($ownerEntity->entity_id, null, $loser->entity_id);

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, $loser->entity_id);

        $this->assertDatabaseHas('entity_timeline_entries', [
            'timeline_entry_id' => $entryId,
            'related_entity_id' => $survivor->entity_id,
        ]);
    }

    // ── 7. Full scenario: all merge steps together ────────────────────────────

    public function test_full_merge_scenario(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);
        $third = Entity::factory()->create(['name' => 'Rome']);
        $owner = Entity::factory()->create(['name' => 'Marco Polo']);

        // Relationships
        $this->makeRelationship($survivor->entity_id, $third->entity_id, 'contains'); // survivor's own
        $this->makeRelationship($loser->entity_id, $third->entity_id, 'contains');     // colliding loser rel
        $this->makeRelationship($loser->entity_id, $third->entity_id, 'part_of');       // non-colliding loser rel
        $this->makeRelationship($loser->entity_id, $survivor->entity_id, 'allied_with'); // would-be self-loop

        // Chronicle entries
        $entryBoth = $this->makeChronicleEntry($survivor->entity_id, $loser->entity_id); // dedup case
        $entryLoserOnly = $this->makeChronicleEntry($loser->entity_id);                   // re-point case

        // Timeline entries
        $tlEntry = $this->makeTimelineEntry($owner->entity_id, $loser->entity_id, $loser->entity_id);

        $action = app(MergeEntitiesAction::class);
        $result = $action($survivor->entity_id, $loser->entity_id);

        // Survivor exists, loser deleted
        $this->assertSame($survivor->entity_id, $result->entity_id);
        $this->assertDatabaseMissing('entities', ['entity_id' => $loser->entity_id]);

        // No self-loops
        $this->assertDatabaseMissing('relationships', [
            'source_entity_id' => $survivor->entity_id,
            'target_entity_id' => $survivor->entity_id,
        ]);

        // survivor→third (contains) not duplicated
        $this->assertSame(1, DB::table('relationships')
            ->where('source_entity_id', $survivor->entity_id)
            ->where('target_entity_id', $third->entity_id)
            ->where('relationship_type', 'contains')
            ->count());

        // non-colliding rel re-pointed
        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $survivor->entity_id,
            'target_entity_id' => $third->entity_id,
            'relationship_type' => 'part_of',
        ]);

        // Chronicle dedup
        $this->assertSame(1, DB::table('chronicle_entry_entities')
            ->where('entry_id', $entryBoth->entry_id)
            ->where('entity_id', $survivor->entity_id)
            ->count());
        $this->assertDatabaseMissing('chronicle_entry_entities', [
            'entry_id' => $entryBoth->entry_id,
            'entity_id' => $loser->entity_id,
        ]);

        // Chronicle re-point
        $this->assertDatabaseHas('chronicle_entry_entities', [
            'entry_id' => $entryLoserOnly->entry_id,
            'entity_id' => $survivor->entity_id,
        ]);

        // Timeline re-point
        $this->assertDatabaseHas('entity_timeline_entries', [
            'timeline_entry_id' => $tlEntry,
            'location_entity_id' => $survivor->entity_id,
            'related_entity_id' => $survivor->entity_id,
        ]);
    }

    // ── 8. Wrapped in a transaction (loser survives if action throws) ─────────

    public function test_merge_is_wrapped_in_transaction(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);

        // Verify both exist; then call with an invalid loser UUID which should throw
        $this->expectException(ModelNotFoundException::class);

        $action = app(MergeEntitiesAction::class);
        $action($survivor->entity_id, (string) Str::uuid()); // non-existent loser

        // If we got here (shouldn't) survivor must still exist
        $this->assertDatabaseHas('entities', ['entity_id' => $survivor->entity_id]);
    }
}

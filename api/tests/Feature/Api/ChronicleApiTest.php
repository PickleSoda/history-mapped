<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class ChronicleApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_index_returns_paginated_chronicles_with_entry_count(): void
    {
        // Create 3 chronicles with entries
        $chronicle1 = Chronicle::create([
            'chronicle_id' => Str::uuid()->toString(),
            'title' => 'Chronicle One',
            'slug' => 'chronicle-one',
            'source_type' => 'video_transcript',
            'status' => 'draft',
            'metadata' => [],
        ]);

        $chronicle2 = Chronicle::create([
            'chronicle_id' => Str::uuid()->toString(),
            'title' => 'Chronicle Two',
            'slug' => 'chronicle-two',
            'source_type' => 'article',
            'status' => 'published',
            'metadata' => [],
        ]);

        $chronicle3 = Chronicle::create([
            'chronicle_id' => Str::uuid()->toString(),
            'title' => 'Chronicle Three',
            'slug' => 'chronicle-three',
            'source_type' => 'video_transcript',
            'status' => 'draft',
            'metadata' => [],
        ]);

        // Add entries to chronicle1
        ChronicleEntry::create([
            'entry_id' => Str::uuid()->toString(),
            'chronicle_id' => $chronicle1->chronicle_id,
            'sequence_order' => 0,
            'narrative_text' => 'First entry',
        ]);

        ChronicleEntry::create([
            'entry_id' => Str::uuid()->toString(),
            'chronicle_id' => $chronicle1->chronicle_id,
            'sequence_order' => 1,
            'narrative_text' => 'Second entry',
        ]);

        // Add 1 entry to chronicle2
        ChronicleEntry::create([
            'entry_id' => Str::uuid()->toString(),
            'chronicle_id' => $chronicle2->chronicle_id,
            'sequence_order' => 0,
            'narrative_text' => 'Only entry',
        ]);

        $this->getJson(route('api.v1.chronicles.index'))
            ->assertOk()
            ->assertJsonCount(3, 'data')
            ->assertJsonPath('data.0.entry_count', 2)
            ->assertJsonPath('data.1.entry_count', 1)
            ->assertJsonPath('data.2.entry_count', 0)
            ->assertJsonStructure([
                'data' => [
                    '*' => [
                        'chronicle_id',
                        'title',
                        'slug',
                        'source_type',
                        'status',
                        'entry_count',
                    ],
                ],
                'meta',
            ]);
    }

    public function test_index_returns_empty_for_no_chronicles(): void
    {
        $this->getJson(route('api.v1.chronicles.index'))
            ->assertOk()
            ->assertJsonCount(0, 'data');
    }

    public function test_index_sorts_by_created_at_desc(): void
    {
        $first = Chronicle::create([
            'chronicle_id' => Str::uuid()->toString(),
            'title' => 'First Chronicle',
            'slug' => 'first-chronicle',
            'source_type' => 'video_transcript',
            'status' => 'draft',
            'metadata' => [],
            'created_at' => now()->subDays(2),
        ]);

        $second = Chronicle::create([
            'chronicle_id' => Str::uuid()->toString(),
            'title' => 'Second Chronicle',
            'slug' => 'second-chronicle',
            'source_type' => 'video_transcript',
            'status' => 'draft',
            'metadata' => [],
            'created_at' => now()->subDays(1),
        ]);

        $third = Chronicle::create([
            'chronicle_id' => Str::uuid()->toString(),
            'title' => 'Third Chronicle',
            'slug' => 'third-chronicle',
            'source_type' => 'video_transcript',
            'status' => 'draft',
            'metadata' => [],
            'created_at' => now(),
        ]);

        $response = $this->getJson(route('api.v1.chronicles.index'));

        $response->assertOk();
        $response->assertJsonPath('data.0.chronicle_id', $third->chronicle_id);
        $response->assertJsonPath('data.1.chronicle_id', $second->chronicle_id);
        $response->assertJsonPath('data.2.chronicle_id', $first->chronicle_id);
    }

    public function test_show_returns_chronicle_with_entries(): void
    {
        $chronicle = Chronicle::create([
            'chronicle_id' => Str::uuid()->toString(),
            'title' => 'Test Chronicle',
            'slug' => 'test-chronicle',
            'source_type' => 'video_transcript',
            'status' => 'published',
            'metadata' => ['event_count' => 1],
        ]);

        $entry1Id = Str::uuid()->toString();
        $entry2Id = Str::uuid()->toString();

        ChronicleEntry::create([
            'entry_id' => $entry1Id,
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => 0,
            'narrative_text' => 'First narrative',
        ]);

        ChronicleEntry::create([
            'entry_id' => $entry2Id,
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => 1,
            'narrative_text' => 'Second narrative',
        ]);

        $this->getJson(route('api.v1.chronicles.show', $chronicle->slug))
            ->assertOk()
            ->assertJsonPath('data.chronicle_id', $chronicle->chronicle_id)
            ->assertJsonPath('data.title', 'Test Chronicle')
            ->assertJsonPath('data.status', 'published')
            ->assertJsonCount(2, 'data.entries')
            ->assertJsonPath('data.entries.0.entry_id', $entry1Id)
            ->assertJsonPath('data.entries.0.sequence_order', 0)
            ->assertJsonPath('data.entries.0.narrative_text', 'First narrative')
            ->assertJsonPath('data.entries.1.entry_id', $entry2Id)
            ->assertJsonPath('data.entries.1.sequence_order', 1);
    }

    public function test_show_returns_404_for_invalid_slug(): void
    {
        $this->getJson(route('api.v1.chronicles.show', 'non-existent-slug'))
            ->assertNotFound();
    }

    public function test_show_includes_secondary_entities_when_loaded(): void
    {
        $chronicle = Chronicle::create([
            'chronicle_id' => Str::uuid()->toString(),
            'title' => 'Chronicle with Entities',
            'slug' => 'chronicle-with-entities',
            'source_type' => 'video_transcript',
            'status' => 'draft',
            'metadata' => [],
        ]);

        $entry = ChronicleEntry::create([
            'entry_id' => Str::uuid()->toString(),
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => 0,
            'narrative_text' => 'Entry with entities',
        ]);

        // Create test entities
        $entity1Id = Str::uuid()->toString();
        $entity2Id = Str::uuid()->toString();

        DB::table('entities')->insert([
            [
                'entity_id' => $entity1Id,
                'name' => 'Test Entity 1',
                'entity_type' => 'person',
                'entity_group' => 'POLITY',
                'verification_status' => 'pipeline_draft',
                'created_at' => now(),
                'updated_at' => now(),
            ],
            [
                'entity_id' => $entity2Id,
                'name' => 'Test Entity 2',
                'entity_type' => 'person',
                'entity_group' => 'POLITY',
                'verification_status' => 'pipeline_draft',
                'created_at' => now(),
                'updated_at' => now(),
            ],
        ]);

        // Attach secondary entities
        DB::table('chronicle_entry_entities')->insert([
            [
                'entry_id' => $entry->entry_id,
                'entity_id' => $entity1Id,
                'role' => 'participant',
                'sequence_in_entry' => 0,
            ],
            [
                'entry_id' => $entry->entry_id,
                'entity_id' => $entity2Id,
                'role' => 'mentioned',
                'sequence_in_entry' => 1,
            ],
        ]);

        $this->getJson(route('api.v1.chronicles.show', $chronicle->slug))
            ->assertOk()
            ->assertJsonCount(2, 'data.entries.0.secondary_entities')
            ->assertJsonPath('data.entries.0.secondary_entities.0.entity_id', $entity1Id)
            ->assertJsonPath('data.entries.0.secondary_entities.0.role', 'participant')
            ->assertJsonPath('data.entries.0.secondary_entities.1.entity_id', $entity2Id)
            ->assertJsonPath('data.entries.0.secondary_entities.1.role', 'mentioned');
    }

    public function test_show_returns_timestamp_from_primary_relationship(): void
    {
        $chronicle = Chronicle::create([
            'chronicle_id' => Str::uuid()->toString(),
            'title' => 'Chronicle with Relationship',
            'slug' => 'chronicle-with-relationship',
            'source_type' => 'video_transcript',
            'status' => 'draft',
            'metadata' => [],
        ]);

        $sourceEntityId = Str::uuid()->toString();
        $targetEntityId = Str::uuid()->toString();
        $relationshipId = Str::uuid()->toString();
        $entryId = Str::uuid()->toString();

        // Create entities for the relationship FK constraints
        DB::table('entities')->insert([
            [
                'entity_id' => $sourceEntityId,
                'name' => 'Source Entity',
                'entity_type' => 'person',
                'entity_group' => 'POLITY',
                'verification_status' => 'pipeline_draft',
                'created_at' => now(),
                'updated_at' => now(),
            ],
            [
                'entity_id' => $targetEntityId,
                'name' => 'Target Entity',
                'entity_type' => 'person',
                'entity_group' => 'POLITY',
                'verification_status' => 'pipeline_draft',
                'created_at' => now(),
                'updated_at' => now(),
            ],
        ]);

        // Create a relationship with temporal data
        DB::table('relationships')->insert([
            'relationship_id' => $relationshipId,
            'source_entity_id' => $sourceEntityId,
            'target_entity_id' => $targetEntityId,
            'relationship_type' => 'participated_in',
            'temporal_start' => '1121-08-12',
            'temporal_end' => '1121-08-12',
            'start_year' => 1121,
            'end_year' => 1121,
            'created_at' => now(),
        ]);

        ChronicleEntry::create([
            'entry_id' => $entryId,
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => 0,
            'primary_relationship_id' => $relationshipId,
            'narrative_text' => 'Entry with relationship',
        ]);

        $this->getJson(route('api.v1.chronicles.show', $chronicle->slug))
            ->assertOk()
            ->assertJsonPath('data.entries.0.timestamp', '1121-08-12');
    }
}

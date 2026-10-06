<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityRelationship;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class EntityRelationshipsSummaryEndsTest extends TestCase
{
    use RefreshDatabase;

    public function test_embedded_entity_summaries_carry_dates_and_location(): void
    {
        $a = Entity::factory()->withTemporalRange('-0490', '-0479')->atLocation('Athens')->create();
        $others = Entity::factory()->count(3)->withTemporalRange('0100', '0200')->atLocation('Rome')->create();
        foreach ($others as $o) {
            EntityRelationship::create([
                'relationship_id' => (string) Str::uuid(),
                'source_entity_id' => $a->entity_id,
                'target_entity_id' => $o->entity_id,
                'relationship_type' => 'allied_with',
            ]);
        }

        DB::enableQueryLog();
        $res = $this->getJson("/api/v1/entities/{$a->entity_id}/relationships")->assertOk();
        $queries = count(DB::getQueryLog());

        $rows = $res->json('data');
        $this->assertCount(3, $rows);
        foreach ($rows as $row) {
            $this->assertSame('-0490', $row['source_entity']['temporal_start']);
            $this->assertSame('-0479', $row['source_entity']['temporal_end']);
            $this->assertSame('Athens', $row['source_entity']['location_name']);
            $this->assertSame('0100', $row['target_entity']['temporal_start']);
            $this->assertSame('Rome', $row['target_entity']['location_name']);
        }

        // Entity lookup + relationships + one query per end: no N+1 per relationship.
        $this->assertLessThanOrEqual(5, $queries);
    }

    public function test_chronicle_show_primary_relationship_ends_are_loaded(): void
    {
        $a = Entity::factory()->withTemporalRange('-0490', '-0479')->create();
        $b = Entity::factory()->withTemporalRange('0100', '0200')->create();
        $rel = EntityRelationship::create([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $a->entity_id,
            'target_entity_id' => $b->entity_id,
            'relationship_type' => 'allied_with',
        ]);
        $chronicle = Chronicle::factory()->create(['slug' => 'c1']);
        ChronicleEntry::factory()->create([
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => 1,
            'primary_relationship_id' => $rel->relationship_id,
        ]);

        $entry = $this->getJson('/api/v1/chronicles/c1')->assertOk()->json('data.entries.0.primary_relationship');
        $this->assertSame('-0490', $entry['source_entity']['temporal_start']);
        $this->assertSame('0100', $entry['target_entity']['temporal_start']);
    }
}

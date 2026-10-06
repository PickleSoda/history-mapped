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

class ChronicleGraphApiTest extends TestCase
{
    use RefreshDatabase;

    private Chronicle $chronicle;

    protected function setUp(): void
    {
        parent::setUp();
        $this->chronicle = Chronicle::factory()->create(['slug' => 'test-chronicle']);
    }

    private function entity(string $name, int $impact = 50): Entity
    {
        return Entity::factory()->state(['name' => $name, 'impact_score' => $impact])->create();
    }

    private function rel(Entity $a, Entity $b, string $type = 'allied_with', string $confidence = 'high'): EntityRelationship
    {
        return EntityRelationship::create([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $a->entity_id,
            'target_entity_id' => $b->entity_id,
            'relationship_type' => $type,
            'confidence' => $confidence,
        ]);
    }

    /** @param list<Entity> $pivot */
    private function step(int $seq, ?EntityRelationship $primary = null, array $pivot = []): ChronicleEntry
    {
        $entry = ChronicleEntry::factory()->create([
            'chronicle_id' => $this->chronicle->chronicle_id,
            'sequence_order' => $seq,
            'primary_relationship_id' => $primary?->relationship_id,
            'start_year' => -400 + $seq,
        ]);
        foreach ($pivot as $i => $e) {
            DB::table('chronicle_entry_entities')->insert([
                'entry_id' => $entry->entry_id,
                'entity_id' => $e->entity_id,
                'role' => 'participant',
                'sequence_in_entry' => $i,
            ]);
        }

        return $entry;
    }

    private function graph(string $query = ''): array
    {
        return $this->getJson('/api/v1/chronicles/test-chronicle/graph'.($query ? "?$query" : ''))
            ->assertOk()->json('data');
    }

    public function test_unknown_slug_returns_404(): void
    {
        $this->getJson('/api/v1/chronicles/nope/graph')->assertNotFound();
    }

    public function test_empty_chronicle_returns_empty_graph(): void
    {
        $data = $this->graph();
        $this->assertSame($this->chronicle->chronicle_id, $data['chronicle_id']);
        $this->assertSame('test-chronicle', $data['slug']);
        $this->assertSame([], $data['nodes']);
        $this->assertSame([], $data['edges']);
        $this->assertSame([], $data['steps']);
    }

    public function test_entity_set_is_pivot_union_primary_relationship_ends(): void
    {
        $a = $this->entity('A');
        $b = $this->entity('B');
        $p = $this->entity('P');
        $this->step(1, $this->rel($a, $b), [$p]);
        $this->entity('Unrelated');

        $data = $this->graph('external=0');
        $this->assertEqualsCanonicalizing(['A', 'B', 'P'], collect($data['nodes'])->pluck('name')->all());
        $this->assertTrue(collect($data['nodes'])->every(fn ($n) => $n['in_chronicle'] && $n['depth'] === 0));
    }

    public function test_step_membership_and_scope_classification(): void
    {
        $a = $this->entity('A');
        $b = $this->entity('B');
        $c = $this->entity('C');
        $d = $this->entity('D');
        $x = $this->entity('X');            // outside
        $primary1 = $this->rel($a, $b);     // step 1 primary
        $primary2 = $this->rel($c, $d);     // step 2 primary
        $internalInStep1 = $this->rel($b, $a, 'at_war_with');   // both ends in step 1 -> step 1 relationship_ids
        $crossStep = $this->rel($b, $c, 'trades_with');         // ends in steps 1 and 2 -> internal, no step contains both
        $external = $this->rel($a, $x, 'allied_with');

        $s1 = $this->step(1, $primary1);
        $s2 = $this->step(2, $primary2, [$a]);   // pivot adds A to step 2 as well

        $data = $this->graph();
        $edges = collect($data['edges'])->keyBy('id');

        $this->assertSame('primary', $edges[$primary1->relationship_id]['scope']);
        $this->assertSame('primary', $edges[$primary2->relationship_id]['scope']);
        $this->assertSame('internal', $edges[$internalInStep1->relationship_id]['scope']);
        $this->assertSame('internal', $edges[$crossStep->relationship_id]['scope']);
        $this->assertSame('external', $edges[$external->relationship_id]['scope']);
        $this->assertSame([], $edges[$external->relationship_id]['steps']);

        $steps = collect($data['steps'])->keyBy('sequence_order');
        $this->assertSame($s1->entry_id, $steps[1]['entry_id']);
        $this->assertSame($primary1->relationship_id, $steps[1]['primary_relationship_id']);
        $this->assertEqualsCanonicalizing([$a->entity_id, $b->entity_id], $steps[1]['entity_ids']);
        $this->assertEqualsCanonicalizing([$primary1->relationship_id, $internalInStep1->relationship_id], $steps[1]['relationship_ids']);

        // Step 2: C, D from the primary plus A from the pivot. Internal edges among {A, C, D}: none besides primary.
        $this->assertEqualsCanonicalizing([$a->entity_id, $c->entity_id, $d->entity_id], $steps[2]['entity_ids']);
        $this->assertSame([$primary2->relationship_id], $steps[2]['relationship_ids']);

        $this->assertEqualsCanonicalizing([1], $edges[$internalInStep1->relationship_id]['steps']);
        $this->assertSame([], $edges[$crossStep->relationship_id]['steps']);

        $nodes = collect($data['nodes'])->keyBy('name');
        $this->assertSame([1, 2], $nodes['A']['steps']);
        $this->assertSame([1], $nodes['B']['steps']);
        $this->assertFalse($nodes['X']['in_chronicle']);
        $this->assertSame(1, $nodes['X']['depth']);
        $this->assertSame([], $nodes['X']['steps']);
    }

    public function test_step_includes_internal_edge_between_pivot_entities(): void
    {
        $a = $this->entity('A');
        $b = $this->entity('B');
        $edge = $this->rel($a, $b);
        $this->step(1, null, [$a, $b]);

        $data = $this->graph();
        $this->assertSame([$edge->relationship_id], $data['steps'][0]['relationship_ids']);
        $this->assertSame([1], $data['edges'][0]['steps']);
        $this->assertNull($data['steps'][0]['primary_relationship_id']);
    }

    public function test_external_can_be_disabled(): void
    {
        $a = $this->entity('A');
        $x = $this->entity('X');
        $this->rel($a, $x);
        $this->step(1, null, [$a]);

        $data = $this->graph('external=0');
        $this->assertCount(1, $data['nodes']);
        $this->assertSame([], $data['edges']);

        $data = $this->graph('external=1');
        $this->assertCount(2, $data['nodes']);
        $this->assertCount(1, $data['edges']);
    }

    public function test_external_edges_are_capped_per_chronicle_entity_by_confidence_then_impact(): void
    {
        $a = $this->entity('A');
        $b = $this->entity('B');
        $this->step(1, null, [$a, $b]);

        $this->rel($a, $this->entity('A-low', 99), confidence: 'low');
        $this->rel($a, $this->entity('A-hi-1', 10));
        $this->rel($this->entity('A-hi-2', 80), $a);          // incoming also counts
        foreach (range(1, 3) as $i) {
            $this->rel($b, $this->entity("B$i"));
        }

        $data = $this->graph('external_limit=2');
        $externalNames = collect($data['nodes'])->where('in_chronicle', false)->pluck('name')->all();

        // A keeps its 2 highest-confidence (the 'low' edge is dropped); B keeps 2 of 3.
        $this->assertNotContains('A-low', $externalNames);
        $this->assertContains('A-hi-1', $externalNames);
        $this->assertContains('A-hi-2', $externalNames);
        $this->assertCount(4, $externalNames);
        $this->assertCount(4, collect($data['edges'])->where('scope', 'external'));

        $this->assertCount(0, collect($this->graph('external_limit=0')['edges']));
    }

    public function test_external_edge_to_outside_is_not_duplicated_and_never_connects_two_outsiders(): void
    {
        $a = $this->entity('A');
        $x = $this->entity('X');
        $y = $this->entity('Y');
        $this->rel($a, $x);
        $this->rel($x, $y);
        $this->step(1, null, [$a]);

        $data = $this->graph();
        $this->assertCount(1, $data['edges']);
        $this->assertEqualsCanonicalizing(['A', 'X'], collect($data['nodes'])->pluck('name')->all());
    }

    public function test_relationship_types_filter_applies_to_internal_and_external_but_not_primary(): void
    {
        $a = $this->entity('A');
        $b = $this->entity('B');
        $c = $this->entity('C');
        $x = $this->entity('X');
        $primary = $this->rel($a, $b, 'allied_with');
        $this->rel($a, $c, 'allied_with');
        $keep = $this->rel($b, $c, 'at_war_with');
        $this->rel($a, $x, 'allied_with');
        $keepExternal = $this->rel($c, $x, 'at_war_with');
        $this->step(1, $primary, [$c]);

        $data = $this->graph('relationship_types=at_war_with');
        $ids = collect($data['edges'])->pluck('id')->all();
        $this->assertEqualsCanonicalizing(
            [$primary->relationship_id, $keep->relationship_id, $keepExternal->relationship_id],
            $ids,
        );
        $this->assertSame('primary', collect($data['edges'])->firstWhere('id', $primary->relationship_id)['scope']);
    }

    public function test_invalid_parameters_are_rejected(): void
    {
        $this->getJson('/api/v1/chronicles/test-chronicle/graph?relationship_types=bogus')->assertStatus(422);
        $this->getJson('/api/v1/chronicles/test-chronicle/graph?external_limit=-1')->assertStatus(422);
    }

    public function test_steps_are_ordered_by_sequence(): void
    {
        $a = $this->entity('A');
        $this->step(3, null, [$a]);
        $this->step(1, null, [$a]);
        $this->step(2, null, [$a]);

        $this->assertSame([1, 2, 3], collect($this->graph()['steps'])->pluck('sequence_order')->all());
        $this->assertSame([1, 2, 3], collect($this->graph()['nodes'])->first()['steps']);
    }
}

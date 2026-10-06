<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\EntityRelationship;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

class EntityGraphApiTest extends TestCase
{
    use RefreshDatabase;

    private function entity(string $name, int $impact = 50, ?EntityType $type = null): Entity
    {
        $factory = Entity::factory()->state(['name' => $name, 'impact_score' => $impact]);
        if ($type) {
            $factory = $factory->ofType($type);
        }

        return $factory->create();
    }

    private function rel(Entity $a, Entity $b, string $type = 'allied_with', array $extra = []): EntityRelationship
    {
        return EntityRelationship::create(array_merge([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $a->entity_id,
            'target_entity_id' => $b->entity_id,
            'relationship_type' => $type,
            'confidence' => 'high',
        ], $extra));
    }

    private function graph(Entity $e, string $query = ''): TestResponse
    {
        return $this->getJson("/api/v1/entities/{$e->entity_id}/graph".($query ? "?$query" : ''));
    }

    public function test_depth_one_returns_root_and_direct_neighbours_only(): void
    {
        $root = $this->entity('Root');
        $a = $this->entity('A');
        $b = $this->entity('B');
        $c = $this->entity('C');
        $this->rel($root, $a);
        $this->rel($b, $root);
        $this->rel($a, $c);

        $res = $this->graph($root)->assertOk();
        $data = $res->json('data');

        $this->assertSame($root->entity_id, $data['root']);
        $this->assertFalse($data['truncated']);
        $this->assertCount(3, $data['nodes']);
        $this->assertCount(2, $data['edges']);
        $depths = collect($data['nodes'])->pluck('depth', 'name');
        $this->assertSame(0, $depths['Root']);
        $this->assertSame(1, $depths['A']);
        $this->assertSame(1, $depths['B']);
        $this->assertArrayNotHasKey('C', $depths->all());
        $edge = collect($data['edges'])->firstWhere('source', $root->entity_id);
        $this->assertSame(['id', 'source', 'target', 'relationship_type', 'start_year', 'end_year', 'description', 'confidence'], array_keys($edge));
    }

    public function test_depth_two_follows_edges_out_of_depth_one_nodes(): void
    {
        $root = $this->entity('Root');
        $a = $this->entity('A');
        $c = $this->entity('C');
        $d = $this->entity('D');
        $this->rel($root, $a);
        $this->rel($a, $c);
        $this->rel($d, $c);   // 3 hops from root: excluded

        $data = $this->graph($root, 'depth=2')->assertOk()->json('data');

        $depths = collect($data['nodes'])->pluck('depth', 'name');
        $this->assertSame(2, $depths['C']);
        $this->assertArrayNotHasKey('D', $depths->all());
        $this->assertCount(2, $data['edges']);
    }

    public function test_depth_two_includes_edges_between_depth_one_nodes(): void
    {
        $root = $this->entity('Root');
        $a = $this->entity('A');
        $b = $this->entity('B');
        $this->rel($root, $a);
        $this->rel($root, $b);
        $this->rel($a, $b);

        $data = $this->graph($root, 'depth=2')->json('data');
        $this->assertCount(3, $data['edges']);
        $this->assertCount(3, $data['nodes']);
    }

    public function test_node_carries_years_group_and_impact(): void
    {
        $root = Entity::factory()->ofType(EntityType::PoliticalEntity)->withTemporalRange('-0490', '-0479')->create(['impact_score' => 77]);
        $a = $this->entity('A');
        $this->rel($root, $a);

        $node = collect($this->graph($root)->json('data.nodes'))->firstWhere('id', $root->entity_id);
        $this->assertSame(-490, $node['start_year']);
        $this->assertSame(-479, $node['end_year']);
        $this->assertSame(77, $node['impact_score']);
        $this->assertSame(EntityType::PoliticalEntity->group()->value, $node['entity_group']);
        $this->assertSame('political_entity', $node['entity_type']);
    }

    public function test_relationship_types_filter(): void
    {
        $root = $this->entity('Root');
        $a = $this->entity('A');
        $b = $this->entity('B');
        $this->rel($root, $a, 'allied_with');
        $this->rel($root, $b, 'at_war_with');

        $data = $this->graph($root, 'relationship_types=at_war_with')->assertOk()->json('data');
        $this->assertCount(1, $data['edges']);
        $this->assertSame('at_war_with', $data['edges'][0]['relationship_type']);
        $this->assertCount(2, $data['nodes']);

        $data = $this->graph($root, 'relationship_types=at_war_with,allied_with')->json('data');
        $this->assertCount(2, $data['edges']);
    }

    public function test_groups_filter_removes_non_root_nodes_and_their_edges(): void
    {
        $root = $this->entity('Root', type: EntityType::PoliticalEntity);
        $polity = $this->entity('Polity', type: EntityType::PoliticalEntity);
        $event = $this->entity('Event', type: EntityType::EventBattle);
        $this->rel($root, $polity);
        $this->rel($root, $event);

        $polityGroup = EntityGroup::Polity->value;
        $data = $this->graph($root, "groups=$polityGroup")->assertOk()->json('data');

        $names = collect($data['nodes'])->pluck('name')->all();
        $this->assertEqualsCanonicalizing(['Root', 'Polity'], $names);
        $this->assertCount(1, $data['edges']);
    }

    public function test_groups_filter_never_removes_the_root(): void
    {
        $root = $this->entity('Root', type: EntityType::EventBattle);
        $other = $this->entity('Other', type: EntityType::PoliticalEntity);
        $this->rel($root, $other);

        $data = $this->graph($root, 'groups='.EntityGroup::Polity->value)->json('data');
        $this->assertCount(2, $data['nodes']);
    }

    public function test_year_filter_keeps_overlapping_and_null_year_edges(): void
    {
        $root = $this->entity('Root');
        $early = $this->entity('Early');
        $mid = $this->entity('Mid');
        $late = $this->entity('Late');
        $open = $this->entity('Open');
        $this->rel($root, $early, extra: ['temporal_start' => '-500', 'temporal_end' => '-400']);
        $this->rel($root, $mid, extra: ['temporal_start' => '-100', 'temporal_end' => '100']);
        $this->rel($root, $late, extra: ['temporal_start' => '500', 'temporal_end' => '600']);
        $this->rel($root, $open);

        $data = $this->graph($root, 'from=-50&to=50')->assertOk()->json('data');
        $names = collect($data['nodes'])->pluck('name')->all();
        $this->assertEqualsCanonicalizing(['Root', 'Mid', 'Open'], $names);

        $data = $this->graph($root, 'from=550')->json('data');
        $this->assertEqualsCanonicalizing(['Root', 'Late', 'Open'], collect($data['nodes'])->pluck('name')->all());

        $data = $this->graph($root, 'to=-450')->json('data');
        $this->assertEqualsCanonicalizing(['Root', 'Early', 'Open'], collect($data['nodes'])->pluck('name')->all());
    }

    public function test_limit_truncates_ordered_by_confidence_then_other_end_impact(): void
    {
        $root = $this->entity('Root');
        $hiConfLowImpact = $this->entity('HiConfLow', 10);
        $hiConfHighImpact = $this->entity('HiConfHigh', 90);
        $lowConf = $this->entity('LowConf', 99);
        $this->rel($root, $lowConf, extra: ['confidence' => 'low']);
        $this->rel($root, $hiConfLowImpact, extra: ['confidence' => 'high']);
        $this->rel($root, $hiConfHighImpact, extra: ['confidence' => 'high']);

        $data = $this->graph($root, 'limit=2')->assertOk()->json('data');
        $this->assertTrue($data['truncated']);
        $this->assertCount(2, $data['edges']);
        $this->assertEqualsCanonicalizing(['Root', 'HiConfHigh', 'HiConfLow'], collect($data['nodes'])->pluck('name')->all());

        $data = $this->graph($root, 'limit=3')->json('data');
        $this->assertFalse($data['truncated']);
    }

    public function test_depth_two_stays_bounded_by_limit(): void
    {
        $root = $this->entity('Root');
        $a = $this->entity('A');
        $this->rel($root, $a);
        foreach (range(1, 5) as $i) {
            $this->rel($a, $this->entity("Leaf$i"));
        }

        $data = $this->graph($root, 'depth=2&limit=4')->assertOk()->json('data');
        $this->assertCount(4, $data['edges']);
        $this->assertTrue($data['truncated']);

        $data = $this->graph($root, 'depth=2&limit=6')->json('data');
        $this->assertCount(6, $data['edges']);
        $this->assertFalse($data['truncated']);
    }

    public function test_limit_is_validated_against_hard_cap(): void
    {
        $root = $this->entity('Root');
        $this->graph($root, 'limit=1001')->assertStatus(422);
        $this->graph($root, 'limit=1000')->assertOk();
    }

    public function test_invalid_parameters_are_rejected(): void
    {
        $root = $this->entity('Root');
        $this->graph($root, 'depth=3')->assertStatus(422);
        $this->graph($root, 'relationship_types=not_a_type')->assertStatus(422);
        $this->graph($root, 'groups=NOPE')->assertStatus(422);
    }

    public function test_unknown_entity_returns_404(): void
    {
        $this->getJson('/api/v1/entities/'.Str::uuid().'/graph')->assertNotFound();
        $this->getJson('/api/v1/entities/not-a-uuid/graph')->assertNotFound();
    }

    public function test_entity_without_relationships_returns_only_root(): void
    {
        $root = $this->entity('Lonely');
        $data = $this->graph($root, 'depth=2')->assertOk()->json('data');
        $this->assertCount(1, $data['nodes']);
        $this->assertSame([], $data['edges']);
        $this->assertFalse($data['truncated']);
    }
}

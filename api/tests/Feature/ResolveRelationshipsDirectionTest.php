<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Actions\Relationship\CreateRelationshipAction;
use App\DTOs\RelationshipData;
use App\Enums\RelationshipType;
use App\Jobs\ResolveRelationshipsJob;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * Wikidata states some relationships on the far end: a battle lists its
 * participants (P710), a work its author (P50). Those hints are created
 * target -> source, so the polity participated_in the battle, not the reverse.
 */
class ResolveRelationshipsDirectionTest extends TestCase
{
    use RefreshDatabase;

    private function entity(string $name, string $type, string $group, string $qid): Entity
    {
        return Entity::factory()->create([
            'name' => $name, 'entity_type' => $type, 'entity_group' => $group, 'wikidata_id' => $qid,
        ]);
    }

    private function hint(Entity $on, string $type, string $targetQid, string $property): void
    {
        DB::table('pipeline_relationship_hints')->insert([
            'source_entity_id' => $on->entity_id,
            'relationship_type' => $type,
            'target_wikidata_id' => $targetQid,
            'target_label' => null,
            'confidence' => 'medium',
            'wikidata_property' => $property,
            'batch_id' => 'direction-test',
            'resolved' => false,
            'created_at' => now(),
        ]);
    }

    private function resolve(): void
    {
        app()->call([new ResolveRelationshipsJob('direction-test'), 'handle']);
    }

    private function has(Entity $source, string $type, Entity $target): bool
    {
        return DB::table('relationships')
            ->where('source_entity_id', $source->entity_id)
            ->where('target_entity_id', $target->entity_id)
            ->where('relationship_type', $type)
            ->exists();
    }

    public function test_participant_and_author_hints_point_from_the_far_end(): void
    {
        $battle = $this->entity('Battle of Bibracte', 'event_battle', 'EVENT', 'Q635028');
        $helvetii = $this->entity('Helvetii', 'political_entity', 'POLITY', 'Q160440');
        $war = $this->entity('Gallic Wars', 'event_war', 'EVENT', 'Q202161');
        $work = $this->entity('Commentarii de Bello Gallico', 'cultural_work', 'CULTURE', 'Q1243');
        $caesar = $this->entity('Julius Caesar', 'person', 'POLITY', 'Q1048');

        $this->hint($battle, 'participated_in', 'Q160440', 'wikidata:P710');
        $this->hint($battle, 'part_of', 'Q202161', 'wikidata:P361');
        $this->hint($work, 'authored', 'Q1048', 'wikidata:P50');
        $this->resolve();

        $this->assertTrue($this->has($helvetii, 'participated_in', $battle));
        $this->assertFalse($this->has($battle, 'participated_in', $helvetii));
        $this->assertTrue($this->has($battle, 'part_of', $war));
        $this->assertTrue($this->has($caesar, 'authored', $work));
        $this->assertFalse($this->has($work, 'authored', $caesar));
    }

    public function test_a_reversed_hint_does_not_duplicate_an_existing_relationship(): void
    {
        $polity = $this->entity('Roman Republic', 'political_entity', 'POLITY', 'Q17167');
        $city = $this->entity('Rome', 'city', 'PLACE', 'Q220');
        app(CreateRelationshipAction::class)(
            new RelationshipData(
                sourceEntityId: $city->entity_id,
                targetEntityId: $polity->entity_id,
                relationshipType: RelationshipType::CapitalOf,
            ),
            'test',
        );

        $this->hint($polity, 'capital_of', 'Q220', 'wikidata:P36');
        $this->resolve();

        $this->assertSame(1, DB::table('relationships')->where('relationship_type', 'capital_of')->count());
        $this->assertFalse($this->has($polity, 'capital_of', $city));
    }
}

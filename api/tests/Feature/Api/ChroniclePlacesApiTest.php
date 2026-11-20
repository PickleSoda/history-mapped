<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefProvider;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\EntityRelationship;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class ChroniclePlacesApiTest extends TestCase
{
    use RefreshDatabase;

    private Chronicle $chronicle;

    protected function setUp(): void
    {
        parent::setUp();
        $this->chronicle = Chronicle::factory()->create(['slug' => 'test-chronicle']);
    }

    private function entity(string $name): Entity
    {
        return Entity::factory()->state(['name' => $name])->create();
    }

    /** Give the entity a primary map point (the factory may already have made its location row). */
    private function place(Entity $entity, float $lng, float $lat): void
    {
        DB::table('entity_locations')->where('entity_id', $entity->entity_id)->delete();
        DB::statement(
            "INSERT INTO entity_locations (location_id, entity_id, geom, location_method, location_confidence, is_primary, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, ST_SetSRID(ST_MakePoint(?, ?), 4326), 'human_assigned'::location_resolution_method, 'high'::confidence_level, true, NOW(), NOW())",
            [$entity->entity_id, $lng, $lat],
        );
    }

    private function unplace(Entity $entity): void
    {
        DB::table('entity_locations')->where('entity_id', $entity->entity_id)->delete();
        DB::table('geometry_periods')->where('entity_id', $entity->entity_id)->delete();
    }

    /** @param list<Entity> $entities */
    private function step(int $seq, ?EntityRelationship $primary = null, array $entities = []): void
    {
        $entry = ChronicleEntry::factory()->create([
            'chronicle_id' => $this->chronicle->chronicle_id,
            'sequence_order' => $seq,
            'primary_relationship_id' => $primary?->relationship_id,
        ]);
        foreach ($entities as $i => $e) {
            DB::table('chronicle_entry_entities')->insert([
                'entry_id' => $entry->entry_id,
                'entity_id' => $e->entity_id,
                'role' => 'participant',
                'sequence_in_entry' => $i,
            ]);
        }
    }

    private function rel(Entity $a, Entity $b, string $type, ?string $year = null): EntityRelationship
    {
        return EntityRelationship::create([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $a->entity_id,
            'target_entity_id' => $b->entity_id,
            'relationship_type' => $type,
            'confidence' => 'high',
            'temporal_start' => $year,
        ]);
    }

    /** @return array<string, array<string, mixed>> keyed by entity id */
    private function places(): array
    {
        $rows = $this->getJson('/api/v1/chronicles/test-chronicle/places')->assertOk()->json('data');

        return collect($rows)->keyBy('id')->all();
    }

    public function test_unknown_slug_returns_404(): void
    {
        $this->getJson('/api/v1/chronicles/nope/places')->assertNotFound();
    }

    public function test_relationship_ends_and_entry_entities_get_their_points(): void
    {
        $carthage = $this->entity('Carthage');
        $cannae = $this->entity('Battle of Cannae');
        $rome = $this->entity('Roman Republic');
        $this->place($carthage, 10.32345678, 36.85);
        $this->place($cannae, 16.13, 41.3);
        $this->place($rome, 12.5, 41.9);
        $this->step(1, $this->rel($carthage, $cannae, 'victorious_at'), [$rome]);

        $places = $this->places();

        $this->assertCount(3, $places);
        $this->assertSame([10.32346, 36.85], $places[$carthage->entity_id]['at']);
        $this->assertSame([16.13, 41.3], $places[$cannae->entity_id]['at']);
        $this->assertSame([12.5, 41.9], $places[$rome->entity_id]['at']);
    }

    /** @param array<string, mixed> $state */
    private function border(Entity $entity, string $id, ?int $from, ?int $to, array $state = []): void
    {
        EntityGeoRef::factory()->forEntity($entity)->create([
            'provider' => GeoRefProvider::Ohm->value,
            'external_type' => GeoRefExternalType::Relation->value,
            'external_id' => $id,
            'temporal_start_year' => $from,
            'temporal_end_year' => $to,
            'match_score' => 0.5,
            ...$state,
        ]);
    }

    public function test_each_dated_border_comes_back_signed_primary_first_and_unplaced_entities_are_left_out(): void
    {
        $empire = $this->entity('German Empire');
        $person = $this->entity('Wilhelm II');
        $this->unplace($empire);
        $this->unplace($person);
        $this->border($empire, '2692425', 1890, 1918);
        $this->border($empire, '2856857', 1878, 1890, ['match_role' => 'primary']);
        $this->border($empire, '999', null, null, ['match_role' => 'rejected']);
        $this->border($empire, '998', null, null, ['external_tags' => ['type' => 'chronology']]);
        $this->border($empire, '997', null, null, ['is_active' => false]);
        $this->step(1, $this->rel($person, $empire, 'rules'));

        $places = $this->places();

        $this->assertSame([$empire->entity_id], array_keys($places));
        $this->assertNull($places[$empire->entity_id]['at']);
        $this->assertSame([
            ['id' => -2856857, 'from' => 1878, 'to' => 1890, 'primary' => true],
            ['id' => -2692425, 'from' => 1890, 'to' => 1918, 'primary' => false],
        ], $places[$empire->entity_id]['borders']);
    }

    public function test_a_thing_that_spreads_lists_what_it_is_recorded_as_reaching_in_the_chronicle(): void
    {
        $flu = $this->entity('1918 influenza pandemic');
        $camp = $this->entity('Camp Funston');
        $brest = $this->entity('Brest');
        $boston = $this->entity('Boston');
        $usa = $this->entity('United States');
        $apia = $this->entity('Apia');
        $buddhism = $this->entity('Buddhism');
        $japan = $this->entity('Japan');
        $battle = $this->entity('Battle of Sekigahara');
        $this->unplace($flu);
        $this->unplace($buddhism);
        foreach ([$camp, $brest, $boston, $usa, $japan, $battle] as $i => $entity) {
            $this->place($entity, $i, $i);
        }

        $this->step(1, $this->rel($flu, $camp, 'located_at', '1918'));
        // A step keeps one primary relationship: the spread links below are none of them.
        $this->step(2, $this->rel($boston, $usa, 'part_of'), [$flu, $brest]);
        $this->rel($flu, $brest, 'spread_to', '1918');
        $this->rel($flu, $boston, 'spread_to');
        $this->rel($flu, $apia, 'spread_to', '1918');
        $this->step(3, null, [$buddhism, $japan, $battle]);
        $this->rel($japan, $buddhism, 'adopted');
        $this->rel($battle, $japan, 'located_at');

        $places = $this->places();

        // It has no point or border of its own, and is kept for what it reaches:
        // its spread_to targets and where it is located, each with the link's year.
        $reached = [
            ['id' => $boston->entity_id, 'year' => null],
            ['id' => $brest->entity_id, 'year' => 1918],
            ['id' => $camp->entity_id, 'year' => 1918],
        ];
        usort($reached, fn (array $a, array $b): int => strcmp($a['id'], $b['id']));
        $this->assertNull($places[$flu->entity_id]['at']);
        $this->assertSame($reached, $places[$flu->entity_id]['reaches']);
        // "Japan adopted Buddhism": Buddhism reached Japan.
        $this->assertSame([['id' => $japan->entity_id, 'year' => null]], $places[$buddhism->entity_id]['reaches']);
        // Being located somewhere does not make a thing spread.
        $this->assertSame([], $places[$battle->entity_id]['reaches']);
        $this->assertSame([], $places[$boston->entity_id]['reaches']);
        // What it reached outside this chronicle is not listed.
        $this->assertArrayNotHasKey($apia->entity_id, $places);
    }

    public function test_entities_of_other_chronicles_are_not_included(): void
    {
        $here = $this->entity('Here');
        $there = $this->entity('There');
        $this->place($here, 1, 2);
        $this->place($there, 3, 4);
        $this->step(1, null, [$here]);
        $other = Chronicle::factory()->create(['slug' => 'other']);
        $entry = ChronicleEntry::factory()->create(['chronicle_id' => $other->chronicle_id, 'sequence_order' => 1]);
        DB::table('chronicle_entry_entities')->insert(['entry_id' => $entry->entry_id, 'entity_id' => $there->entity_id, 'role' => 'participant']);

        $this->assertSame([$here->entity_id], array_keys($this->places()));
    }
}

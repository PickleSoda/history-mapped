<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\MapStory;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Builders shared by the Discover endpoint tests. Rows are written with plain
 * SQL where a model would fire an observer (timeline rebuilds) the tests do
 * not need.
 */
trait DiscoverTestHelpers
{
    /**
     * An entity the atlas shows (the factory picks a random status, some of
     * them hidden), with nothing random that the endpoints read.
     *
     * @param  array<string, mixed>  $state
     */
    protected function entity(EntityType $type, string $name, int $impact = 70, array $state = []): Entity
    {
        return Entity::factory()->ofType($type)->verified()->create([
            'name' => $name,
            'impact_score' => $impact,
            'display_priority' => null,
            'summary' => "{$name}: a summary long enough to serve as a clue for the reader.",
            'attributes' => [],
            ...$state,
        ]);
    }

    /** The entity's primary date range, as text ("1066-10-14", "-0753", null). */
    protected function dated(Entity $entity, ?string $start, ?string $end = null): Entity
    {
        DB::table('entity_temporal_ranges')->where('entity_id', $entity->entity_id)->delete();
        DB::table('entity_temporal_ranges')->insert([
            'temporal_range_id' => (string) Str::uuid(),
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'is_primary' => true,
            'start_date' => $start,
            'end_date' => $end,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $entity;
    }

    /** Give the entity a primary map point, optionally named. */
    protected function located(Entity $entity, float $lng, float $lat, ?string $name = null): Entity
    {
        DB::table('entity_locations')->where('entity_id', $entity->entity_id)->delete();
        DB::statement(
            'INSERT INTO entity_locations (location_id, entity_id, location_name, geom, is_primary, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, ?, ST_SetSRID(ST_MakePoint(?, ?), 4326), true, NOW(), NOW())',
            [$entity->entity_id, $name, $lng, $lat],
        );

        return $entity;
    }

    /**
     * Put the entity on the map: a point geometry period, which is what the
     * tiles draw. Call refreshTiles() once the scene is set.
     */
    protected function onMap(Entity $entity, float $lng, float $lat, int $start, ?int $end = null): Entity
    {
        DB::statement(
            "INSERT INTO geometry_periods (geometry_period_id, entity_id, period_type, start_year, end_year, geom, provenance_mode, created_by, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, 'territory', ?, ?, ST_SetSRID(ST_MakePoint(?, ?), 4326), 'manual', 'test', NOW(), NOW())",
            [$entity->entity_id, $start, $end, $lng, $lat],
        );

        return $entity;
    }

    protected function refreshTiles(): void
    {
        DB::statement('REFRESH MATERIALIZED VIEW tiles.atlas_features');
    }

    /** A relationship row; returns its id. */
    protected function link(Entity $from, string $type, Entity $to, string $confidence = 'medium'): string
    {
        $id = (string) Str::uuid();
        DB::table('relationships')->insert([
            'relationship_id' => $id,
            'source_entity_id' => $from->entity_id,
            'target_entity_id' => $to->entity_id,
            'relationship_type' => $type,
            'confidence' => $confidence,
            'created_at' => now(),
        ]);

        return $id;
    }

    /** @param array<string, mixed> $state */
    protected function chronicle(string $title, int $impact = 50, array $state = []): Chronicle
    {
        return Chronicle::factory()->create([
            'title' => $title,
            'slug' => Str::slug($title),
            'impact_score' => $impact,
            ...$state,
        ]);
    }

    /**
     * One entry of a chronicle, naming the entities and, optionally, built on
     * a primary relationship.
     *
     * @param  list<Entity>  $entities
     */
    protected function entry(Chronicle $chronicle, array $entities = [], ?string $primaryRelationshipId = null): ChronicleEntry
    {
        $entry = ChronicleEntry::factory()->create([
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => (int) DB::table('chronicle_entries')->where('chronicle_id', $chronicle->chronicle_id)->count() + 1,
            'primary_relationship_id' => $primaryRelationshipId,
        ]);
        foreach ($entities as $i => $entity) {
            DB::table('chronicle_entry_entities')->insert([
                'entry_id' => $entry->entry_id,
                'entity_id' => $entity->entity_id,
                'role' => 'participant',
                'sequence_in_entry' => $i,
            ]);
        }

        return $entry;
    }

    /** Mention the entity in `$times` entries of a throwaway chronicle. */
    protected function mention(Entity $entity, int $times = 1): void
    {
        $chronicle = $this->chronicle('Mentions of '.$entity->name.' '.Str::random(6));
        for ($i = 0; $i < $times; $i++) {
            $this->entry($chronicle, [$entity]);
        }
    }

    protected function story(Entity $entity, string $slug, ?int $year = null): MapStory
    {
        return MapStory::query()->create([
            'entity_id' => $entity->entity_id,
            'slug' => $slug,
            'kind' => 'battle',
            'title' => $entity->name,
            'year' => $year,
            'step_count' => 3,
            'document' => (object) ['slug' => $slug],
        ]);
    }

    /** The entity as every Discover endpoint gives it, for exact comparisons. */
    protected function shape(Entity $entity, ?int $start, ?int $end, ?array $at, bool $story = false): array
    {
        return [
            'id' => $entity->entity_id,
            'name' => $entity->name,
            'entity_type' => $entity->entity_type->value,
            'entity_group' => $entity->entity_group->value,
            'summary' => $entity->summary,
            'start_year' => $start,
            'end_year' => $end,
            'at' => $at,
            'has_map_story' => $story,
        ];
    }
}

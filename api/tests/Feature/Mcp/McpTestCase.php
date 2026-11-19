<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

use App\Actions\Tag\SyncTagsAction;
use App\Enums\EntityType;
use App\Enums\TagSource;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityRelationship;
use Database\Seeders\TagSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

/** Builders shared by the MCP tool tests. */
abstract class McpTestCase extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        config(['app.frontend_url' => 'https://atlas.test']);
    }

    protected function seedTags(): void
    {
        $this->seed(TagSeeder::class);
    }

    /** An entity with a primary point and, when given, a primary year range. */
    protected function placed(string $name, float $lng, float $lat, ?int $start = null, ?int $end = null, array $state = []): Entity
    {
        $factory = Entity::factory()->verified()->atLocation($name.' place');
        if ($start !== null) {
            $factory = $factory->withTemporalRange((string) $start, (string) ($end ?? $start));
        }
        if (isset($state['entity_type'])) {
            $state['entity_group'] = EntityType::from($state['entity_type'])->group()->value;
        }
        $entity = $factory->create(['name' => $name, 'date_confidence' => 'high'] + $state);
        DB::update(
            'UPDATE entity_locations SET geom = ST_SetSRID(ST_Point(?, ?), 4326) WHERE entity_id = ? AND is_primary',
            [$lng, $lat, $entity->entity_id],
        );

        return $entity;
    }

    protected function entity(string $name, ?EntityType $type = null, array $state = []): Entity
    {
        $factory = Entity::factory()->verified();
        if ($type !== null) {
            $factory = $factory->ofType($type);
        }

        return $factory->create(['name' => $name] + $state);
    }

    protected function relate(Entity $a, Entity $b, string $type = 'allied_with', array $extra = []): EntityRelationship
    {
        return EntityRelationship::create($extra + [
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $a->entity_id,
            'target_entity_id' => $b->entity_id,
            'relationship_type' => $type,
            'confidence' => 'high',
        ]);
    }

    /** @param list<string> $tags */
    protected function chronicle(string $title, array $tags = [], array $state = []): Chronicle
    {
        $chronicle = Chronicle::factory()->create(['title' => $title, 'slug' => Str::slug($title)] + $state);
        if ($tags !== []) {
            app(SyncTagsAction::class)($chronicle, $tags, TagSource::Curated);
        }

        return $chronicle;
    }

    /** @param list<Entity> $entities */
    protected function entry(Chronicle $chronicle, int $sequence, string $text, array $entities = [], array $state = []): ChronicleEntry
    {
        $entry = ChronicleEntry::factory()->create($state + [
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => $sequence,
            'narrative_text' => $text,
        ]);
        foreach ($entities as $i => $entity) {
            DB::table('chronicle_entry_entities')->insert([
                'entry_id' => $entry->entry_id,
                'entity_id' => $entity->entity_id,
                'sequence_in_entry' => $i,
            ]);
        }

        return $entry;
    }
}

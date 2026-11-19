<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Actions\Entity\ListEntitiesAction;
use App\DTOs\EntityFilterData;
use App\Enums\EntityType;
use App\Models\Entity;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * 2026_11_19_000001: `entity_names`, the narrow copy of entities.name that the
 * search count reads, is kept by triggers (importers bypass Eloquent), and the
 * count it serves equals the count over entities.
 */
class EntityNamesSyncTest extends TestCase
{
    use RefreshDatabase;

    private function mirrored(string $id): ?string
    {
        return DB::table('entity_names')->where('entity_id', $id)->value('name');
    }

    public function test_an_inserted_entity_is_mirrored(): void
    {
        $entity = Entity::factory()->create(['name' => 'Mirror Zed']);

        $this->assertSame('Mirror Zed', $this->mirrored($entity->entity_id));
    }

    public function test_a_rename_is_mirrored_and_an_unchanged_name_is_left_alone(): void
    {
        $entity = Entity::factory()->create(['name' => 'Before Zed']);

        $entity->update(['name' => 'After Zed']);
        $this->assertSame('After Zed', $this->mirrored($entity->entity_id));

        // A raw bulk update, as the importers write.
        DB::update('UPDATE entities SET name = ? WHERE entity_id = ?', ['Raw Zed', $entity->entity_id]);
        $this->assertSame('Raw Zed', $this->mirrored($entity->entity_id));

        $entity->update(['summary' => 'Only the summary changed']);
        $this->assertSame('Raw Zed', $this->mirrored($entity->entity_id));
    }

    public function test_a_delete_removes_the_mirror(): void
    {
        $entity = Entity::factory()->create(['name' => 'Gone Zed']);

        DB::delete('DELETE FROM entities WHERE entity_id = ?', [$entity->entity_id]);

        $this->assertNull($this->mirrored($entity->entity_id));
    }

    public function test_a_raw_sql_insert_is_mirrored(): void
    {
        $source = Entity::factory()->create(['name' => 'Source Zed']);

        DB::statement('CREATE TEMP TABLE entity_copy ON COMMIT DROP AS SELECT * FROM entities WHERE entity_id = ?', [$source->entity_id]);
        DB::statement("UPDATE entity_copy SET entity_id = gen_random_uuid(), name = 'Bulk Zed', wikidata_id = NULL");
        DB::statement('INSERT INTO entities SELECT * FROM entity_copy');

        $id = DB::table('entities')->where('name', 'Bulk Zed')->value('entity_id');
        $this->assertNotNull($id);
        $this->assertSame('Bulk Zed', $this->mirrored($id));
        $this->assertSame(DB::table('entities')->count(), DB::table('entity_names')->count());
    }

    public function test_the_capped_search_count_matches_the_count_over_entities(): void
    {
        foreach (['Battle of Alpha', 'Battle of Beta', 'Battle of Gamma', 'Siege of Alpha'] as $name) {
            Entity::factory()->verified()->create(['name' => $name, 'entity_type' => EntityType::EventBattle]);
        }
        Entity::factory()->verified()->create(['name' => 'Alphabet', 'entity_type' => EntityType::Person]);

        foreach (['battle of', 'alpha', 'Battle of Alpha', 'btl of', 'zz'] as $term) {
            foreach ([[], ['type' => 'person'], ['type' => 'event_battle']] as $extra) {
                $filters = EntityFilterData::fromArray(['search' => $term, 'per_page' => 2] + $extra);

                $exact = app(ListEntitiesAction::class)($filters)->total();
                $capped = app(ListEntitiesAction::class)($filters, totalCap: 1000);

                $this->assertSame($exact, $capped->total(), "{$term} ".json_encode($extra));
                $this->assertFalse($capped->totalCapped);
            }
        }

        $filters = EntityFilterData::fromArray(['search' => 'battle of', 'per_page' => 2]);
        $capped = app(ListEntitiesAction::class)($filters, totalCap: 2);
        $this->assertSame(2, $capped->total());
        $this->assertTrue($capped->totalCapped);
    }

    public function test_down_removes_the_table_and_triggers_and_entities_keep_working(): void
    {
        $migration = require database_path('migrations/2026_11_19_000001_create_entity_names_table.php');
        $this->assertInstanceOf(Migration::class, $migration);

        $migration->down();

        $this->assertFalse(DB::getSchemaBuilder()->hasTable('entity_names'));
        $this->assertSame([], DB::select("SELECT 1 FROM pg_trigger WHERE tgname LIKE 'entity_names_%'"));
        $this->assertSame([], DB::select("SELECT 1 FROM pg_proc WHERE proname = 'entity_names_sync'"));

        $entity = Entity::factory()->create(['name' => 'After Down Zed']);
        $entity->update(['name' => 'Renamed Zed']);
        $entity->delete();
        $this->assertDatabaseMissing('entities', ['entity_id' => $entity->entity_id]);
    }
}

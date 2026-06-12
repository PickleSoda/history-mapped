<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class ImportRelationsCommandTest extends TestCase
{
    use RefreshDatabase;

    /**
     * @param  list<array<string, mixed>>  $records
     */
    private function writeRelationsFile(array $records): string
    {
        $path = sys_get_temp_dir().DIRECTORY_SEPARATOR.'import_relations_'.uniqid('', true).'.jsonl';

        file_put_contents(
            $path,
            implode("\n", array_map(
                static fn (array $r): string => json_encode($r, JSON_THROW_ON_ERROR),
                $records,
            ))."\n",
        );

        $this->beforeApplicationDestroyed(function () use ($path): void {
            if (is_file($path)) {
                unlink($path);
            }
        });

        return $path;
    }

    private function makeEntity(string $name, string $type, string $group): Entity
    {
        return Entity::factory()->create([
            'name' => $name,
            'entity_type' => $type,
            'entity_group' => $group,
        ]);
    }

    public function test_creates_relationship_resolving_both_ends_by_name(): void
    {
        $alex = $this->makeEntity('Alexander the Great', 'person', 'POLITY');
        $issus = $this->makeEntity('Battle of Issus', 'event_battle', 'EVENT');

        $path = $this->writeRelationsFile([[
            'source_name' => 'Alexander the Great',
            'target_name' => 'Battle of Issus',
            'relationship_type' => 'victorious_at',
            'start_date' => '-0333',
            'description' => 'Decisive victory.',
        ]]);

        $this->artisan('pipeline:import-relations', ['path' => $path, '--batch-id' => 'rel-test'])
            ->assertExitCode(0);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $alex->entity_id,
            'target_entity_id' => $issus->entity_id,
            'relationship_type' => 'victorious_at',
        ]);
    }

    public function test_resolves_names_case_insensitively(): void
    {
        $this->makeEntity('Alexander the Great', 'person', 'POLITY');
        $this->makeEntity('Battle of Issus', 'event_battle', 'EVENT');

        $path = $this->writeRelationsFile([[
            'source_name' => 'alexander the great',
            'target_name' => 'BATTLE OF ISSUS',
            'relationship_type' => 'victorious_at',
        ]]);

        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);

        $this->assertSame(1, DB::table('relationships')->where('relationship_type', 'victorious_at')->count());
    }

    public function test_is_idempotent_on_rerun(): void
    {
        $this->makeEntity('Alexander the Great', 'person', 'POLITY');
        $this->makeEntity('Battle of Issus', 'event_battle', 'EVENT');

        $path = $this->writeRelationsFile([[
            'source_name' => 'Alexander the Great',
            'target_name' => 'Battle of Issus',
            'relationship_type' => 'victorious_at',
        ]]);

        $cmd = ['path' => $path, '--batch-id' => 'rel-rerun'];
        $this->artisan('pipeline:import-relations', $cmd)->assertExitCode(0);
        $this->artisan('pipeline:import-relations', $cmd)->assertExitCode(0);

        $this->assertSame(1, DB::table('relationships')->where('relationship_type', 'victorious_at')->count());
    }

    public function test_unresolved_target_creates_no_row_but_succeeds(): void
    {
        $this->makeEntity('Alexander the Great', 'person', 'POLITY');

        $path = $this->writeRelationsFile([[
            'source_name' => 'Alexander the Great',
            'target_name' => 'Some Entity That Does Not Exist',
            'relationship_type' => 'victorious_at',
        ]]);

        // Unresolved is a data gap, not a fault: exit 0, no row.
        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);
        $this->assertSame(0, DB::table('relationships')->count());
    }

    public function test_invalid_relationship_type_is_skipped(): void
    {
        $this->makeEntity('Alexander the Great', 'person', 'POLITY');
        $this->makeEntity('Battle of Issus', 'event_battle', 'EVENT');

        $path = $this->writeRelationsFile([[
            'source_name' => 'Alexander the Great',
            'target_name' => 'Battle of Issus',
            'relationship_type' => 'not_a_real_type',
        ]]);

        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);
        $this->assertSame(0, DB::table('relationships')->count());
    }
}

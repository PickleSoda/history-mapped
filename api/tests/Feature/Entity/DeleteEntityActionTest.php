<?php

declare(strict_types=1);

namespace Tests\Feature\Entity;

use App\Actions\Entity\DeleteEntityAction;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class DeleteEntityActionTest extends TestCase
{
    use RefreshDatabase;

    private function makeChronicleEntry(string ...$entityIds): ChronicleEntry
    {
        $chronicle = Chronicle::factory()->create();
        $entry = ChronicleEntry::create([
            'entry_id' => (string) Str::uuid(),
            'chronicle_id' => $chronicle->chronicle_id,
            'narrative_text' => 'Test narrative',
            'sequence_order' => 1,
        ]);

        foreach ($entityIds as $eid) {
            DB::table('chronicle_entry_entities')->insert([
                'entry_id' => $entry->entry_id,
                'entity_id' => $eid,
            ]);
        }

        return $entry;
    }

    public function test_deletes_entity_with_no_references(): void
    {
        $entity = Entity::factory()->create();

        app(DeleteEntityAction::class)($entity);

        $this->assertDatabaseMissing('entities', ['entity_id' => $entity->entity_id]);
    }

    public function test_deletes_entity_referenced_by_chronicle_entry(): void
    {
        $entity = Entity::factory()->create();
        $other = Entity::factory()->create();
        $entry = $this->makeChronicleEntry($entity->entity_id, $other->entity_id);

        app(DeleteEntityAction::class)($entity);

        // Entity is gone and its participant row detached...
        $this->assertDatabaseMissing('entities', ['entity_id' => $entity->entity_id]);
        $this->assertDatabaseMissing('chronicle_entry_entities', [
            'entry_id' => $entry->entry_id,
            'entity_id' => $entity->entity_id,
        ]);

        // ...but the entry itself and the other participant survive.
        $this->assertDatabaseHas('chronicle_entries', ['entry_id' => $entry->entry_id]);
        $this->assertDatabaseHas('chronicle_entry_entities', [
            'entry_id' => $entry->entry_id,
            'entity_id' => $other->entity_id,
        ]);
    }
}

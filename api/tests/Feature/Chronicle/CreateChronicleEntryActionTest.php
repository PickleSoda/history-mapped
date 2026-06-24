<?php

declare(strict_types=1);

namespace Tests\Feature\Chronicle;

use App\Actions\Chronicle\CreateChronicleEntryAction;
use App\DTOs\ChronicleEntryData;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CreateChronicleEntryActionTest extends TestCase
{
    use RefreshDatabase;

    public function test_creates_entry_with_narrative_and_linked_entities(): void
    {
        $chronicle = Chronicle::factory()->create();
        $e1 = Entity::factory()->create();
        $e2 = Entity::factory()->create();

        $entry = app(CreateChronicleEntryAction::class)(
            $chronicle->chronicle_id,
            new ChronicleEntryData(narrativeText: 'Rome defeats Carthage.', entityIds: [$e1->entity_id, $e2->entity_id]),
            createdBy: 'agent:u1',
        );

        $this->assertSame('Rome defeats Carthage.', $entry->narrative_text);
        $this->assertSame($chronicle->chronicle_id, $entry->chronicle_id);
        $this->assertEqualsCanonicalizing(
            [$e1->entity_id, $e2->entity_id],
            $entry->secondaryEntities()->pluck('entities.entity_id')->all(),
        );
    }
}

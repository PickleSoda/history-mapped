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
        $this->assertSame('agent:u1', $entry->generated_by);
        $this->assertEqualsCanonicalizing(
            [$e1->entity_id, $e2->entity_id],
            $entry->secondaryEntities()->pluck('entities.entity_id')->all(),
        );
    }

    public function test_defaults_generated_by_to_agent_when_no_creator(): void
    {
        $chronicle = Chronicle::factory()->create();

        $entry = app(CreateChronicleEntryAction::class)(
            $chronicle->chronicle_id,
            new ChronicleEntryData(narrativeText: 'Some narrative.'),
        );

        $this->assertSame('agent', $entry->generated_by);
    }

    public function test_null_entity_ids_leaves_no_links_and_empty_array_clears(): void
    {
        $chronicle = Chronicle::factory()->create();

        $entry = app(CreateChronicleEntryAction::class)(
            $chronicle->chronicle_id,
            new ChronicleEntryData(narrativeText: 'Narrative with no entities.', entityIds: null),
        );

        $this->assertSame(0, $entry->secondaryEntities()->count());
    }

    public function test_rejects_null_or_empty_narrative(): void
    {
        $chronicle = Chronicle::factory()->create();

        $this->expectException(\InvalidArgumentException::class);

        app(CreateChronicleEntryAction::class)(
            $chronicle->chronicle_id,
            new ChronicleEntryData(narrativeText: null),
        );
    }
}

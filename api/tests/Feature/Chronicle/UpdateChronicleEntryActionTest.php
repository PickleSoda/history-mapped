<?php

declare(strict_types=1);

namespace Tests\Feature\Chronicle;

use App\Actions\Chronicle\CreateChronicleEntryAction;
use App\Actions\Chronicle\UpdateChronicleEntryAction;
use App\DTOs\ChronicleEntryData;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class UpdateChronicleEntryActionTest extends TestCase
{
    use RefreshDatabase;

    public function test_updates_narrative_only_and_preserves_existing_entity_links(): void
    {
        $chronicle = Chronicle::factory()->create();
        $e1 = Entity::factory()->create();

        $entry = app(CreateChronicleEntryAction::class)(
            $chronicle->chronicle_id,
            new ChronicleEntryData(narrativeText: 'Original narrative.', entityIds: [$e1->entity_id]),
        );

        $updated = app(UpdateChronicleEntryAction::class)(
            $entry,
            new ChronicleEntryData(narrativeText: 'Updated narrative.'),
        );

        $this->assertSame('Updated narrative.', $updated->narrative_text);
        $this->assertEqualsCanonicalizing(
            [$e1->entity_id],
            $updated->secondaryEntities()->pluck('entities.entity_id')->all(),
        );
    }

    public function test_updates_entity_links_when_entity_ids_provided(): void
    {
        $chronicle = Chronicle::factory()->create();
        $e1 = Entity::factory()->create();
        $e2 = Entity::factory()->create();

        $entry = app(CreateChronicleEntryAction::class)(
            $chronicle->chronicle_id,
            new ChronicleEntryData(narrativeText: 'Narrative.', entityIds: [$e1->entity_id]),
        );

        $updated = app(UpdateChronicleEntryAction::class)(
            $entry,
            new ChronicleEntryData(entityIds: [$e2->entity_id]),
        );

        $this->assertEqualsCanonicalizing(
            [$e2->entity_id],
            $updated->secondaryEntities()->pluck('entities.entity_id')->all(),
        );
        // narrative unchanged
        $this->assertSame('Narrative.', $updated->narrative_text);
    }

    public function test_null_entity_ids_preserves_links(): void
    {
        $chronicle = Chronicle::factory()->create();
        $e1 = Entity::factory()->create();

        $entry = app(CreateChronicleEntryAction::class)(
            $chronicle->chronicle_id,
            new ChronicleEntryData(narrativeText: 'Narrative.', entityIds: [$e1->entity_id]),
        );

        $updated = app(UpdateChronicleEntryAction::class)(
            $entry,
            new ChronicleEntryData(notes: 'A note.'),
        );

        $this->assertSame('A note.', $updated->notes);
        $this->assertSame('Narrative.', $updated->narrative_text);
        $this->assertEqualsCanonicalizing(
            [$e1->entity_id],
            $updated->secondaryEntities()->pluck('entities.entity_id')->all(),
        );
    }
}

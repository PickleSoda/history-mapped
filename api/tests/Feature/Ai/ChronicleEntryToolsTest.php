<?php

namespace Tests\Feature\Ai;

use App\Ai\Agents\ChronicleEditorAgent;
use App\Ai\Tools\CreateChronicleEntry;
use App\Ai\Tools\UpdateChronicleEntry;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ChronicleEntryToolsTest extends TestCase
{
    use RefreshDatabase;

    // ──────────────────────────────────────────────────────────────────
    // CreateChronicleEntry
    // ──────────────────────────────────────────────────────────────────

    public function test_create_entry_build_returns_one_part_with_correct_tool(): void
    {
        $chronicle = Chronicle::factory()->create();
        $tool = app(CreateChronicleEntry::class);

        $parts = $tool->buildParts([
            'chronicle_id' => $chronicle->chronicle_id,
            'narrative_text' => 'Rome crossed the Rubicon.',
        ]);

        $this->assertCount(1, $parts);
        $this->assertSame('create_chronicle_entry', $parts[0]['tool']);
        $this->assertSame('entry', $parts[0]['key']);
    }

    public function test_create_entry_apply_creates_entry_with_agent_provenance(): void
    {
        $chronicle = Chronicle::factory()->create();
        $tool = app(CreateChronicleEntry::class);

        $parts = $tool->buildParts([
            'chronicle_id' => $chronicle->chronicle_id,
            'narrative_text' => 'Rome crossed the Rubicon.',
        ]);

        $result = $tool->applyPart($parts[0]['payload'], ['user_id' => 'u1']);

        $entry = ChronicleEntry::findOrFail($result['result_id']);

        $this->assertSame('Rome crossed the Rubicon.', $entry->narrative_text);
        $this->assertSame($chronicle->chronicle_id, $entry->chronicle_id);
        $this->assertSame('agent:u1', $entry->generated_by);
        $this->assertSame($entry->entry_id, $result['result_id']);
    }

    public function test_create_entry_apply_links_entities(): void
    {
        $chronicle = Chronicle::factory()->create();
        $entity1 = Entity::factory()->create();
        $entity2 = Entity::factory()->create();

        $tool = app(CreateChronicleEntry::class);

        $parts = $tool->buildParts([
            'chronicle_id' => $chronicle->chronicle_id,
            'narrative_text' => 'Two entities are linked here.',
            'entity_ids' => [$entity1->entity_id, $entity2->entity_id],
        ]);

        $result = $tool->applyPart($parts[0]['payload'], ['user_id' => 'u1']);

        $entry = ChronicleEntry::findOrFail($result['result_id']);
        $entry->load('secondaryEntities');

        $linkedIds = $entry->secondaryEntities->pluck('entity_id')->sort()->values()->toArray();
        $expectedIds = collect([$entity1->entity_id, $entity2->entity_id])->sort()->values()->toArray();

        $this->assertSame($expectedIds, $linkedIds);
    }

    // ──────────────────────────────────────────────────────────────────
    // UpdateChronicleEntry
    // ──────────────────────────────────────────────────────────────────

    public function test_update_entry_build_returns_one_part_with_correct_tool(): void
    {
        $chronicle = Chronicle::factory()->create();
        $entry = ChronicleEntry::factory()->for($chronicle, 'chronicle')->create([
            'narrative_text' => 'Original text.',
        ]);

        $tool = app(UpdateChronicleEntry::class);

        $parts = $tool->buildParts([
            'entry_id' => $entry->entry_id,
            'narrative_text' => 'Updated text.',
        ]);

        $this->assertCount(1, $parts);
        $this->assertSame('update_chronicle_entry', $parts[0]['tool']);
        $this->assertSame('entry', $parts[0]['key']);
    }

    public function test_update_entry_apply_updates_narrative(): void
    {
        $chronicle = Chronicle::factory()->create();
        $entry = ChronicleEntry::factory()->for($chronicle, 'chronicle')->create([
            'narrative_text' => 'Original text.',
        ]);

        $tool = app(UpdateChronicleEntry::class);

        $parts = $tool->buildParts([
            'entry_id' => $entry->entry_id,
            'narrative_text' => 'Updated text.',
        ]);

        $result = $tool->applyPart($parts[0]['payload'], ['user_id' => 'u2']);

        $this->assertSame($entry->entry_id, $result['result_id']);
        $entry->refresh();
        $this->assertSame('Updated text.', $entry->narrative_text);
    }

    public function test_update_entry_apply_preserves_entity_links_when_no_entity_ids(): void
    {
        $chronicle = Chronicle::factory()->create();
        $entity = Entity::factory()->create();
        $entry = ChronicleEntry::factory()->for($chronicle, 'chronicle')->create([
            'narrative_text' => 'Original text.',
        ]);
        $entry->secondaryEntities()->sync([$entity->entity_id]);

        $tool = app(UpdateChronicleEntry::class);

        $parts = $tool->buildParts([
            'entry_id' => $entry->entry_id,
            'narrative_text' => 'Updated text, no entity_ids field.',
        ]);

        $result = $tool->applyPart($parts[0]['payload'], ['user_id' => 'u2']);

        $entry->refresh()->load('secondaryEntities');
        // entity_ids was not passed — links should be preserved
        $this->assertCount(1, $entry->secondaryEntities);
        $this->assertSame($entity->entity_id, $entry->secondaryEntities->first()->entity_id);
    }

    // ──────────────────────────────────────────────────────────────────
    // ChronicleEditorAgent wiring
    // ──────────────────────────────────────────────────────────────────

    public function test_chronicle_editor_agent_includes_entry_tools_with_context(): void
    {
        $chronicle = Chronicle::factory()->create();
        $user = User::factory()->create();
        $context = [
            'user_id' => 'u1',
            'context_type' => 'chronicle',
            'context_id' => $chronicle->chronicle_id,
            'conversation_id' => null,
        ];

        $agent = new ChronicleEditorAgent($chronicle, $user, $context);
        $tools = collect($agent->tools());
        $names = $tools->map(fn ($t) => $t::name())->toArray();

        $this->assertContains('create_chronicle_entry', $names);
        $this->assertContains('update_chronicle_entry', $names);

        // Verify context is injected on both entry tools
        foreach (['create_chronicle_entry', 'update_chronicle_entry'] as $toolName) {
            $toolInstance = $tools->first(fn ($t) => $t::name() === $toolName);
            $ref = new \ReflectionProperty($toolInstance, 'context');
            $ref->setAccessible(true);
            $this->assertSame('u1', $ref->getValue($toolInstance)['user_id']);
        }
    }
}

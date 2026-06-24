<?php

namespace Tests\Feature\Ai;

use App\Ai\Agents\ChronicleCreatorAgent;
use App\Ai\Agents\EntityCreatorAgent;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CreatorAgentsTest extends TestCase
{
    use RefreshDatabase;

    private function ctx(): array
    {
        return ['user_id' => 'u1', 'context_type' => 'entity', 'context_id' => 'create', 'conversation_id' => null];
    }

    public function test_entity_creator_exposes_only_creation_tools_with_context(): void
    {
        $agent = new EntityCreatorAgent(User::factory()->create(), $this->ctx());
        $names = array_map(fn ($t) => $t::name(), array_filter(
            iterator_to_array((function () use ($agent) { yield from $agent->tools(); })()),
            fn ($t) => method_exists($t, 'name'),
        ));
        $this->assertContains('create_entity', $names);
        $this->assertContains('verify_wikidata', $names);
        $this->assertNotContains('merge_duplicate_entities', $names);

        // context injected on the staging tool
        $createEntity = collect($agent->tools())->first(fn ($t) => $t::name() === 'create_entity');
        $ref = new \ReflectionProperty($createEntity, 'context');
        $ref->setAccessible(true);
        $this->assertSame('u1', $ref->getValue($createEntity)['user_id']);
    }

    public function test_chronicle_creator_instructions_explain_entry_handoff(): void
    {
        $agent = new ChronicleCreatorAgent(User::factory()->create(), ['user_id' => 'u1', 'context_type' => 'chronicle', 'context_id' => 'create', 'conversation_id' => null]);
        $instructions = $agent->instructions();
        $this->assertStringContainsStringIgnoringCase('entr', $instructions); // mentions entries
        $this->assertStringContainsStringIgnoringCase('edit', $instructions);  // points to the edit page
        $names = array_map(fn ($t) => $t::name(), iterator_to_array((function () use ($agent) { yield from $agent->tools(); })()));
        $this->assertContains('create_chronicle', $names);
    }
}

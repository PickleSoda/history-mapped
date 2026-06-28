<?php

namespace Tests\Feature\Ai;

use App\Ai\Agents\GlobalAgent;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class GlobalAgentTest extends TestCase
{
    use RefreshDatabase;

    private function ctx(): array
    {
        return [
            'user_id' => 'u1',
            'context_type' => 'global',
            'context_id' => 'some-session-uuid',
            'conversation_id' => 'some-session-uuid',
        ];
    }

    public function test_global_agent_exposes_all_eleven_tools_with_context(): void
    {
        $user = User::factory()->create();
        $agent = new GlobalAgent($user, $this->ctx());

        $tools = iterator_to_array($agent->tools());
        $names = array_map(fn ($t) => $t::name(), $tools);

        // Create tools
        $this->assertContains('create_entity', $names);
        $this->assertContains('create_chronicle', $names);
        $this->assertContains('create_chronicle_entry', $names);

        // Edit tools
        $this->assertContains('update_entity_fields', $names);
        $this->assertContains('set_entity_location', $names);
        $this->assertContains('set_entity_wikidata', $names);
        $this->assertContains('create_relationship', $names);
        $this->assertContains('update_chronicle_entry', $names);
        $this->assertContains('merge_duplicate_entities', $names);

        // Read-only (no context needed)
        $this->assertContains('get_entity_context', $names);
        $this->assertContains('verify_wikidata', $names);

        $this->assertCount(11, $tools);
    }

    public function test_global_agent_injects_context_on_staging_tools(): void
    {
        $user = User::factory()->create();
        $agent = new GlobalAgent($user, $this->ctx());

        $createEntity = collect($agent->tools())
            ->first(fn ($t) => $t::name() === 'create_entity');

        // The context is stored in a protected/private property — reflect to verify.
        $ref = new \ReflectionProperty($createEntity, 'context');
        $ref->setAccessible(true);

        $this->assertSame('u1', $ref->getValue($createEntity)['user_id']);
        $this->assertSame('global', $ref->getValue($createEntity)['context_type']);
    }

    public function test_global_agent_instructions_mention_proposal_workflow_and_no_redirect(): void
    {
        $user = User::factory()->create();
        $agent = new GlobalAgent($user, $this->ctx());
        $instructions = $agent->instructions();

        $this->assertStringContainsStringIgnoringCase('propose', $instructions);
        // Should tell the model the conversation continues (stay-in-session), not
        // that it hands off / navigates away after creating a record.
        $this->assertStringContainsStringIgnoringCase('continue', $instructions);
        // Should mention it can work on any record type
        $this->assertStringContainsStringIgnoringCase('entity', $instructions);
        $this->assertStringContainsStringIgnoringCase('chronicle', $instructions);
    }
}

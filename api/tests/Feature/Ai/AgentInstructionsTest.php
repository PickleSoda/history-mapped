<?php

namespace Tests\Feature\Ai;

use App\Ai\Agents\EntityCreatorAgent;
use App\Ai\Agents\EntityEditorAgent;
use App\Ai\Agents\GlobalAgent;
use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/** The shared prompt sections reach every agent that edits or places entities. */
class AgentInstructionsTest extends TestCase
{
    use RefreshDatabase;

    private function ctx(): array
    {
        return ['user_id' => 'u1', 'context_type' => 'global', 'context_id' => null, 'conversation_id' => null];
    }

    public function test_editors_explain_fields_and_placement(): void
    {
        $user = User::factory()->create();
        $editors = [
            new EntityEditorAgent(Entity::factory()->create(), $user, $this->ctx()),
            new GlobalAgent($user, $this->ctx()),
        ];

        foreach ($editors as $agent) {
            $instructions = $agent->instructions();
            $this->assertStringContainsString('attribute_fields', $instructions, $agent::class);
            $this->assertStringContainsString('`clear: [', $instructions, $agent::class);
            $this->assertStringContainsString('Placing an entity on the map', $instructions, $agent::class);
            $this->assertStringContainsString('nearest_coast', $instructions, $agent::class);
        }
    }

    public function test_the_creator_gets_the_placement_recipe(): void
    {
        $instructions = (new EntityCreatorAgent(User::factory()->create(), $this->ctx()))->instructions();

        $this->assertStringContainsString('find_place', $instructions);
        $this->assertStringContainsString('create_entity', $instructions);
    }
}

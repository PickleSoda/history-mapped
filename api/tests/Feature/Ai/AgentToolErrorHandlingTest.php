<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\UpdateEntityFields;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Ai\Tools\Request;
use Tests\TestCase;

/**
 * The staging-tool base (AgentTool::handle) must never let a buildParts
 * exception escape — an uncaught throw aborts the SSE stream and hangs the
 * chat. It must return an error payload and stage nothing.
 */
class AgentToolErrorHandlingTest extends TestCase
{
    use RefreshDatabase;

    private function context(): array
    {
        $user = User::factory()->create();

        return [
            'user_id' => $user->id,
            'conversation_id' => null,
            'context_type' => 'global',
            'context_id' => 'global',
        ];
    }

    public function test_handle_returns_error_payload_when_build_parts_throws(): void
    {
        $tool = app(UpdateEntityFields::class)->withContext($this->context());

        // Valid UUID, no such entity → buildParts' findOrFail throws.
        $json = $tool->handle(new Request([
            'entity_id' => '00000000-0000-0000-0000-000000000000',
            'summary' => 'x',
        ]));

        $data = json_decode((string) $json, true);
        $this->assertArrayHasKey('error', $data);
    }

    public function test_handle_stages_no_change_when_build_parts_throws(): void
    {
        $tool = app(UpdateEntityFields::class)->withContext($this->context());

        $tool->handle(new Request([
            'entity_id' => '00000000-0000-0000-0000-000000000000',
            'summary' => 'x',
        ]));

        // No orphaned ProposedChange row from the failed attempt.
        $this->assertDatabaseCount('agent_proposed_changes', 0);
    }
}

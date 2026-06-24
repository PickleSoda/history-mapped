<?php

namespace Tests\Feature\Ai;

use App\Models\Ai\ProposedChange;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Laravel\Ai\Models\Conversation;
use Laravel\Ai\Models\ConversationMessage;
use Tests\TestCase;

class AiSessionEndpointTest extends TestCase
{
    use RefreshDatabase;

    public function test_agent_conversations_has_context_columns(): void
    {
        $this->assertTrue(Schema::hasColumn('agent_conversations', 'context_type'));
        $this->assertTrue(Schema::hasColumn('agent_conversations', 'context_id'));
    }

    public function test_sessions_index_lists_only_the_callers_sessions_newest_first(): void
    {
        $user = $this->userWithPermissions(['entities.write']);
        $other = $this->userWithPermissions(['entities.write']);

        $entity = Entity::factory()->create(['name' => 'Rome']);

        $older = Conversation::create([
            'id' => (string) Str::uuid7(),
            'user_id' => $user->id, 'title' => 'Older',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
            'updated_at' => now()->subHour(),
        ]);
        $newer = Conversation::create([
            'id' => (string) Str::uuid7(),
            'user_id' => $user->id, 'title' => 'Newer',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
            'updated_at' => now(),
        ]);
        Conversation::create([
            'id' => (string) Str::uuid7(),
            'user_id' => $other->id, 'title' => 'Not mine',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
        ]);

        $response = $this->actingAs($user)->getJson('/ai/sessions');

        $response->assertOk();
        $ids = array_column($response->json('data'), 'id');
        $this->assertSame([$newer->id, $older->id], $ids); // newest first, others excluded
        $this->assertSame('Entity: Rome', $response->json('data.0.context_label'));
    }

    public function test_sessions_index_filters_by_context(): void
    {
        $user = $this->userWithPermissions(['entities.write']);
        $e1 = Entity::factory()->create(['name' => 'Rome']);
        $e2 = Entity::factory()->create(['name' => 'Carthage']);

        foreach ([$e1, $e2] as $e) {
            Conversation::create([
                'id' => (string) Str::uuid7(),
                'user_id' => $user->id, 'title' => 'c',
                'context_type' => 'entity', 'context_id' => $e->entity_id,
            ]);
        }

        $response = $this->actingAs($user)->getJson(
            '/ai/sessions?context_type=entity&context_id='.$e2->entity_id,
        );

        $response->assertOk()->assertJsonCount(1, 'data');
        $this->assertSame($e2->entity_id, $response->json('data.0.context_id'));
    }

    public function test_sessions_index_requires_entities_write(): void
    {
        $user = $this->userWithRole('user');
        $this->actingAs($user)->getJson('/ai/sessions')->assertForbidden();
    }

    public function test_session_show_returns_messages_and_proposal_statuses(): void
    {
        $user = $this->userWithPermissions(['entities.write']);
        $entity = Entity::factory()->create(['name' => 'Rome']);

        $session = Conversation::create([
            'id' => (string) Str::uuid7(),
            'user_id' => $user->id, 'title' => 'Chat',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
        ]);

        ConversationMessage::create([
            'id' => (string) Str::uuid7(),
            'conversation_id' => $session->id, 'user_id' => $user->id,
            'agent' => 'X', 'role' => 'user', 'content' => 'hi',
            'attachments' => [], 'tool_calls' => [], 'tool_results' => [],
            'usage' => [], 'meta' => [],
            'created_at' => now()->subMinute(), 'updated_at' => now()->subMinute(),
        ]);
        ConversationMessage::create([
            'id' => (string) Str::uuid7(),
            'conversation_id' => $session->id, 'user_id' => $user->id,
            'agent' => 'X', 'role' => 'assistant', 'content' => 'hello',
            'attachments' => [], 'tool_calls' => [], 'tool_results' => [],
            'usage' => [], 'meta' => [],
            'created_at' => now(), 'updated_at' => now(),
        ]);

        $change = ProposedChange::create([
            'user_id' => (string) $user->id,
            'conversation_id' => $session->id,
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
        ]);
        $change->parts()->create([
            'key' => 'fields', 'tool' => 'update_entity_fields',
            'payload' => ['summary' => 'x'], 'human_diff' => ['summary' => 'set summary'],
            'status' => 'applied', 'result_id' => $entity->entity_id,
        ]);

        $response = $this->actingAs($user)->getJson('/ai/sessions/'.$session->id);

        $response->assertOk();
        $this->assertSame(['hi', 'hello'], array_column($response->json('messages'), 'content'));
        $this->assertSame('applied', $response->json('proposals.0.parts.0.status'));
        $this->assertSame('update_entity_fields', $response->json('proposals.0.parts.0.tool'));
    }

    public function test_session_show_forbids_non_owner(): void
    {
        $owner = $this->userWithPermissions(['entities.write']);
        $intruder = $this->userWithPermissions(['entities.write']);

        $session = Conversation::create([
            'id' => (string) Str::uuid7(),
            'user_id' => $owner->id, 'title' => 'Chat',
            'context_type' => 'entity', 'context_id' => 'x',
        ]);

        $this->actingAs($intruder)->getJson('/ai/sessions/'.$session->id)->assertForbidden();
    }
}

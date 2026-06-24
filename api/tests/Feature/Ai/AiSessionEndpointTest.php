<?php

namespace Tests\Feature\Ai;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Schema;
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

        $entity = \App\Models\Entity::factory()->create(['name' => 'Rome']);

        $older = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $user->id, 'title' => 'Older',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
            'updated_at' => now()->subHour(),
        ]);
        $newer = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $user->id, 'title' => 'Newer',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
            'updated_at' => now(),
        ]);
        \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
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
        $e1 = \App\Models\Entity::factory()->create(['name' => 'Rome']);
        $e2 = \App\Models\Entity::factory()->create(['name' => 'Carthage']);

        foreach ([$e1, $e2] as $e) {
            \Laravel\Ai\Models\Conversation::create([
                'id' => (string) \Illuminate\Support\Str::uuid7(),
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
}

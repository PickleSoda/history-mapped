<?php

namespace Tests\Feature\Ai;

use App\Ai\Agents\ChronicleEditorAgent;
use App\Ai\Agents\EntityEditorAgent;
use App\Ai\Tools\CreateEntity;
use App\Ai\Tools\CreateRelationship;
use App\Ai\Tools\GetEntityContext;
use App\Ai\Tools\MergeDuplicateEntities;
use App\Ai\Tools\SetEntityLocation;
use App\Ai\Tools\SetEntityWikidata;
use App\Ai\Tools\UpdateEntityFields;
use App\Ai\Tools\VerifyWikidata;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\TestCase;

class AiChatStreamTest extends TestCase
{
    use RefreshDatabase;

    // ── Helpers ───────────────────────────────────────────────────────────────

    private function fakeWikidata(): void
    {
        Http::fake(['*' => Http::response(['entities' => []])]);
    }

    private function makeEntity(): Entity
    {
        return Entity::factory()->create([
            'name' => 'Roman Empire',
            'entity_type' => 'political_entity',
        ]);
    }

    /**
     * Create a Chronicle with one entry that references the given entity.
     */
    private function makeChronicleWithEntity(Entity $entity): Chronicle
    {
        $chronicle = Chronicle::factory()->create([
            'title' => 'Rise of Rome',
        ]);

        $entryId = (string) Str::uuid();

        DB::table('chronicle_entries')->insert([
            'entry_id' => $entryId,
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => 1,
            'narrative_text' => 'Rome was founded.',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        DB::table('chronicle_entry_entities')->insert([
            'entry_id' => $entryId,
            'entity_id' => $entity->entity_id,
            'role' => 'participant',
        ]);

        return $chronicle;
    }

    // ── Unit: agent construction ──────────────────────────────────────────────

    /**
     * EntityEditorAgent::tools() must return all expected tools with context
     * properly injected into every staging tool.
     */
    public function test_entity_editor_agent_tools_have_context_injected(): void
    {
        $this->fakeWikidata();

        $user = $this->userWithRole('admin');
        $entity = $this->makeEntity();

        $context = [
            'user_id' => (string) $user->id,
            'context_type' => 'entity',
            'context_id' => $entity->entity_id,
            'conversation_id' => null,
        ];

        $agent = new EntityEditorAgent($entity, $user, $context);
        $tools = collect($agent->tools());

        // Expect 8 tools.
        $this->assertCount(8, $tools);

        // Read-only tools present.
        $this->assertTrue(
            $tools->contains(fn ($t) => $t instanceof GetEntityContext),
            'GetEntityContext must be in the tools list'
        );
        $this->assertTrue(
            $tools->contains(fn ($t) => $t instanceof VerifyWikidata),
            'VerifyWikidata must be in the tools list'
        );

        // Staging tools present.
        foreach ([CreateEntity::class, SetEntityLocation::class, UpdateEntityFields::class, SetEntityWikidata::class, CreateRelationship::class, MergeDuplicateEntities::class] as $toolClass) {
            $this->assertTrue(
                $tools->contains(fn ($t) => $t instanceof $toolClass),
                "{$toolClass} must be in the tools list"
            );
        }

        // Every staging tool has the context injected.
        $stagingTools = $tools->filter(fn ($t) => ! ($t instanceof GetEntityContext) && ! ($t instanceof VerifyWikidata));
        foreach ($stagingTools as $tool) {
            $reflection = new \ReflectionProperty($tool, 'context');
            $reflection->setAccessible(true);
            $injected = $reflection->getValue($tool);
            $this->assertSame($context, $injected, get_class($tool).' must have context injected');
        }
    }

    /**
     * EntityEditorAgent::instructions() must include the entity ID so the model
     * always knows which entity it is operating on.
     */
    public function test_entity_editor_agent_instructions_contain_entity_id(): void
    {
        $this->fakeWikidata();

        $user = $this->userWithRole('admin');
        $entity = $this->makeEntity();

        $agent = new EntityEditorAgent($entity, $user, [
            'user_id' => (string) $user->id,
            'context_type' => 'entity',
            'context_id' => $entity->entity_id,
            'conversation_id' => null,
        ]);

        $instructions = $agent->instructions();

        $this->assertStringContainsString($entity->entity_id, $instructions);
        $this->assertStringContainsString('Roman Empire', $instructions);
    }

    // ── Feature: HTTP endpoint ────────────────────────────────────────────────

    /**
     * A valid entity chat POST returns a streaming 200 response.
     * We fake the agent so no real provider call is made.
     */
    public function test_chat_endpoint_streams_200_for_entity_context(): void
    {
        $this->fakeWikidata();

        // Fake the agent BEFORE the request so the FakeTextGateway intercepts.
        EntityEditorAgent::fake(['Hello from the fake agent.']);

        // Use a user with entities.write permission so the gate passes.
        $user = $this->userWithPermissions(['entities.write']);
        $entity = $this->makeEntity();

        $response = $this->actingAs($user)
            ->postJson('/ai/chat', [
                'context_type' => 'entity',
                'context_id' => $entity->entity_id,
                'prompt' => 'Tell me about this entity.',
            ]);

        $response->assertOk();
        $response->assertHeader('Content-Type', 'text/event-stream; charset=utf-8');
    }

    /**
     * A user without entities.write must be forbidden from using the chat endpoint.
     */
    public function test_chat_endpoint_returns_403_without_entities_write(): void
    {
        $this->fakeWikidata();

        $user = $this->userWithRole('user');
        $entity = $this->makeEntity();

        $this->actingAs($user)
            ->postJson('/ai/chat', [
                'context_type' => 'entity',
                'context_id' => $entity->entity_id,
                'prompt' => 'Tell me about this entity.',
            ])
            ->assertForbidden();
    }

    /**
     * A valid chronicle chat POST returns a streaming 200 response (Task 9: ChronicleEditorAgent).
     * Previously this returned 422 — that placeholder has been replaced.
     */
    public function test_chat_endpoint_streams_200_for_chronicle_context(): void
    {
        $this->fakeWikidata();

        ChronicleEditorAgent::fake(['Hello from the chronicle agent.']);

        $user = $this->userWithPermissions(['entities.write']);
        $entity = $this->makeEntity();
        $chronicle = $this->makeChronicleWithEntity($entity);

        $response = $this->actingAs($user)
            ->postJson('/ai/chat', [
                'context_type' => 'chronicle',
                'context_id' => $chronicle->chronicle_id,
                'prompt' => 'Help me curate the entities in this chronicle.',
            ]);

        $response->assertOk();
        $response->assertHeader('Content-Type', 'text/event-stream; charset=utf-8');
    }

    /**
     * Unauthenticated requests must be redirected (standard Inertia/web auth behaviour).
     */
    public function test_chat_endpoint_requires_authentication(): void
    {
        $this->postJson('/ai/chat', [
            'context_type' => 'entity',
            'context_id' => 'any',
            'prompt' => 'Hello',
        ])->assertUnauthorized();
    }

    /**
     * Missing required fields must return a validation error.
     */
    public function test_chat_endpoint_validates_required_fields(): void
    {
        $user = $this->userWithRole('admin');

        $this->actingAs($user)
            ->postJson('/ai/chat', [])
            ->assertUnprocessable();
    }

    // ── Unit: ChronicleEditorAgent ────────────────────────────────────────────

    /**
     * ChronicleEditorAgent::instructions() must contain the chronicle ID, its title,
     * and at least one referenced entity ID.
     */
    public function test_chronicle_editor_agent_instructions_contain_chronicle_and_entity_ids(): void
    {
        $this->fakeWikidata();

        $user = $this->userWithRole('admin');
        $entity = $this->makeEntity();
        $chronicle = $this->makeChronicleWithEntity($entity);

        $agent = new ChronicleEditorAgent($chronicle, $user, [
            'user_id' => (string) $user->id,
            'context_type' => 'chronicle',
            'context_id' => $chronicle->chronicle_id,
            'conversation_id' => null,
        ]);

        $instructions = $agent->instructions();

        $this->assertStringContainsString($chronicle->chronicle_id, $instructions);
        $this->assertStringContainsString('Rise of Rome', $instructions);
        $this->assertStringContainsString($entity->entity_id, $instructions);
    }

    /**
     * ChronicleEditorAgent::tools() must return 7 tools with context injected into
     * every staging tool (all tools except VerifyWikidata).
     */
    public function test_chronicle_editor_agent_tools_have_context_injected(): void
    {
        $this->fakeWikidata();

        $user = $this->userWithRole('admin');
        $entity = $this->makeEntity();
        $chronicle = $this->makeChronicleWithEntity($entity);

        $context = [
            'user_id' => (string) $user->id,
            'context_type' => 'chronicle',
            'context_id' => $chronicle->chronicle_id,
            'conversation_id' => null,
        ];

        $agent = new ChronicleEditorAgent($chronicle, $user, $context);
        $tools = collect($agent->tools());

        // Expect 7 tools (no GetEntityContext, but VerifyWikidata + 6 staging tools).
        $this->assertCount(7, $tools);

        // VerifyWikidata present.
        $this->assertTrue(
            $tools->contains(fn ($t) => $t instanceof VerifyWikidata),
            'VerifyWikidata must be in the tools list'
        );

        // All six staging tools present.
        foreach ([CreateEntity::class, SetEntityLocation::class, UpdateEntityFields::class, SetEntityWikidata::class, CreateRelationship::class, MergeDuplicateEntities::class] as $toolClass) {
            $this->assertTrue(
                $tools->contains(fn ($t) => $t instanceof $toolClass),
                "{$toolClass} must be in the tools list"
            );
        }

        // Every staging tool (all except VerifyWikidata) has context injected.
        $stagingTools = $tools->filter(fn ($t) => ! ($t instanceof VerifyWikidata));
        foreach ($stagingTools as $tool) {
            $reflection = new \ReflectionProperty($tool, 'context');
            $reflection->setAccessible(true);
            $injected = $reflection->getValue($tool);
            $this->assertSame($context, $injected, get_class($tool).' must have context injected');
        }
    }
}

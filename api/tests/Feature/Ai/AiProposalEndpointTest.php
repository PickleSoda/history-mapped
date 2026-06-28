<?php

namespace Tests\Feature\Ai;

use App\Models\Ai\ProposedChange;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class AiProposalEndpointTest extends TestCase
{
    use RefreshDatabase;

    // ── Helpers ───────────────────────────────────────────────────────────────

    /**
     * Stub Wikidata HTTP so CreateEntity::buildParts doesn't hit the network.
     */
    private function fakeWikidata(): void
    {
        Http::fake(['*' => Http::response(['entities' => []])]);
    }

    /**
     * Stage a ProposedChange owned by $user with a single create_entity part.
     * Returns [ProposedChange, ProposedChangePart].
     */
    private function stageCreateEntityProposal(User $user): array
    {
        $change = ProposedChange::create([
            'user_id' => $user->id,
            'context_type' => 'entity',
            'context_id' => 'test',
        ]);

        $part = $change->parts()->create([
            'key' => 'entity',
            'tool' => 'create_entity',
            'payload' => [
                'name' => 'Test Empire',
                'entity_type' => 'political_entity',
            ],
            'human_diff' => ['summary' => 'Create entity "Test Empire"'],
            'status' => 'pending',
        ]);

        return [$change, $part];
    }

    /**
     * Stage a ProposedChange owned by $user with a single create_chronicle part.
     * Returns [ProposedChange, ProposedChangePart].
     */
    private function stageCreateChronicleProposal(User $user): array
    {
        $change = ProposedChange::create([
            'user_id' => $user->id,
            'context_type' => 'chronicle',
            'context_id' => 'test',
        ]);

        $part = $change->parts()->create([
            'key' => 'chronicle',
            'tool' => 'create_chronicle',
            'payload' => [
                'title' => 'Test Chronicle',
            ],
            'human_diff' => ['summary' => 'Create chronicle "Test Chronicle"'],
            'status' => 'pending',
        ]);

        return [$change, $part];
    }

    /**
     * Stage a ProposedChange with a set_entity_location part (non-creator tool).
     * Requires a pre-existing entity. Returns [ProposedChange, ProposedChangePart].
     */
    private function stageSetEntityLocationProposal(User $user, Entity $entity): array
    {
        $change = ProposedChange::create([
            'user_id' => $user->id,
            'context_type' => 'entity',
            'context_id' => $entity->entity_id,
        ]);

        $part = $change->parts()->create([
            'key' => 'location',
            'tool' => 'set_entity_location',
            'payload' => [
                'entity_id' => $entity->entity_id,
                'lon' => 12.4964,
                'lat' => 41.9028,
            ],
            'human_diff' => ['summary' => 'Set location'],
            'status' => 'pending',
        ]);

        return [$change, $part];
    }

    // ── Tests ─────────────────────────────────────────────────────────────────

    /**
     * Key provenance test: applying via the HTTP endpoint must write
     * created_by = 'agent:{user->id}' — not a null or stub value.
     * This verifies ProposalApplier injects auth()->id() end-to-end.
     */
    public function test_apply_runs_action_and_wires_acting_user_provenance(): void
    {
        $this->fakeWikidata();
        $user = $this->userWithPermissions(['entities.write']);

        [$change, $part] = $this->stageCreateEntityProposal($user);

        $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/{$part->key}/apply")
            ->assertOk()
            ->assertJsonPath('status', 'applied')
            ->assertJsonStructure(['status', 'result_id']);

        $part->refresh();
        $this->assertSame('applied', $part->status);
        $this->assertNotNull($part->result_id);

        // The entity must exist and carry the real user id as provenance.
        $entity = Entity::find($part->result_id);
        $this->assertNotNull($entity, 'Entity should have been created by the apply action');
        $this->assertSame('agent:'.$user->id, $entity->created_by);
    }

    public function test_discard_marks_part_discarded_and_creates_no_entity(): void
    {
        $this->fakeWikidata();
        $user = $this->userWithPermissions(['entities.write']);

        [$change, $part] = $this->stageCreateEntityProposal($user);

        $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/{$part->key}/discard")
            ->assertOk()
            ->assertJsonPath('status', 'discarded');

        $this->assertSame('discarded', $part->fresh()->status);
        $this->assertNull($part->fresh()->result_id);
        $this->assertDatabaseMissing('entities', ['name' => 'Test Empire']);
    }

    public function test_apply_requires_entities_write_permission(): void
    {
        $this->fakeWikidata();
        // 'user' role has no extra permissions
        $user = $this->userWithRole('user');

        [$change, $part] = $this->stageCreateEntityProposal($user);

        $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/{$part->key}/apply")
            ->assertForbidden();
    }

    public function test_apply_rejects_another_users_proposal(): void
    {
        $this->fakeWikidata();
        $owner = $this->userWithPermissions(['entities.write']);
        $other = $this->userWithPermissions(['entities.write']);

        [$change, $part] = $this->stageCreateEntityProposal($owner);

        // `other` has the permission but doesn't own this proposal
        $this->actingAs($other)
            ->postJson("/ai/proposals/{$change->id}/parts/{$part->key}/apply")
            ->assertForbidden();
    }

    public function test_discard_rejects_another_users_proposal(): void
    {
        $owner = $this->userWithRole('user');
        $other = $this->userWithRole('user');

        [$change, $part] = $this->stageCreateEntityProposal($owner);

        $this->actingAs($other)
            ->postJson("/ai/proposals/{$change->id}/parts/{$part->key}/discard")
            ->assertForbidden();
    }

    public function test_discard_allowed_for_owner_without_entities_write(): void
    {
        $user = $this->userWithRole('user');

        [$change, $part] = $this->stageCreateEntityProposal($user);

        $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/{$part->key}/discard")
            ->assertOk()
            ->assertJsonPath('status', 'discarded');

        $this->assertSame('discarded', $part->fresh()->status);
    }

    public function test_apply_create_entity_returns_redirect_url(): void
    {
        $this->fakeWikidata();
        $user = $this->userWithPermissions(['entities.write']);

        [$change, $part] = $this->stageCreateEntityProposal($user);

        $response = $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/{$part->key}/apply")
            ->assertOk()
            ->assertJsonStructure(['status', 'result_id', 'redirect_url']);

        $part->refresh();
        $entityId = $part->result_id;
        $this->assertNotNull($entityId);

        $expected = route('entities.edit', $entityId);
        $response->assertJsonPath('redirect_url', $expected);
    }

    public function test_apply_create_chronicle_returns_redirect_url(): void
    {
        $user = $this->userWithPermissions(['entities.write']);

        [$change, $part] = $this->stageCreateChronicleProposal($user);

        $response = $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/{$part->key}/apply")
            ->assertOk()
            ->assertJsonStructure(['status', 'result_id', 'redirect_url']);

        $part->refresh();
        $chronicleId = $part->result_id;
        $this->assertNotNull($chronicleId);

        $chronicle = Chronicle::findOrFail($chronicleId);
        $expected = route('chronicles.edit', $chronicle->slug);
        $response->assertJsonPath('redirect_url', $expected);
    }

    public function test_apply_returns_created_ref_for_global_session_create_entity(): void
    {
        $this->fakeWikidata();
        $user = $this->userWithPermissions(['entities.write']);

        $change = ProposedChange::create([
            'user_id' => $user->id,
            'context_type' => 'global',
            'context_id' => 'global-session-uuid',
        ]);

        $part = $change->parts()->create([
            'key' => 'entity',
            'tool' => 'create_entity',
            'payload' => [
                'name' => 'Test Empire',
                'entity_type' => 'political_entity',
            ],
            'human_diff' => ['summary' => 'Create Rome'],
            'status' => 'pending',
            'result_id' => null,
        ]);

        $response = $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/entity/apply");

        $response->assertOk();
        $this->assertSame('applied', $response->json('status'));
        $this->assertNull($response->json('redirect_url'));
        $this->assertSame('entity', $response->json('created_ref.type'));
        $this->assertSame($response->json('result_id'), $response->json('created_ref.id'));
        $this->assertStringContainsString('entities', $response->json('created_ref.url'));
        $this->assertNotEmpty($response->json('created_ref.label'));
    }

    public function test_apply_returns_redirect_url_not_created_ref_for_scoped_session(): void
    {
        $this->fakeWikidata();
        $user = $this->userWithPermissions(['entities.write']);

        $change = ProposedChange::create([
            'user_id' => $user->id,
            'context_type' => 'entity',
            'context_id' => 'some-entity-id',
        ]);

        $part = $change->parts()->create([
            'key' => 'entity',
            'tool' => 'create_entity',
            'payload' => [
                'name' => 'Test Empire',
                'entity_type' => 'political_entity',
            ],
            'human_diff' => ['summary' => 'Create Carthage'],
            'status' => 'pending',
            'result_id' => null,
        ]);

        $response = $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/entity/apply");

        $response->assertOk();
        $this->assertNotNull($response->json('redirect_url'));
        $this->assertNull($response->json('created_ref'));
    }

    public function test_apply_non_creator_tool_returns_null_redirect_url(): void
    {
        $this->fakeWikidata();
        $user = $this->userWithPermissions(['entities.write']);

        // First create an entity to reference in the location update.
        [$createChange, $createPart] = $this->stageCreateEntityProposal($user);
        $this->actingAs($user)
            ->postJson("/ai/proposals/{$createChange->id}/parts/{$createPart->key}/apply")
            ->assertOk();
        $createPart->refresh();
        $entity = Entity::findOrFail($createPart->result_id);

        // Now stage a set_entity_location part (non-creator).
        [$change, $part] = $this->stageSetEntityLocationProposal($user, $entity);

        $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/{$part->key}/apply")
            ->assertOk()
            ->assertJsonPath('redirect_url', null);
    }
}

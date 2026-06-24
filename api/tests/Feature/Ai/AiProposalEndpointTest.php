<?php

namespace Tests\Feature\Ai;

use App\Models\Ai\ProposedChange;
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
}

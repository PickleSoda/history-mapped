<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Contribution;
use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * Text corrections submitted from the public atlas.
 */
class ContributionApiTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = $this->userWithRole('user');
    }

    public function test_a_contribution_is_stored_as_a_diff_against_the_current_text(): void
    {
        $entity = Entity::factory()->create(['name' => 'Marathon', 'summary' => 'The battle was fougth in 490 BC.']);

        $res = $this->actingAs($this->user)->postJson('/api/v1/contributions', [
            'target_type' => 'entity',
            'target_id' => $entity->entity_id,
            'field' => 'summary',
            'proposed_text' => 'The battle was fought in 490 BC.',
            'note' => 'Typo',
        ])->assertCreated()
            ->assertJsonPath('data.status', 'pending')
            ->assertJsonPath('data.target_label', 'Marathon')
            ->assertJsonPath('data.base_text', 'The battle was fougth in 490 BC.')
            ->assertJsonPath('data.stats', ['added' => 1, 'removed' => 1])
            ->assertJsonPath('data.note', 'Typo');

        $this->assertSame(
            [['=', 'The battle was '], ['-', 'fougth'], ['+', 'fought'], ['=', ' in 490 BC.']],
            $res->json('data.diff'),
        );
        // Submitting never touches the record itself.
        $this->assertSame('The battle was fougth in 490 BC.', $entity->fresh()->summary);
    }

    public function test_chronicle_steps_can_be_corrected(): void
    {
        $chronicle = Chronicle::factory()->create(['title' => 'Persian Wars']);
        $entry = ChronicleEntry::factory()->create([
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => 1,
            'narrative_text' => 'Darius sends heralds.',
        ]);

        $this->actingAs($this->user)->postJson('/api/v1/contributions', [
            'target_type' => 'chronicle_entry',
            'target_id' => $entry->entry_id,
            'field' => 'narrative_text',
            'proposed_text' => 'Darius I sends heralds.',
        ])->assertCreated()->assertJsonPath('data.target_label', 'Persian Wars · step 1');
    }

    public function test_invalid_contributions_are_rejected(): void
    {
        $entity = Entity::factory()->create(['name' => 'Marathon', 'summary' => 'Same.']);
        $base = ['target_type' => 'entity', 'target_id' => $entity->entity_id];
        $this->actingAs($this->user);

        $this->postJson('/api/v1/contributions', [...$base, 'field' => 'summary', 'proposed_text' => 'Same.'])
            ->assertUnprocessable()->assertJsonValidationErrors('proposed_text');
        $this->postJson('/api/v1/contributions', [...$base, 'field' => 'wikidata_id', 'proposed_text' => 'Q1'])
            ->assertUnprocessable()->assertJsonValidationErrors('field');
        $this->postJson('/api/v1/contributions', [...$base, 'field' => 'name', 'proposed_text' => '   '])
            ->assertUnprocessable()->assertJsonValidationErrors('proposed_text');
        $this->postJson('/api/v1/contributions', [...$base, 'field' => 'name', 'proposed_text' => str_repeat('x', 256)])
            ->assertUnprocessable()->assertJsonValidationErrors('proposed_text');
        $this->postJson('/api/v1/contributions', [
            'target_type' => 'entity', 'target_id' => 'nope', 'field' => 'summary', 'proposed_text' => 'x',
        ])->assertUnprocessable()->assertJsonValidationErrors('target_id');

        $this->assertSame(0, Contribution::count());
    }

    public function test_submitting_requires_the_contribute_permission(): void
    {
        $entity = Entity::factory()->create();
        $payload = [
            'target_type' => 'entity', 'target_id' => $entity->entity_id,
            'field' => 'summary', 'proposed_text' => 'New text',
        ];

        $this->postJson('/api/v1/contributions', $payload)->assertUnauthorized();
        $this->actingAs($this->userWithPermissions([]))
            ->postJson('/api/v1/contributions', $payload)
            ->assertForbidden();
    }

    public function test_contributors_list_and_withdraw_their_own(): void
    {
        $entity = Entity::factory()->create(['summary' => 'Old']);
        $this->actingAs($this->user);
        $id = $this->postJson('/api/v1/contributions', [
            'target_type' => 'entity', 'target_id' => $entity->entity_id,
            'field' => 'summary', 'proposed_text' => 'New',
        ])->json('data.id');

        $this->getJson('/api/v1/me/contributions')->assertOk()->assertJsonCount(1, 'data');

        $this->actingAs($this->userWithRole('user'))
            ->postJson("/api/v1/me/contributions/{$id}/withdraw")
            ->assertNotFound();

        $this->actingAs($this->user)
            ->postJson("/api/v1/me/contributions/{$id}/withdraw")
            ->assertOk()->assertJsonPath('data.status', 'withdrawn');
        $this->postJson("/api/v1/me/contributions/{$id}/withdraw")
            ->assertUnprocessable()->assertJsonValidationErrors('status');

        $this->getJson('/api/v1/me/contributions?status=pending')->assertJsonCount(0, 'data');
    }
}

<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Actions\Contribution\SubmitContributionAction;
use App\Enums\ContributionTargetType;
use App\Models\Contribution;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

/**
 * Staff review of submitted text corrections in the admin panel.
 */
class ContributionReviewTest extends TestCase
{
    use RefreshDatabase;

    private User $reviewer;

    protected function setUp(): void
    {
        parent::setUp();
        $this->reviewer = $this->userWithRole('moderator');
    }

    private function submit(Entity $entity, string $field, string $text): Contribution
    {
        return app(SubmitContributionAction::class)(
            $this->userWithRole('user'), ContributionTargetType::Entity, $entity->entity_id, $field, $text,
        );
    }

    public function test_only_reviewers_reach_the_queue(): void
    {
        $this->actingAs($this->userWithRole('user'))->get('/contributions')->assertForbidden();
        $this->actingAs($this->userWithRole('geo_moderator'))->get('/contributions')->assertForbidden();
        $this->actingAs($this->userWithRole('history_moderator'))->get('/contributions')->assertOk();
    }

    public function test_index_lists_pending_contributions_with_counts(): void
    {
        $entity = Entity::factory()->create(['name' => 'Marathon', 'summary' => 'Old']);
        $this->submit($entity, 'summary', 'New');
        $done = $this->submit($entity, 'name', 'Battle of Marathon');
        $done->update(['status' => 'rejected']);

        $this->actingAs($this->reviewer)->get('/contributions')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('contributions/index')
                ->where('filters.status', 'pending')
                ->where('counts.pending', 1)
                ->where('counts.rejected', 1)
                ->has('contributions.data', 1)
                ->where('contributions.data.0.target_label', 'Marathon')
                ->where('contributions.data.0.is_stale', false)
                ->where('contributions.data.0.stats', ['added' => 1, 'removed' => 1])
            );

        $this->actingAs($this->reviewer)->get('/contributions?status=all')
            ->assertInertia(fn (Assert $page) => $page->has('contributions.data', 2));
    }

    public function test_show_renders_the_diff_and_flags_stale_text(): void
    {
        $entity = Entity::factory()->create(['summary' => 'Rome fell in 476.']);
        $c = $this->submit($entity, 'summary', 'Rome fell in AD 476.');

        $this->actingAs($this->reviewer)->get("/contributions/{$c->id}")
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('contributions/show')
                ->where('contribution.diff', [['=', 'Rome fell in '], ['+', 'AD '], ['=', '476.']])
                ->where('contribution.is_stale', false)
                ->where('current_diff', null)
                ->where('current_text', 'Rome fell in 476.')
                ->where('public_url', config('app.frontend_url').'/?sel='.$entity->entity_id.'&full=1')
            );

        $entity->update(['summary' => 'The Western Empire fell in 476.']);

        $this->actingAs($this->reviewer)->get("/contributions/{$c->id}")
            ->assertInertia(fn (Assert $page) => $page
                ->where('contribution.is_stale', true)
                ->where('current_text', 'The Western Empire fell in 476.')
                ->whereNot('current_diff', null)
            );
    }

    public function test_approving_applies_the_proposed_text(): void
    {
        $entity = Entity::factory()->create(['summary' => 'Old text.']);
        $c = $this->submit($entity, 'summary', 'New text.');

        $this->actingAs($this->reviewer)
            ->post("/contributions/{$c->id}/approve", ['review_note' => 'Thanks!'])
            ->assertRedirect("/contributions/{$c->id}");

        $this->assertSame('New text.', $entity->fresh()->summary);
        $c->refresh();
        $this->assertSame('approved', $c->status->value);
        $this->assertSame($this->reviewer->id, $c->reviewer_id);
        $this->assertSame('Thanks!', $c->review_note);
        $this->assertNotNull($c->reviewed_at);

        // A second decision is refused.
        $this->actingAs($this->reviewer)
            ->post("/contributions/{$c->id}/reject")
            ->assertSessionHasErrors('status');
    }

    public function test_a_stale_contribution_needs_an_explicit_overwrite(): void
    {
        $entity = Entity::factory()->create(['summary' => 'Original.']);
        $c = $this->submit($entity, 'summary', 'Proposed.');
        $entity->update(['summary' => 'Edited meanwhile.']);

        $this->actingAs($this->reviewer)
            ->from("/contributions/{$c->id}")
            ->post("/contributions/{$c->id}/approve")
            ->assertSessionHasErrors('conflict');
        $this->assertSame('Edited meanwhile.', $entity->fresh()->summary);
        $this->assertTrue($c->fresh()->isPending());

        $this->actingAs($this->reviewer)
            ->post("/contributions/{$c->id}/approve", ['force' => true])
            ->assertSessionHasNoErrors();
        $this->assertSame('Proposed.', $entity->fresh()->summary);
    }

    public function test_rejecting_leaves_the_record_untouched(): void
    {
        $entity = Entity::factory()->create(['name' => 'Marathon']);
        $c = $this->submit($entity, 'name', 'Maraton');

        $this->actingAs($this->reviewer)
            ->post("/contributions/{$c->id}/reject", ['review_note' => 'The spelling is correct.'])
            ->assertRedirect("/contributions/{$c->id}");

        $this->assertSame('Marathon', $entity->fresh()->name);
        $this->assertSame('rejected', $c->fresh()->status->value);
        $this->assertSame('The spelling is correct.', $c->fresh()->review_note);
    }

    public function test_approving_a_relationship_description(): void
    {
        [$a, $b] = Entity::factory()->count(2)->create();
        $rel = EntityRelationship::create([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $a->entity_id,
            'target_entity_id' => $b->entity_id,
            'relationship_type' => 'allied_with',
            'description' => 'Allied.',
        ]);
        $c = app(SubmitContributionAction::class)(
            $this->userWithRole('user'), ContributionTargetType::Relationship, $rel->relationship_id, 'description', 'Allied in 480 BC.',
        );

        $this->actingAs($this->reviewer)->post("/contributions/{$c->id}/approve")->assertSessionHasNoErrors();

        $this->assertSame('Allied in 480 BC.', $rel->fresh()->description);
    }
}

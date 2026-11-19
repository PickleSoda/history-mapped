<?php

declare(strict_types=1);

namespace Tests\Feature\Contribution;

use App\Actions\Contribution\CloseContributionAction;
use App\Actions\Contribution\ProposeEntityAction;
use App\Actions\Contribution\ProposeRelationshipAction;
use App\Actions\Contribution\SubmitContributionAction;
use App\Enums\ContributionSource;
use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use App\Models\Contribution;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

/** Proposals for new entities and relationships: record, review (approve / reject) and show. */
class ProposalReviewTest extends TestCase
{
    use RefreshDatabase;

    private User $author;

    private User $moderator;

    protected function setUp(): void
    {
        parent::setUp();
        $this->author = $this->userWithRole('user');
        $this->moderator = $this->userWithRole('moderator');
    }

    private function propose(array $extra = [], ?User $as = null, bool $ack = false): Contribution
    {
        return app(ProposeEntityAction::class)($as ?? $this->author, $extra + [
            'name' => 'Aethelbald of Wessex', 'entity_type' => 'person',
            'temporal_start' => '839', 'temporal_end' => '860', 'summary' => 'King of Wessex.',
            'location_name' => 'Wessex', 'geojson' => ['type' => 'Point', 'coordinates' => [-1.31, 51.06]],
            'wikidata_id' => 'Q123456', 'alternative_names' => ['Æthelbald'],
            'source_citations' => [['title' => 'ASC', 'url' => 'https://example.org/asc']],
        ], 'a note', $ack, ContributionSource::Mcp, 'Claude');
    }

    private function link(string|int $source, string|int $target, ?User $as = null): Contribution
    {
        return app(ProposeRelationshipAction::class)($as ?? $this->author, [
            'source' => (string) $source, 'target' => (string) $target, 'relationship_type' => 'participated_in',
            'temporal_start' => '871', 'description' => 'He fought there.',
        ], null, ContributionSource::Mcp, 'Claude');
    }

    private function approve(Contribution $c, ?string $note = null)
    {
        return $this->actingAs($this->moderator)->post("/contributions/{$c->id}/approve", ['review_note' => $note]);
    }

    // ── approving an entity ──────────────────────────────────────────────

    public function test_approving_an_entity_proposal_creates_it_verified_and_credited_to_the_contributor(): void
    {
        $c = $this->propose();

        $this->approve($c, 'Looks right.')->assertRedirect("/contributions/{$c->id}");

        $c->refresh();
        $this->assertSame(ContributionStatus::Approved, $c->status);
        $this->assertSame($this->moderator->id, $c->reviewer_id);
        $this->assertSame('Looks right.', $c->review_note);

        $entity = Entity::query()->findOrFail($c->target_id);
        $this->assertSame('Aethelbald of Wessex', $entity->name);
        $this->assertSame(EntityType::Person, $entity->entity_type);
        $this->assertSame(VerificationStatus::HumanVerified, $entity->verification_status);
        $this->assertSame((string) $this->author->id, $entity->created_by);
        $this->assertSame('Q123456', $entity->wikidata_id);
        $this->assertSame('King of Wessex.', $entity->summary);
        $this->assertSame(839, (int) $entity->temporalRanges()->where('is_primary', true)->value('start_year'));
        $this->assertSame(['Æthelbald'], $entity->aliases()->pluck('name')->all());
        $this->assertTrue($entity->locations()->where('is_primary', true)->exists());
    }

    public function test_a_proposal_cannot_be_approved_twice(): void
    {
        $c = $this->propose();
        $this->approve($c)->assertRedirect();

        $this->approve($c)->assertSessionHasErrors('status');
        $this->assertSame(1, Entity::query()->where('name', 'Aethelbald of Wessex')->count());
    }

    public function test_approval_is_refused_when_the_qid_has_appeared_in_the_meantime(): void
    {
        $c = $this->propose();
        Entity::factory()->create(['wikidata_id' => 'Q123456']);

        $this->approve($c)->assertSessionHasErrors('payload');
        $this->assertSame(ContributionStatus::Pending, $c->fresh()->status);
        $this->assertNull($c->fresh()->target_id);
    }

    public function test_only_reviewers_can_approve_or_reject_proposals(): void
    {
        $c = $this->propose();

        $this->actingAs($this->author)->post("/contributions/{$c->id}/approve")->assertForbidden();
        $this->actingAs($this->author)->post("/contributions/{$c->id}/reject")->assertForbidden();
        $this->assertSame(ContributionStatus::Pending, $c->fresh()->status);
        $this->assertSame(0, Entity::query()->where('name', 'Aethelbald of Wessex')->count());
    }

    // ── approving a relationship ─────────────────────────────────────────

    public function test_approving_a_relationship_between_existing_entities_creates_it(): void
    {
        $a = Entity::factory()->ofType(EntityType::Person)->create(['name' => 'A']);
        $b = Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'B']);
        $c = $this->link($a->entity_id, $b->entity_id);

        $this->approve($c)->assertRedirect();

        $rel = EntityRelationship::query()->findOrFail($c->fresh()->target_id);
        $this->assertSame($a->entity_id, $rel->source_entity_id);
        $this->assertSame($b->entity_id, $rel->target_entity_id);
        $this->assertSame('participated_in', $rel->relationship_type->value);
        $this->assertSame('871', $rel->temporal_start);
        $this->assertSame((string) $this->author->id, $rel->created_by);
        $this->assertSame(ContributionStatus::Approved, $c->fresh()->status);
    }

    public function test_a_relationship_to_a_pending_entity_proposal_cannot_be_approved_first(): void
    {
        $b = Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'B']);
        $entityProposal = $this->propose();
        $rel = $this->link($entityProposal->id, $b->entity_id);

        $this->approve($rel)->assertSessionHasErrors('dependency');
        $this->assertSame(ContributionStatus::Pending, $rel->fresh()->status);
        $this->assertSame(0, EntityRelationship::query()->count());

        // The entity first, then the relationship resolves to the entity that was created.
        $this->approve($entityProposal)->assertSessionHasNoErrors();
        $this->approve($rel)->assertSessionHasNoErrors();

        $created = $entityProposal->fresh()->target_id;
        $this->assertSame($created, EntityRelationship::query()->sole()->source_entity_id);
        $this->assertSame(ContributionStatus::Approved, $rel->fresh()->status);
    }

    public function test_the_review_page_of_a_blocked_relationship_says_so(): void
    {
        $b = Entity::factory()->create(['name' => 'B']);
        $entityProposal = $this->propose();
        $rel = $this->link($entityProposal->id, $b->entity_id);

        $this->actingAs($this->moderator)->get("/contributions/{$rel->id}")
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('proposal.blocked', true)
                ->where('proposal.depends_on.0.id', $entityProposal->id)
                ->where('proposal.depends_on.0.status', 'pending'));
    }

    public function test_a_relationship_that_already_exists_cannot_be_approved(): void
    {
        $a = Entity::factory()->create(['name' => 'A']);
        $b = Entity::factory()->create(['name' => 'B']);
        $c = $this->link($a->entity_id, $b->entity_id);
        EntityRelationship::create([
            'relationship_id' => (string) Str::uuid(), 'source_entity_id' => $a->entity_id,
            'target_entity_id' => $b->entity_id, 'relationship_type' => 'participated_in', 'confidence' => 'high',
        ]);

        $this->approve($c)->assertSessionHasErrors('payload');
        $this->assertSame(ContributionStatus::Pending, $c->fresh()->status);
    }

    // ── rejecting, and the dependency rule ───────────────────────────────

    public function test_rejecting_an_entity_proposal_creates_nothing_and_keeps_the_note(): void
    {
        $c = $this->propose();

        $this->actingAs($this->moderator)->post("/contributions/{$c->id}/reject", ['review_note' => 'Not notable.'])->assertRedirect();

        $c->refresh();
        $this->assertSame(ContributionStatus::Rejected, $c->status);
        $this->assertSame('Not notable.', $c->review_note);
        $this->assertNull($c->target_id);
        $this->assertSame(0, Entity::query()->where('name', 'Aethelbald of Wessex')->count());
    }

    public function test_rejecting_an_entity_proposal_closes_the_relationship_proposals_that_depend_on_it(): void
    {
        $b = Entity::factory()->create(['name' => 'B']);
        $entityProposal = $this->propose();
        $dependent = $this->link($entityProposal->id, $b->entity_id);
        $unrelated = $this->link($b->entity_id, Entity::factory()->create()->entity_id);

        $this->actingAs($this->moderator)->post("/contributions/{$entityProposal->id}/reject", ['review_note' => 'No.']);

        $dependent->refresh();
        $this->assertSame(ContributionStatus::Rejected, $dependent->status);
        $this->assertStringContainsString("#{$entityProposal->id}", (string) $dependent->review_note);
        $this->assertSame($this->moderator->id, $dependent->reviewer_id);
        $this->assertSame(ContributionStatus::Pending, $unrelated->fresh()->status);
    }

    public function test_withdrawing_an_entity_proposal_withdraws_its_dependents(): void
    {
        $b = Entity::factory()->create(['name' => 'B']);
        $entityProposal = $this->propose();
        $dependent = $this->link($b->entity_id, $entityProposal->id);

        app(CloseContributionAction::class)->withdraw($entityProposal);

        $this->assertSame(ContributionStatus::Withdrawn, $dependent->fresh()->status);
    }

    public function test_a_closed_dependency_blocks_approval_with_a_clear_message(): void
    {
        $b = Entity::factory()->create(['name' => 'B']);
        $entityProposal = $this->propose();
        $dependent = $this->link($entityProposal->id, $b->entity_id);
        // Closed behind the relationship's back (not through CloseContributionAction).
        $entityProposal->update(['status' => 'rejected']);

        $this->approve($dependent)->assertSessionHasErrors('dependency');
        $this->assertSame(ContributionStatus::Pending, $dependent->fresh()->status);
    }

    // ── admin pages ──────────────────────────────────────────────────────

    public function test_the_queue_lists_proposals_with_source_and_summary_and_filters_by_kind(): void
    {
        $this->propose();
        $entity = Entity::factory()->create(['summary' => 'Old']);
        app(SubmitContributionAction::class)($this->author, ContributionTargetType::Entity, $entity->entity_id, 'summary', 'New');

        $this->actingAs($this->moderator)->get('/contributions')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('counts.pending', 2)
                ->has('contributions.data', 2)
                ->where('contributions.data.0.kind', 'create')
                ->where('contributions.data.0.source', 'mcp')
                ->where('contributions.data.0.client', 'Claude')
                ->where('contributions.data.0.target_label', 'Aethelbald of Wessex')
                ->where('contributions.data.0.summary', 'New person: Aethelbald of Wessex, 839–860')
                ->where('contributions.data.1.kind', 'edit')
                ->where('contributions.data.1.source', 'atlas'));

        $this->actingAs($this->moderator)->get('/contributions?kind=create')
            ->assertInertia(fn (Assert $page) => $page->has('contributions.data', 1)->where('counts.pending', 1));
    }

    public function test_the_review_page_shows_the_proposal_and_its_possible_duplicates(): void
    {
        $twin = Entity::factory()->ofType(EntityType::Person)->create(['name' => 'Aethelbald of Wessex']);
        $c = $this->propose(ack: true);

        $this->actingAs($this->moderator)->get("/contributions/{$c->id}")
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('contributions/show')
                ->where('contribution.kind', 'create')
                ->where('contribution.source', 'mcp')
                ->where('contribution.note', 'a note')
                ->where('proposal.blocked', false)
                ->where('proposal.possible_duplicates.0.entity_id', $twin->entity_id)
                ->where('proposal.possible_duplicates.0.admin_url', url('/entities/'.$twin->entity_id))
                ->where('proposal.rows', fn ($rows) => collect($rows)->contains(fn ($r) => $r['label'] === 'Name' && $r['value'] === 'Aethelbald of Wessex')
                    && collect($rows)->contains(fn ($r) => $r['label'] === 'Wikidata' && $r['value'] === 'Q123456')));
    }

    public function test_an_approved_proposal_page_links_to_the_created_record(): void
    {
        $c = $this->propose();
        $this->approve($c);
        $entityId = $c->fresh()->target_id;

        $this->actingAs($this->moderator)->get("/contributions/{$c->id}")
            ->assertInertia(fn (Assert $page) => $page
                ->where('contribution.status', 'approved')
                ->where('admin_url', url('/entities/'.$entityId)));
    }

    // ── API (the SPA's "my contributions") ───────────────────────────────

    public function test_my_contributions_in_the_api_keeps_edit_rows_unchanged_and_describes_proposals(): void
    {
        $entity = Entity::factory()->create(['name' => 'Marathon', 'summary' => 'Old']);
        app(SubmitContributionAction::class)($this->author, ContributionTargetType::Entity, $entity->entity_id, 'summary', 'New');
        $c = $this->propose();

        $rows = $this->actingAs($this->author)->getJson('/api/v1/me/contributions')->assertOk()->json('data');
        $byKind = collect($rows)->keyBy('kind');

        $edit = $byKind['edit'];
        $this->assertSame('summary', $edit['field']);
        $this->assertSame('Old', $edit['base_text']);
        $this->assertSame('New', $edit['proposed_text']);
        $this->assertSame($entity->entity_id, $edit['target_id']);
        $this->assertNotEmpty($edit['diff']);

        $create = $byKind['create'];
        $this->assertSame($c->id, $create['id']);
        $this->assertSame('entity', $create['target_type']);
        $this->assertNull($create['target_id']);
        $this->assertSame('', $create['field']);
        $this->assertSame([], $create['diff']);
        $this->assertSame('mcp', $create['source']);
        $this->assertSame('Aethelbald of Wessex', $create['target_label']);
        $this->assertSame('New person: Aethelbald of Wessex, 839–860', $create['summary']);
        $this->assertNotEmpty($create['proposal']);
    }

    public function test_a_contributor_can_withdraw_their_own_proposal_over_the_api(): void
    {
        $c = $this->propose();

        $this->actingAs($this->author)->postJson("/api/v1/me/contributions/{$c->id}/withdraw")
            ->assertOk()->assertJsonPath('data.status', 'withdrawn');
    }

    public function test_the_user_admin_page_lists_proposals_too(): void
    {
        $this->propose();
        $admin = $this->userWithRole('admin');

        $this->actingAs($admin)->get('/users/'.$this->author->id)->assertOk()
            ->assertInertia(fn (Assert $page) => $page->where('recent_contributions.0.kind', 'create'));
    }

    // ── validation (the action, shared with other entry points) ──────────

    public function test_the_action_rejects_bad_payloads(): void
    {
        $this->expectException(ValidationException::class);
        $this->propose(['entity_type' => 'nonsense']);
    }
}

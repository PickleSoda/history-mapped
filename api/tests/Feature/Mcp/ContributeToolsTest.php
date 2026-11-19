<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

use App\Actions\Contribution\SubmitContributionAction;
use App\Enums\ContributionKind;
use App\Enums\ContributionSource;
use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Enums\EntityType;
use App\Mcp\Servers\ContributeServer;
use App\Mcp\Tools\Contribute\MyContributions;
use App\Mcp\Tools\Contribute\ProposeEntity;
use App\Mcp\Tools\Contribute\ProposeRelationship;
use App\Mcp\Tools\Contribute\SuggestCorrection;
use App\Models\Contribution;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\User;
use Illuminate\Support\Str;
use Laravel\Passport\ClientRepository;
use Laravel\Passport\Passport;

/** The four contributor tools, called as a signed-in contributor. Nothing here creates an entity. */
class ContributeToolsTest extends ContributeTestCase
{
    private User $user;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = $this->userWithRole('user');
    }

    private function tool(string $tool, array $args, ?User $as = null)
    {
        return ContributeServer::actingAs($as ?? $this->user)->tool($tool, $args);
    }

    private function entityArgs(array $extra = []): array
    {
        return $extra + ['name' => 'Aethelbald of Wessex', 'entity_type' => 'person', 'start_year' => 839, 'end_year' => 860];
    }

    // ── suggest-correction ───────────────────────────────────────────────

    public function test_suggest_correction_records_an_edit_contribution_from_mcp(): void
    {
        $entity = Entity::factory()->create(['name' => 'Marathon', 'summary' => 'Old summary']);

        $this->tool(SuggestCorrection::class, [
            'target_type' => 'entity', 'target_id' => $entity->entity_id, 'field' => 'summary',
            'proposed_text' => 'A new summary.', 'note' => 'Per the Perseus text.',
        ])->assertOk()
            ->assertStructuredContentPath('status', 'pending')
            ->assertSee('nothing has changed');

        $c = Contribution::query()->sole();
        $this->assertSame(ContributionKind::Edit, $c->kind);
        $this->assertSame(ContributionSource::Mcp, $c->source);
        $this->assertSame('MCP client', $c->client);
        $this->assertSame('Old summary', $c->base_text);
        $this->assertSame($this->user->id, $c->user_id);
        $this->assertSame('Old summary', $entity->fresh()->summary, 'the record is untouched until approval');
    }

    public function test_suggest_correction_records_the_oauth_client_name(): void
    {
        $client = app(ClientRepository::class)->createAuthorizationCodeGrantClient('Claude', ['https://claude.ai/api/mcp/auth_callback'], confidential: false);
        $user = $this->user;
        Passport::actingAs($user, ['mcp:use'], 'api', $client);
        $entity = Entity::factory()->create(['summary' => 'Old']);

        $this->postJson('/mcp/contribute', [
            'jsonrpc' => '2.0', 'id' => 1, 'method' => 'tools/call',
            'params' => ['name' => 'suggest-correction', 'arguments' => [
                'target_type' => 'entity', 'target_id' => $entity->entity_id, 'field' => 'summary', 'proposed_text' => 'New',
            ]],
        ], ['Accept' => 'application/json, text/event-stream'])->assertOk()->assertJsonPath('result.isError', false);

        $this->assertSame('Claude', Contribution::query()->sole()->client);
    }

    public function test_suggest_correction_applies_the_existing_rules(): void
    {
        $entity = Entity::factory()->create(['name' => 'Marathon', 'summary' => 'Same']);
        $base = ['target_type' => 'entity', 'target_id' => $entity->entity_id];

        $this->tool(SuggestCorrection::class, $base + ['field' => 'wikidata_id', 'proposed_text' => 'Q1'])->assertHasErrors(['cannot be edited']);
        $this->tool(SuggestCorrection::class, $base + ['field' => 'summary', 'proposed_text' => 'Same'])->assertHasErrors(['Nothing has changed']);
        $this->tool(SuggestCorrection::class, $base + ['field' => 'name', 'proposed_text' => str_repeat('x', 256)])->assertHasErrors(['at most 255']);
        $this->tool(SuggestCorrection::class, ['target_type' => 'entity', 'target_id' => (string) Str::uuid(), 'field' => 'summary', 'proposed_text' => 'x'])
            ->assertHasErrors(['no longer exists']);
        $this->assertSame(0, Contribution::query()->count());
    }

    public function test_the_pending_cap_applies_to_the_tools(): void
    {
        $entity = Entity::factory()->create(['summary' => 'Old']);
        for ($i = 0; $i < SubmitContributionAction::MAX_PENDING_PER_USER; $i++) {
            $this->user->contributions()->create([
                'target_type' => ContributionTargetType::Entity, 'target_id' => $entity->entity_id, 'field' => 'summary',
                'base_text' => 'a', 'proposed_text' => 'b'.$i, 'diff' => [], 'status' => ContributionStatus::Pending,
            ]);
        }

        $this->tool(SuggestCorrection::class, ['target_type' => 'entity', 'target_id' => $entity->entity_id, 'field' => 'summary', 'proposed_text' => 'one more'])
            ->assertHasErrors(['too many']);
        $this->tool(ProposeEntity::class, $this->entityArgs())->assertHasErrors(['too many']);
    }

    // ── propose-entity ───────────────────────────────────────────────────

    public function test_propose_entity_stores_a_validated_create_proposal_and_creates_nothing(): void
    {
        $this->tool(ProposeEntity::class, $this->entityArgs([
            'summary' => 'King of Wessex.', 'place' => 'Wessex', 'latitude' => 51.06, 'longitude' => -1.31,
            'wikidata_qid' => 'q123456', 'alternative_names' => ['Æthelbald', 'Aethelbald'],
            'sources' => [['title' => 'ASC', 'url' => 'https://example.org/asc']], 'note' => 'From the Chronicle.',
        ]))->assertOk()
            ->assertStructuredContentPath('recorded', true)
            ->assertStructuredContentPath('status', 'pending');

        $c = Contribution::query()->sole();
        $this->assertSame(ContributionKind::Create, $c->kind);
        $this->assertSame(ContributionTargetType::Entity, $c->target_type);
        $this->assertNull($c->target_id);
        $this->assertNull($c->field);
        $this->assertSame(ContributionSource::Mcp, $c->source);
        $this->assertSame('From the Chronicle.', $c->note);
        $e = $c->payload['entity'];
        $this->assertSame('Aethelbald of Wessex', $e['name']);
        $this->assertSame('person', $e['entity_type']);
        $this->assertSame('POLITY', $e['entity_group']);
        $this->assertSame('839', $e['temporal_start']);
        $this->assertSame('Q123456', $e['wikidata_id']);
        $this->assertSame(['type' => 'Point', 'coordinates' => [-1.31, 51.06]], $e['geojson']);
        $this->assertEquals([['source_type' => 'reference', 'title' => 'ASC', 'url' => 'https://example.org/asc']], $e['source_citations']);
        $this->assertSame(0, Entity::query()->where('name', 'Aethelbald of Wessex')->count());
    }

    public function test_propose_entity_validates_like_the_entity_store_request(): void
    {
        $this->tool(ProposeEntity::class, $this->entityArgs(['entity_type' => 'spaceship']))->assertHasErrors();
        $this->tool(ProposeEntity::class, $this->entityArgs(['name' => '']))->assertHasErrors();
        $this->tool(ProposeEntity::class, $this->entityArgs(['wikidata_qid' => 'Q12x']))->assertHasErrors();
        $this->tool(ProposeEntity::class, $this->entityArgs(['start_year' => 0]))->assertHasErrors(['year 0']);
        $this->tool(ProposeEntity::class, $this->entityArgs(['start_year' => 900, 'end_year' => 800]))->assertHasErrors(['cannot be before']);
        $this->tool(ProposeEntity::class, $this->entityArgs(['latitude' => 95, 'longitude' => 0]))->assertHasErrors();
        $this->tool(ProposeEntity::class, $this->entityArgs(['latitude' => 10]))->assertHasErrors();
        $this->tool(ProposeEntity::class, $this->entityArgs(['sources' => [['url' => 'ftp://x']]]))->assertHasErrors();
        $this->tool(ProposeEntity::class, $this->entityArgs(['sources' => [['title' => '']]]))->assertHasErrors();
        $this->assertSame(0, Contribution::query()->count());
    }

    public function test_propose_entity_refuses_a_qid_the_atlas_has_and_returns_that_entity(): void
    {
        $existing = $this->entity('Alfred the Great', EntityType::Person, ['wikidata_id' => 'Q83476']);

        $this->tool(ProposeEntity::class, $this->entityArgs(['name' => 'Alfred', 'wikidata_qid' => 'Q83476']))
            ->assertOk()
            ->assertStructuredContentPath('recorded', false)
            ->assertStructuredContentPath('existing_entity.id', $existing->entity_id)
            ->assertStructuredContentPath('existing_entity.atlas_url', 'https://atlas.test/entities/'.$existing->entity_id);
        $this->assertSame(0, Contribution::query()->count());
    }

    public function test_propose_entity_refuses_a_qid_already_proposed_and_pending(): void
    {
        $this->tool(ProposeEntity::class, $this->entityArgs(['wikidata_qid' => 'Q999']))->assertStructuredContentPath('recorded', true);

        $this->tool(ProposeEntity::class, $this->entityArgs(['name' => 'Other', 'wikidata_qid' => 'Q999']))
            ->assertHasErrors(['already been proposed']);
        $this->assertSame(1, Contribution::query()->count());
    }

    public function test_propose_entity_returns_possible_duplicates_and_records_nothing_until_acknowledged(): void
    {
        $near = $this->placed('Aethelbald of Wessex', 0, 0, 830, 870, ['entity_type' => 'person']);
        $this->placed('Aethelbald of Wessex', 0, 0, 1500, 1520, ['entity_type' => 'person']); // 600 years away
        $this->placed('Aethelbald of Wessex', 0, 0, 840, 850, ['entity_type' => 'city']);     // other type

        $this->tool(ProposeEntity::class, $this->entityArgs())
            ->assertOk()
            ->assertStructuredContentPath('recorded', false)
            ->assertStructuredContentCount(1, 'possible_duplicates')
            ->assertStructuredContentPath('possible_duplicates.0.id', $near->entity_id)
            ->assertStructuredContentPath('possible_duplicates.0.atlas_url', 'https://atlas.test/entities/'.$near->entity_id)
            ->assertSee('acknowledge_duplicates');
        $this->assertSame(0, Contribution::query()->count());

        $this->tool(ProposeEntity::class, $this->entityArgs(['acknowledge_duplicates' => true]))
            ->assertStructuredContentPath('recorded', true);
        $c = Contribution::query()->sole();
        $this->assertSame($near->entity_id, $c->payload['possible_duplicates'][0]['entity_id'], 'the moderator sees what the caller was told');
    }

    public function test_a_same_name_entity_without_dates_counts_as_a_possible_duplicate(): void
    {
        $this->entity('Aethelbald of Wessex', EntityType::Person);

        $this->tool(ProposeEntity::class, $this->entityArgs())->assertStructuredContentPath('recorded', false);
    }

    // ── propose-relationship ─────────────────────────────────────────────

    public function test_propose_relationship_between_existing_entities(): void
    {
        $a = $this->entity('Caesar', EntityType::Person);
        $b = $this->entity('Gallic Wars', EntityType::EventWar);

        $this->tool(ProposeRelationship::class, [
            'source' => $a->entity_id, 'target' => $b->entity_id, 'relationship_type' => 'commanded',
            'start_year' => -58, 'end_year' => -50, 'description' => 'Proconsul in Gaul.',
            'sources' => [['title' => 'De Bello Gallico']],
        ])->assertOk()->assertStructuredContentPath('status', 'pending')->assertStructuredContentPath('waits_for', []);

        $c = Contribution::query()->sole();
        $this->assertSame(ContributionTargetType::Relationship, $c->target_type);
        $this->assertSame(ContributionKind::Create, $c->kind);
        $r = $c->payload['relationship'];
        $this->assertEquals(['entity_id' => $a->entity_id, 'label' => 'Caesar'], $r['source']);
        $this->assertSame('commanded', $r['relationship_type']);
        $this->assertSame('-58', $r['temporal_start']);
        $this->assertSame(0, EntityRelationship::query()->count());
    }

    public function test_propose_relationship_to_the_callers_pending_entity_proposal(): void
    {
        $other = $this->entity('Battle of Ashdown', EntityType::EventBattle);
        $this->tool(ProposeEntity::class, $this->entityArgs());
        $proposal = Contribution::query()->sole();

        $this->tool(ProposeRelationship::class, [
            'source' => (string) $proposal->id, 'target' => $other->entity_id, 'relationship_type' => 'participated_in',
        ])->assertOk()->assertStructuredContentPath('waits_for', [$proposal->id]);

        $r = Contribution::query()->where('target_type', 'relationship')->sole()->payload['relationship'];
        $this->assertEquals(['contribution_id' => $proposal->id, 'label' => 'Aethelbald of Wessex'], $r['source']);
    }

    public function test_propose_relationship_validates_ends_type_and_duplicates(): void
    {
        $a = $this->entity('A', EntityType::Person);
        $b = $this->entity('B', EntityType::City);
        $ok = ['source' => $a->entity_id, 'target' => $b->entity_id, 'relationship_type' => 'born_in'];

        $this->tool(ProposeRelationship::class, [...$ok, 'relationship_type' => 'frenemies'])->assertHasErrors();
        $this->tool(ProposeRelationship::class, [...$ok, 'target' => (string) Str::uuid()])->assertHasErrors(['No entity has this id']);
        $this->tool(ProposeRelationship::class, [...$ok, 'target' => 'Paris'])->assertHasErrors(['entity id']);
        $this->tool(ProposeRelationship::class, [...$ok, 'target' => $a->entity_id])->assertHasErrors(['two different']);
        $this->tool(ProposeRelationship::class, [...$ok, 'start_year' => 900, 'end_year' => 800])->assertHasErrors(['cannot be before']);
        $this->tool(ProposeRelationship::class, [...$ok, 'target' => '999999'])->assertHasErrors(['No entity proposal of yours']);

        $this->relate($a, $b, 'born_in');
        $this->tool(ProposeRelationship::class, $ok)->assertHasErrors(['already has this relationship']);
        $this->assertSame(0, Contribution::query()->count());
    }

    public function test_a_relationship_cannot_use_someone_elses_entity_proposal_or_a_rejected_one(): void
    {
        $b = $this->entity('B', EntityType::City);
        $other = $this->userWithRole('user');
        $this->tool(ProposeEntity::class, $this->entityArgs(), $other);
        $theirs = Contribution::query()->sole();

        $this->tool(ProposeRelationship::class, ['source' => (string) $theirs->id, 'target' => $b->entity_id, 'relationship_type' => 'born_in'])
            ->assertHasErrors(['No entity proposal of yours']);

        $this->tool(ProposeEntity::class, $this->entityArgs(['name' => 'Mine']));
        $mine = Contribution::query()->where('user_id', $this->user->id)->sole();
        $mine->update(['status' => 'rejected']);
        $this->tool(ProposeRelationship::class, ['source' => (string) $mine->id, 'target' => $b->entity_id, 'relationship_type' => 'born_in'])
            ->assertHasErrors(['was rejected']);
    }

    public function test_an_approved_entity_proposal_resolves_to_the_created_entity(): void
    {
        $b = $this->entity('B', EntityType::City);
        $created = $this->entity('Created', EntityType::Person);
        $this->tool(ProposeEntity::class, $this->entityArgs());
        $proposal = Contribution::query()->sole();
        $proposal->update(['status' => 'approved', 'target_id' => $created->entity_id]);

        $this->tool(ProposeRelationship::class, ['source' => (string) $proposal->id, 'target' => $b->entity_id, 'relationship_type' => 'born_in'])
            ->assertStructuredContentPath('waits_for', []);
        $this->assertSame($created->entity_id, Contribution::query()->where('target_type', 'relationship')->sole()->payload['relationship']['source']['entity_id']);
    }

    // ── my-contributions ─────────────────────────────────────────────────

    public function test_my_contributions_lists_own_rows_with_status_and_review_note(): void
    {
        $entity = Entity::factory()->create(['name' => 'Marathon', 'summary' => 'Old']);
        $this->tool(SuggestCorrection::class, ['target_type' => 'entity', 'target_id' => $entity->entity_id, 'field' => 'summary', 'proposed_text' => 'New']);
        $this->tool(ProposeEntity::class, $this->entityArgs());
        Contribution::query()->where('kind', 'edit')->update(['status' => 'rejected', 'review_note' => 'Not sourced.']);
        $other = $this->userWithRole('user');
        $this->tool(ProposeEntity::class, $this->entityArgs(['name' => 'Someone else\'s']), $other);

        $this->tool(MyContributions::class, [])
            ->assertOk()
            ->assertStructuredContentPath('total', 2)
            ->assertStructuredContentCount(2, 'contributions')
            ->assertStructuredContent(fn ($json) => $json
                ->where('contributions.0.kind', 'create')
                ->where('contributions.0.about', 'Aethelbald of Wessex')
                ->where('contributions.0.status', 'pending')
                ->where('contributions.1.status', 'rejected')
                ->where('contributions.1.review_note', 'Not sourced.')
                ->where('contributions.1.about', 'Marathon')
                ->where('contributions.1.field', 'summary')
                ->etc());

        $this->tool(MyContributions::class, ['status' => 'pending'])->assertStructuredContentCount(1, 'contributions');
    }

    public function test_my_contributions_shows_the_created_entity_once_approved(): void
    {
        $this->tool(ProposeEntity::class, $this->entityArgs());
        $created = $this->entity('Aethelbald of Wessex (created)', EntityType::Person);
        Contribution::query()->update(['status' => 'approved', 'target_id' => $created->entity_id]);

        $this->tool(MyContributions::class, [])
            ->assertStructuredContentPath('contributions.0.created_entity_id', $created->entity_id)
            ->assertStructuredContentPath('contributions.0.about', 'Aethelbald of Wessex (created)');
    }
}

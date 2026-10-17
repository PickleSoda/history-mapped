<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Actions\Contribution\ApproveContributionAction;
use App\Models\Contribution;
use App\Models\Entity;
use App\Models\EntityAlias;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * Suggestions for empty fields, alias lists, and keeping a replaced name.
 */
class ContributionFieldsTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    private User $reviewer;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = $this->userWithRole('user');
        $this->reviewer = $this->userWithRole('moderator');
    }

    /** @param  list<string>  $names */
    private function aliases(Entity $entity, array $names): void
    {
        foreach ($names as $name) {
            EntityAlias::query()->create(['entity_id' => $entity->entity_id, 'name' => $name, 'source' => 'wikidata']);
        }
    }

    private function submit(Entity $entity, string $field, string $text): Contribution
    {
        $id = $this->actingAs($this->user)->postJson('/api/v1/contributions', [
            'target_type' => 'entity',
            'target_id' => $entity->entity_id,
            'field' => $field,
            'proposed_text' => $text,
        ])->assertCreated()->json('data.id');

        return Contribution::findOrFail($id);
    }

    public function test_a_missing_field_can_be_suggested_and_applied(): void
    {
        $entity = Entity::factory()->create(['significance' => null]);

        $c = $this->submit($entity, 'significance', 'Ended the first Persian invasion.');
        $this->assertSame('', $c->base_text);
        $this->assertSame([['+', 'Ended the first Persian invasion.']], $c->diff);

        $this->actingAs($this->reviewer)->post("/contributions/{$c->id}/approve")->assertSessionHasNoErrors();
        $this->assertSame('Ended the first Persian invasion.', $entity->fresh()->significance);
    }

    public function test_alias_lists_are_normalised_before_diffing(): void
    {
        $entity = Entity::factory()->create(['name' => 'Athens']);
        $this->aliases($entity, ['Athenai', 'Athína']);

        // Reordered, padded, duplicated by case (first spelling wins) — only
        // "Atene" is new.
        $c = $this->submit($entity, 'aliases', "  Athína\nAthenai\nathenai\n\nAtene ");

        $this->assertSame("Athenai\nAthína", $c->base_text);
        $this->assertSame("Atene\nAthenai\nAthína", $c->proposed_text);
        $this->assertSame(['added' => 1, 'removed' => 0], $c->stats());

        $this->actingAs($this->user)->postJson('/api/v1/contributions', [
            'target_type' => 'entity', 'target_id' => $entity->entity_id,
            // Same set, reordered and padded: nothing to review.
            'field' => 'aliases', 'proposed_text' => " Athína\n\nAthenai\n",
        ])->assertUnprocessable()->assertJsonValidationErrors('proposed_text');
    }

    public function test_padding_cannot_change_which_spelling_is_kept(): void
    {
        $entity = Entity::factory()->create();
        $this->aliases($entity, ['Charles the Wise']);

        $c = $this->submit($entity, 'aliases', "Charles the Wise\nCharles le Sage\n charles the wise ");

        $this->assertSame("Charles le Sage\nCharles the Wise", $c->proposed_text);
        $this->assertSame([['+', "Charles le Sage\n"], ['=', 'Charles the Wise']], $c->diff);
    }

    public function test_approving_an_alias_list_syncs_the_rows(): void
    {
        $entity = Entity::factory()->create();
        $this->aliases($entity, ['Keep me', 'Drop me']);

        $c = $this->submit($entity, 'aliases', "Keep me\nBrand new");
        $this->actingAs($this->reviewer)->post("/contributions/{$c->id}/approve")->assertSessionHasNoErrors();

        $rows = $entity->aliases()->orderBy('name')->get();
        $this->assertSame(['Brand new', 'Keep me'], $rows->pluck('name')->all());
        $this->assertSame('contribution', $rows->firstWhere('name', 'Brand new')->source);
        $this->assertSame('wikidata', $rows->firstWhere('name', 'Keep me')->source);
    }

    public function test_alias_changes_since_submission_make_it_stale(): void
    {
        $entity = Entity::factory()->create();
        $this->aliases($entity, ['One']);
        $c = $this->submit($entity, 'aliases', "One\nTwo");

        $this->aliases($entity, ['Three']);

        $this->actingAs($this->reviewer)->from("/contributions/{$c->id}")
            ->post("/contributions/{$c->id}/approve")
            ->assertSessionHasErrors('conflict');
        $this->assertTrue($c->fresh()->isPending());
    }

    public function test_a_rename_can_keep_the_old_name_as_an_alias(): void
    {
        $kept = Entity::factory()->create(['name' => 'Byzantine Empire']);
        $c = $this->submit($kept, 'name', 'Eastern Roman Empire');
        $this->actingAs($this->reviewer)
            ->post("/contributions/{$c->id}/approve", ['keep_old_name_as_alias' => true])
            ->assertSessionHasNoErrors();

        $this->assertSame('Eastern Roman Empire', $kept->fresh()->name);
        $this->assertSame(['Byzantine Empire'], $kept->aliases()->pluck('name')->all());

        // Default: a typo fix does not leave the typo behind.
        $typo = Entity::factory()->create(['name' => 'Maraton']);
        $c = $this->submit($typo, 'name', 'Marathon');
        app(ApproveContributionAction::class)($c, $this->reviewer);

        $this->assertSame('Marathon', $typo->fresh()->name);
        $this->assertSame(0, $typo->aliases()->count());
    }
}

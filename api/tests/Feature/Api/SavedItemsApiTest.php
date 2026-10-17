<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\SavedFolder;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * Stars + saved folders under /api/v1/me (signed-in users only).
 */
class SavedItemsApiTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = $this->userWithRole('user');
    }

    public function test_saved_items_require_authentication(): void
    {
        $this->getJson('/api/v1/me')->assertUnauthorized();
        $this->getJson('/api/v1/me/stars')->assertUnauthorized();
        $this->getJson('/api/v1/me/folders')->assertUnauthorized();
        $this->postJson('/api/v1/me/stars', [])->assertUnauthorized();
    }

    public function test_me_reports_capabilities(): void
    {
        $this->actingAs($this->user)->getJson('/api/v1/me')
            ->assertOk()
            ->assertJsonPath('data.email', $this->user->email)
            ->assertJsonPath('data.roles', ['user'])
            ->assertJsonPath('data.can', [
                'access_admin' => false,
                'contribute' => true,
                'review_contributions' => false,
            ]);

        $this->actingAs($this->userWithRole('admin'))->getJson('/api/v1/me')
            ->assertJsonPath('data.can', [
                'access_admin' => true,
                'contribute' => true,
                'review_contributions' => true,
            ]);
    }

    public function test_starring_is_idempotent_and_returns_a_summary(): void
    {
        $entity = Entity::factory()->create(['name' => 'Marathon', 'summary' => 'A battle.']);
        $payload = ['type' => 'entity', 'id' => $entity->entity_id];

        $this->actingAs($this->user)->postJson('/api/v1/me/stars', $payload)
            ->assertCreated()
            ->assertJsonPath('data.type', 'entity')
            ->assertJsonPath('data.target_id', $entity->entity_id)
            ->assertJsonPath('data.item.name', 'Marathon')
            ->assertJsonPath('data.item.summary', 'A battle.');

        $this->actingAs($this->user)->postJson('/api/v1/me/stars', $payload)->assertOk();
        $this->assertSame(1, $this->user->stars()->count());
    }

    public function test_stars_of_every_type_are_listed_with_their_summaries(): void
    {
        [$a, $b] = Entity::factory()->count(2)->create();
        $rel = $this->relationship($a, $b);
        $chronicle = Chronicle::factory()->create(['title' => 'The Persian Wars']);

        $this->actingAs($this->user);
        $this->postJson('/api/v1/me/stars', ['type' => 'entity', 'id' => $a->entity_id])->assertCreated();
        $this->postJson('/api/v1/me/stars', ['type' => 'relationship', 'id' => $rel->relationship_id])->assertCreated();
        $this->postJson('/api/v1/me/stars', ['type' => 'chronicle', 'id' => $chronicle->chronicle_id])->assertCreated();

        $res = $this->getJson('/api/v1/me/stars')->assertOk();
        $this->assertCount(3, $res->json('data'));
        $byType = collect($res->json('data'))->keyBy('type');
        $this->assertSame($chronicle->slug, $byType['chronicle']['item']['slug']);
        $this->assertSame($a->name, $byType['relationship']['item']['source']['name']);
        $this->assertSame($b->name, $byType['relationship']['item']['target']['name']);

        $this->getJson('/api/v1/me/stars?type=chronicle')->assertOk()->assertJsonCount(1, 'data');

        $keys = $this->getJson('/api/v1/me/stars/keys')->assertOk()->json('data');
        $this->assertEqualsCanonicalizing(
            ['entity', 'relationship', 'chronicle'],
            array_column($keys, 'type'),
        );
    }

    public function test_starring_validates_the_target(): void
    {
        $this->actingAs($this->user);

        $this->postJson('/api/v1/me/stars', ['type' => 'entity', 'id' => (string) Str::uuid()])
            ->assertUnprocessable()->assertJsonValidationErrors('id');
        $this->postJson('/api/v1/me/stars', ['type' => 'entity', 'id' => 'not-a-uuid'])
            ->assertUnprocessable()->assertJsonValidationErrors('id');
        $this->postJson('/api/v1/me/stars', ['type' => 'source', 'id' => (string) Str::uuid()])
            ->assertUnprocessable()->assertJsonValidationErrors('type');
    }

    public function test_a_deleted_target_leaves_a_dangling_star(): void
    {
        $entity = Entity::factory()->create();
        $this->actingAs($this->user)->postJson('/api/v1/me/stars', ['type' => 'entity', 'id' => $entity->entity_id]);
        $entity->delete();

        $this->getJson('/api/v1/me/stars')->assertOk()->assertJsonPath('data.0.item', null);
    }

    public function test_unstarring_removes_the_item_from_every_folder(): void
    {
        $entity = Entity::factory()->create();
        $this->actingAs($this->user);
        $folder = $this->postJson('/api/v1/me/folders', ['name' => 'Battles'])->assertCreated()->json('data');

        $this->putJson("/api/v1/me/folders/{$folder['id']}/items/entity/{$entity->entity_id}")
            ->assertOk()
            ->assertJsonPath('data.folder_ids', [$folder['id']]);
        $this->assertSame(1, $this->user->stars()->count());

        $this->deleteJson("/api/v1/me/stars/entity/{$entity->entity_id}")->assertNoContent();
        $this->assertSame(0, $this->user->stars()->count());
        $this->getJson('/api/v1/me/folders')->assertJsonPath('data.0.stars_count', 0);
    }

    public function test_folders_crud_and_membership(): void
    {
        $entity = Entity::factory()->create();
        $this->actingAs($this->user);

        $folder = $this->postJson('/api/v1/me/folders', ['name' => '  Reading list ', 'color' => '#3b82f6'])
            ->assertCreated()
            ->assertJsonPath('data.name', 'Reading list')
            ->assertJsonPath('data.stars_count', 0)
            ->json('data');
        $this->postJson('/api/v1/me/folders', ['name' => 'Reading list'])
            ->assertUnprocessable()->assertJsonValidationErrors('name');
        $this->postJson('/api/v1/me/folders', ['name' => 'Bad', 'color' => 'blue'])
            ->assertUnprocessable()->assertJsonValidationErrors('color');

        $this->patchJson("/api/v1/me/folders/{$folder['id']}", ['name' => 'To read', 'description' => 'Later'])
            ->assertOk()->assertJsonPath('data.name', 'To read')->assertJsonPath('data.description', 'Later');

        $this->postJson('/api/v1/me/stars', [
            'type' => 'entity', 'id' => $entity->entity_id, 'folder_ids' => [$folder['id']],
        ])->assertCreated()->assertJsonPath('data.folder_ids', [$folder['id']]);
        $this->getJson("/api/v1/me/stars?folder={$folder['id']}")->assertJsonCount(1, 'data');

        // Leaving a folder keeps the star.
        $this->deleteJson("/api/v1/me/folders/{$folder['id']}/items/entity/{$entity->entity_id}")->assertNoContent();
        $this->getJson("/api/v1/me/stars?folder={$folder['id']}")->assertJsonCount(0, 'data');
        $this->assertSame(1, $this->user->stars()->count());

        // Deleting a folder keeps its stars.
        $this->putJson("/api/v1/me/folders/{$folder['id']}/items/entity/{$entity->entity_id}")->assertOk();
        $this->deleteJson("/api/v1/me/folders/{$folder['id']}")->assertNoContent();
        $this->assertSame(0, $this->user->savedFolders()->count());
        $this->assertSame(1, $this->user->stars()->count());
    }

    public function test_another_users_folder_is_not_found(): void
    {
        $entity = Entity::factory()->create();
        $theirs = SavedFolder::create(['user_id' => $this->userWithRole('user')->id, 'name' => 'Theirs']);

        $this->actingAs($this->user);
        $this->patchJson("/api/v1/me/folders/{$theirs->id}", ['name' => 'Mine now'])->assertNotFound();
        $this->deleteJson("/api/v1/me/folders/{$theirs->id}")->assertNotFound();
        $this->putJson("/api/v1/me/folders/{$theirs->id}/items/entity/{$entity->entity_id}")->assertNotFound();
        $this->getJson("/api/v1/me/stars?folder={$theirs->id}")->assertNotFound();
        $this->postJson('/api/v1/me/stars', [
            'type' => 'entity', 'id' => $entity->entity_id, 'folder_ids' => [$theirs->id],
        ])->assertUnprocessable()->assertJsonValidationErrors('folder_ids');

        $this->assertSame('Theirs', $theirs->fresh()->name);
    }

    private function relationship(Entity $a, Entity $b): EntityRelationship
    {
        return EntityRelationship::create([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $a->entity_id,
            'target_entity_id' => $b->entity_id,
            'relationship_type' => 'allied_with',
            'description' => 'Allied against Persia.',
        ]);
    }
}

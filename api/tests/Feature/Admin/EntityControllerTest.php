<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class EntityControllerTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = User::factory()->create();
    }

    // ── create ───────────────────────────────────────────────────────────────

    public function test_create_renders_form_page(): void
    {
        $this->actingAs($this->user)
            ->get(route('entities.create'))
            ->assertOk()
            ->assertInertia(function ($page) {
                $page->component('entities/create');
                $props = $page->toArray()['props'];
                $this->assertArrayHasKey('formOptions', $props);
                $this->assertArrayHasKey('types', $props['formOptions']);
                $this->assertArrayHasKey('statuses', $props['formOptions']);
            });
    }

    public function test_create_redirects_guests(): void
    {
        $this->get(route('entities.create'))
            ->assertRedirect(route('login'));
    }

    // ── store ────────────────────────────────────────────────────────────────

    public function test_store_creates_entity_and_redirects_to_show(): void
    {
        $response = $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Battle of Actium',
                'entity_type' => EntityType::EventBattle->value,
                'entity_group' => EntityGroup::Event->value,
                'summary' => 'A decisive confrontation.',
                'impact_score' => 85,
            ]);

        $response->assertRedirect();
        $this->assertDatabaseHas('entities', [
            'name' => 'Battle of Actium',
            'entity_type' => EntityType::EventBattle->value,
        ]);
    }

    public function test_store_requires_name(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'entity_type' => EntityType::City->value,
                'entity_group' => EntityGroup::Place->value,
            ])
            ->assertSessionHasErrors('name');
    }

    public function test_store_requires_entity_type(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Rome',
                'entity_group' => EntityGroup::Place->value,
            ])
            ->assertSessionHasErrors('entity_type');
    }

    public function test_store_validates_wikidata_id_format(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Rome',
                'entity_type' => EntityType::City->value,
                'entity_group' => EntityGroup::Place->value,
                'wikidata_id' => 'not-a-qid',
            ])
            ->assertSessionHasErrors('wikidata_id');
    }

    public function test_store_accepts_valid_wikidata_id(): void
    {
        $response = $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Rome',
                'entity_type' => EntityType::City->value,
                'entity_group' => EntityGroup::Place->value,
                'wikidata_id' => 'Q220',
            ]);

        $response->assertRedirect();
        $this->assertDatabaseHas('entities', ['wikidata_id' => 'Q220']);
    }

    public function test_store_persists_attributes(): void
    {
        $response = $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Battle of Marathon',
                'entity_type' => EntityType::EventBattle->value,
                'entity_group' => EntityGroup::Event->value,
                'attributes' => ['battle_subtype' => 'pitched_battle', 'outcome' => 'decisive_victory'],
            ]);

        $response->assertRedirect();

        $entity = Entity::query()->where('name', 'Battle of Marathon')->first();
        $this->assertNotNull($entity);
        $this->assertSame('pitched_battle', $entity->attributes['battle_subtype']);
        $this->assertSame('decisive_victory', $entity->attributes['outcome']);
    }

    public function test_store_redirects_guests(): void
    {
        $this->post(route('entities.store'), [
            'name' => 'Rome',
            'entity_type' => EntityType::City->value,
            'entity_group' => EntityGroup::Place->value,
        ])->assertRedirect(route('login'));
    }

    // ── show ─────────────────────────────────────────────────────────────────

    public function test_show_renders_entity_detail(): void
    {
        $entity = Entity::factory()
            ->ofType(EntityType::City)
            ->create(['name' => 'Carthage']);

        $this->actingAs($this->user)
            ->get(route('entities.show', $entity->entity_id))
            ->assertOk()
            ->assertInertia(function ($page) {
                $page->component('entities/show');
                $props = $page->toArray()['props'];
                $this->assertArrayHasKey('entity', $props);
                $this->assertSame('Carthage', $props['entity']['name']);
                $this->assertArrayHasKey('geojson', $props['entity']);
                $this->assertArrayHasKey('territory_geojson', $props['entity']);
                $this->assertArrayHasKey('geometry_periods_url', $props['entity']);
            });
    }

    public function test_show_redirects_guests(): void
    {
        $entity = Entity::factory()->create();
        $this->get(route('entities.show', $entity->entity_id))
            ->assertRedirect(route('login'));
    }

    public function test_show_returns_404_for_missing_entity(): void
    {
        $this->actingAs($this->user)
            ->get(route('entities.show', '00000000-0000-0000-0000-000000000000'))
            ->assertNotFound();
    }

    // ── edit ─────────────────────────────────────────────────────────────────

    public function test_edit_renders_form_prepopulated(): void
    {
        $entity = Entity::factory()
            ->ofType(EntityType::Person)
            ->create([
                'name' => 'Julius Caesar',
                'summary' => 'Roman dictator.',
                'impact_score' => 95,
            ]);

        $this->actingAs($this->user)
            ->get(route('entities.edit', $entity->entity_id))
            ->assertOk()
            ->assertInertia(function ($page) {
                $page->component('entities/edit');
                $props = $page->toArray()['props'];
                $this->assertArrayHasKey('entity', $props);
                $this->assertArrayHasKey('formOptions', $props);
                $this->assertSame('Julius Caesar', $props['entity']['name']);
                $this->assertSame(95, $props['entity']['impact_score']);
                $this->assertArrayHasKey('geometry_periods_url', $props['entity']);
            });
    }

    public function test_edit_redirects_guests(): void
    {
        $entity = Entity::factory()->create();
        $this->get(route('entities.edit', $entity->entity_id))
            ->assertRedirect(route('login'));
    }

    // ── update ───────────────────────────────────────────────────────────────

    public function test_update_persists_changes_and_redirects_to_show(): void
    {
        $entity = Entity::factory()
            ->ofType(EntityType::City)
            ->create(['name' => 'Old Name', 'impact_score' => 10]);

        $this->actingAs($this->user)
            ->put(route('entities.update', $entity->entity_id), [
                'name' => 'Rome',
                'entity_type' => $entity->entity_type->value,
                'entity_group' => $entity->entity_group->value,
                'impact_score' => 90,
            ])
            ->assertRedirect(route('entities.show', $entity->entity_id));

        $this->assertDatabaseHas('entities', [
            'entity_id' => $entity->entity_id,
            'name' => 'Rome',
            'impact_score' => 90,
        ]);
    }

    public function test_update_allows_partial_updates(): void
    {
        $entity = Entity::factory()
            ->ofType(EntityType::City)
            ->create(['name' => 'Rome', 'summary' => 'Original summary.']);

        $this->actingAs($this->user)
            ->put(route('entities.update', $entity->entity_id), [
                'summary' => 'Updated summary.',
            ])
            ->assertRedirect();

        $this->assertDatabaseHas('entities', [
            'entity_id' => $entity->entity_id,
            'name' => 'Rome',   // unchanged
            'summary' => 'Updated summary.',
        ]);
    }

    public function test_update_rejects_invalid_impact_score(): void
    {
        $entity = Entity::factory()->ofType(EntityType::City)->create();

        $this->actingAs($this->user)
            ->put(route('entities.update', $entity->entity_id), [
                'impact_score' => 999,
            ])
            ->assertSessionHasErrors('impact_score');
    }

    public function test_update_persists_verification_status(): void
    {
        $entity = Entity::factory()
            ->draft()
            ->ofType(EntityType::City)
            ->create(['name' => 'Alexandria']);

        $this->actingAs($this->user)
            ->put(route('entities.update', $entity->entity_id), [
                'verification_status' => VerificationStatus::HumanVerified->value,
            ])
            ->assertRedirect();

        $this->assertDatabaseHas('entities', [
            'entity_id' => $entity->entity_id,
            'verification_status' => VerificationStatus::HumanVerified->value,
        ]);
    }

    public function test_update_redirects_guests(): void
    {
        $entity = Entity::factory()->create();
        $this->put(route('entities.update', $entity->entity_id), ['name' => 'X'])
            ->assertRedirect(route('login'));
    }

    // ── destroy ──────────────────────────────────────────────────────────────

    public function test_destroy_deletes_entity_and_redirects_to_index(): void
    {
        $entity = Entity::factory()->create(['name' => 'To Delete']);

        $this->actingAs($this->user)
            ->delete(route('entities.destroy', $entity->entity_id))
            ->assertRedirect(route('entities.index'));

        $this->assertDatabaseMissing('entities', ['entity_id' => $entity->entity_id]);
    }

    public function test_destroy_redirects_guests(): void
    {
        $entity = Entity::factory()->create();
        $this->delete(route('entities.destroy', $entity->entity_id))
            ->assertRedirect(route('login'));
    }

    public function test_destroy_returns_404_for_missing_entity(): void
    {
        $this->actingAs($this->user)
            ->delete(route('entities.destroy', '00000000-0000-0000-0000-000000000000'))
            ->assertNotFound();
    }
}

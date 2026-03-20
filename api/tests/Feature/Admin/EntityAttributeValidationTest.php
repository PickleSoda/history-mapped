<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * Tests for per-entity-type attributes.* validation rules
 * added via the ValidatesEntityAttributes trait.
 */
class EntityAttributeValidationTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = User::factory()->create();
    }

    // ── store: enum attributes accept valid values ────────────────────────────

    public function test_store_accepts_valid_political_entity_attributes(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Roman Empire',
                'entity_type' => EntityType::PoliticalEntity->value,
                'entity_group' => EntityGroup::Polity->value,
                'attributes' => [
                    'political_subtype' => 'empire',
                    'government_type' => 'bureaucratic_centralized',
                    'succession_type' => 'primogeniture',
                ],
            ])
            ->assertSessionHasNoErrors()
            ->assertRedirect();
    }

    public function test_store_rejects_invalid_political_subtype(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Roman Empire',
                'entity_type' => EntityType::PoliticalEntity->value,
                'entity_group' => EntityGroup::Polity->value,
                'attributes' => [
                    'political_subtype' => 'not_a_real_subtype',
                ],
            ])
            ->assertSessionHasErrors('attributes.political_subtype');
    }

    public function test_store_accepts_valid_person_attributes(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Julius Caesar',
                'entity_type' => EntityType::Person->value,
                'entity_group' => EntityGroup::Polity->value,
                'attributes' => [
                    'gender' => 'male',
                    'birth_date' => '-100',
                    'death_date' => '-44',
                    'ethnicity' => 'Roman',
                    'cause_of_death' => 'assassination',
                ],
            ])
            ->assertSessionHasNoErrors()
            ->assertRedirect();
    }

    public function test_store_rejects_invalid_gender_for_person(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Julius Caesar',
                'entity_type' => EntityType::Person->value,
                'entity_group' => EntityGroup::Polity->value,
                'attributes' => [
                    'gender' => 'robot',
                ],
            ])
            ->assertSessionHasErrors('attributes.gender');
    }

    public function test_store_accepts_valid_battle_attributes(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Battle of Actium',
                'entity_type' => EntityType::EventBattle->value,
                'entity_group' => EntityGroup::Event->value,
                'attributes' => [
                    'battle_subtype' => 'naval_battle',
                    'outcome' => 'decisive_victory',
                    'victor_side' => 'side_a',
                ],
            ])
            ->assertSessionHasNoErrors()
            ->assertRedirect();
    }

    public function test_store_rejects_invalid_battle_subtype(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Battle of Actium',
                'entity_type' => EntityType::EventBattle->value,
                'entity_group' => EntityGroup::Event->value,
                'attributes' => [
                    'battle_subtype' => 'space_battle',
                ],
            ])
            ->assertSessionHasErrors('attributes.battle_subtype');
    }

    public function test_store_accepts_valid_epidemic_attributes(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Black Death',
                'entity_type' => EntityType::EpidemicDisease->value,
                'entity_group' => EntityGroup::Event->value,
                'attributes' => [
                    'epidemic_subtype' => 'plague_bacterial',
                    'severity' => 'pandemic',
                    'spread_vector' => 'fleas/rats',
                ],
            ])
            ->assertSessionHasNoErrors()
            ->assertRedirect();
    }

    public function test_store_rejects_invalid_epidemic_severity(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Black Death',
                'entity_type' => EntityType::EpidemicDisease->value,
                'entity_group' => EntityGroup::Event->value,
                'attributes' => [
                    'severity' => 'apocalyptic',
                ],
            ])
            ->assertSessionHasErrors('attributes.severity');
    }

    // ── store: attributes pass-through when type doesn't define them ──────────

    public function test_store_accepts_string_fields_regardless_of_type(): void
    {
        // Fields like 'founding_legend', 'casus_belli' etc. are nullable strings
        // and should pass for any type
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Rome',
                'entity_type' => EntityType::City->value,
                'entity_group' => EntityGroup::Place->value,
                'attributes' => [
                    'settlement_subtype' => 'capital_city',
                    'elevation_m' => 21,
                    'founding_legend' => 'Founded by Romulus.',
                ],
            ])
            ->assertSessionHasNoErrors()
            ->assertRedirect();
    }

    public function test_store_rejects_invalid_settlement_subtype(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Rome',
                'entity_type' => EntityType::City->value,
                'entity_group' => EntityGroup::Place->value,
                'attributes' => [
                    'settlement_subtype' => 'space_station',
                ],
            ])
            ->assertSessionHasErrors('attributes.settlement_subtype');
    }

    // ── update: same validation rules apply ───────────────────────────────────

    public function test_update_rejects_invalid_war_subtype(): void
    {
        $entity = \App\Models\Entity::factory()->create([
            'entity_type' => EntityType::EventWar->value,
            'entity_group' => EntityGroup::Event->value,
        ]);

        $this->actingAs($this->user)
            ->put(route('entities.update', $entity->entity_id), [
                'name' => $entity->name,
                'entity_type' => EntityType::EventWar->value,
                'entity_group' => EntityGroup::Event->value,
                'attributes' => [
                    'war_subtype' => 'intergalactic_war',
                ],
            ])
            ->assertSessionHasErrors('attributes.war_subtype');
    }

    public function test_update_accepts_valid_language_attributes(): void
    {
        $entity = \App\Models\Entity::factory()->create([
            'entity_type' => EntityType::Language->value,
            'entity_group' => EntityGroup::Culture->value,
        ]);

        $this->actingAs($this->user)
            ->put(route('entities.update', $entity->entity_id), [
                'name' => $entity->name,
                'entity_type' => EntityType::Language->value,
                'entity_group' => EntityGroup::Culture->value,
                'attributes' => [
                    'language_family' => 'Indo-European',
                    'language_status' => 'extinct',
                    'writing_system' => 'Latin alphabet',
                    'iso_639_code' => 'lat',
                ],
            ])
            ->assertSessionHasNoErrors()
            ->assertRedirect();
    }

    public function test_update_rejects_invalid_language_status(): void
    {
        $entity = \App\Models\Entity::factory()->create([
            'entity_type' => EntityType::Language->value,
            'entity_group' => EntityGroup::Culture->value,
        ]);

        $this->actingAs($this->user)
            ->put(route('entities.update', $entity->entity_id), [
                'name' => $entity->name,
                'entity_type' => EntityType::Language->value,
                'entity_group' => EntityGroup::Culture->value,
                'attributes' => [
                    'language_status' => 'half_dead',
                ],
            ])
            ->assertSessionHasErrors('attributes.language_status');
    }

    public function test_store_accepts_valid_natural_resource_attributes(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Iberian Silver',
                'entity_type' => EntityType::NaturalResource->value,
                'entity_group' => EntityGroup::Economy->value,
                'attributes' => [
                    'resource_category' => 'metal_precious',
                    'renewability' => 'finite',
                    'is_tradeable' => true,
                ],
            ])
            ->assertSessionHasNoErrors()
            ->assertRedirect();
    }

    public function test_store_rejects_invalid_resource_category(): void
    {
        $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Iberian Silver',
                'entity_type' => EntityType::NaturalResource->value,
                'entity_group' => EntityGroup::Economy->value,
                'attributes' => [
                    'resource_category' => 'dark_matter',
                ],
            ])
            ->assertSessionHasErrors('attributes.resource_category');
    }
}

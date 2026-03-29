<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

/**
 * @extends Factory<EntityGeoRef>
 */
class EntityGeoRefFactory extends Factory
{
    protected $model = EntityGeoRef::class;

    /**
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'geo_ref_id' => Str::uuid()->toString(),
            'entity_id' => Entity::factory(),
            'provider' => GeoRefProvider::Ohm->value,
            'external_type' => GeoRefExternalType::Relation->value,
            'external_id' => (string) fake()->numberBetween(1, 999999),
            'match_role' => GeoRefMatchRole::Candidate->value,
            'retrieval_method' => GeoRefRetrievalMethod::Rest->value,
            'temporal_start_year' => fake()->optional()->numberBetween(-2000, 1800),
            'temporal_end_year' => fake()->optional()->numberBetween(-2000, 1900),
            'external_tags' => [
                'name' => fake()->words(2, true),
            ],
            'source_meta' => [
                'source' => 'factory',
            ],
            'match_score' => fake()->randomFloat(4, 0.1, 0.9999),
            'is_active' => true,
        ];
    }

    public function forEntity(Entity $entity): static
    {
        return $this->state(fn (): array => [
            'entity_id' => $entity->entity_id,
        ]);
    }

    public function primary(): static
    {
        return $this->state(fn (): array => [
            'match_role' => GeoRefMatchRole::Primary->value,
            'is_active' => true,
        ]);
    }
}

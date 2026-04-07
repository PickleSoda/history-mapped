<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Enums\ConfidenceLevel;
use App\Enums\DateResolutionMethod;
use App\Enums\DurationType;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\IconClass;
use App\Enums\LocationResolutionMethod;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use App\Models\EntityLocation;
use App\Models\EntityTemporalRange;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

/**
 * @extends Factory<Entity>
 */
class EntityFactory extends Factory
{
    protected $model = Entity::class;

    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        $entityType = fake()->randomElement(EntityType::cases());

        return [
            'entity_id' => Str::uuid()->toString(),
            'name' => fake()->words(rand(2, 5), true),
            'entity_type' => $entityType->value,
            'entity_group' => $entityType->group()->value,
            'summary' => fake()->paragraph(3),
            'significance' => fake()->paragraph(2),
            'impact_score' => fake()->numberBetween(1, 100),
            'verification_status' => fake()->randomElement(VerificationStatus::cases())->value,
            'confidence' => fake()->randomElement(ConfidenceLevel::cases())->value,
            'date_method' => fake()->randomElement(DateResolutionMethod::cases())->value,
            'date_confidence' => fake()->randomElement(ConfidenceLevel::cases())->value,
            'duration_type' => fake()->randomElement(DurationType::cases())->value,
            'location_confidence' => fake()->randomElement(ConfidenceLevel::cases())->value,
            'location_method' => fake()->randomElement(LocationResolutionMethod::cases())->value,
            'display_priority' => fake()->numberBetween(1, 10),
            'icon_class' => fake()->randomElement(IconClass::cases())->value,
            'attributes' => json_encode([
                'entity_color' => fake()->hexColor(),
            ]),
            'created_by' => 'factory',
        ];
    }

    // ── Type States ──────────────────────────────────────────

    /**
     * Set a specific entity type (group is derived automatically).
     */
    public function ofType(EntityType $type): static
    {
        return $this->state(fn () => [
            'entity_type' => $type->value,
            'entity_group' => $type->group()->value,
        ]);
    }

    /**
     * Set a random entity type within the given group.
     */
    public function inGroup(EntityGroup $group): static
    {
        $types = array_filter(
            EntityType::cases(),
            fn (EntityType $t) => $t->group() === $group,
        );

        $type = fake()->randomElement($types);

        return $this->state(fn () => [
            'entity_type' => $type->value,
            'entity_group' => $group->value,
        ]);
    }

    // ── Verification States ─────────────────────────────────

    /**
     * Mark as human-verified with high confidence.
     */
    public function verified(): static
    {
        return $this->state(fn () => [
            'verification_status' => VerificationStatus::HumanVerified->value,
            'confidence' => ConfidenceLevel::High->value,
        ]);
    }

    /**
     * Mark as pipeline draft (unreviewed).
     */
    public function draft(): static
    {
        return $this->state(fn () => [
            'verification_status' => VerificationStatus::PipelineDraft->value,
            'confidence' => ConfidenceLevel::Low->value,
        ]);
    }

    /**
     * Mark as flagged for review.
     */
    public function flagged(): static
    {
        return $this->state(fn () => [
            'verification_status' => VerificationStatus::Flagged->value,
        ]);
    }

    // ── Temporal States ─────────────────────────────────────

    /**
     * Set temporal bounds (ISO date strings like '-0500' or '1453').
     */
    public function withTemporalRange(string $start, string $end): static
    {
        return $this->state(fn () => [
            'temporal_start' => $start,
            'temporal_end' => $end,
            'temporal_start_year' => (int) $start,
            'temporal_end_year' => (int) $end,
            'duration_type' => DurationType::Period->value,
        ])->afterCreating(function (Entity $entity) use ($start, $end): void {
            EntityTemporalRange::query()->updateOrCreate(
                [
                    'entity_id' => $entity->entity_id,
                    'is_primary' => true,
                ],
                [
                    'range_type' => 'primary',
                    'start_year' => (int) $start,
                    'end_year' => (int) $end,
                    'start_date' => $start,
                    'end_date' => $end,
                    'duration_type' => DurationType::Period,
                    'date_method' => $entity->date_method,
                    'date_confidence' => $entity->date_confidence,
                ],
            );
        });
    }

    /**
     * Set a point-in-time event.
     */
    public function atTime(string $date): static
    {
        return $this->state(fn () => [
            'temporal_start' => $date,
            'temporal_end' => $date,
            'temporal_start_year' => (int) $date,
            'temporal_end_year' => (int) $date,
            'duration_type' => DurationType::Point->value,
        ])->afterCreating(function (Entity $entity) use ($date): void {
            EntityTemporalRange::query()->updateOrCreate(
                [
                    'entity_id' => $entity->entity_id,
                    'is_primary' => true,
                ],
                [
                    'range_type' => 'primary',
                    'start_year' => (int) $date,
                    'end_year' => (int) $date,
                    'start_date' => $date,
                    'end_date' => $date,
                    'duration_type' => DurationType::Point,
                    'date_method' => $entity->date_method,
                    'date_confidence' => $entity->date_confidence,
                ],
            );
        });
    }

    // ── Spatial States ──────────────────────────────────────

    /**
     * Set a location name without geometry.
     */
    public function atLocation(string $name): static
    {
        return $this->state(fn () => [
            'location_name' => $name,
        ])->afterCreating(function (Entity $entity) use ($name): void {
            EntityLocation::query()->updateOrCreate(
                [
                    'entity_id' => $entity->entity_id,
                    'is_primary' => true,
                ],
                [
                    'location_name' => $name,
                    'location_method' => $entity->location_method,
                    'location_confidence' => $entity->location_confidence,
                ],
            );
        });
    }
}

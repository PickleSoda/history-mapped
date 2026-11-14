<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use App\Models\Chronicle;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

class ChronicleFactory extends Factory
{
    protected $model = Chronicle::class;

    public function definition(): array
    {
        $startYear = $this->faker->numberBetween(-3000, 1900);
        $endYear = $startYear + $this->faker->numberBetween(0, 200);

        return [
            'chronicle_id' => (string) Str::uuid(),
            'title' => $this->faker->sentence(),
            'slug' => $this->faker->slug(),
            'source_type' => $this->faker->randomElement(SourceType::cases()),
            'source_reference' => $this->faker->word(),
            // Every imported chronicle starts as a draft. A random status would
            // make public listings flaky now that archived ones are hidden.
            'status' => ChronicleStatus::Draft->value,
            'start_year' => $startYear,
            'end_year' => $endYear,
            'impact_score' => $this->faker->numberBetween(1, 10),
            'approximate_location' => ['lat' => $this->faker->latitude(), 'lng' => $this->faker->longitude()],
            'metadata' => [],
        ];
    }

    public function published(): static
    {
        return $this->state(['status' => ChronicleStatus::Published->value]);
    }

    public function archived(): static
    {
        return $this->state(['status' => ChronicleStatus::Archived->value]);
    }
}

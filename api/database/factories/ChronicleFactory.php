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
        return [
            'chronicle_id' => (string) Str::uuid(),
            'title' => $this->faker->sentence(),
            'slug' => $this->faker->slug(),
            'source_type' => $this->faker->randomElement(SourceType::cases()),
            'source_reference' => $this->faker->word(),
            'status' => $this->faker->randomElement(ChronicleStatus::cases()),
            'start_year' => $this->faker->year(),
            'end_year' => $this->faker->year(),
            'impact_score' => $this->faker->numberBetween(1, 10),
            'approximate_location' => ['lat' => $this->faker->latitude(), 'lng' => $this->faker->longitude()],
            'metadata' => [],
        ];
    }
}
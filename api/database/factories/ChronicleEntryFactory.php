<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

class ChronicleEntryFactory extends Factory
{
    protected $model = ChronicleEntry::class;

    public function definition(): array
    {
        return [
            'entry_id' => (string) Str::uuid(),
            'chronicle_id' => Chronicle::factory(),
            'narrative_text' => $this->faker->paragraph(),
            'notes' => null,
            'generated_by' => 'test',
        ];
    }
}

<?php

declare(strict_types=1);

namespace Tests\Feature\Actions;

use App\Actions\Chronicle\CreateChronicleAction;
use App\DTOs\ChronicleData;
use App\Enums\SourceType;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CreateChronicleActionTest extends TestCase
{
    use RefreshDatabase;

    public function test_create_chronicle_action_persists_new_entry_fields(): void
    {
        $data = new ChronicleData(
            title: 'Test Chronicle',
            sourceType: SourceType::VideoTranscript,
            entries: [
                [
                    'sequence_order' => 1,
                    'start_year' => 1000,
                    'end_year' => 1050,
                    'impact_score' => 5,
                    'approximate_location' => ['lat' => 40.0, 'lng' => -74.0],
                    'narrative_text' => 'Test narrative',
                ]
            ]
        );

        $action = new CreateChronicleAction();
        $chronicle = $action($data, 'test_user');

        $this->assertDatabaseHas('chronicle_entries', [
            'chronicle_id' => $chronicle->chronicle_id,
            'start_year' => 1000,
            'end_year' => 1050,
            'impact_score' => 5,
            'approximate_location' => json_encode(['lat' => 40.0, 'lng' => -74.0]),
        ]);
    }
}

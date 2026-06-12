<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

class ImportChroniclesCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_import_persists_new_fields_and_source_evidence(): void
    {
        $fixturePath = storage_path('app/testing/chronicle.json');
        
        $fixtureData = [
            'title' => 'Test Chronicle',
            'slug' => 'test-chronicle',
            'source_type' => 'video_transcript',
            'source_reference' => 'ref-123',
            'status' => 'draft',
            'start_year' => -1200,
            'end_year' => -1100,
            'impact_score' => 8,
            'approximate_location' => ['lat' => 30.0, 'lng' => 31.0],
            'metadata' => [],
            'entries' => [
                [
                    'sequence_order' => 0,
                    'narrative_text' => 'Test narrative',
                    'start_year' => -1150,
                    'end_year' => -1140,
                    'impact_score' => 5,
                    'approximate_location' => ['lat' => 30.5, 'lng' => 31.5],
                    'source_evidence' => ['event:0'],
                    'secondary_entities' => [],
                ],
            ],
        ];

        File::ensureDirectoryExists(dirname($fixturePath));
        File::put($fixturePath, json_encode($fixtureData, JSON_PRETTY_PRINT));

        try {
            $this->artisan('chronicles:import', ['path' => $fixturePath, '--force' => true])
                ->assertExitCode(0);

            $chronicle = Chronicle::where('slug', 'test-chronicle')->first();
            $this->assertNotNull($chronicle);
            $this->assertEquals(-1200, $chronicle->start_year);
            $this->assertEquals(-1100, $chronicle->end_year);
            $this->assertEquals(8, $chronicle->impact_score);
            $this->assertEquals(['lat' => 30.0, 'lng' => 31.0], $chronicle->approximate_location);

            $entry = ChronicleEntry::where('chronicle_id', $chronicle->chronicle_id)->first();
            $this->assertNotNull($entry);
            $this->assertEquals(-1150, $entry->start_year);
            $this->assertEquals(-1140, $entry->end_year);
            $this->assertEquals(5, $entry->impact_score);
            $this->assertEquals(['lat' => 30.5, 'lng' => 31.5], $entry->approximate_location);
            $this->assertEquals(['event:0'], $entry->source_evidence);
        } finally {
            File::delete($fixturePath);
        }
    }
}

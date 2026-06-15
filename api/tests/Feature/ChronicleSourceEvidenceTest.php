<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ChronicleSourceEvidenceTest extends TestCase
{
    use RefreshDatabase;

    public function test_source_evidence_casts_to_array(): void
    {
        $chronicle = Chronicle::factory()->create();

        $entry = ChronicleEntry::create([
            'chronicle_id' => $chronicle->chronicle_id,
            'narrative_text' => 'Test narrative',
            'source_evidence' => ['event:0'],
        ]);

        $reloadedEntry = ChronicleEntry::where('chronicle_id', $chronicle->chronicle_id)->first();

        $this->assertNotNull($reloadedEntry);
        $this->assertIsArray($reloadedEntry->source_evidence);
        $this->assertEquals(['event:0'], $reloadedEntry->source_evidence);
    }

    public function test_source_evidence_can_be_null(): void
    {
        $chronicle = Chronicle::factory()->create();

        $entry = ChronicleEntry::create([
            'chronicle_id' => $chronicle->chronicle_id,
            'narrative_text' => 'Test narrative with null source evidence',
            'source_evidence' => null,
        ]);

        $reloadedEntry = ChronicleEntry::where('chronicle_id', $chronicle->chronicle_id)->first();

        $this->assertNotNull($reloadedEntry);
        $this->assertNull($reloadedEntry->source_evidence);
    }
}

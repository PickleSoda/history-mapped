<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\CreateChronicle;
use App\Models\Chronicle;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CreateChronicleToolTest extends TestCase
{
    use RefreshDatabase;

    public function test_build_then_apply_creates_a_chronicle_with_agent_provenance(): void
    {
        $tool = app(CreateChronicle::class);

        $parts = $tool->buildParts([
            'title' => 'The Punic Wars', 'summary' => 'Rome vs Carthage',
            'start_year' => -264, 'end_year' => -146,
        ]);
        $this->assertCount(1, $parts);
        $this->assertSame('create_chronicle', $parts[0]['tool']);

        $result = $tool->applyPart($parts[0]['payload'], ['user_id' => 'u1']);
        $chronicle = Chronicle::findOrFail($result['result_id']);

        $this->assertSame('The Punic Wars', $chronicle->title);
        $this->assertSame(-264, $chronicle->start_year);
        $this->assertSame('agent:u1', $chronicle->created_by);
    }
}

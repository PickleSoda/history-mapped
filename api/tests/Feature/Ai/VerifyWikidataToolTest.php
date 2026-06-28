<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\VerifyWikidata;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Laravel\Ai\Tools\Request;
use LogicException;
use Tests\TestCase;

class VerifyWikidataToolTest extends TestCase
{
    use RefreshDatabase;

    public function test_handle_returns_wikidata_label_and_coord_when_found(): void
    {
        $wikidataPayload = [
            'entities' => [
                'Q28567' => [
                    'labels' => ['en' => ['value' => 'Maya civilization']],
                    'descriptions' => ['en' => ['value' => 'Pre-Columbian Mesoamerican civilization']],
                    'claims' => [
                        'P31' => [
                            ['mainsnak' => ['datavalue' => ['value' => ['id' => 'Q11514315']]]],
                        ],
                        'P625' => [
                            ['mainsnak' => ['datavalue' => ['value' => ['longitude' => -89.6, 'latitude' => 17.2]]]],
                        ],
                    ],
                ],
            ],
        ];
        Http::fake(['*' => Http::response($wikidataPayload)]);

        $tool = app(VerifyWikidata::class);
        $json = $tool->handle(new Request(['qid' => 'Q28567']));

        $data = json_decode($json, true);
        $this->assertTrue($data['found']);
        $this->assertSame('Q28567', $data['qid']);
        $this->assertSame('Maya civilization', $data['label']);
        $this->assertSame(-89.6, $data['coord']['lon']);
        $this->assertSame(17.2, $data['coord']['lat']);
    }

    public function test_handle_returns_not_found_when_qid_missing(): void
    {
        Http::fake(['*' => Http::response(['entities' => []])]);

        $tool = app(VerifyWikidata::class);
        $json = $tool->handle(new Request(['qid' => 'Q9999999']));

        $data = json_decode($json, true);
        $this->assertFalse($data['found']);
        $this->assertSame('Q9999999', $data['qid']);
        $this->assertArrayHasKey('message', $data);
    }

    public function test_build_parts_throws_logic_exception(): void
    {
        $tool = app(VerifyWikidata::class);

        $this->expectException(LogicException::class);
        $tool->buildParts(['qid' => 'Q1']);
    }

    public function test_apply_part_throws_logic_exception(): void
    {
        $tool = app(VerifyWikidata::class);

        $this->expectException(LogicException::class);
        $tool->applyPart([], []);
    }
}

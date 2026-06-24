<?php

namespace Tests\Feature\Ai;

use App\Services\WikidataService;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class WikidataServiceTest extends TestCase
{
    public function test_it_parses_label_p31_and_coordinate(): void
    {
        $response = [
            'entities' => [
                'Q522862' => [
                    'labels' => ['en' => ['value' => 'Karnak Temple Complex']],
                    'descriptions' => ['en' => ['value' => 'ancient Egyptian temple complex']],
                    'claims' => [
                        'P31' => [['mainsnak' => ['datavalue' => ['value' => ['id' => 'Q839954']]]]],
                        'P625' => [['mainsnak' => ['datavalue' => ['value' => ['longitude' => 32.6583, 'latitude' => 25.7183]]]]],
                    ],
                ],
            ],
        ];

        Http::fake(['*' => Http::response($response)]);

        $meta = app(WikidataService::class)->fetch('Q522862');

        $this->assertSame('Karnak Temple Complex', $meta['label']);
        $this->assertContains('Q839954', $meta['p31']);
        $this->assertEqualsWithDelta(32.6583, $meta['coord']['lon'], 0.001);
    }

    public function test_it_returns_null_for_missing_entity(): void
    {
        Http::fake(['*' => Http::response(['entities' => []], 200)]);
        $this->assertNull(app(WikidataService::class)->fetch('Q0'));
    }
}

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

    public function test_it_resolves_a_non_canonical_qid_lowercase_or_padded(): void
    {
        // Wikidata always keys the JSON under the canonical uppercase QID,
        // regardless of how the id was requested (lowercase requests 301 to it).
        $response = [
            'entities' => [
                'Q42' => ['labels' => ['en' => ['value' => 'Douglas Adams']]],
            ],
        ];

        Http::fake(['*' => Http::response($response)]);

        $this->assertSame('Douglas Adams', app(WikidataService::class)->fetch('q42')['label']);
        $this->assertSame('Douglas Adams', app(WikidataService::class)->fetch('  Q42 ')['label']);
    }

    public function test_it_resolves_a_redirected_qid_returned_under_a_different_key(): void
    {
        // A merged QID redirects: the requested id is gone, the entity comes
        // back keyed under its new canonical QID.
        $response = [
            'entities' => [
                'Q42' => ['labels' => ['en' => ['value' => 'Douglas Adams']]],
            ],
        ];

        Http::fake(['*' => Http::response($response)]);

        $this->assertSame('Douglas Adams', app(WikidataService::class)->fetch('Q99999999')['label']);
    }

    public function test_it_sends_a_descriptive_user_agent(): void
    {
        // Wikimedia returns 403 to requests without a descriptive User-Agent
        // (policy https://w.wiki/4wJS, phabricator T400119), so the request
        // MUST carry one or every lookup fails.
        Http::fake(['*' => Http::response(['entities' => ['Q42' => []]])]);

        app(WikidataService::class)->fetch('Q42');

        Http::assertSent(function ($request) {
            $ua = $request->header('User-Agent')[0] ?? '';

            return $ua !== '' && ! str_starts_with($ua, 'GuzzleHttp');
        });
    }
}
